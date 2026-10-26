from datetime import date
import logging
import re
from pathlib import Path
from typing import Any, Collection, Dict, List, Optional, Tuple, Union

import jinja2
from markupsafe import Markup

from app.models import TailoredCVSchema

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" / "cv"

# Registre : source unique des modèles et des couleurs (API, rendu, test de parité frontend).
CV_TEMPLATES = ("sidebar_elegance", "executive_minimalist", "classique", "creatif")
CV_TEMPLATES_WITHOUT_PHOTO: frozenset = frozenset({"classique"})
CV_ACCENTS = {
    "marine":    {"primary": "#1e3a8a", "tint": "#eef2fb", "line": "#a9b8e0"},
    "bleu_vert": {"primary": "#0f766e", "tint": "#e6f2f1", "line": "#99c9c4"},
    "ardoise":   {"primary": "#4f6d8a", "tint": "#eff3f7", "line": "#b3c3d3"},
    "sauge":     {"primary": "#4d6b4f", "tint": "#eff4ef", "line": "#b5c7b6"},
    "bordeaux":  {"primary": "#8b1e3f", "tint": "#f8eef1", "line": "#d8a9b7"},
    "graphite":  {"primary": "#374151", "tint": "#f1f2f4", "line": "#c3c7ce"},
}
DEFAULT_TEMPLATE = "sidebar_elegance"
DEFAULT_ACCENT = "marine"

# Titres de section standard (règle ATS 3), communs aux quatre modèles.
SECTION_TITLES = {
    "experience": "Expérience professionnelle",
    "skills": "Compétences",
    "education": "Formation",
    "languages": "Langues",
    "certifications": "Certifications & habilitations",
    "projects": "Projets",
    "interests": "Centres d'intérêt",
}

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)
# Markup : « & » et « ' » restent bruts, comme un titre écrit en dur dans le gabarit.
_jinja_env.globals["SECTION_TITLES"] = {key: Markup(title) for key, title in SECTION_TITLES.items()}


def _get_monogram(full_name: str) -> str:
    parts = full_name.strip().split()
    if not parts:
        return "CV"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _resolve(value: Optional[str], allowed: Collection[str], default: str, kind: str) -> str:
    """Clé du registre, ou valeur par défaut pour une clé absente ou inconnue (ancien document)."""
    key = (value or "").lower().strip()
    if key in allowed:
        return key
    if value:
        logger.warning("Unknown CV %s '%s', defaulting to '%s'", kind, value, default)
    return default


_MONTHS = {
    "janv": 1, "févr": 2, "fevr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12,
}
_ONGOING = ("présent", "present", "aujourd", "en cours", "actuel")


def _date_key(value: Optional[str]) -> Tuple[int, int]:
    """(année, mois) d'une date libre : « 2023-02 », « 02/2023 », « sept. 2021 », « 2021 ». (0, 0) si illisible."""
    text = (value or "").casefold()
    year = re.search(r"(?:19|20)\d{2}", text)
    if not year:
        return (0, 0)
    rest = text.replace(year.group(), " ", 1)
    digits = re.search(r"\b(\d{1,2})\b", rest)
    if digits and 1 <= int(digits.group(1)) <= 12:
        return (int(year.group()), int(digits.group(1)))
    return (int(year.group()), next((n for name, n in _MONTHS.items() if name in rest), 0))


def _end_key(value: Optional[str]) -> Tuple[int, int]:
    text = (value or "").casefold()
    if not text.strip() or any(word in text for word in _ONGOING):
        return (9999, 12)
    return _date_key(value)


def _month_year(value: Optional[str]) -> Optional[str]:
    """« 2023-02 », « sept. 2023 » → « 02/2023 » ; mois inconnu → « 2023 » ; « Présent », vide ou sans année : inchangé."""
    year, month = _date_key(value)
    if not year:
        return value
    return f"{month:02d}/{year}" if month else str(year)


