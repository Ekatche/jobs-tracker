# backend/scripts/transfer_user.py
"""Transfère un compte (par email) d'une base Mongo vers une autre, en deux
temps : `export` sur la machine source écrit un fichier JSON, `import` sur la
machine cible le relit.

Copié : le compte (`users`, sans `role`, `cv_url` ni hash de mot de passe) et
les documents de l'utilisateur dans `COPIED_COLLECTIONS`, plus les offres
qu'ils référencent ou auxquelles il est rattaché (`matched_user_ids`). Ignoré :
`api_usage` (quota), `offer_relevance` (recalculé) et `offer_embeddings`
(cache) — lancer `scripts/rematch_all_users.py` après l'import.

À l'import, le compte et chacun de ses documents reçoivent un nouvel `_id` ;
toute référence à un ancien identifiant (ObjectId ou chaîne) est réécrite vers
le nouveau, en gardant son type. Une offre déjà présente en cible (même `_id`,
puis même `url`, puis même `unique_key`) est réutilisée telle quelle ; une
offre absente est insérée avec son `_id` source, `matched_user_ids` vide et
sans `evaluation_score`. Le compte est inséré en dernier : une interruption
laisse des documents orphelins (nouvel identifiant affiché au départ) mais
jamais un compte incomplet utilisable.

Le fichier exporté contient des données personnelles : le supprimer après
l'import.

Usage:
    # Machine source :
    docker exec -w /app jobtracker-backend uv run python scripts/transfer_user.py \\
        export --email <email> --out /tmp/user.json
    # Machine cible, simulation (aucune écriture) :
    docker exec -w /app jobtracker-backend uv run python scripts/transfer_user.py \\
        import --in /tmp/user.json
    # Machine cible, import réel (le nouveau mot de passe est demandé au terminal) :
    docker exec -it -w /app jobtracker-backend uv run python scripts/transfer_user.py \\
        import --in /tmp/user.json --apply
"""

import argparse
import asyncio
import getpass
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from bson import ObjectId, json_util
from pymongo.errors import DuplicateKeyError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import get_password_hash
from app.database import get_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

COPIED_COLLECTIONS = (
    "candidate_profile",
    "applications",
    "user_offer_interactions",
    "cover_letters",
    "offer_evaluations",
    "tailored_resumes",
    "cv_tailored",
    "tasks",
    "interview_preps",
    "star_stories",
)
USER_DROPPED_FIELDS = ("hashed_password", "role", "cv_url")
OFFER_DROPPED_FIELDS = ("evaluation_score",)


class TransferError(Exception):
    """Transfert refusé : rien n'a été écrit."""


@dataclass
class ImportSummary:
    new_user_id: str
    counts: dict[str, int]
    offers_existing: int
    offers_new: int


