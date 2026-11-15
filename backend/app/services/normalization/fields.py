"""Offer title syntax cleanup, contract type detection, seniority, and field normalization."""

import re
from typing import Any, Dict, Optional, Set

from app.services.normalization.text import (
    clean_html_entities_and_tags,
    compute_unique_key,
    normalize_city,
)

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)
_MARKETING_PATTERNS = (
    r"\[(?:urgent|top mission|super opportunit[ée]|exclusivit[ée]|nouveau|hot|asap|recrutement|imm[ée]diat)\]",
    r"\b(?:urgent|top mission|super opportunit[ée]|exclusivit[ée]|asap)\b",
)
_LEGAL_PATTERNS = (
    r"\(\s*(?:h|f|m)\s*[\/\-]?\s*(?:h|f|w)(?:\s*[\/\-]\s*(?:[dxn]|nb|non[\s\-]binaire))?\s*\)",
    r"\b(?:h\/f\/nb|f\/h\/nb|h\/f\/d|f\/h\/d|h\/f\/x|f\/h\/x|h\/f\/n|f\/h\/n)\b",
    r"\b(?:h\/f|f\/h|hf|fh|h\-f|f\-h|m\/f|m\/w\/d|m\/f\/d)\b",
    r"\b(?:homme\s*[\/\-]?\s*femme|femme\s*[\/\-]?\s*homme)\b",
    r"\(\s*[\/\-]\s*(?:nb|non[\s\-]binaire|[dxn])?\s*\)",
    r"\s*[\/\-–—]\s*(?:nb|non[\s\-]binaire|n)\b",
)
_TITLE_CONTRACT_PATTERNS = (
    r"\b(?:cdi\s*[\-–—]?\s*cdd|cdd\s*[\-–—]?\s*cdi)\b",
    r"\b(?:cdi\s*int[ée]rimaire|contrat\s*pro(?:fessionnalisation)?)\b",
    r"\b(?:cdi|cdd|freelance|stage|stagiaire|alternance|alternant|alternante|apprentissage|apprenti|apprentie|int[ée]rim)\b",
)
_LOC_REMOTE_PATTERNS = (
    r"\s*[\-–—\|\/]\s*(?:paris|lyon|marseille|toulouse|bordeaux|nantes|lille|strasbourg|rennes|nice|montpellier|grenoble|france|remote|t[ée]l[ée]travail|full[\s\-]remote|hybride)\b.*$",
    r"\(\s*(?:paris|lyon|marseille|toulouse|bordeaux|nantes|lille|strasbourg|rennes|nice|montpellier|grenoble|france|remote|t[ée]l[ée]travail|full[\s\-]remote|hybride)\s*\)",
)


def clean_job_title_syntax(title: Optional[str]) -> str:
    """Couche 1 : Nettoyage syntaxique déterministe de l'intitulé de poste."""
    if not title or not isinstance(title, str):
        return "Non spécifié"

    cleaned = clean_html_entities_and_tags(title)
    if not cleaned:
        return "Non spécifié"

    cleaned = _EMOJI_PATTERN.sub(" ", cleaned)
    for pat in (*_MARKETING_PATTERNS, *_LEGAL_PATTERNS):
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[[^\]]*\]", " ", cleaned)
    for pat in (*_TITLE_CONTRACT_PATTERNS, *_LOC_REMOTE_PATTERNS):
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)

    for empty_brackets in (r"\(\s*\)", r"\[\s*\]", r"\{\s*\}"):
        cleaned = re.sub(empty_brackets, " ", cleaned)

    cleaned = cleaned.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    cleaned = cleaned.replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"^[\s\-–—\|\/,\.:;]+|[\s\-–—\|\/,\.:;]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else (title.strip() or "Non spécifié")


CONTRACT_PLACEHOLDERS: Set[str] = {"", "non spécifié", "non disponible", "inconnu", "none", "null", "undefined", "nan"}

# Ordre de priorité : le premier libellé reconnu l'emporte (« CDI intérimaire » reste un CDI).
CONTRACT_PATTERNS = (
    ("Stage", r"(?<!-)\b(?:stage|stagiaire|internship|intern)\b"),
    ("Alternance", r"\b(?:alternance|alternant|alternante|apprentissage|apprenti|apprentie|apprenticeship|contrat\s+pro(?:fessionnalisation)?)\b"),
    ("Freelance", r"\b(?:freelance|ind[ée]pendant|prestation|contractor)\b"),
    ("CDI", r"\b(?:cdi|permanent|dur[ée]e\s+ind[ée]termin[ée]e)\b"),
    ("CDD", r"\b(?:cdd|fixed[\s\-]term|temporary|dur[ée]e\s+d[ée]termin[ée]e)\b"),
    ("Intérim", r"\b(?:int[ée]rim|int[ée]rimaire|travail\s+temporaire)\b"),
)

# Expressions qui contiennent un mot-clé de contrat sans en désigner un
NOT_A_CONTRACT_PATTERNS = (
    r"\b(?:early|late|later|seed|growth|pre[\s\-]?seed|multi)[\s\-]+stage\b",
    r"\bapprentissage\s+(?:automatique|machine|profond|statistique|supervis[ée]|non\s+supervis[ée]|par\s+renforcement)\b",
)

