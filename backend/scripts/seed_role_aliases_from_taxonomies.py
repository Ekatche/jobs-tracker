"""Script one-shot pour enrichir `role_aliases` depuis les taxonomies ROME (France
Travail) et ESCO (Commission Européenne), en complément de `seed_role_aliases.py`
(liste tech codée en dur).

Pourquoi ces deux sources combinées : ROME couvre tous les métiers du marché
français (1911 fiches, ~14k appellations) mais sa mise à jour est lente sur les
intitulés tech anglicisés récents. ESCO complète avec des alt-labels FR/EN par
occupation, mieux à jour sur ce point. Aucune des deux ne capte les intitulés
tout juste émergents (ex: "Prompt Engineer" avant standardisation) — c'est le
rôle du `normalize_role()` en continu sur les offres scrapées.

Fichiers source attendus (téléchargement manuel, pas d'accès programmatique) :

  ROME  : https://www.data.gouv.fr/datasets/repertoire-operationnel-des-metiers-et-des-emplois-rome
          -> format CSV, placer les fichiers *referentiel_appellation* et
             *referentiel_code_rome* dans --rome-dir (défaut: scripts/data/rome/)

  ESCO  : https://esco.ec.europa.eu/en/use-esco/download
          -> Content: classification, Language: fr (+ en optionnel), File type: csv
             placer occupations_fr.csv (et occupations_en.csv si dispo) dans
             --esco-dir (défaut: scripts/data/esco/)

Les noms de colonnes exacts varient selon la version publiée : ce script détecte
les colonnes par mots-clés plutôt que par position, et échoue avec un message
explicite (en-têtes trouvées) si une colonne attendue est introuvable.

Usage :
    uv run python scripts/seed_role_aliases_from_taxonomies.py --dry-run
    uv run python scripts/seed_role_aliases_from_taxonomies.py
    uv run python scripts/seed_role_aliases_from_taxonomies.py --rome-dir /path --esco-dir /path
"""

import argparse
import asyncio
import csv
import glob
import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.services.role_normalizer import EMBEDDING_MODEL, ensure_role_aliases_indexes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_ROME_DIR = Path(__file__).resolve().parent / "data" / "rome"
DEFAULT_ESCO_DIR = Path(__file__).resolve().parent / "data" / "esco"

EMBEDDING_BATCH_SIZE = 100


