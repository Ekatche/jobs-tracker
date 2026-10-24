"""Opérations MongoDB sur la banque d'histoires STAR+R (`star_stories`) et sur
la lecture hydratée d'un kit d'entretien (`interview_preps`).

Isolation : toute lecture ou écriture est filtrée par `user_filter(user_id)`.
Une histoire d'un autre utilisateur se comporte comme absente (`None`).

Le champ historique `interview_preps.stories` (copie de sûreté) n'est jamais
écrit par ce module. Il n'est lu que dans `ensure_prep_migrated`, pour remplir
la banque une seule fois par kit (migration paresseuse, idempotente).
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

import pymongo
from bson import ObjectId

from app.models import BankStory, DiscardedStoryVersion, StoryFacts, StorySlot, utcnow_with_timezone
from app.services.star_bank_rules import (
    _mask_invented_numbers,
    _story_facts_sources,
    find_duplicate_pairs,
    guess_experience,
)

JOB_OFFERS_COLLECTION = "job_offers"

logger = logging.getLogger(__name__)

STAR_STORIES_COLLECTION = "star_stories"
INTERVIEW_PREPS_COLLECTION = "interview_preps"
CANDIDATE_PROFILE_COLLECTION = "candidate_profile"


class StoryNotFoundError(LookupError):
    """Levée quand une histoire de la banque (ou une version archivée) référencée
    est absente ou appartient à un autre utilisateur."""


def user_filter(user_id: str) -> Dict[str, Any]:
    """Motif `$or` chaîne/`ObjectId` déjà utilisé par `app/routers/interview_prep.py`."""
    if ObjectId.is_valid(user_id):
        return {"$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}]}
    return {"user_id": str(user_id)}


async def ensure_prep_migrated(db, prep: Dict[str, Any]) -> Dict[str, Any]:
    """Migre paresseusement un kit hérité vers la banque, au premier accès.

    Ne fait rien si le kit a déjà `story_slots` (déjà migré) ou n'a pas d'`_id`
    (coquille vide, jamais enregistrée). Sinon, chaque histoire héritée de
    `prep["stories"]` entre dans la banque en conservant son `id` (les
    `mapped_story_id` des questions anticipées restent valides sans
    réécriture), puis le kit reçoit une ligne `story_slots` par histoire.
    """
    if "story_slots" in prep or "_id" not in prep:
        return prep

    user_id = str(prep["user_id"])
    offer_id = str(prep.get("offer_id"))

    profile = await db[CANDIDATE_PROFILE_COLLECTION].find_one(user_filter(user_id))
    experiences = (profile or {}).get("experiences") or []

    legacy_stories = prep.get("stories") or []
    slots: List[Dict[str, Any]] = []
    for legacy in legacy_stories:
        story_id = legacy.get("id") or str(uuid.uuid4())
        situation = legacy.get("situation") or ""
        experience = guess_experience(situation, experiences)

        now = utcnow_with_timezone()
        story_doc = {
            "id": story_id,
            "user_id": user_id,
            "title": legacy.get("title") or "Histoire sans titre",
            "theme": legacy.get("theme") or "Général",
            "situation": situation,
            "task": legacy.get("task") or "",
            "action": legacy.get("action") or "",
            "result": legacy.get("result") or "",
            "reflection": legacy.get("reflection") or "",
            "key_tags": legacy.get("key_tags") or [],
            "experience": experience.model_dump() if experience else None,
            "origin": {"kind": "migrated", "offer_id": offer_id},
            "discarded_versions": [],
            "not_duplicate_of": [],
            "created_at": now,
            "updated_at": now,
        }
        try:
            await db[STAR_STORIES_COLLECTION].update_one(
                {"id": story_id}, {"$setOnInsert": story_doc}, upsert=True
            )
        except pymongo.errors.DuplicateKeyError:
            # Upsert concurrent : une autre requête a créé l'histoire entre-temps.
            pass

        slots.append(
            {
                "id": str(uuid.uuid4()),
                "requirement": legacy.get("target_requirement") or "",
                "story_id": story_id,
                "fit": "strong",
                "angle": "",
                "angle_edited": False,
            }
        )

    await db[INTERVIEW_PREPS_COLLECTION].update_one(
        {"_id": prep["_id"], "story_slots": {"$exists": False}},
        {"$set": {"story_slots": slots}},
    )

    updated = await db[INTERVIEW_PREPS_COLLECTION].find_one({"_id": prep["_id"]})
    return updated if updated is not None else prep


async def load_bank(db, user_id: str) -> List[BankStory]:
    """Toutes les histoires de la banque d'un utilisateur, les plus récemment modifiées d'abord."""
    cursor = db[STAR_STORIES_COLLECTION].find(user_filter(user_id)).sort("updated_at", -1)
    docs = await cursor.to_list(length=None)
    return [BankStory(**doc) for doc in docs]


async def bank_story_ids(db, user_id: str) -> set:
    """Ids de toutes les histoires de la banque d'un utilisateur, sans les désérialiser."""
    return set(await db[STAR_STORIES_COLLECTION].distinct("id", user_filter(user_id)))


