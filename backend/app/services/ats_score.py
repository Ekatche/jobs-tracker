"""Deterministic ATS-friendliness scorer, plain-text exporter, and invisible-marker sanitizer."""

import re
from typing import Any, Dict, List, Literal, Optional

from app.models import TailoredCVSchema

_NAMED_INVISIBLE_MARKERS: Dict[int, str] = {
    0x200B: "ZERO-WIDTH SPACE",
    0x200C: "ZWNJ",
    0x200D: "ZWJ",
    0x2060: "WORD JOINER",
    0xFEFF: "BOM/ZWNBSP",
    0x00AD: "SOFT HYPHEN",
    0x180E: "MONGOLIAN VOWEL SEP",
    0x200E: "LRM",
    0x200F: "RLM",
    0x202A: "LRE",
    0x202B: "RLE",
    0x202C: "PDF(bidi)",
    0x202D: "LRO",
    0x202E: "RLO",
    0x2066: "LRI",
    0x2067: "RLI",
    0x2068: "FSI",
    0x2069: "PDI",
}

_STYLE_SCRIPT_RE = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_ASCII_REPLACEMENTS = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
})
_METRIC_HINT_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|k|m|x|ans|years|\+|€|\$|£)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.IGNORECASE)
_HIDDEN_CSS_RE = re.compile(r"(?:display\s*:\s*none|opacity\s*:\s*0\b|font-size\s*:\s*0(?:px|pt|em|rem)?\b)", re.IGNORECASE)


def _marker_label(cp: int) -> Optional[str]:
    if cp in _NAMED_INVISIBLE_MARKERS:
        return _NAMED_INVISIBLE_MARKERS[cp]
    if 0xE0000 <= cp <= 0xE007F:
        return f"TAG U+{cp:X}"
    if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
        return f"VARIATION-SEL U+{cp:X}"
    return None


def _mask_style_script(text: str) -> tuple[str, List[str]]:
    masks: List[str] = []

    def _repl(match: "re.Match[str]") -> str:
        token = f"__CLEAN_MARKERS_MASK_{len(masks)}__"
        masks.append(match.group(0))
        return token

    return _STYLE_SCRIPT_RE.sub(_repl, text), masks


def _restore_style_script(text: str, masks: List[str]) -> str:
    return re.sub(r"__CLEAN_MARKERS_MASK_(\d+)__", lambda m: masks[int(m.group(1))], text)


def scan_invisible_markers(text: str) -> Dict[str, int]:
    """Count hidden Unicode characters (ZWSP, bidi controls, soft hyphens, tag chars)."""
    if not text:
        return {}
    masked, _ = _mask_style_script(text) if "<" in text else (text, [])
    counts: Dict[str, int] = {}
    for ch in masked:
        lbl = _marker_label(ord(ch))
        if lbl:
            counts[lbl] = counts.get(lbl, 0) + 1
    return counts


def clean_invisible_markers(text: str, ascii_punctuation: bool = False) -> str:
    """Strip invisible Unicode characters while preserving CSS/JS blocks in HTML."""
    if not text:
        return text
    has_markup = "<" in text and ">" in text
    masked, masks = _mask_style_script(text) if has_markup else (text, [])
    cleaned = "".join(ch for ch in masked if _marker_label(ord(ch)) is None)
    if ascii_punctuation:
        cleaned = cleaned.translate(_ASCII_REPLACEMENTS).replace("\u2026", "...")
    return _restore_style_script(cleaned, masks) if masks else cleaned


