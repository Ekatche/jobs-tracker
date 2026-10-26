"""Moteur de matching persistant entre un profil candidat et le stock d'offres.

Chaque offre active du stock reçoit, par profil, un score de pertinence
hybride (app.services.offer_scoring). Le rattachement ne passe plus par
source_query : une offre est rattachée (job_offers.matched_user_ids) quand
elle n'est pas filtrée dur et que son score est au moins FLOOR, et détachée
sinon — sauf si le candidat a interagi avec elle (vue/sauvegardée/masquée/
candidature), auquel cas elle est simplement laissée telle quelle. Le score
de chaque offre évaluée (hors filtre dur) est persisté dans offer_relevance.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Literal, Optional

from bson import ObjectId
from pymongo import DeleteOne, UpdateOne

from app.database import create_offer_scoring_indexes
from app.services.offer_scoring.assess import assess_offer
from app.services.offer_scoring.constants import FLOOR, SCORING_VERSION
from app.services.offer_scoring.embeddings import (
    embed_texts,
    get_offer_vectors,
    get_profile_vector,
    offer_embedding_text,
)
from app.services.offer_scoring.score import (
    ScoreResult,
    SkillIdf,
    build_skill_idf,
    profile_features,
)
from app.services.role_normalizer import cosine_similarity

logger = logging.getLogger(__name__)


async def load_skill_idf(db) -> SkillIdf:
    """IDF des compétences sur le stock actif.

    Agrégation `$unwind`/`$group` plutôt qu'un `to_list` complet des offres :
    seules les compétences de chaque offre active transitent, pas le reste
    du document (description, etc).
    """
    pipeline = [
        {"$match": {"is_deleted": {"$ne": True}}},
        {"$unwind": {"path": "$competences_cles", "preserveNullAndEmptyArrays": True}},
        {"$group": {"_id": "$_id", "skills": {"$addToSet": "$competences_cles"}}},
    ]
    skill_lists: List[List[str]] = []
    async for doc in db["job_offers"].aggregate(pipeline):
        skill_lists.append([s for s in (doc.get("skills") or []) if s])
    return build_skill_idf(skill_lists)


async def interacted_offer_ids(user_id: str, db) -> set[str]:
    """Offres avec lesquelles le candidat a interagi : interaction explicite à
    statut réel (ni `None` ni `"none"` — ce dernier est écrit par
    `set_offer_seen`, job_offers.py:666, pour une simple vue, pas une
    interaction) ou candidature. Sert de garde contre le détachement d'une
    offre sous FLOOR mais déjà vue/postulée par l'utilisateur."""
    ids: set[str] = set()

    interactions = await db["user_offer_interactions"].find(
        {"user_id": user_id, "status": {"$nin": [None, "none"]}}
    ).to_list(length=None)
    for doc in interactions:
        offer_id = doc.get("offer_id")
        if offer_id:
            ids.add(str(offer_id))

    applications = await db["applications"].find(
        {"user_id": {"$in": [user_id, ObjectId(user_id)]}, "offer_id": {"$ne": None}}
    ).to_list(length=None)
    for doc in applications:
        offer_id = doc.get("offer_id")
        if offer_id:
            ids.add(str(offer_id))

    return ids


@dataclass
class RematchSummary:
    attached: int = 0
    detached: int = 0
    kept_by_guard: int = 0
    semantic_unknown: int = 0
    kept_below_floor: list = field(default_factory=list)
    kept_hard_filtered: list = field(default_factory=list)
    levels: dict = field(default_factory=dict)


def _attachment_action(
    reason: Optional[str],
    result: Optional[ScoreResult],
    already_attached: bool,
    guarded: bool,
) -> Literal["attach", "detach", "keep", "none"]:
    """Décision pure de rattachement, partagée par `rematch_user` et
    `tag_new_offers` : ne dépend que de l'état déjà connu de l'offre (filtre
    dur ou non, score éventuel, déjà rattachée ou non, protégée par une
    interaction ou non) — aucun accès base de données.

    Une offre qui mérite d'être rattachée (pas de filtre dur, score au moins
    FLOOR) l'est si elle ne l'est pas déjà, sinon rien à faire. Sinon : si
    elle est déjà rattachée, la garde d'interaction décide entre la garder
    (`keep`) ou la détacher (`detach`) ; si elle ne l'est pas, rien à faire
    (`none`) qu'elle soit gardée ou non — on ne rattache jamais une offre sous
    FLOOR ou filtrée dur au seul motif d'une interaction passée."""
    should_attach = reason is None and result is not None and result.score >= FLOOR
    if should_attach:
        return "none" if already_attached else "attach"
    if not already_attached:
        return "none"
    return "keep" if guarded else "detach"


def _relevance_delete(user_id: str, offer_id_str: str) -> DeleteOne:
    """Supprime un document `offer_relevance` périmé : l'offre vient de devenir
    filtrée dur (un filtre dur n'a jamais de score à conserver)."""
    return DeleteOne({"user_id": user_id, "offer_id": offer_id_str})