def _format_duration(start: Optional[str], end: Optional[str]) -> Optional[str]:
    """Formate la durée d'une expérience en français (ex: '8 ans', '1 an 6 mois', '6 mois').

    Calcule la durée déterministe entre start et end. Si end est 'Présent', vide
    ou en cours, la date courante (année/mois) est utilisée.
    Retourne None si les dates sont absentes, illisibles ou incohérentes (end < start).
    """
    start_year, start_month = _date_key(start)
    if not start_year:
        return None

    end_year, end_month = _end_key(end)
    if end_year == 9999:
        today = date.today()
        end_year, end_month = today.year, today.month
    elif not end_year:
        return None

    # Si l'un des deux mois est inconnu (mois == 0), calcul sur les années entières
    if start_month == 0 or end_month == 0:
        years = end_year - start_year
        if years <= 0:
            return None
        return "1 an" if years == 1 else f"{years} ans"

    # Calcul au mois près
    total_months = (end_year - start_year) * 12 + (end_month - start_month)
    if total_months <= 0:
        return None

    years = total_months // 12
    months = total_months % 12

    if years == 0:
        return f"{months} mois"
    year_str = "1 an" if years == 1 else f"{years} ans"
    if months == 0:
        return year_str
    return f"{year_str} {months} mois"


def _with_month_year(exp: Dict[str, Any]) -> Dict[str, Any]:
    start_val = exp.get("start_date") or exp.get("start")
    end_val = exp.get("end_date") or exp.get("end")
    return {
        **exp,
        "start_date": _month_year(start_val),
        "end_date": _month_year(end_val),
        "duration": _format_duration(start_val, end_val),
    }


def _most_recent_first(experiences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ordre antéchronologique par date de début, puis de fin ; le tri stable garde l'ordre des postes non datés."""
    return sorted(
        experiences,
        key=lambda exp: (_date_key(exp.get("start_date")), _end_key(exp.get("end_date"))),
        reverse=True,
    )


def _cumulative_career_years(profile: Dict[str, Any]) -> float:
    """Durée cumulée des expériences en années, fusionnant les intervalles qui se chevauchent."""
    today = date.today()
    intervals: List[Tuple[int, int]] = []

    for exp in profile.get("experiences") or []:
        start_year, start_month = _date_key(exp.get("start") or exp.get("start_date"))
        if not start_year:
            continue
        start_val = start_year * 12 + (start_month or 1)

        end_year, end_month = _end_key(exp.get("end") or exp.get("end_date"))
        if end_year == 9999:
            end_year, end_month = today.year, today.month
        elif not end_year:
            continue
        end_val = end_year * 12 + (end_month or 12)

        if end_val >= start_val:
            intervals.append((start_val, end_val))

    if not intervals:
        return 0.0

    intervals.sort()
    merged: List[Tuple[int, int]] = [intervals[0]]
    for current_start, current_end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if current_start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, current_end))
        else:
            merged.append((current_start, current_end))

    total_months = sum(end - start for start, end in merged)
    return max(0.0, total_months / 12.0)


def _accent_css(accent: str) -> str:
    colors = CV_ACCENTS[accent]
    return (
        f":root {{ --accent: {colors['primary']}; "
        f"--accent-tint: {colors['tint']}; --accent-line: {colors['line']}; }}"
    )


def render_cv_html(
    cv: Union[TailoredCVSchema, Dict[str, Any]],
    candidate: Dict[str, Any],
    template_name: Optional[str] = DEFAULT_TEMPLATE,
    with_photo: bool = False,
    photo_url: Optional[str] = None,
    accent: Optional[str] = DEFAULT_ACCENT,
) -> str:
    """
    Render a tailored CV into a self-contained HTML page using Jinja2 and base European A4 print CSS.
    """
    cv_dict = cv.model_dump() if isinstance(cv, TailoredCVSchema) else cv
    # Copie : le dict de l'appelant (document stocké) garde son ordre et ses dates complètes.
    experiences = _most_recent_first(cv_dict.get("experiences") or [])
    cv_dict = {**cv_dict, "experiences": [_with_month_year(exp) for exp in experiences]}

    base_css_file = TEMPLATES_DIR / "base_cv.css"
    base_css = base_css_file.read_text(encoding="utf-8") if base_css_file.exists() else ""

    template_key = _resolve(template_name, CV_TEMPLATES, DEFAULT_TEMPLATE, "template")
    accent_key = _resolve(accent, CV_ACCENTS, DEFAULT_ACCENT, "accent")
    if template_key in CV_TEMPLATES_WITHOUT_PHOTO:
        with_photo = False

    template = _jinja_env.get_template(f"{template_key}.html")
    monogram = _get_monogram(candidate.get("full_name") or "CV")

    # Le bloc :root vient après base_css : @import doit rester la première règle de la feuille.
    styles = Markup(base_css + "\n" + _accent_css(accent_key))

    return template.render(
        cv=cv_dict,
        candidate=candidate,
        monogram=monogram,
        with_photo=with_photo,
        photo_url=photo_url,
        base_css=styles,
    )
