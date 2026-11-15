import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from ...models import UserModel

GENERIC_ROLE_MODIFIERS = {
    "responsable",
    "directeur",
    "directrice",
    "chef",
    "manager",
    "charge",
    "chargée",
    "chargee",
    "assistant",
    "assistante",
    "coordinateur",
    "coordinatrice",
    "consultant",
    "consultante",
    "junior",
    "senior",
    "lead",
    "head",
    "officer",
    "analyst",
    "analyste",
    "espace",
    "pole",
    "pôle",
    "service",
    "departement",
    "secteur",
    "centre",
    "hub",
    "unite",
    "unité",
    "metier",
    "métier",
    "specialise",
    "spécialisé",
    "specialisee",
    "spécialisée",
    "permanent",
    "permanente",
}

STOPWORDS = {
    "de", "du", "des", "le", "la", "les", "un", "une", "en", "pour",
    "et", "ou", "au", "aux", "par", "sur", "dans", "avec", "sans",
    "sous", "chez", "d", "l", "h", "f", "a", "à",
}

ACCENT_VARIANTS = {
    "a": "aàâäáã",
    "c": "cç",
    "e": "eéèêë",
    "i": "iîïí",
    "n": "nñ",
    "o": "oôöó",
    "u": "uùûüú",
    "y": "yÿ",
}

STEM_PREFIXES = ("animat", "educat", "jeun", "enfant", "periscol", "developp")


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text) if not unicodedata.combining(ch)
    )


def _accent_insensitive(text: str) -> str:
    """Motif regex qui trouve `text` avec ou sans accents, en minuscules comme en
    majuscules (« ingenieur » trouve « INGÉNIEUR »), sans dépendre du repliement
    de casse Unicode de l'option `i` de Mongo."""
    parts = []
    for ch in _strip_accents(text):
        variants = ACCENT_VARIANTS.get(ch.lower())
        parts.append(f"[{variants}{variants.upper()}]" if variants else re.escape(ch))
    return "".join(parts)


def _stem_keyword(w: str) -> str:
    """Racine lexicale tolérante aux accords de genre/nombre, au pluriel et aux accents."""
    bare = _strip_accents(w)
    for prefix in STEM_PREFIXES:
        if bare.startswith(prefix):
            return _accent_insensitive(prefix)
    return _accent_insensitive(w)


def _build_keywords_filter(keywords: str) -> dict:
    """Construit un filtre de recherche tolérant, précis et sans dilution par des mots génériques."""
    clean_kw = keywords.strip()
    if not clean_kw:
        return {}

    if "|" in clean_kw:
        sub_filters = [
            _build_keywords_filter(term.strip())
            for term in clean_kw.split("|")
            if term.strip()
        ]
        sub_filters = [f for f in sub_filters if f]
        if not sub_filters:
            return {}
        return sub_filters[0] if len(sub_filters) == 1 else {"$or": sub_filters}

    words = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", clean_kw.lower())
    meaningful = [w for w in words if len(w) >= 2 and w not in STOPWORDS]
    if not meaningful:
        return {"poste": {"$regex": _accent_insensitive(clean_kw), "$options": "i"}}

    domain_words = [w for w in meaningful if w not in GENERIC_ROLE_MODIFIERS]
    modifier_words = [w for w in meaningful if w in GENERIC_ROLE_MODIFIERS]

    # 1. Correspondance exacte sur le titre du poste
    or_branches = [{"poste": {"$regex": _accent_insensitive(clean_kw), "$options": "i"}}]

    if domain_words:
        domain_patterns = [_stem_keyword(w) for w in domain_words]
        # 2. Présence de TOUS les termes du domaine dans l'intitulé ou les compétences
        domain_and_poste = [
            {
                "$or": [
                    {"poste": {"$regex": dp, "$options": "i"}},
                    {"competences_cles": {"$regex": dp, "$options": "i"}},
                ]
            }
            for dp in domain_patterns
        ]
        or_branches.append({"$and": domain_and_poste})

        # 3. Présence conjointe des mots du domaine et du rôle
        if modifier_words:
            combined_and = [
                {
                    "$or": [
                        {"poste": {"$regex": _stem_keyword(m), "$options": "i"}},
                        {"description": {"$regex": _stem_keyword(m), "$options": "i"}},
                    ]
                }
                for m in modifier_words
            ]
            combined_and.extend(domain_and_poste)
            or_branches.append({"$and": combined_and})
    else:
        # Aucun terme de domaine spécifique, que des modificateurs (ex: recherche "responsable")
        mod_patterns = [_stem_keyword(w) for w in modifier_words]
        or_branches.append({"poste": {"$regex": "|".join(mod_patterns), "$options": "i"}})

    return {"$or": or_branches}


