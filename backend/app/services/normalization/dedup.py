"""Cross-platform deduplication, Jaccard similarity, source priority, and merging."""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set

from app.services.normalization.fields import clean_job_title_syntax, extract_seniority
from app.services.normalization.text import (
    GENERIC_CITY_KEYS,
    _city_key,
    company_match_strength,
    compute_unique_key,
)

FRENCH_ENGLISH_STOPWORDS: Set[str] = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "en", "pour", "et", "ou",
    "qui", "que", "dans", "sur", "avec", "par", "au", "aux", "ce", "cette", "ces",
    "est", "sont", "nous", "vous", "ils", "elles", "notre", "votre", "leur", "plus",
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "by",
    "is", "are", "we", "you", "they", "our", "your", "their", "of", "from", "as",
}

_ATS_INDICATORS = (
    "greenhouse.io", "lever.co", "workable.com", "ashbyhq.com",
    "teamtailor.com", "recruitee.com", "personio", "myworkdayjobs.com",
    "smartrecruiters.com", "taleo.net", "icims.com", "bamboohr.com",
    "breezy.hr", "flatchr.io", "jobs2web.com",
)


def jaccard_description_similarity(desc1: Optional[str], desc2: Optional[str]) -> float:
    """Couche 3 : Calcule la similarité de Jaccard sur les tokens signifiants des descriptions."""
    if not desc1 or not desc2:
        return 0.0

    def tokenize(text: str) -> Set[str]:
        words = re.findall(r"\b[a-zA-ZÀ-ÿ0-9]{3,}\b", text.lower())
        return {w for w in words if w not in FRENCH_ENGLISH_STOPWORDS}

    tokens1 = tokenize(desc1)
    tokens2 = tokenize(desc2)
    if len(tokens1) < 15 or len(tokens2) < 15:
        return 0.0

    union = len(tokens1 | tokens2)
    return len(tokens1 & tokens2) / union if union > 0 else 0.0


def are_offers_duplicates(
    offer1: Dict[str, Any],
    offer2: Dict[str, Any],
    title_similarity_threshold: float = 0.82,
    jaccard_threshold: float = 0.65,
) -> bool:
    """Couche 3 : Évalue si deux offres représentent le même poste (multidiffusion ou repost)."""
    url1 = (offer1.get("url") or "").strip()
    url2 = (offer2.get("url") or "").strip()
    if url1 and url2 and url1 == url2:
        return True

    strength = company_match_strength(offer1.get("entreprise", ""), offer2.get("entreprise", ""))
    if not strength:
        return False

    loc1 = _city_key(offer1.get("localisation", ""))
    loc2 = _city_key(offer2.get("localisation", ""))
    if loc1 not in GENERIC_CITY_KEYS and loc2 not in GENERIC_CITY_KEYS and loc1 != loc2:
        return False

    p1 = clean_job_title_syntax(offer1.get("poste", "")).lower()
    p2 = clean_job_title_syntax(offer2.get("poste", "")).lower()
    ratio_title = SequenceMatcher(None, p1, p2).ratio()
    title_match = (p1 == p2 and p1 != "non spécifié") or ratio_title >= title_similarity_threshold
    if strength == "strong" and title_match:
        return True

    jaccard = jaccard_description_similarity(offer1.get("description") or "", offer2.get("description") or "")
    if strength == "weak" and jaccard < 0.5:
        return False
    return title_match or (jaccard >= jaccard_threshold and ratio_title >= 0.45)


def get_source_priority(url: Optional[str]) -> int:
    """Couche 4 : Hiérarchie de confiance et de pérennité des sources."""
    if not url:
        return 20
    url_lower = url.lower()
    if any(ats in url_lower for ats in _ATS_INDICATORS):
        return 100
    if any(jb in url_lower for jb in ("welcometothejungle.com", "apec.fr", "francetravail.fr")):
        return 80
    if any(agg in url_lower for agg in ("linkedin.com", "hellowork.com", "indeed.com", "cadremploi.fr", "meteojob.com", "glassdoor")):
        return 50
    return 20


def _source_records(offer: Dict[str, Any]) -> Dict[str, Any]:
    """`raw_data` rangé par source ({"linkedin": {...}}), ou {} pour l'ancienne copie à plat de l'offre."""
    raw = offer.get("raw_data")
    if isinstance(raw, dict) and raw and all(isinstance(v, dict) for v in raw.values()):
        return raw
    return {}