def _clean_nested(obj: Any) -> Any:
    if isinstance(obj, str):
        return clean_invisible_markers(obj)
    if isinstance(obj, list):
        return [_clean_nested(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _clean_nested(v) for k, v in obj.items()}
    return obj


def clean_tailored_cv_markers(cv: TailoredCVSchema) -> TailoredCVSchema:
    """Return a copy of TailoredCVSchema stripped of any invisible Unicode markers."""
    return TailoredCVSchema(**_clean_nested(cv.model_dump()))


def _collect_cv_text(content: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    parts: List[str] = [
        str(candidate.get("full_name") or ""),
        str(candidate.get("email") or ""),
        str(candidate.get("phone") or ""),
        str(candidate.get("location") or ""),
        str(content.get("target_role_title") or ""),
        str(content.get("professional_summary") or ""),
    ]
    for grp in content.get("prioritized_skills") or []:
        if isinstance(grp, dict):
            parts.append(str(grp.get("category") or ""))
            parts.extend(str(s) for s in grp.get("skills") or [])
    for exp in content.get("experiences") or []:
        if isinstance(exp, dict):
            parts.extend([str(exp.get("title") or ""), str(exp.get("company") or "")])
            parts.extend(str(b) for b in exp.get("bullet_points") or [])
            parts.extend(str(t) for t in exp.get("relevant_technologies") or [])
    for proj in content.get("featured_projects") or []:
        if isinstance(proj, dict):
            parts.extend([str(proj.get("name") or ""), str(proj.get("description") or "")])
            parts.extend(str(t) for t in proj.get("technologies") or [])
    for edu in content.get("education") or []:
        if isinstance(edu, dict):
            parts.extend([str(edu.get("degree") or ""), str(edu.get("institution") or "")])
    parts.extend(str(c) for c in content.get("certifications") or [])
    for lang in content.get("languages") or []:
        if isinstance(lang, dict):
            parts.append(f"{lang.get('language', '')} {lang.get('level', '')}")
    return "\n".join(p.strip() for p in parts if p and p.strip())


def export_cv_ats_plain_text(
    tailored_content: Dict[str, Any],
    candidate: Dict[str, Any],
    fmt: Literal["markdown", "txt"] = "markdown",
) -> str:
    """Render a clean, single-column ATS-safe Markdown or plain text CV without invisible characters."""
    is_md = fmt == "markdown"
    h1 = "# " if is_md else ""
    h2 = "## " if is_md else ""
    h3 = "### " if is_md else ""

    lines: List[str] = []
    name = (candidate.get("full_name") or "Candidat").strip()
    role = (tailored_content.get("target_role_title") or "").strip()
    header = f"{name} — {role}" if role else name
    lines.append(f"{h1}{header}" if is_md else header.upper())

    contact_bits = [
        str(candidate.get(k) or "").strip()
        for k in ("email", "phone", "location", "linkedin_url", "github_url", "website_url")
        if candidate.get(k)
    ]
    if contact_bits:
        lines.append(" | ".join(contact_bits))

    summary = (tailored_content.get("professional_summary") or "").strip()
    if summary:
        lines.extend(["", f"{h2}PROFIL PROFESSIONNEL" if not is_md else f"{h2}Profil professionnel", summary])

    skills = tailored_content.get("prioritized_skills") or []
    if skills:
        lines.extend(["", f"{h2}COMPÉTENCES" if not is_md else f"{h2}Compétences"])
        for grp in skills:
            if isinstance(grp, dict) and grp.get("skills"):
                cat = (grp.get("category") or "Compétences").strip()
                items = ", ".join(str(s).strip() for s in grp["skills"] if str(s).strip())
                lines.append(f"- {cat}: {items}")

    experiences = tailored_content.get("experiences") or []
    if experiences:
        lines.extend(["", f"{h2}EXPÉRIENCES PROFESSIONNELLES" if not is_md else f"{h2}Expériences professionnelles"])
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
            period = f"{exp.get('start_date', '')} - {exp.get('end_date') or 'Présent'}".strip(" -")
            lines.append("")
            lines.append(f"{h3}{exp.get('title', '')} — {exp.get('company', '')} ({period})")
            for bullet in exp.get("bullet_points") or []:
                if str(bullet).strip():
                    lines.append(f"- {str(bullet).strip()}")
            techs = [str(t).strip() for t in (exp.get("relevant_technologies") or []) if str(t).strip()]
            if techs:
                lines.append(f"  Technologies: {', '.join(techs)}")

    projects = tailored_content.get("featured_projects") or []
    if projects:
        lines.extend(["", f"{h2}PROJETS" if not is_md else f"{h2}Projets"])
        for proj in projects:
            if isinstance(proj, dict) and proj.get("name"):
                desc = (proj.get("description") or "").strip()
                lines.append(f"- {proj['name']}: {desc}" if desc else f"- {proj['name']}")

    education = tailored_content.get("education") or []
    if education:
        lines.extend(["", f"{h2}FORMATION" if not is_md else f"{h2}Formation"])
        for edu in education:
            if isinstance(edu, dict):
                lines.append(f"- {edu.get('degree', '')} — {edu.get('institution', '')} ({edu.get('year', '')})")

    certs = [str(c).strip() for c in (tailored_content.get("certifications") or []) if str(c).strip()]
    if certs:
        lines.extend(["", f"{h2}CERTIFICATIONS" if not is_md else f"{h2}Certifications"])
        for cert in certs:
            lines.append(f"- {cert}")

    langs = tailored_content.get("languages") or []
    if langs:
        lines.extend(["", f"{h2}LANGUES" if not is_md else f"{h2}Langues"])
        lang_labels = [
            f"{l.get('language', '')} ({l.get('level', '')})"
            for l in langs
            if isinstance(l, dict) and l.get("language")
        ]
        if lang_labels:
            lines.append(", ".join(lang_labels))

    raw_export = "\n".join(lines).strip() + "\n"
    return clean_invisible_markers(raw_export)


def score_cv_ats_friendliness(
    tailored_content: Dict[str, Any],
    candidate: Dict[str, Any],
    target_keywords: Optional[List[str]] = None,
    html_content: Optional[str] = None,
) -> Dict[str, Any]:
    """Deterministically score a CV's ATS parseability (0-100), issues, markers, and optional keyword coverage."""
    issues: List[str] = []
    full_text = _collect_cv_text(tailored_content, candidate)
    visible_text = (
        re.sub(r"\s+", " ", _HTML_TAG_RE.sub(" ", _STYLE_SCRIPT_RE.sub(" ", html_content))).strip()
        if html_content
        else full_text
    )

    # 1. Selectable text (15 pts)
    char_count = len(visible_text)
    if char_count >= 300:
        text_score = 15
    elif char_count >= 150:
        text_score = 8
        issues.append(f"Contenu textuel court ({char_count} caractères) : vise au moins 300 caractères.")
    else:
        text_score = 0
        issues.append(f"Contenu textuel insuffisant ({char_count} caractères) pour un parseur ATS.")

    # 2. Recognizable sections (20 pts)
    section_score = 0
    if (tailored_content.get("professional_summary") or "").strip():
        section_score += 5
    else:
        issues.append("Résumé professionnel manquant.")
    experiences = tailored_content.get("experiences") or []
    if experiences:
        section_score += 6
    else:
        issues.append("Aucune expérience professionnelle renseignée.")
    if tailored_content.get("prioritized_skills"):
        section_score += 5
    else:
        issues.append("Section compétences absente.")
    if tailored_content.get("education") or tailored_content.get("certifications") or tailored_content.get("languages"):
        section_score += 4
    else:
        issues.append("Formation, certifications ou langues absentes.")

    # 3. Reachable contact details (15 pts)
    contact_score = 0
    email = str(candidate.get("email") or "")
    if _EMAIL_RE.search(email) or _EMAIL_RE.search(full_text):
        contact_score += 10
    else:
        issues.append("Adresse e-mail valide introuvable.")
    if candidate.get("phone") or candidate.get("linkedin_url") or candidate.get("github_url"):
        contact_score += 5
    else:
        issues.append("Téléphone ou lien LinkedIn/GitHub absent.")

    # 4. Layout & hierarchy (20 pts)
    layout_score = 20
    if not (tailored_content.get("target_role_title") or "").strip():
        layout_score -= 5
        issues.append("Titre du poste visé absent.")
    if html_content:
        if re.search(r"<table\b", html_content, re.IGNORECASE):
            layout_score -= 10
            issues.append("Tableaux HTML détectés : risque de mauvaise lecture par les ATS.")
        if re.search(r"column-count\s*:\s*[2-9]", html_content, re.IGNORECASE):
            layout_score -= 5
            issues.append("Colonnes CSS multiples détectées.")
    layout_score = max(0, layout_score)

    # 5. Bullets & measurable impact (15 pts)
    all_bullets = [
        str(b).strip()
        for exp in experiences
        if isinstance(exp, dict)
        for b in (exp.get("bullet_points") or [])
        if str(b).strip()
    ]
    bullets_score = 0
    if all_bullets:
        bullets_score += 10
        if any(len(b) > 400 for b in all_bullets):
            bullets_score -= 3
            issues.append("Certaines puces dépassent 400 caractères : privilégie des puces concises.")
        if any(_METRIC_HINT_RE.search(b) for b in all_bullets):
            bullets_score += 5
        else:
            issues.append("Aucune métrique chiffrée détectée dans les puces d'expérience.")
    else:
        issues.append("Aucune puce d'expérience détectée.")

    # 6. Charset & invisible Unicode markers (15 pts)
    markers_found = scan_invisible_markers(full_text)
    if html_content:
        for lbl, cnt in scan_invisible_markers(html_content).items():
            markers_found[lbl] = max(markers_found.get(lbl, 0), cnt)
    markers_score = 15
    if markers_found:
        markers_score -= 10
        issues.append(f"Caractères Unicode invisibles détectés : {', '.join(sorted(markers_found))}.")
    if html_content:
        if "utf-8" not in html_content.lower():
            markers_score -= 5
            issues.append("Déclaration charset UTF-8 absente du HTML.")
        if _HIDDEN_CSS_RE.search(html_content):
            markers_score -= 5
            issues.append("Texte potentiellement masqué en CSS (display:none / opacity:0 / font-size:0).")
    markers_score = max(0, markers_score)

    total = text_score + section_score + contact_score + layout_score + bullets_score + markers_score
    grade = "A" if total >= 90 else "B" if total >= 75 else "C" if total >= 60 else "D"

    result: Dict[str, Any] = {
        "score": total,
        "grade": grade,
        "breakdown": {
            "text": text_score,
            "sections": section_score,
            "contact": contact_score,
            "layout": layout_score,
            "metrics_and_bullets": bullets_score,
            "charset_and_markers": markers_score,
        },
        "issues": issues,
        "invisible_markers": markers_found,
        "keyword_coverage": None,
    }

    if target_keywords:
        lower_text = full_text.lower()
        clean_kws = [str(kw).strip() for kw in target_keywords if str(kw).strip()]
        unique_kws = list(dict.fromkeys(clean_kws))
        matched = [kw for kw in unique_kws if kw.lower() in lower_text]
        missing = [kw for kw in unique_kws if kw.lower() not in lower_text]
        coverage_pct = round(100.0 * len(matched) / len(unique_kws), 1) if unique_kws else 100.0
        result["keyword_coverage"] = {
            "matched": matched,
            "missing": missing,
            "coverage_pct": coverage_pct,
        }

    return result