STAGE_DESCRIPTION_MARKERS = (
    r"\ben\s+tant\s+que\s+stagiaire\b",
    r"(?:^|[.!?:\n]\s*)(?:le|la)\s+stagiaire\b",
    r"\bstage\s+(?:de|d['’]une\s+dur[ée]e\s+de)\s+\d+\s*(?:(?:à|a|-)\s*\d+\s*)?mois\b",
    r"\bdur[ée]e\s+du\s+stage\b",
    r"\bconvention\s+de\s+stage\b",
    r"\bgratification\s+de\s+stage\b",
    r"\boffre\s+de\s+stage\b",
    r"\bce\s+stage\b",
    r"\b(?:this|our)\s+internship\b",
    r"\bas\s+an?\s+intern\b",
)
ALTERNANCE_DESCRIPTION_MARKERS = (
    r"\bcontrat\s+d['’]apprentissage\b",
    r"\bcontrat\s+de\s+professionnalisation\b",
    r"\brythme\s+d['’]alternance\b",
    r"\ben\s+tant\s+qu['’]alternante?\b",
    r"(?:^|[.!?:\n]\s*)l['’]alternante?\b",
)


def _contract_from_keywords(text: str) -> Optional[str]:
    for pattern in NOT_A_CONTRACT_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    found = [label for label, pattern in CONTRACT_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE)]
    if "Stage" in found and "Alternance" in found:
        return "Stage / Alternance"
    return found[0] if found else None


def _contract_from_description(description: str) -> Optional[str]:
    is_stage = any(re.search(p, description, flags=re.IGNORECASE) for p in STAGE_DESCRIPTION_MARKERS)
    is_alternance = any(re.search(p, description, flags=re.IGNORECASE) for p in ALTERNANCE_DESCRIPTION_MARKERS)
    if is_stage and is_alternance:
        return "Stage / Alternance"
    if is_stage:
        return "Stage"
    return "Alternance" if is_alternance else None


def detect_contract_type(
    source_contract: Optional[str], raw_title: Optional[str], description: Optional[str] = None
) -> str:
    """Type de contrat d'une offre, déduit au besoin de l'intitulé brut puis de la description."""
    source = clean_html_entities_and_tags(source_contract)
    if source.lower() in CONTRACT_PLACEHOLDERS:
        source = ""
    title_contract = _contract_from_keywords(str(raw_title or ""))
    # Un intitulé « Stage - … » prime : certains ATS déclarent CDI ou « Permanent » pour un stage
    if title_contract in ("Stage", "Alternance", "Stage / Alternance"):
        return title_contract
    return (
        (_contract_from_keywords(source) if source else None)
        or title_contract
        or _contract_from_description(str(description or ""))
        or source
        or "Non spécifié"
    )


def normalize_offer_fields(offer: Dict[str, Any]) -> Dict[str, Any]:
    """Nettoie et normalise l'ensemble des champs d'une offre (titre, entreprise, ville, contrat, etc.) hors IA."""
    if not offer or not isinstance(offer, dict):
        return offer

    cleaned = dict(offer)
    cleaned["type_contrat"] = detect_contract_type(
        cleaned.get("type_contrat"), cleaned.get("poste"), cleaned.get("description")
    )
    if "poste" in cleaned and cleaned["poste"]:
        cleaned["poste"] = clean_job_title_syntax(cleaned["poste"])
    if "entreprise" in cleaned and cleaned["entreprise"]:
        ent = clean_html_entities_and_tags(str(cleaned["entreprise"]))
        cleaned["entreprise"] = ent if ent else "Non spécifié"
    if "localisation" in cleaned and cleaned["localisation"]:
        loc = clean_html_entities_and_tags(str(cleaned["localisation"]))
        cleaned["localisation"] = normalize_city(loc) if loc else "Non spécifié"
    for field in ("type_contrat", "salaire", "mode_travail"):
        if field in cleaned and cleaned[field]:
            val = clean_html_entities_and_tags(str(cleaned[field]))
            cleaned[field] = val if val else "Non spécifié"
    if "description" in cleaned and cleaned["description"]:
        desc = str(cleaned["description"])
        if "<" in desc or "&" in desc:
            from app.services.ats.router import clean_html_to_text
            cleaned["description"] = clean_html_to_text(desc)

    cleaned["unique_key"] = compute_unique_key(
        company=cleaned.get("entreprise", ""),
        position=cleaned.get("poste", ""),
        location=cleaned.get("localisation"),
        url=cleaned.get("url"),
    )
    return cleaned


def extract_seniority(title: Optional[str], description: Optional[str] = None) -> Optional[str]:
    """Couche 2 : Extraction du niveau de séniorité standardisé."""
    text_to_check = (title or "").lower()
    patterns = [
        ("intern", r"\b(stage|stagiaire|alternance|alternant|alternante|apprenti|apprentie|apprentissage|intern|internship)\b"),
        ("director", r"\b(director|directeur|directrice|head of|vp|chief|cto|cpo|ceo|coo)\b"),
        ("lead", r"\b(lead|principal|staff|tech lead|architecte|architect|team lead)\b"),
        ("senior", r"\b(senior|sr\.?|exp[ée]riment[ée]|5\+?\s*ans)\b"),
        ("junior", r"\b(junior|jr\.?|d[ée]butant|d[ée]butante|graduate|entry[\s\-]level|0[\s\-]2\s*ans)\b"),
        ("mid", r"\b(mid|confirm[ée]|interm[ée]diaire|2[\s\-]5\s*ans)\b"),
    ]
    for level, pat in patterns:
        if re.search(pat, text_to_check, flags=re.IGNORECASE):
            return level

    if description and isinstance(description, str):
        desc_snippet = description[:500].lower()
        for level, pat in patterns:
            if re.search(pat, desc_snippet, flags=re.IGNORECASE):
                return level
    return None
