"""Moteur de matching persistant entre un profil candidat et le stock d'offres.

Compare le canonical_title / localisation déjà normalisés sur chaque offre
(via normalize_role / normalize_city lors de la collecte) aux préférences
normalisées d'un profil, pour maintenir à jour job_offers.matched_user_ids.
"""

from bson import ObjectId

from app.services.normalization import normalize_city
from app.services.role_normalizer import normalize_role


def offer_matches_criteria(
    offer: dict,
    normalized_roles: set[str],
    normalized_locations: set[str],
    remote_policy: str,
) -> bool:
    """Pure, sans I/O. Un profil sans aucun critère exploitable (ni rôle ni
    localisation) ne matche jamais aucune offre, pour ne jamais afficher le
    stock entier comme s'il était filtré."""
    if not normalized_roles and not normalized_locations:
        return False

    canonical_title = (offer.get("canonical_title") or "").lower()
    role_match = not normalized_roles or canonical_title in normalized_roles

    localisation = (offer.get("localisation") or "").lower()
    loc_match = (
        not normalized_locations
        or localisation in normalized_locations
        or (remote_policy == "full_remote" and offer.get("mode_travail") == "Télétravail total")
    )

    return role_match and loc_match


async def get_normalized_profile_criteria(
    prefs: dict, db
) -> tuple[set[str], set[str], str]:
    """Normalise target_roles (normalize_role, async, caché via role_aliases)
    et locations (normalize_city, sync) vers les mêmes formes canoniques que
    celles déjà stockées sur les offres. Retourne (roles, locations, remote_policy)."""
    target_roles = prefs.get("target_roles") or []
    locations = prefs.get("locations") or []
    remote_policy = prefs.get("remote_policy") or "flexible"

    normalized_roles: set[str] = set()
    for role in target_roles:
        if not role or not role.strip():
            continue
        canonical = await normalize_role(role, db=db)
        if canonical:
            normalized_roles.add(canonical.lower())

    normalized_locations = {normalize_city(loc).lower() for loc in locations if loc}

    return normalized_roles, normalized_locations, remote_policy


async def rematch_user(user_id: str, db) -> None:
    """Recalcule le matching d'UN user contre tout le stock actif.
    $addToSet sur les offres qui matchent désormais, $pull sur celles qui
    ne matchent plus. Idempotent : rejouer sans changement de préférences
    ne modifie pas matched_user_ids."""
    profile = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)})
    if not profile:
        return

    prefs = profile.get("preferences") or {}
    normalized_roles, normalized_locations, remote_policy = await get_normalized_profile_criteria(prefs, db)

    collection = db["job_offers"]
    offers = await collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)

    matching_ids = [
        offer["_id"]
        for offer in offers
        if offer_matches_criteria(offer, normalized_roles, normalized_locations, remote_policy)
    ]
    matching_id_set = set(matching_ids)
    non_matching_ids = [offer["_id"] for offer in offers if offer["_id"] not in matching_id_set]

    if matching_ids:
        await collection.update_many(
            {"_id": {"$in": matching_ids}},
            {"$addToSet": {"matched_user_ids": user_id}},
        )
    if non_matching_ids:
        await collection.update_many(
            {"_id": {"$in": non_matching_ids}},
            {"$pull": {"matched_user_ids": user_id}},
        )


async def tag_new_offers(offer_ids: list, db) -> None:
    """Recalcule le matching de TOUS les profils contre un lot d'offres
    fraîchement sauvegardées. Utilisé en fin de cycle de collecte."""
    if not offer_ids:
        return

    collection = db["job_offers"]
    offers = await collection.find({"_id": {"$in": offer_ids}}).to_list(length=None)
    if not offers:
        return

    profiles = await db["candidate_profile"].find({}).to_list(length=None)

    for profile in profiles:
        user_id = str(profile["user_id"])
        prefs = profile.get("preferences") or {}
        normalized_roles, normalized_locations, remote_policy = await get_normalized_profile_criteria(prefs, db)

        matching_ids = [
            offer["_id"]
            for offer in offers
            if offer_matches_criteria(offer, normalized_roles, normalized_locations, remote_policy)
        ]
        if matching_ids:
            await collection.update_many(
                {"_id": {"$in": matching_ids}},
                {"$addToSet": {"matched_user_ids": user_id}},
            )
