"""Contrôles déterministes de l'évaluation : préférences candidat (Bloc A) et signaux d'offre (Bloc G).

Aucun appel LLM ici : ces comparaisons reposent sur des champs structurés de l'offre
(type_contrat, seniority_level, salaire, description) et du profil (preferences).
"""

import re
from typing import Any, Dict, List, Optional

from app.models import BlocA, BlocG, PreferenceMismatch, RiskSummaryItem

SHORT_DESCRIPTION_CHARS = 500

# Ordre de séniorité : la distance entre niveaux fixe le poids de l'écart.
SENIORITY_ORDER = ["intern", "junior", "mid", "senior", "lead", "director"]

_PAY_RANGE_RE = re.compile(
    r"(?:[$€£]\s*)?"
    r"(\d[\d\s\u202f.,]*)\s*(k)?\s*(?:€|\$|£|eur|euros?|usd)?"
    r"\s*(?:-|–|—|\bà\b|\bto\b|\bet\b|\band\b)\s*"
    r"(?:[$€£]\s*)?"
    r"(\d[\d\s\u202f.,]*)\s*(k)?\s*(?:€|\$|£|eur|euros?|usd)?",
    re.I,
)
_CURRENCY_OR_K_RE = re.compile(r"(?:€|\$|£|\bk\b|eur|euros?|usd|salaire|r[ée]mun[ée]ration|salary|comp)", re.I)

_CONTRACTOR_MARKER_RE = re.compile(
    r"\b("
    r"facturation|auto-entrepreneur|micro-entreprise|ind[ée]pendant|freelance|"
    r"portage\s+salarial|tjm|prestation\s+de\s+services|"
    r"independent\s+contractor|invoice\s+for\s+services|self-employed|"
    r"1099|outside\s+ir35|t4a|service\s+agreement|consulting\s+agreement"
    r")\b",
    re.I,
)
_EMPLOYEE_BENEFITS_RE = re.compile(
    r"\b("
    r"cong[ée]s\s+pay[ée]s|mutuelle|pr[ée]voyance|rtt|tickets?\s+restaurant|"
    r"participation|int[ée]ressement|paid\s+time\s+off|pto|401\(k\)|health\s+insurance"
    r")\b",
    re.I,
)

_AI_BUZZWORDS_RE = re.compile(
    r"\b("
    r"transformation\s+ia|ai\s+transformation|ai\s+enablement|digital\s+transformation|"
    r"transformation\s+digitale|r[ée]volutionner\s+par\s+l['’]ia|ai-first|generative\s+ai\s+strategy|"
    r"innovation\s+ia"
    r")\b",
    re.I,
)
_SMALL_TEAM_RE = re.compile(
    r"(?:[ée]quipe\s+(?:de\s+)?[1-5]\s+personnes?|petite\s+[ée]quipe|small\s+team|team\s+of\s+[1-5])",
    re.I,
)
_JUNIOR_MID_SCOPE_RE = re.compile(
    r"\b(junior|mid-?level|charg[ée]\s+de|consultant\s+junior|assistant|confirm[ée]|sp[ée]cialiste)\b",
    re.I,
)
_LEGACY_INDUSTRY_RE = re.compile(
    r"\b(industrie|industriel|manufacturing|logistique|supply\s+chain|bâtiment|construction|"
    r"a[ée]rospatial|d[ée]fense|aerospace|defense|transport|retail|distribution)\b",
    re.I,
)
_CONCRETE_AI_INFRA_RE = re.compile(
    r"\b(pytorch|tensorflow|kubernetes|mlflow|databricks|snowflake|airflow|dbt|fastapi|"
    r"vllm|hugging\s*face|langgraph|rag|postgres|vector\s*db|mlops|ci/cd)\b",
    re.I,
)

# Première règle qui matche gagne ; valeurs non reconnues ("Non spécifié", "Temps partiel") ignorées.
CONTRACT_PATTERNS = [
    ("cdi", re.compile(r"\bcdii?\b|permanent", re.I)),
    ("cdd", re.compile(r"\bcdd\b", re.I)),
    ("freelance", re.compile(r"freelance|prestation|ind[ée]pendant|portage", re.I)),
    ("alternance", re.compile(r"alternance|apprentissage|contrat pro", re.I)),
    ("stage", re.compile(r"\bstage\b|intern", re.I)),
    ("interim", re.compile(r"int[ée]rim", re.I)),
]


