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
