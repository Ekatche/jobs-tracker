"""Shared HTTP defaults, HTML cleaning, contract normalization, and curl_cffi helper."""

import html
import logging
import re
from typing import Any, Optional

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

_SAFE_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class ExpiredOfferError(Exception):
    """L'ATS confirme que l'offre n'existe plus : aucun crawl de repli ne doit être tenté."""


def _is_safe_segment(segment: str) -> bool:
    return bool(segment and ".." not in segment and _SAFE_PATH_SEGMENT_RE.match(segment))


def clean_html_to_text(raw_html: str) -> str:
    """Convertit du HTML brut (ou encodé en entités) en texte lisible avec retours à la ligne propres."""
    if not raw_html:
        return "Non spécifié"
    text = raw_html
    # Déséchapper au préalable pour que les balises encodées (&lt;p&gt;) soient traitées par le regex
    for _ in range(2):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped

    text = re.sub(r"<(script|style|svg)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|h[1-6]|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip() or "Non spécifié"


def normalize_employment_type(emp_type: Any) -> str:
    """Normalise les types de contrats standards (schema.org et ATS) en français."""
    if not emp_type:
        return "Non spécifié"
    raw = str(emp_type).upper().replace("-", "_").replace(" ", "_")
    if "FULL_TIME" in raw or "FULLTIME" in raw or "CDI" in raw or "PERMANENT" in raw:
        return "CDI"
    if "PART_TIME" in raw or "PARTTIME" in raw:
        return "Temps partiel"
    if "CONTRACT" in raw or "CDD" in raw or "TEMPORARY" in raw:
        return "CDD"
    if "INTERN" in raw or "STAGE" in raw:
        return "Stage"
    if "APPRENTICE" in raw or "ALTERNANCE" in raw:
        return "Alternance"
    if "FREELANCE" in raw or "CONTRACTOR" in raw:
        return "Freelance"
    return str(emp_type).strip()


def _fetch_with_curl_cffi(url: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[tuple[int, str]]:
    """Fetch direct avec curl_cffi pour contourner les protections Cloudflare (ex: Cadremploi)."""
    if curl_requests is None:
        return None
    try:
        r = curl_requests.get(
            url,
            headers={
                "User-Agent": DEFAULT_HEADERS["User-Agent"],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            impersonate="chrome124",
            timeout=timeout,
        )
        return r.status_code, r.text
    except Exception as e:
        logger.debug(f"curl_cffi fetch error for {url}: {e}")
        return None