async def get_bank_story(db, user_id: str, story_id: Optional[str]) -> Optional[BankStory]:
    """Une histoire de la banque, ou `None` si absente ou appartenant à un autre utilisateur."""
    if not story_id:
        return None
    query: Dict[str, Any] = {**user_filter(user_id), "id": story_id}
    doc = await db[STAR_STORIES_COLLECTION].find_one(query)
    return BankStory(**doc) if doc else None


async def story_usage_counts(db, user_id: str) -> Dict[str, int]:
    """Nombre de kits distincts de l'utilisateur dont une ligne pointe vers chaque histoire."""
    counts: Dict[str, int] = {}
    cursor = db[INTERVIEW_PREPS_COLLECTION].find(user_filter(user_id), {"story_slots": 1})
    async for prep in cursor:
        slots = prep.get("story_slots") or []
        distinct_story_ids = {slot.get("story_id") for slot in slots if slot.get("story_id")}
        for story_id in distinct_story_ids:
            counts[story_id] = counts.get(story_id, 0) + 1
    return counts


async def slots_with_stories(
    db, user_id: str, slots: List[Dict[str, Any]]
) -> List[Tuple[StorySlot, Optional[BankStory]]]:
    """Chaque ligne du kit appariée à l'histoire de la banque qu'elle référence (ou `None`).

    Un angle écrit par l'IA (`angle_edited` faux) est recontrôlé contre les
    faits courants de l'histoire : un nombre qui n'y figure plus (chiffre
    corrigé, fusion, restauration depuis la génération) devient `[à chiffrer]`
    dans la ligne renvoyée, sans écriture en base. Un angle écrit à la main
    reste intact. Sert à `hydrate_prep`, à l'export et au prompt des questions.
    """
    pairs: List[Tuple[StorySlot, Optional[BankStory]]] = []
    for slot_doc in slots:
        slot = StorySlot(**slot_doc)
        story = await get_bank_story(db, user_id, slot.story_id)
        if story is not None and not slot.angle_edited:
            masked_angle = _mask_invented_numbers(slot.angle, _story_facts_sources(story))
            slot = slot.model_copy(update={"angle": masked_angle})
        pairs.append((slot, story))
    return pairs


