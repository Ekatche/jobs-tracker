import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import jinja2

from app.models import TailoredCVSchema

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" / "cv"

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)


def _get_monogram(full_name: str) -> str:
    parts = full_name.strip().split()
    if not parts:
        return "CV"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def render_cv_html(
    cv: Union[TailoredCVSchema, Dict[str, Any]],
    candidate: Dict[str, Any],
    template_name: str = "sidebar_elegance",
    with_photo: bool = False,
    photo_url: Optional[str] = None,
) -> str:
    """
    Render a tailored CV into a self-contained HTML page using Jinja2 and base European A4 print CSS.
    """
    # Normalize CV schema to dict or pydantic model
    cv_dict = cv.model_dump() if isinstance(cv, TailoredCVSchema) else cv

    # Load base stylesheet
    base_css_file = TEMPLATES_DIR / "base_cv.css"
    base_css = base_css_file.read_text(encoding="utf-8") if base_css_file.exists() else ""

    # Select template
    normalized_template = template_name.lower().strip()
    if normalized_template not in ["sidebar_elegance", "executive_minimalist"]:
        logger.warning(f"Unknown template '{template_name}', defaulting to 'sidebar_elegance'")
        normalized_template = "sidebar_elegance"

    template = _jinja_env.get_template(f"{normalized_template}.html")

    monogram = _get_monogram(candidate.get("full_name", "CV"))

    rendered = template.render(
        cv=cv_dict,
        candidate=candidate,
        monogram=monogram,
        with_photo=with_photo,
        photo_url=photo_url,
        base_css=base_css,
    )
    return rendered
