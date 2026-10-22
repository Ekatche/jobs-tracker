import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" / "letter"

_FRENCH_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]

# nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)


def format_french_date(d: Optional[date] = None) -> str:
    """Format a date into French standard letter format (e.g. '22 octobre 2026')."""
    if d is None:
        d = datetime.now(timezone.utc).date()
    day_str = "1er" if d.day == 1 else str(d.day)
    month_str = _FRENCH_MONTHS[d.month - 1]
    return f"{day_str} {month_str} {d.year}"


def _split_into_paragraphs(body: str) -> List[str]:
    """Split letter text into clean paragraphs preserving internal structure."""
    if not body:
        return []
    # Split on double linebreaks or blank lines
    chunks = re.split(r"\n\s*\n", body.strip())
    paragraphs = [c.strip() for c in chunks if c.strip()]
    return paragraphs if paragraphs else [body.strip()]


def render_letter_html(
    body: str,
    candidate: Dict[str, Any],
    company: str,
    position: str,
    location: Optional[str] = None,
    today: Optional[date] = None,
) -> str:
    """
    Render self-contained HTML for an official French cover letter with full header.
    All user-supplied content is auto-escaped by Jinja2 to prevent injection.
    """
    template = _jinja_env.get_template("letter.html")
    french_date = format_french_date(today)
    paragraphs = _split_into_paragraphs(body)

    # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
    return template.render(
        candidate=candidate,
        company=company,
        position=position,
        location=location,
        french_date=french_date,
        paragraphs=paragraphs,
    )


def slugify(text: str) -> str:
    """Normalize a text string for filenames (alphanumeric and underscores)."""
    cleaned = re.sub(r"[^\w\s-]", "", text or "").strip().lower()
    return re.sub(r"[-\s]+", "_", cleaned) or "document"


def build_candidate_info(profile_doc: Dict[str, Any], user: Any) -> Dict[str, Any]:
    """Extract and prioritize candidate contact details for the cover letter header."""
    contact_info = profile_doc.get("personal_info") or profile_doc.get("contact") or {}
    github_url = contact_info.get("github_url") or contact_info.get("github") or profile_doc.get("github_url")
    website_url = contact_info.get("website_url") or contact_info.get("website")

    # Name fallback hierarchy: contact_info full_name -> profile full_name -> user full_name -> username
    full_name = (
        contact_info.get("full_name")
        or profile_doc.get("full_name")
        or getattr(user, "full_name", None)
        or getattr(user, "username", "")
    )
    email = (
        contact_info.get("email")
        or profile_doc.get("email")
        or getattr(user, "email", "")
    )

    return {
        "full_name": full_name,
        "email": email,
        "phone": contact_info.get("phone") or profile_doc.get("phone"),
        "location": contact_info.get("location") or profile_doc.get("location"),
        "linkedin_url": contact_info.get("linkedin_url") or contact_info.get("linkedin") or profile_doc.get("linkedin_url"),
        "github_url": github_url,
        "website_url": website_url,
    }