async def hydrate_prep(db, prep: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Joint les faits de la banque à chaque ligne du kit.

    Ajoute à chaque ligne `story` (histoire de la banque sérialisée, avec
    `used_in_kits`, ou `None` si absente/pas la sienne), et au kit `bank_count`
    (taille de la banque de l'utilisateur) et `duplicates`.

    `duplicates` : une entrée par paire de `find_duplicate_pairs` dont au moins
    une histoire est référencée par une ligne de ce kit. Si les deux le sont,
    une seule entrée, `story_id` = le premier id de la paire ; sinon `story_id`
    = celle du kit. `other_story` est l'autre histoire sérialisée, avec
    `used_in_kits` (même forme que `story` ci-dessus).
    """
    hydrated = dict(prep)
    slots = hydrated.get("story_slots") or []

    pairs = await slots_with_stories(db, user_id, slots)
    bank = await load_bank(db, user_id)
    usage_counts = await story_usage_counts(db, user_id)
    story_by_id = {story.id: story for story in bank}

    rows: List[Dict[str, Any]] = []
    for slot, story in pairs:
        row = slot.model_dump()
        if story is not None:
            story_data = story.model_dump()
            story_data["used_in_kits"] = usage_counts.get(story.id, 0)
            row["story"] = story_data
        else:
            row["story"] = None
        rows.append(row)

    hydrated["story_slots"] = rows
    hydrated["bank_count"] = len(bank)

    kit_story_ids = {slot.story_id for slot, _ in pairs if slot.story_id}
    duplicates: List[Dict[str, Any]] = []
    for a_id, b_id in find_duplicate_pairs(bank):
        a_in_kit = a_id in kit_story_ids
        b_in_kit = b_id in kit_story_ids
        if not a_in_kit and not b_in_kit:
            continue
        story_id, other_id = (a_id, b_id) if a_in_kit else (b_id, a_id)
        other_story = story_by_id.get(other_id)
        if other_story is None:
            continue
        other_data = other_story.model_dump()
        other_data["used_in_kits"] = usage_counts.get(other_story.id, 0)
        duplicates.append({"story_id": story_id, "other_story": other_data})

    hydrated["duplicates"] = duplicates
    return hydrated


async def story_usage(db, user_id: str, story_id: str) -> List[Dict[str, str]]:
    """Kits de l'utilisateur dont une ligne référence `story_id` : offre, entreprise, poste.

    Import paresseux de `_offer_role_and_company` : évite de charger les
    dépendances LLM d'`interview_prep_service` pour les usages légers de ce
    module (migration autonome notamment).
    """
    from app.services.interview_prep_service import _offer_role_and_company

    kits: List[Dict[str, str]] = []
    cursor = db[INTERVIEW_PREPS_COLLECTION].find(
        {**user_filter(user_id), "story_slots.story_id": story_id}, {"offer_id": 1}
    )
    async for prep in cursor:
        offer_id = str(prep.get("offer_id"))
        offer_doc = None
        if ObjectId.is_valid(offer_id):
            offer_doc = await db[JOB_OFFERS_COLLECTION].find_one({"_id": ObjectId(offer_id)})
        role, company = _offer_role_and_company(offer_doc or {})
        kits.append({"offer_id": offer_id, "company": company, "role": role})
    return kits


async def update_story_facts(db, user_id: str, story_id: str, changes: Dict[str, Any]) -> Optional[BankStory]:
    """Écrit uniquement les champs envoyés d'une histoire de la banque ; `updated_at` toujours rafraîchi.

    N'appelle jamais le LLM : une modification manuelle se propage telle
    quelle à tous les kits qui référencent cette histoire (jointure faite à la
    lecture par `hydrate_prep`). `None` si l'histoire est absente ou
    appartient à un autre utilisateur.
    """
    existing = await get_bank_story(db, user_id, story_id)
    if existing is None:
        return None

    update_fields: Dict[str, Any] = dict(changes)
    update_fields["updated_at"] = utcnow_with_timezone()
    await db[STAR_STORIES_COLLECTION].update_one(
        {**user_filter(user_id), "id": story_id}, {"$set": update_fields}
    )
    return await get_bank_story(db, user_id, story_id)


async def delete_bank_story(db, user_id: str, story_id: str) -> Optional[int]:
    """Détache `story_id` de chaque kit qui la référence puis la supprime de la banque.

    Les lignes concernées passent à `story_id=None`, `fit="gap"`, `angle=""`,
    `angle_edited=False` ; les questions anticipées qui la mentionnaient
    perdent leur `mapped_story_id`. Retourne le nombre de kits touchés, ou
    `None` si l'histoire est absente ou appartient à un autre utilisateur.
    """
    existing = await get_bank_story(db, user_id, story_id)
    if existing is None:
        return None

    base_filter = user_filter(user_id)
    reference_filter = {
        **base_filter,
        "$or": [
            {"story_slots.story_id": story_id},
            {"anticipated_questions.mapped_story_id": story_id},
        ],
    }
    cursor = db[INTERVIEW_PREPS_COLLECTION].find(reference_filter, {"_id": 1})
    affected_ids = [doc["_id"] async for doc in cursor]

    # Deux `update_many` séparés, chacun filtré sur son propre champ : un
    # array_filter `$[q]` ciblant `anticipated_questions` lève "the path ...
    # must exist" sur un kit qui ne matche le filtre externe que via
    # `story_slots` (et vice versa). Scinder évite ce cas.
    await db[INTERVIEW_PREPS_COLLECTION].update_many(
        {**base_filter, "story_slots.story_id": story_id},
        {
            "$set": {
                "story_slots.$[s].story_id": None,
                "story_slots.$[s].fit": "gap",
                "story_slots.$[s].angle": "",
                "story_slots.$[s].angle_edited": False,
            }
        },
        array_filters=[{"s.story_id": story_id}],
    )
    await db[INTERVIEW_PREPS_COLLECTION].update_many(
        {**base_filter, "anticipated_questions.mapped_story_id": story_id},
        {"$set": {"anticipated_questions.$[q].mapped_story_id": None}},
        array_filters=[{"q.mapped_story_id": story_id}],
    )

    await db[STAR_STORIES_COLLECTION].delete_one({**base_filter, "id": story_id})
    return len(affected_ids)


def _story_facts(story: BankStory) -> StoryFacts:
    return StoryFacts.model_validate(story.model_dump(include=set(StoryFacts.model_fields)))


async def merge_stories(db, user_id: str, keep_id: str, discard_id: str) -> BankStory:
    """Fusionne `discard_id` dans `keep_id` : l'historique de B est conservé dans A,
    puis toutes les lignes et questions des kits de l'utilisateur sont redirigées
    de B vers A, et B est supprimée.

    `keep` garde sa propre `experience` et son propre `not_duplicate_of`. Ordre
    choisi pour qu'une interruption ne perde rien : (1) écrire les faits de B
    comme nouvelle version archivée à la fin de celles de A, suivie des
    archives propres de B ; (2) rediriger lignes et questions ; (3) supprimer B.

    `StoryNotFoundError` si l'une des deux histoires est absente ou appartient à
    un autre utilisateur, levée avant toute écriture.
    """
    keep = await get_bank_story(db, user_id, keep_id)
    discard = await get_bank_story(db, user_id, discard_id)
    if keep is None:
        raise StoryNotFoundError(keep_id)
    if discard is None:
        raise StoryNotFoundError(discard_id)

    new_version = DiscardedStoryVersion(source_story_id=discard.id, facts=_story_facts(discard))
    combined_versions = keep.discarded_versions + [new_version] + discard.discarded_versions

    base_filter = user_filter(user_id)

    await db[STAR_STORIES_COLLECTION].update_one(
        {**base_filter, "id": keep_id},
        {
            "$set": {
                "discarded_versions": [v.model_dump() for v in combined_versions],
                "updated_at": utcnow_with_timezone(),
            }
        },
    )

    # Deux `update_many` séparés (même motif que `delete_bank_story`) : un
    # array_filter `$[q]` sur `anticipated_questions` échoue sur un kit qui ne
    # matche le filtre externe que via `story_slots`, et inversement.
    await db[INTERVIEW_PREPS_COLLECTION].update_many(
        {**base_filter, "story_slots.story_id": discard_id},
        {"$set": {"story_slots.$[s].story_id": keep_id}},
        array_filters=[{"s.story_id": discard_id}],
    )
    await db[INTERVIEW_PREPS_COLLECTION].update_many(
        {**base_filter, "anticipated_questions.mapped_story_id": discard_id},
        {"$set": {"anticipated_questions.$[q].mapped_story_id": keep_id}},
        array_filters=[{"q.mapped_story_id": discard_id}],
    )

    await db[STAR_STORIES_COLLECTION].delete_one({**base_filter, "id": discard_id})

    updated = await get_bank_story(db, user_id, keep_id)
    assert updated is not None  # vient d'être écrite, dans le même filtre utilisateur
    return updated


async def mark_not_duplicate(db, user_id: str, story_id: str, other_id: str) -> BankStory:
    """Enregistre que `story_id` et `other_id` ne sont pas des doublons, dans les
    deux sens. Retourne l'histoire `story_id` mise à jour.

    `StoryNotFoundError` si l'une des deux histoires est absente ou appartient à
    un autre utilisateur.
    """
    story = await get_bank_story(db, user_id, story_id)
    if story is None:
        raise StoryNotFoundError(story_id)
    other = await get_bank_story(db, user_id, other_id)
    if other is None:
        raise StoryNotFoundError(other_id)

    base_filter = user_filter(user_id)
    await db[STAR_STORIES_COLLECTION].update_one(
        {**base_filter, "id": story_id}, {"$addToSet": {"not_duplicate_of": other_id}}
    )
    await db[STAR_STORIES_COLLECTION].update_one(
        {**base_filter, "id": other_id}, {"$addToSet": {"not_duplicate_of": story_id}}
    )

    updated = await get_bank_story(db, user_id, story_id)
    assert updated is not None
    return updated


async def restore_discarded_version(db, user_id: str, story_id: str, version_id: str) -> BankStory:
    """Restaure une version archivée : ses faits remplacent les faits courants de
    l'histoire ; les faits courants, eux, deviennent une nouvelle version
    archivée ajoutée à la fin de la liste (après retrait de la version
    restaurée). `updated_at` est rafraîchi.

    `StoryNotFoundError` si l'histoire est absente/d'un autre utilisateur, ou si
    `version_id` ne correspond à aucune de ses versions archivées.
    """
    story = await get_bank_story(db, user_id, story_id)
    if story is None:
        raise StoryNotFoundError(story_id)

    target = next((v for v in story.discarded_versions if v.id == version_id), None)
    if target is None:
        raise StoryNotFoundError(version_id)

    new_version = DiscardedStoryVersion(source_story_id=story.id, facts=_story_facts(story))
    remaining = [v for v in story.discarded_versions if v.id != version_id] + [new_version]

    update_fields: Dict[str, Any] = target.facts.model_dump()
    update_fields["discarded_versions"] = [v.model_dump() for v in remaining]
    update_fields["updated_at"] = utcnow_with_timezone()

    await db[STAR_STORIES_COLLECTION].update_one(
        {**user_filter(user_id), "id": story_id}, {"$set": update_fields}
    )

    updated = await get_bank_story(db, user_id, story_id)
    assert updated is not None
    return updated