def _merge_scalar_fields(p_copy: Dict[str, Any], s_copy: Dict[str, Any]) -> None:
    """Fill missing salary, contract, and location fields from secondary offer."""
    empty = ("", "None", "Non spécifié")
    for field, extra_empty in (("salaire", empty), ("type_contrat", empty), ("localisation", (*empty, "France"))):
        p_val = str(p_copy.get(field) or "").strip()
        s_val = str(s_copy.get(field) or "").strip()
        if p_val in extra_empty and s_val not in empty:
            p_copy[field] = s_val


def merge_multidiffusion_offers(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    """Couche 4 : Fusionne deux offres doublons en conservant les données les plus riches."""
    p_copy = dict(primary)
    s_copy = dict(secondary)

    p_url = p_copy.get("url") or ""
    s_url = s_copy.get("url") or ""
    if get_source_priority(s_url) > get_source_priority(p_url):
        chosen_primary_url, other_url = s_url, p_url
        p_copy["poste"] = clean_job_title_syntax(s_copy.get("poste") or p_copy.get("poste"))
    else:
        chosen_primary_url = p_url or s_url
        other_url = s_url if s_url != chosen_primary_url else ""
        p_copy["poste"] = clean_job_title_syntax(p_copy.get("poste") or s_copy.get("poste"))

    p_copy["url"] = chosen_primary_url
    existing_alts = set(p_copy.get("alternative_urls") or []) | set(s_copy.get("alternative_urls") or [])
    if other_url and other_url != chosen_primary_url:
        existing_alts.add(other_url)
    existing_alts.discard(chosen_primary_url)
    p_copy["alternative_urls"] = sorted(existing_alts)

    _merge_scalar_fields(p_copy, s_copy)

    p_desc = str(p_copy.get("description") or "").strip()
    s_desc = str(s_copy.get("description") or "").strip()
    if len(s_desc) > len(p_desc):
        p_copy["description"] = s_desc

    combined_skills = set(p_copy.get("competences_cles") or []) | set(s_copy.get("competences_cles") or [])
    if combined_skills:
        p_copy["competences_cles"] = sorted(combined_skills)

    if not p_copy.get("seniority_level"):
        p_copy["seniority_level"] = s_copy.get("seniority_level") or extract_seniority(
            p_copy.get("poste"), p_copy.get("description")
        )
    if not p_copy.get("canonical_title"):
        p_copy["canonical_title"] = s_copy.get("canonical_title")

    if s_copy.get("created_at") and p_copy.get("created_at"):
        try:
            p_copy["created_at"] = min(p_copy["created_at"], s_copy["created_at"])
        except Exception:
            pass

    for preserved_key in ("evaluation", "user_interaction"):
        if not p_copy.get(preserved_key) and s_copy.get(preserved_key):
            p_copy[preserved_key] = s_copy[preserved_key]

    p_copy["unique_key"] = compute_unique_key(
        company=p_copy.get("entreprise", ""),
        position=p_copy.get("poste", ""),
        location=p_copy.get("localisation"),
    )
    source_records = {**_source_records(p_copy), **_source_records(s_copy)}
    if source_records:
        p_copy["raw_data"] = source_records
    return p_copy


def deduplicate_and_merge_offers(
    offers: List[Dict[str, Any]],
    title_similarity_threshold: float = 0.82,
    jaccard_threshold: float = 0.65,
) -> List[Dict[str, Any]]:
    """Couche 4 : Déduplication multi-critères et fusion des offres multidiffusées."""
    if not offers:
        return []

    survivors: List[Dict[str, Any]] = []
    for candidate in offers:
        matched_idx = next(
            (
                idx
                for idx, existing in enumerate(survivors)
                if are_offers_duplicates(
                    candidate,
                    existing,
                    title_similarity_threshold=title_similarity_threshold,
                    jaccard_threshold=jaccard_threshold,
                )
            ),
            -1,
        )
        if matched_idx >= 0:
            survivors[matched_idx] = merge_multidiffusion_offers(survivors[matched_idx], candidate)
        else:
            survivors.append(candidate)
    return survivors
