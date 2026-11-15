"""Non-content page marker detection and SmartRecruiters board status guard."""

import html
import logging
import re
from typing import Any, Dict, Literal, Optional

from app.services.ats.common import ExpiredOfferError

logger = logging.getLogger(__name__)

_SUBSTANTIVE_JD_RE = re.compile(
    r"\b(?:missions|responsibilities|qualifications|profil\s+recherché|requirements)\b",
    re.IGNORECASE,
)
_NON_CONTENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "404-shell",
        re.compile(
            r"(?:job|offre|page|position|role)\s+(?:not\s+found|introuvable|n['’]existe\s+plus"
            r"|no\s+longer\s+available|expired|closed|clôturée|fermée)"
            r"|404\s+not\s+found|this\s+job\s+is\s+no\s+longer\s+open",
            re.IGNORECASE,
        ),
    ),
    (
        "login-wall",
        re.compile(
            r"sign\s+in\s+to\s+(?:view|continue|apply)|log\s+in\s+to\s+continue"
            r"|connexion\s+requise|connectez-vous\s+pour\s+accéder|please\s+log\s+in",
            re.IGNORECASE,
        ),
    ),
    (
        "paywall",
        re.compile(
            r"subscribe\s+to\s+(?:read|continue|unlock)|abonnez-vous\s+pour\s+lire"
            r"|contenu\s+réservé\s+aux\s+abonnés|paywall",
            re.IGNORECASE,
        ),
    ),
    (
        "js-required",
        re.compile(
            r"enable\s+javascript\s+and\s+cookies|you\s+need\s+to\s+enable\s+javascript"
            r"|javascript\s+is\s+required|veuillez\s+activer\s+javascript",
            re.IGNORECASE,
        ),
    ),
)


def detect_non_content_marker(text: str) -> Optional[Dict[str, str]]:
    """Detect login walls, 404 shells, paywalls, and JS-required blockers while avoiding long-JD false positives."""
    if not text or not text.strip():
        return None
    stripped = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    visible = re.sub(r"<[^>]+>", " ", html.unescape(stripped))
    visible = re.sub(r"\s+", " ", visible).strip()
    target = visible or text.strip()
    if len(visible) > 1200 and _SUBSTANTIVE_JD_RE.search(visible):
        return None
    for category, pattern in _NON_CONTENT_PATTERNS:
        match = pattern.search(target)
        if match:
            return {"category": category, "reason": match.group(0)}
    return None


def _check_non_content_html(raw_html: str, url: str) -> bool:
    """Raise ExpiredOfferError on 404 shells; return True when another non-content gate should halt scraping."""
    marker = detect_non_content_marker(raw_html)
    if not marker:
        return False
    if marker["category"] == "404-shell":
        raise ExpiredOfferError(f"Offre fermée détectée ({marker['reason']}): {url}")
    logger.info(f"Marqueur non-contenu ({marker['category']}) détecté pour {url}: {marker['reason']}")
    return True


def check_smartrecruiters_board_status(data: Any) -> Literal["active", "not_found"]:
    """Treat SmartRecruiters HTTP 200 empty boards (#4215) as not_found rather than empty."""
    if not isinstance(data, dict):
        return "not_found"
    content = data.get("content")
    total = data.get("totalFound", 0)
    if not isinstance(content, list) or len(content) == 0 or total == 0:
        return "not_found"
    return "active"
