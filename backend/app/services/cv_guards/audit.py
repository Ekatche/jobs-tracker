import logging
import re
from typing import Any, Dict, List, Set, Tuple

from app.models import TailoredCVSchema
from app.services.cv_templates import _cumulative_career_years

from .constants import SENIORITY_CLAIM_RE
from .experience_audit import _audit_experience
from .metrics import _ClaimContext
from .models import CVAudit, Finding
from .text_matching import (
    _cert_matches,
    _clean_str,
    _collect_strings,
    _dates_agree,
    _is_fuzzy_match,
    _is_skill_supported,
    _profile_title,
    _tokens_overlap,
)

logger = logging.getLogger(__name__)


def _match_experiences(
    tailored: TailoredCVSchema, source_profile: Dict[str, Any], violations: List[Finding]
) -> Dict[int, List[Dict[str, Any]]]:
    known_companies = {
        str(exp.get("company") or exp.get("entreprise")).strip()
        for exp in source_profile.get("experiences", [])
        if exp.get("company") or exp.get("entreprise")
    }
    matched_posts: Dict[int, List[Dict[str, Any]]] = {}
    for exp_idx, exp in enumerate(tailored.experiences):
        if not _is_fuzzy_match(exp.company, known_companies):
            violations.append(
                Finding(
                    f"Entreprise '{exp.company}' non trouvée dans les expériences du profil candidat.",
                    "company", exp_idx,
                )
            )
            continue
        same_employer = [
            p
            for p in source_profile.get("experiences", [])
            if _is_fuzzy_match(exp.company, {str(p.get("company") or p.get("entreprise") or "")})
        ]
        known_stints = " ; ".join(
            f"{_profile_title(p) or '?'} {p.get('start') or p.get('start_date') or '?'} → "
            f"{p.get('end') or p.get('end_date') or 'Présent'}"
            for p in same_employer
        )
        candidates = [
            p
            for p in same_employer
            if not _profile_title(p) or _is_fuzzy_match(exp.title, {_profile_title(p)})
        ]
        if not candidates:
            violations.append(
                Finding(
                    f"Intitulé '{exp.title}' chez '{exp.company}' absent du profil (postes connus : {known_stints}). "
                    "Reprends l'intitulé et les dates du profil, un poste par entrée, sans supprimer le poste.",
                    "title", exp_idx,
                )
            )
            continue
        matched_posts[exp_idx] = candidates
        if not any(
            _dates_agree(exp.start_date, p.get("start") or p.get("start_date"), is_end=False)
            and _dates_agree(exp.end_date, p.get("end") or p.get("end_date"), is_end=True)
            for p in candidates
        ):
            violations.append(
                Finding(
                    f"Dates {exp.start_date} → {exp.end_date} du poste '{exp.title}' chez '{exp.company}' absentes du profil "
                    f"(postes connus : {known_stints}). "
                    "Reprends l'intitulé et les dates du profil, un poste par entrée, sans supprimer le poste.",
                    "dates", exp_idx,
                )
            )
    return matched_posts


def _build_skill_corpus(source_profile: Dict[str, Any]) -> Tuple[Set[str], str, Set[str]]:
    known_skills: Set[str] = set()
    corpus_fragments: List[str] = []

    def _extract_fragments(data: Any) -> None:
        if isinstance(data, list):
            for item in data:
                _extract_fragments(item)
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(k, str) and not k.lower().endswith(("_skills", "skills", "langages")):
                    known_skills.add(k.strip())
                _extract_fragments(v)
        elif isinstance(data, str) and data.strip():
            known_skills.add(data.strip())
            corpus_fragments.append(data.strip())
            for token in re.findall(r"[\w\.\+#\-]+", data):
                if len(token) > 1:
                    known_skills.add(token.strip())

    _extract_fragments(source_profile.get("skills"))
    for section, list_keys, text_keys in (
        ("experiences", ["stack", "technologies", "missions", "missions_alt", "achievements"], ["description", "role", "title", "company"]),
        ("projects", ["stack", "technologies", "highlights"], ["description", "name", "title"]),
    ):
        for entry in source_profile.get(section, []) or []:
            for key in list_keys:
                if entry.get(key):
                    _extract_fragments(entry[key])
            for key in text_keys:
                val = entry.get(key)
                if val and isinstance(val, str):
                    corpus_fragments.append(val)
                    known_skills.add(val.strip())

    contact = source_profile.get("contact") or {}
    if isinstance(contact, dict):
        for key in ("mobility", "availability"):
            if isinstance(contact.get(key), str):
                _extract_fragments(contact[key])
    for cert in source_profile.get("certifications", []) or []:
        if isinstance(cert, dict) and cert.get("name"):
            _extract_fragments(cert.get("name"))
            _extract_fragments(cert.get("topics"))
        elif isinstance(cert, str):
            _extract_fragments(cert)
    for edu in source_profile.get("education", []) or []:
        if isinstance(edu, dict):
            _extract_fragments(edu.get("degree") or edu.get("diplome"))
            _extract_fragments(edu.get("topics"))
    for field in ("headline", "summary"):
        if isinstance(source_profile.get(field), str):
            corpus_fragments.append(source_profile[field])

    profile_corpus = _clean_str(" ".join(corpus_fragments))
    return known_skills, profile_corpus, set(re.findall(r"[\w\.\+#\-]+", profile_corpus))