def _relevance_update(user_id: str, offer_id_str: str, result, now) -> UpdateOne:
    return UpdateOne(
        {"user_id": user_id, "offer_id": offer_id_str},
        {
            "$set": {
                "user_id": user_id,
                "offer_id": offer_id_str,
                "score": result.score,
                "level": result.level,
                "breakdown": result.breakdown,
                "unknown_components": result.unknown_components,
                "failed_conditions": result.failed_conditions,
                "scoring_version": SCORING_VERSION,
                "updated_at": now,
            }
        },
        upsert=True,
    )


async def rematch_user(user_id: str, db, *, apply: bool = True, embed=embed_texts) -> "RematchSummary":
    """Recalcule le score hybride d'UN user contre tout le stock actif et
    rattache/détache selon FLOOR, avec garde d'interaction. `apply=False`
    calcule le résumé sans rien écrire (ni job_offers, ni offer_relevance, ni
    le cache offer_embeddings — `cache=apply` est passé à `get_offer_vectors`)."""
    summary = RematchSummary()

    profile = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)})
    if not profile:
        return summary

    features = profile_features(profile)
    offers = await db["job_offers"].find({"is_deleted": {"$ne": True}}).to_list(length=None)
    idf = await load_skill_idf(db)
    offer_vectors = await get_offer_vectors(offers, db, embed=embed, cache=apply)
    profile_vector = await get_profile_vector(features.identity, embed=embed)
    guarded_ids = await interacted_offer_ids(user_id, db)

    now = datetime.now(timezone.utc)
    attach_ids = []
    detach_ids = []
    relevance_ops: List[UpdateOne] = []

    for offer in offers:
        offer_id = offer["_id"]
        offer_id_str = str(offer_id)
        already_attached = user_id in (offer.get("matched_user_ids") or [])

        cos = None
        if profile_vector is not None:
            vector = offer_vectors.get(offer_id_str)
            if vector is not None:
                cos = cosine_similarity(profile_vector, vector)

        reason, result = assess_offer(offer, features, cos, idf)

        # Panne d'embedding : profil exploitable (identité non vide) mais
        # cosinus indisponible (vecteur profil ou offre manquant). Si l'offre
        # n'est pas filtrée dur, elle n'est pas évaluée ce tour — ni rattachée
        # ni détachée, aucune écriture — plutôt que de (dés)attacher tout le
        # stock sur un score à moitié connu par panne plutôt que par absence
        # de préférence candidat.
        if reason is None and features.identity.strip() and cos is None:
            summary.semantic_unknown += 1
            continue

        if reason is not None:
            relevance_ops.append(_relevance_delete(user_id, offer_id_str))
        elif result is not None:
            summary.levels[result.level] = summary.levels.get(result.level, 0) + 1
            relevance_ops.append(_relevance_update(user_id, offer_id_str, result, now))

        guarded = offer_id_str in guarded_ids
        action = _attachment_action(reason, result, already_attached, guarded)

        if action == "attach":
            attach_ids.append(offer_id)
            summary.attached += 1
        elif action == "detach":
            detach_ids.append(offer_id)
            summary.detached += 1
        elif action == "keep":
            summary.kept_by_guard += 1
            if reason is not None:
                summary.kept_hard_filtered.append(offer_id_str)
                logger.warning(
                    "Offre %s filtrée dur (%s) mais conservée (garde interaction) pour user %s",
                    offer_id_str,
                    reason,
                    user_id[:8],
                )
            elif result is not None:
                summary.kept_below_floor.append(offer_id_str)
        # action == "none" : offre non rattachée que la garde ne doit pas
        # faire rattacher — rien à compter, rien à écrire.

    if apply:
        if attach_ids:
            await db["job_offers"].update_many(
                {"_id": {"$in": attach_ids}}, {"$addToSet": {"matched_user_ids": user_id}}
            )
        if detach_ids:
            await db["job_offers"].update_many(
                {"_id": {"$in": detach_ids}}, {"$pull": {"matched_user_ids": user_id}}
            )
        if relevance_ops:
            await db["offer_relevance"].bulk_write(relevance_ops)

    return summary