def remap_ids(value, mapping: dict[str, str]):
    """Remplace récursivement tout ancien identifiant présent dans `mapping`
    (clé = ancien id en chaîne) par le nouveau, en gardant son type : un
    ObjectId reste ObjectId, une chaîne reste chaîne. Les clés de dict sont
    remappées aussi ; les autres valeurs sont inchangées."""
    if isinstance(value, ObjectId):
        new = mapping.get(str(value))
        return ObjectId(new) if new else value
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, dict):
        return {remap_ids(key, mapping): remap_ids(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [remap_ids(item, mapping) for item in value]
    return value


def _id_candidates(value, found: set) -> set:
    """Tous les identifiants (ObjectId, ou chaîne au format ObjectId sous ses
    deux formes) contenus dans `value`, pour retrouver les offres référencées
    quel que soit le champ qui les porte."""
    if isinstance(value, ObjectId):
        found.update((value, str(value)))
    elif isinstance(value, str) and ObjectId.is_valid(value):
        found.update((value, ObjectId(value)))
    elif isinstance(value, dict):
        for item in value.values():
            _id_candidates(item, found)
    elif isinstance(value, list):
        for item in value:
            _id_candidates(item, found)
    return found


async def export_user(db, email: str) -> dict:
    user = await db.users.find_one({"email": email})
    if user is None:
        raise TransferError(f"Aucun compte avec l'email {email}")
    user_oid = user["_id"]
    user_str = str(user_oid)

    owner = {"user_id": {"$in": [user_str, user_oid]}}
    collections = {name: await db[name].find(owner).to_list(length=None) for name in COPIED_COLLECTIONS}

    referenced = _id_candidates(collections, set())
    offers = await db.job_offers.find(
        {"$or": [{"_id": {"$in": list(referenced)}}, {"matched_user_ids": user_str}]}
    ).to_list(length=None)

    for field in USER_DROPPED_FIELDS:
        user.pop(field, None)
    return {"user": user, "collections": collections, "job_offers": offers}


def dump_bundle(bundle: dict) -> str:
    return json_util.dumps(bundle, json_options=json_util.CANONICAL_JSON_OPTIONS, ensure_ascii=False)


def load_bundle(text: str) -> dict:
    return json_util.loads(text, json_options=json_util.CANONICAL_JSON_OPTIONS)


async def _find_existing_offer(db, offer: dict):
    for field in ("_id", "url", "unique_key"):
        if offer.get(field):
            existing = await db.job_offers.find_one({field: offer[field]}, {"_id": 1})
            if existing is not None:
                return existing
    return None


async def import_user(db, bundle: dict, *, apply: bool, password_hash: str | None) -> ImportSummary:
    if apply and not password_hash:
        raise TransferError("--apply exige un nouveau mot de passe")
    source_user = bundle["user"]
    identity = [{"email": source_user["email"]}]
    if source_user.get("username"):
        identity.append({"username": source_user["username"]})
    if await db.users.find_one({"$or": identity}, {"_id": 1}) is not None:
        raise TransferError("Un compte avec cet email ou ce nom d'utilisateur existe déjà en cible")

    new_user_oid = ObjectId()
    logger.info("Nouvel identifiant du compte : %s", new_user_oid)
    mapping = {str(source_user["_id"]): str(new_user_oid)}

    # Offres d'abord : leurs identifiants cibles entrent dans la table de
    # correspondance avant le remappage des documents de l'utilisateur.
    offers_existing = 0
    offers_new = 0
    for offer in bundle["job_offers"]:
        existing = await _find_existing_offer(db, offer)
        if existing is None:
            offers_new += 1
            if not apply:
                continue
            fresh = {key: value for key, value in offer.items() if key not in OFFER_DROPPED_FIELDS}
            fresh["matched_user_ids"] = []
            try:
                await db.job_offers.insert_one(fresh)
                continue
            except DuplicateKeyError:
                # Insérée entre-temps (même url ou unique_key) : on la réutilise.
                existing = await _find_existing_offer(db, offer)
                offers_new -= 1
        offers_existing += 1
        if existing["_id"] != offer["_id"]:
            mapping[str(offer["_id"])] = str(existing["_id"])

    for docs in bundle["collections"].values():
        for doc in docs:
            mapping[str(doc["_id"])] = str(ObjectId())

    remapped = {}
    for name, docs in bundle["collections"].items():
        remapped[name] = []
        for doc in docs:
            new_doc = remap_ids(doc, mapping)
            new_doc["_id"] = ObjectId(mapping[str(doc["_id"])])
            remapped[name].append(new_doc)

    summary = ImportSummary(
        new_user_id=str(new_user_oid),
        counts={name: len(docs) for name, docs in remapped.items()},
        offers_existing=offers_existing,
        offers_new=offers_new,
    )
    if not apply:
        return summary

    for name, docs in remapped.items():
        if docs:
            await db[name].insert_many(docs)

    user = remap_ids(source_user, mapping)
    user["_id"] = new_user_oid
    user["hashed_password"] = password_hash
    user["disabled"] = False
    await db.users.insert_one(user)
    return summary


def _ask_new_password() -> str:
    password = getpass.getpass("Nouveau mot de passe du compte : ")
    if not password or password != getpass.getpass("Confirmer le mot de passe : "):
        raise TransferError("Mot de passe vide ou confirmation différente")
    return get_password_hash(password)


async def _run(args) -> None:
    db = await get_database()
    if args.command == "export":
        bundle = await export_user(db, args.email)
        args.out.write_text(dump_bundle(bundle), encoding="utf-8")
        args.out.chmod(0o600)
        counts = {name: len(docs) for name, docs in bundle["collections"].items()}
        logger.info("Export écrit dans %s : %d offres, %s", args.out, len(bundle["job_offers"]), counts)
        return

    bundle = load_bundle(args.in_path.read_text(encoding="utf-8"))
    password_hash = _ask_new_password() if args.apply else None
    summary = await import_user(db, bundle, apply=args.apply, password_hash=password_hash)
    logger.info(
        "%s : compte %s, offres existantes %d, offres nouvelles %d, documents %s",
        "Import écrit" if args.apply else "Simulation (aucune écriture)",
        summary.new_user_id,
        summary.offers_existing,
        summary.offers_new,
        summary.counts,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Transfère un compte d'une base Mongo vers une autre.")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Écrit le compte et ses données dans un fichier JSON.")
    export.add_argument("--email", required=True)
    export.add_argument("--out", required=True, type=Path)
    imported = commands.add_parser("import", help="Importe un fichier d'export (simulation sans --apply).")
    imported.add_argument("--in", dest="in_path", required=True, type=Path)
    imported.add_argument("--apply", action="store_true", help="Écrit réellement en base.")
    args = parser.parse_args()
    try:
        asyncio.run(_run(args))
    except TransferError as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