def _audit_certs_and_education(
    tailored: TailoredCVSchema, source_profile: Dict[str, Any], audit: CVAudit
) -> None:
    contact = source_profile.get("contact") or {}
    known_certs: Set[str] = set()
    for cert in source_profile.get("certifications", []) or []:
        name = cert.get("name") if isinstance(cert, dict) else cert
        if name and isinstance(name, str):
            known_certs.add(name.strip())
    if isinstance(contact, dict) and isinstance(contact.get("mobility"), str):
        known_certs.add(contact["mobility"].strip())

    elsewhere: List[str] = []
    for edu in source_profile.get("education", []) or []:
        if isinstance(edu, dict):
            for key in ("degree", "diplome", "title", "intitule"):
                elsewhere.extend(_collect_strings(edu.get(key)))
    for lang in source_profile.get("languages", []) or []:
        elsewhere.extend(
            _collect_strings(lang) + ([" ".join(_collect_strings(lang))] if isinstance(lang, dict) else [])
        )
    elsewhere.extend(_collect_strings(source_profile.get("skills")))

    for cert_idx, cert in enumerate(tailored.certifications):
        if _cert_matches(cert, known_certs):
            continue
        if _tokens_overlap(cert, set(elsewhere), both_ways=False):
            audit.unverifiable.append(
                Finding(
                    f"Certification '{cert}' absente des certifications du profil, présente en formation, langues ou compétences.",
                    "certifications", item_index=cert_idx,
                )
            )
        else:
            audit.violations.append(
                Finding(
                    f"Certification '{cert}' absente du profil candidat vérifié.",
                    "certifications", item_index=cert_idx,
                )
            )

    known_schools = {
        str(edu.get("school") or edu.get("institution") or edu.get("ecole")).strip()
        for edu in source_profile.get("education", []) or []
        if edu.get("school") or edu.get("institution") or edu.get("ecole")
    }
    known_degrees = {
        str(edu.get("degree") or edu.get("diplome")).strip()
        for edu in source_profile.get("education", []) or []
        if edu.get("degree") or edu.get("diplome")
    }
    for edu in tailored.education:
        if not (_is_fuzzy_match(edu.institution, known_schools) or _is_fuzzy_match(edu.degree, known_degrees)):
            audit.violations.append(
                Finding(
                    f"Formation '{edu.degree}' à '{edu.institution}' absente du cursus du profil candidat.",
                    "education",
                )
            )


def verify_cv_honesty(
    tailored: TailoredCVSchema, source_profile: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Inventions confirmées seulement."""
    violations = [f.message for f in audit_cv_claims(tailored, source_profile).violations]
    return not violations, violations


def audit_cv_claims(tailored: TailoredCVSchema, source_profile: Dict[str, Any]) -> CVAudit:
    """Anti-hallucination guardrail for tailored CV generation."""
    audit = CVAudit()
    matched_posts = _match_experiences(tailored, source_profile, audit.violations)
    known_skills, profile_corpus, profile_tokens = _build_skill_corpus(source_profile)

    for group_idx, group in enumerate(tailored.prioritized_skills):
        for skill_idx, skill in enumerate(group.skills):
            if not _is_skill_supported(skill, known_skills, profile_corpus, profile_tokens):
                audit.violations.append(
                    Finding(
                        f"Compétence '{skill}' (catégorie '{group.category}') absente du profil candidat vérifié.",
                        "prioritized_skills", group_index=group_idx, item_index=skill_idx,
                    )
                )

    global_ctx = _ClaimContext.from_strings(_collect_strings(source_profile))
    for exp_idx, candidates in matched_posts.items():
        others = [
            p for p in source_profile.get("experiences", []) or [] if not any(p is c for c in candidates)
        ]
        _audit_experience(
            tailored.experiences[exp_idx], exp_idx, candidates, others,
            global_ctx, known_skills, profile_corpus, profile_tokens, audit,
        )

    _audit_certs_and_education(tailored, source_profile, audit)

    if tailored.professional_summary:
        actual_years = _cumulative_career_years(source_profile)
        for match in SENIORITY_CLAIM_RE.finditer(tailored.professional_summary):
            claimed_years = int(match.group(1))
            if claimed_years > int(actual_years):
                audit.violations.append(
                    Finding(
                        f"Résumé professionnel mentionne {claimed_years} ans d'expérience alors que le profil en totalise {actual_years:.1f} ans.",
                        "professional_summary",
                    )
                )

    for item in audit.unverifiable:
        logger.info(f"CV claim not verifiable (kept): {item.message}")
    return audit