def normalize_contract(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    for label, pattern in CONTRACT_PATTERNS:
        if pattern.search(value):
            return label
    return None


def parse_annual_salary_max(value: Optional[str]) -> Optional[int]:
    """Borne haute annuelle d'un salaire texte ; montants < 10 000 considérés mensuels."""
    if not value:
        return None
    amounts = []
    for raw in re.findall(r"\d[\d\s .,]*", value):
        digits = re.sub(r"[\s ]", "", raw)
        digits = re.sub(r"[.,]\d{1,2}$", "", digits)  # centimes
        digits = re.sub(r"[.,]", "", digits)
        if digits.isdigit() and int(digits) >= 1000:
            amounts.append(int(digits))
    if not amounts:
        return None
    top = max(amounts)
    return top * 12 if top < 10000 else top


def check_preference_fit(offer: Dict[str, Any], preferences: Dict[str, Any]) -> List[PreferenceMismatch]:
    """Écarts entre l'offre et les préférences déclarées ; champ absent d'un côté = pas d'écart."""
    mismatches: List[PreferenceMismatch] = []

    offer_contract = normalize_contract(offer.get("type_contrat"))
    wanted_contracts = {normalize_contract(c) for c in preferences.get("contract_types") or []} - {None}
    if offer_contract and wanted_contracts and offer_contract not in wanted_contracts:
        mismatches.append(
            PreferenceMismatch(
                criterion="contrat",
                offer_value=str(offer.get("type_contrat")),
                expected=", ".join(preferences.get("contract_types") or []),
                weight="high",
            )
        )

    offer_level = (offer.get("seniority_level") or "").lower()
    wanted_levels = [lvl.lower() for lvl in preferences.get("seniority_levels") or [] if lvl]
    if offer_level in SENIORITY_ORDER:
        known = [SENIORITY_ORDER.index(lvl) for lvl in wanted_levels if lvl in SENIORITY_ORDER]
        if known:
            distance = min(abs(SENIORITY_ORDER.index(offer_level) - k) for k in known)
            if distance:
                mismatches.append(
                    PreferenceMismatch(
                        criterion="séniorité",
                        offer_value=offer_level,
                        expected=", ".join(wanted_levels),
                        weight="meaningful" if distance == 1 else "high",
                    )
                )

    min_salary = preferences.get("min_salary")
    offer_salary_max = parse_annual_salary_max(offer.get("salaire"))
    if min_salary and offer_salary_max and offer_salary_max < min_salary:
        mismatches.append(
            PreferenceMismatch(
                criterion="salaire",
                offer_value=str(offer.get("salaire")),
                expected=f">= {min_salary} {preferences.get('currency') or 'EUR'} / an",
                weight="high",
            )
        )

    return mismatches


def _normalize_bound(raw_num: str, has_k: bool) -> Optional[int]:
    digits = re.sub(r"[\s\u202f]", "", raw_num)
    digits = re.sub(r"[.,]\d{1,2}$", "", digits)
    digits = re.sub(r"[.,]", "", digits)
    if not digits.isdigit():
        return None
    val = int(digits)
    if has_k:
        val *= 1000
    return val if val > 0 else None


def check_pay_range_width(offer: Dict[str, Any]) -> Optional[str]:
    """Detect unusually wide salary bands where (top - bottom) > 0.5 * bottom."""
    candidates: List[tuple[str, bool]] = []
    if offer.get("salaire"):
        candidates.append((str(offer["salaire"]), True))
    if offer.get("description"):
        candidates.append((str(offer["description"]), False))

    for text, from_salary_field in candidates:
        for match in _PAY_RANGE_RE.finditer(text):
            snippet = match.group(0)
            if not from_salary_field and not _CURRENCY_OR_K_RE.search(snippet):
                continue
            if not from_salary_field and re.search(r"\b(?:et|and)\b", snippet, re.I):
                lead = text[max(0, match.start() - 30) : match.start()].lower()
                if "entre" not in lead and "between" not in lead:
                    continue
            bot_k = bool(match.group(2))
            top_k = bool(match.group(4))
            bottom = _normalize_bound(match.group(1), bot_k or top_k)
            top = _normalize_bound(match.group(3), top_k)
            if not bottom or not top or top <= bottom:
                continue
            if not from_salary_field and top < 1000 and not (bot_k or top_k):
                continue
            if bottom < 10000 and top < 10000 and bottom >= 1000:
                bottom *= 12
                top *= 12
            if (top - bottom) > 0.5 * bottom:
                return (
                    f"Fourchette salariale très large ({bottom}–{top}, écart > 50 % de la borne basse) : "
                    "le niveau réel du poste peut être encore mal défini."
                )
    return None


def check_employment_classification_risk(offer: Dict[str, Any]) -> Optional[str]:
    """Flag contractor/freelance status markers paired with salaried framing or absent employee benefits."""
    description = (offer.get("description") or "").strip()
    if not description:
        return None
    marker_match = _CONTRACTOR_MARKER_RE.search(description)
    if not marker_match:
        return None

    contract_norm = normalize_contract(offer.get("type_contrat"))
    has_employee_benefits = bool(_EMPLOYEE_BENEFITS_RE.search(description))
    salaried_framing = contract_norm in ("cdi", "cdd", "alternance", "stage")
    if salaried_framing or not has_employee_benefits:
        phrase = marker_match.group(0)
        return (
            f"Risque de classification prestation/indépendant (mention « {phrase} ») : "
            "vérifier le statut réel du contrat et les protections/avantages associés."
        )
    return None


def check_ai_buzzword_mismatch(offer: Dict[str, Any]) -> Optional[str]:
    """Flag AI/transformation buzzwords mismatched with seniority, team size, or missing technical stack (2+ signals)."""
    title = (offer.get("poste") or offer.get("title") or "").strip()
    description = (offer.get("description") or "").strip()
    combined = f"{title}\n{description}"
    buzzwords = _AI_BUZZWORDS_RE.findall(combined)
    if not buzzwords:
        return None

    signals_hit = 0
    # Signal 1: Transformation buzzwords paired with junior/mid IC scope or absent senior ownership
    if _JUNIOR_MID_SCOPE_RE.search(title) or _JUNIOR_MID_SCOPE_RE.search(description):
        signals_hit += 1
    # Signal 2: Small team tasked with org-wide AI transformation
    if _SMALL_TEAM_RE.search(description):
        signals_hit += 1
    # Signal 3: Legacy/traditional industry or absence of concrete AI/data tooling
    if _LEGACY_INDUSTRY_RE.search(combined) or not _CONCRETE_AI_INFRA_RE.search(combined):
        signals_hit += 1

    if signals_hit >= 2:
        sample = ", ".join(dict.fromkeys(b.strip() for b in buzzwords[:3]))
        return (
            f"Décalage potentiel discours IA / infrastructure ({sample}) : "
            "le quotidien pourrait relever de la numérisation de base ; vérifier la maturité technique en entretien."
        )
    return None


def build_risk_summary(
    bloc_a: BlocA,
    bloc_g: BlocG,
    offer: Optional[Dict[str, Any]] = None,
) -> List[RiskSummaryItem]:
    """Aggregate existing Block A and Block G signals into an ordered Risk Summary without re-scoring."""
    legitimacy_reasons: List[str] = []
    if bloc_g.is_scam_risk:
        legitimacy_reasons.append("risque d'arnaque")
    if bloc_g.is_ghost_job:
        legitimacy_reasons.append("offre potentiellement fantôme")
    if bloc_g.reposted_frequency:
        legitimacy_reasons.append(bloc_g.reposted_frequency)
    legitimacy_status = (
        f"⚠️ Proceed with Caution — {', '.join(legitimacy_reasons)}"
        if legitimacy_reasons
        else "✅ High Confidence"
    )

    classification_status = (
        f"⚠️ {bloc_g.employment_classification_risk}"
        if bloc_g.employment_classification_risk
        else "✅ clear"
    )

    if bloc_g.pay_range_width_warning:
        pay_status = f"⚠️ {bloc_g.pay_range_width_warning}"
    elif offer and offer.get("salaire"):
        pay_status = "✅ clear"
    else:
        pay_status = "— not evaluated"

    ai_status = (
        f"⚠️ {bloc_g.ai_buzzword_mismatch}"
        if bloc_g.ai_buzzword_mismatch
        else "✅ consistent"
    )

    fit_issues: List[str] = []
    if bloc_a.domain_mismatch:
        fit_issues.append("domain mismatch")
    if bloc_a.geo_mismatch:
        fit_issues.append("geo mismatch")
    if bloc_a.visa_sponsoring_refused:
        fit_issues.append("visa refused")
    if bloc_a.preference_mismatches:
        fit_issues.append(f"{len(bloc_a.preference_mismatches)} écart(s) préférences")
    if bloc_a.red_flags:
        fit_issues.append(f"{len(bloc_a.red_flags)} drapeau(x) rouge(s)")
    fit_status = f"⚠️ {', '.join(fit_issues)}" if fit_issues else "✅ pass"

    return [
        RiskSummaryItem(signal="Posting legitimacy", status=legitimacy_status),
        RiskSummaryItem(signal="Employment classification", status=classification_status),
        RiskSummaryItem(signal="Pay range transparency", status=pay_status),
        RiskSummaryItem(signal="AI claims vs. infrastructure", status=ai_status),
        RiskSummaryItem(signal="Preference & domain fit", status=fit_status),
    ]


def offer_quality_warnings(offer: Dict[str, Any], publication_count: int) -> List[str]:
    """Alertes Bloc G factuelles, issues de la base et non du jugement du modèle."""
    warnings: List[str] = []
    if publication_count >= 2:
        warnings.append(
            f"Offre publiée {publication_count} fois (même entreprise et même intitulé) : possible republication."
        )
    description_len = len((offer.get("description") or "").strip())
    if description_len < SHORT_DESCRIPTION_CHARS:
        warnings.append(
            f"Description courte ({description_len} caractères) : exigences probablement incomplètes, évaluation peu fiable."
        )
    for extra in (
        check_pay_range_width(offer),
        check_employment_classification_risk(offer),
        check_ai_buzzword_mismatch(offer),
    ):
        if extra:
            warnings.append(extra)
    return warnings