async def tag_new_offers(offer_ids: list, db, *, embed=embed_texts) -> None:
    """Recalcule le score hybride de TOUS les profils contre les offres du lot
    `offer_ids` et contre les offres encore en attente d'une réévaluation
    (`scoring_pending`, laissées de côté par une panne d'embedding lors d'un
    appel précédent). Utilisé en fin de cycle de collecte : `offer_ids`
    mélange des offres neuves et des offres existantes mises à jour par la
    collecte ; applique la même décision de rattachement que `rematch_user`
    (`_attachment_action`) — une offre déjà rattachée qui devient filtrée
    dur, sans score ou sous FLOOR est détachée, sauf garde d'interaction
    (`interacted_offer_ids`, un appel par profil).

    Une offre non évaluée pour un profil faute de cosinus (panne d'embedding
    sur un profil à l'identité non vide, et offre non filtrée dur) est
    marquée `scoring_pending` pour être rejouée au prochain appel — sauf si
    elle n'a ni intitulé ni description, auquel cas elle ne pourra jamais
    être embarquée et n'est donc jamais mise en attente. Une offre en attente
    qui a pu être évaluée ce tour perd son marqueur `scoring_pending`. Une
    offre non évaluée faute de cosinus n'est, comme dans `rematch_user`,
    jamais détachée (ni rattachée).
    """
    # M21 (index) : seul `tag_new_offers` est appelé sur le chemin de
    # collecte Airflow, qui ne passe jamais par le `lifespan` FastAPI — on
    # (ré)applique donc les index ici aussi, idempotent. Fail-open : un
    # problème d'index (droits, Mongo indisponible) ne doit jamais bloquer
    # un cycle de scoring.
    try:
        await create_offer_scoring_indexes(db)
    except Exception as exc:
        logger.warning(
            "⚠️ Impossible de (re)créer les index offer_scoring, on continue : %s", exc
        )

    if offer_ids:
        query = {
            "$or": [
                {"_id": {"$in": offer_ids}},
                {"scoring_pending": True, "is_deleted": {"$ne": True}},
            ]
        }
    else:
        query = {"scoring_pending": True, "is_deleted": {"$ne": True}}

    offers = await db["job_offers"].find(query).to_list(length=None)
    if not offers:
        return

    idf = await load_skill_idf(db)
    offer_vectors = await get_offer_vectors(offers, db, embed=embed)

    profiles = await db["candidate_profile"].find({}).to_list(length=None)
    now = datetime.now(timezone.utc)

    unscored_ids: set = set()
    affected_profile_count = 0

    for profile in profiles:
        user_id = str(profile["user_id"])
        features = profile_features(profile)
        profile_vector = await get_profile_vector(features.identity, embed=embed)
        guarded_ids = await interacted_offer_ids(user_id, db)

        attach_ids = []
        detach_ids = []
        relevance_ops: List[UpdateOne] = []
        profile_has_unscored = False

        for offer in offers:
            offer_id = offer["_id"]
            offer_id_str = str(offer_id)
            already_attached = user_id in (offer.get("matched_user_ids") or [])

            cos = None
            if profile_vector is not None:
                vector = offer_vectors.get(offer_id_str)
                if vector is not None:
                    cos = cosine_similarity(profile_vector, vector)

            reason, result = assess_offer(offer, features, cos, idf)

            # Même garde que rematch_user : panne d'embedding sur une offre
            # non filtrée dur => pas évaluée ce tour (cf. commentaire là-bas).
            # L'offre est rejouée au prochain appel via scoring_pending.
            if reason is None and features.identity.strip() and cos is None:
                unscored_ids.add(offer_id)
                profile_has_unscored = True
                continue

            if reason is not None:
                relevance_ops.append(_relevance_delete(user_id, offer_id_str))
            elif result is not None:
                relevance_ops.append(_relevance_update(user_id, offer_id_str, result, now))

            guarded = offer_id_str in guarded_ids
            action = _attachment_action(reason, result, already_attached, guarded)
            if action == "attach":
                attach_ids.append(offer_id)
            elif action == "detach":
                detach_ids.append(offer_id)

        if profile_has_unscored:
            affected_profile_count += 1

        if attach_ids:
            await db["job_offers"].update_many(
                {"_id": {"$in": attach_ids}}, {"$addToSet": {"matched_user_ids": user_id}}
            )
        if detach_ids:
            await db["job_offers"].update_many(
                {"_id": {"$in": detach_ids}}, {"$pull": {"matched_user_ids": user_id}}
            )
        if relevance_ops:
            await db["offer_relevance"].bulk_write(relevance_ops)

    if unscored_ids:
        pending_ids = [
            offer["_id"]
            for offer in offers
            if offer["_id"] in unscored_ids and offer_embedding_text(offer) is not None
        ]
        if pending_ids:
            await db["job_offers"].update_many(
                {"_id": {"$in": pending_ids}}, {"$set": {"scoring_pending": True}}
            )
        logger.error(
            "%d offre(s) en attente de réévaluation (panne d'embedding) pour %d profil(s) : "
            "seront rejouées au prochain cycle de collecte. offer_ids=%s",
            len(unscored_ids),
            affected_profile_count,
            [str(offer_id) for offer_id in unscored_ids],
        )

    resolved_ids = [
        offer["_id"] for offer in offers if offer["_id"] not in unscored_ids and offer.get("scoring_pending")
    ]
    if resolved_ids:
        await db["job_offers"].update_many({"_id": {"$in": resolved_ids}}, {"$unset": {"scoring_pending": ""}})