def _build_contract_type_filter(contract_type: str) -> dict:
    """Construit le filtre de contrat (inclut Non spécifié hors stage/alternance)."""
    c_lower = contract_type.lower()
    if (
        ("stage" in c_lower or "alternance" in c_lower)
        and "cdi" not in c_lower
        and "cdd" not in c_lower
    ):
        return {"type_contrat": {"$regex": contract_type, "$options": "i"}}

    return {
        "$and": [
            {
                "$or": [
                    {"type_contrat": {"$regex": contract_type, "$options": "i"}},
                    {"type_contrat": "Non spécifié"},
                    {"type_contrat": None},
                    {"type_contrat": {"$exists": False}},
                ]
            },
            {"type_contrat": {"$not": {"$regex": "stage|alternance", "$options": "i"}}},
        ]
    }


def _build_sector_filter(sector: List[str]) -> dict:
    """Filtre par secteur(s) (taxonomie `SECTORS`) : plusieurs valeurs se combinent en $in."""
    return {"sector": {"$in": sector}}


def _build_company_size_filter(company_size: List[str]) -> dict:
    """Filtre par taille(s) d'entreprise (taxonomie `COMPANY_SIZES`) : plusieurs valeurs se combinent en $in."""
    return {"company_size": {"$in": company_size}}


def restrict_to_profile_offers(
    match_filter: dict,
    current_user: Optional[UserModel],
    only_saved: bool = False,
    interaction_status: Optional[str] = None,
) -> dict:
    """Un utilisateur connecté ne voit que les offres rattachées à son profil."""
    if current_user and not only_saved and not interaction_status:
        match_filter["matched_user_ids"] = str(current_user.id)
    return match_filter


def _append_and(match_filter: dict, clause: dict) -> None:
    match_filter.setdefault("$and", []).append(clause)


def _apply_search_filters(
    match_filter: dict,
    *,
    keywords: Optional[str],
    location: Optional[str],
    company: Optional[str],
    contract_type: Optional[str],
    work_mode: Optional[str],
    sector: Optional[List[str]],
    company_size: Optional[List[str]],
    days_recent: Optional[int],
    current_user: Optional[UserModel],
    only_saved: bool,
    interaction_status: Optional[str],
) -> dict:
    """Applique au filtre Mongo les critères de recherche partagés par la liste et le count."""
    if keywords:
        kw_filter = _build_keywords_filter(keywords)
        if kw_filter:
            _append_and(match_filter, kw_filter)

    if location:
        match_filter["localisation"] = {"$regex": _accent_insensitive(location), "$options": "i"}
    if company:
        match_filter["entreprise"] = {"$regex": _accent_insensitive(company), "$options": "i"}
    if contract_type:
        _append_and(match_filter, _build_contract_type_filter(contract_type))
    if work_mode:
        match_filter["mode_travail"] = {"$regex": work_mode, "$options": "i"}
    if sector:
        _append_and(match_filter, _build_sector_filter(sector))
    if company_size:
        _append_and(match_filter, _build_company_size_filter(company_size))

    restrict_to_profile_offers(match_filter, current_user, only_saved, interaction_status)

    if days_recent and days_recent > 0:
        threshold_dt = datetime.now(timezone.utc) - timedelta(days=days_recent)
        iso_str = threshold_dt.isoformat()
        _append_and(
            match_filter,
            {
                "$or": [
                    {"created_at": {"$gte": threshold_dt}},
                    {"created_at": {"$gte": iso_str}},
                ]
            },
        )

    return match_filter