def _find_column(header: list[str], *keywords: str) -> Optional[str]:
    """Retourne le nom de colonne dont le header (casefold, sans accents) contient
    tous les mots-clés donnés. None si aucune correspondance."""
    import unicodedata

    def strip_accents(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

    for col in header:
        normalized = strip_accents(col).casefold()
        if all(kw in normalized for kw in keywords):
            return col
    return None


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        # ROME/ESCO utilisent des séparateurs différents selon les exports (`,` ou `;`)
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        rows = list(reader)
        header = reader.fieldnames or []
    return header, rows


def _find_one_file(directory: Path, *name_fragments: str) -> Optional[Path]:
    if not directory.is_dir():
        return None
    for fragment in name_fragments:
        matches = sorted(glob.glob(str(directory / f"*{fragment}*")))
        if matches:
            return Path(matches[0])
    return None


def load_rome_candidates(rome_dir: Path) -> dict[str, set[str]]:
    """Charge le référentiel ROME: canonical = libellé de la fiche métier,
    variants = toutes les appellations rattachées à son code ROME."""
    appellation_file = _find_one_file(rome_dir, "referentiel_appellation")
    rome_libelle_file = _find_one_file(rome_dir, "referentiel_code_rome")

    if not appellation_file or not rome_libelle_file:
        found = sorted(p.name for p in rome_dir.glob("*")) if rome_dir.is_dir() else []
        raise FileNotFoundError(
            f"Fichiers ROME introuvables dans {rome_dir}. "
            f"Attendu: un fichier '*referentiel_appellation*' et un '*referentiel_code_rome*'. "
            f"Fichiers présents: {found or '(dossier vide ou inexistant)'}"
        )

    libelle_header, libelle_rows = _read_csv_rows(rome_libelle_file)
    code_col = _find_column(libelle_header, "code", "rome")
    libelle_col = _find_column(libelle_header, "libelle") or _find_column(libelle_header, "libelle", "rome")
    if not code_col or not libelle_col:
        raise ValueError(
            f"Colonnes code/libellé introuvables dans {rome_libelle_file.name}. "
            f"En-têtes trouvées: {libelle_header}"
        )

    canonical_by_code: dict[str, str] = {}
    for row in libelle_rows:
        code = (row.get(code_col) or "").strip()
        libelle = (row.get(libelle_col) or "").strip()
        if code and libelle:
            canonical_by_code[code] = libelle

    appellation_header, appellation_rows = _read_csv_rows(appellation_file)
    appellation_code_col = _find_column(appellation_header, "code", "rome")
    appellation_libelle_col = _find_column(appellation_header, "libelle", "appellation", "long") or _find_column(
        appellation_header, "libelle", "appellation"
    )
    if not appellation_code_col or not appellation_libelle_col:
        raise ValueError(
            f"Colonnes code/libellé introuvables dans {appellation_file.name}. "
            f"En-têtes trouvées: {appellation_header}"
        )

    candidates: dict[str, set[str]] = {}
    for row in appellation_rows:
        code = (row.get(appellation_code_col) or "").strip()
        appellation = (row.get(appellation_libelle_col) or "").strip()
        canonical = canonical_by_code.get(code)
        if not canonical or not appellation:
            continue
        candidates.setdefault(canonical, set()).add(canonical.lower())
        candidates[canonical].add(appellation.lower())

    logger.info(f"📖 ROME: {len(candidates)} fiches métiers chargées depuis {rome_dir}")
    return candidates


def load_esco_candidates(esco_dir: Path) -> dict[str, set[str]]:
    """Charge occupations_*.csv ESCO: canonical = preferredLabel,
    variants = preferredLabel + altLabels + hiddenLabels (une langue par fichier)."""
    occupation_files = sorted(esco_dir.glob("occupations_*.csv")) if esco_dir.is_dir() else []
    if not occupation_files:
        found = sorted(p.name for p in esco_dir.glob("*")) if esco_dir.is_dir() else []
        raise FileNotFoundError(
            f"Aucun fichier 'occupations_*.csv' dans {esco_dir}. "
            f"Fichiers présents: {found or '(dossier vide ou inexistant)'}"
        )

    candidates: dict[str, set[str]] = {}
    for occupation_file in occupation_files:
        header, rows = _read_csv_rows(occupation_file)
        type_col = _find_column(header, "concepttype")
        preferred_col = _find_column(header, "preferredlabel")
        alt_col = _find_column(header, "altlabels")
        hidden_col = _find_column(header, "hiddenlabels")
        if not preferred_col:
            raise ValueError(
                f"Colonne 'preferredLabel' introuvable dans {occupation_file.name}. "
                f"En-têtes trouvées: {header}"
            )

        loaded = 0
        for row in rows:
            if type_col and (row.get(type_col) or "").strip().lower() not in ("occupation", ""):
                continue
            preferred = (row.get(preferred_col) or "").strip()
            if not preferred:
                continue
            variants = {preferred.lower()}
            for col in (alt_col, hidden_col):
                if not col:
                    continue
                raw = row.get(col) or ""
                for line in raw.replace("|", "\n").splitlines():
                    label = line.strip()
                    if label:
                        variants.add(label.lower())
            candidates.setdefault(preferred, set()).update(variants)
            loaded += 1
        logger.info(f"📖 ESCO: {loaded} occupations chargées depuis {occupation_file.name}")

    return candidates


def merge_candidates(*sources: dict[str, set[str]]) -> dict[str, set[str]]:
    """Fusionne par canonical exact (casse identique). Les quasi-doublons entre
    sources (ex: 'Data Scientist' ROME vs 'Data scientist' ESCO) restent des
    entrées séparées: la fusion sémantique se fait déjà en continu par
    normalize_role() via son seuil de similarité cosinus."""
    merged: dict[str, set[str]] = {}
    for source in sources:
        for canonical, variants in source.items():
            merged.setdefault(canonical, set()).update(variants)
    return merged


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    from litellm import aembedding

    resp = await aembedding(model=EMBEDDING_MODEL, input=texts)
    data = resp.data if hasattr(resp, "data") else resp["data"]
    embeddings = []
    for item in data:
        embedding = (
            item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", item["embedding"])
        )
        embeddings.append(embedding)
    return embeddings


async def seed_from_taxonomies(
    candidates: dict[str, set[str]],
    dry_run: bool = False,
    limit: Optional[int] = None,
) -> None:
    db = await get_database()
    collection = db["role_aliases"]

    logger.info("🔧 Vérification et création des index...")
    await ensure_role_aliases_indexes(db)

    items = list(candidates.items())
    if limit:
        items = items[:limit]

    existing_canonicals = {
        doc["canonical"] async for doc in collection.find({}, {"canonical": 1})
    }

    to_update = [(c, v) for c, v in items if c in existing_canonicals]
    to_insert = [(c, v) for c, v in items if c not in existing_canonicals]

    logger.info(
        f"📊 {len(items)} candidats au total: {len(to_update)} déjà présents (variantes à fusionner), "
        f"{len(to_insert)} nouveaux (embedding à calculer)"
    )

    if dry_run:
        logger.info("🧪 --dry-run: aucune écriture. Exemples de nouveaux canonicals:")
        for canonical, variants in to_insert[:10]:
            logger.info(f"   - {canonical} ({len(variants)} variantes)")
        return

    updated_count = 0
    for canonical, variants in to_update:
        await collection.update_one(
            {"canonical": canonical},
            {"$addToSet": {"variants": {"$each": sorted(variants)}}},
        )
        updated_count += 1
    logger.info(f"🔄 {updated_count} canonicals mis à jour (variantes fusionnées).")

    inserted_count = 0
    for i in range(0, len(to_insert), EMBEDDING_BATCH_SIZE):
        batch = to_insert[i : i + EMBEDDING_BATCH_SIZE]
        canonicals = [c for c, _ in batch]
        logger.info(
            f"✨ Batch {i // EMBEDDING_BATCH_SIZE + 1}/{(len(to_insert) - 1) // EMBEDDING_BATCH_SIZE + 1}: "
            f"embeddings pour {len(canonicals)} canonicals..."
        )
        try:
            embeddings = await _embed_batch(canonicals)
        except Exception as e:
            logger.error(f"❌ Échec embedding batch (canonicals: {canonicals[:3]}...): {e}")
            continue

        docs = [
            {"canonical": canonical, "embedding": embedding, "variants": sorted(variants)}
            for (canonical, variants), embedding in zip(batch, embeddings)
        ]
        try:
            await collection.insert_many(docs, ordered=False)
            inserted_count += len(docs)
        except Exception as e:
            logger.warning(f"⚠️ Erreur insertion batch (doublons possibles ignorés): {e}")

    total = await collection.count_documents({})
    logger.info(
        f"🎉 Seeding terminé: {inserted_count} insérés, {updated_count} mis à jour. Total documents: {total}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rome-dir", type=Path, default=DEFAULT_ROME_DIR)
    parser.add_argument("--esco-dir", type=Path, default=DEFAULT_ESCO_DIR)
    parser.add_argument("--skip-rome", action="store_true", help="Ignore la source ROME")
    parser.add_argument("--skip-esco", action="store_true", help="Ignore la source ESCO")
    parser.add_argument("--dry-run", action="store_true", help="N'écrit rien, affiche juste les comptes")
    parser.add_argument("--limit", type=int, default=None, help="Limite le nombre de candidats traités (debug)")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    sources: list[dict[str, set[str]]] = []
    if not args.skip_rome:
        sources.append(load_rome_candidates(args.rome_dir))
    if not args.skip_esco:
        sources.append(load_esco_candidates(args.esco_dir))

    if not sources:
        logger.error("❌ --skip-rome et --skip-esco activés simultanément: rien à charger.")
        return

    merged = merge_candidates(*sources)
    logger.info(f"🔗 {len(merged)} canonicals uniques après fusion (dédoublonnage exact seulement).")

    await seed_from_taxonomies(merged, dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
