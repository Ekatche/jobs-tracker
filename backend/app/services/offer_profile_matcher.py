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
