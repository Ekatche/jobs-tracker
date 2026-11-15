"""Zero-token ATS & Schema.org JSON-LD offer extraction router and facade."""

import asyncio
import logging
import sys
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from app.services.ats.boards_api import (
    extract_greenhouse_job,
    extract_lever_job,
    extract_smartrecruiters_job,
    extract_workable_job,
)
from app.services.ats.common import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    ExpiredOfferError,
    _fetch_with_curl_cffi,
    _is_safe_segment,
    clean_html_to_text,
    curl_requests,
    normalize_employment_type,
)
from app.services.ats.enterprise_ats import extract_ashby_job, extract_workday_job
from app.services.ats.jsonld import parse_jsonld_job_posting
from app.services.ats.non_content import (
    _check_non_content_html,
    check_smartrecruiters_board_status,
    detect_non_content_marker,
)
from app.services.ats.regional import (
    INDEED_GRAPHQL_URL,
    INDEED_JOB_QUERY,
    KNOWN_CONTRACTS,
    extract_indeed_job,
    extract_wttj_job,
)
from app.services.egress_guard import public_only_transport
from app.services.profile.urls import reject_non_public_request

__all__ = [
    "DEFAULT_HEADERS",
    "DEFAULT_TIMEOUT",
    "ExpiredOfferError",
    "INDEED_GRAPHQL_URL",
    "INDEED_JOB_QUERY",
    "KNOWN_CONTRACTS",
    "_check_non_content_html",
    "_fetch_with_curl_cffi",
    "_is_safe_segment",
    "check_smartrecruiters_board_status",
    "clean_html_to_text",
    "curl_requests",
    "detect_non_content_marker",
    "extract_ashby_job",
    "extract_ats_or_jsonld_offer",
    "extract_greenhouse_job",
    "extract_indeed_job",
    "extract_lever_job",
    "extract_smartrecruiters_job",
    "extract_workable_job",
    "extract_workday_job",
    "extract_wttj_job",
    "normalize_employment_type",
    "parse_jsonld_job_posting",
]

logger = logging.getLogger(__name__)

_API_EXTRACTORS: tuple[tuple[str, str, str], ...] = (
    ("greenhouse.io", "Greenhouse", "extract_greenhouse_job"),
    ("lever.co", "Lever", "extract_lever_job"),
    ("workable.com", "Workable", "extract_workable_job"),
    ("smartrecruiters.com", "SmartRecruiters", "extract_smartrecruiters_job"),
    ("indeed.", "Indeed", "extract_indeed_job"),
    ("welcometothejungle.", "WTTJ", "extract_wttj_job"),
    ("ashbyhq.com", "Ashby", "extract_ashby_job"),
    ("myworkdayjobs.com", "Workday", "extract_workday_job"),
)

_JSONLD_PLATFORM_HINTS: tuple[tuple[str, str], ...] = (
    ("ashbyhq.com", "ashby"),
    ("hellowork.com", "hellowork"),
    ("jobteaser.com", "jobteaser"),
    ("francetravail.fr", "francetravail"),
)


async def _try_curl_jsonld_fallback(
    url: str,
    platform_override: Optional[str] = None,
    log_label: str = "JSON-LD via curl_cffi",
) -> Optional[Dict[str, Any]]:
    """Fetch Cloudflare-protected HTML via curl_cffi and extract Schema.org JSON-LD."""
    router_mod = sys.modules[__name__]
    curl_res = await asyncio.to_thread(router_mod._fetch_with_curl_cffi, url)
    if not curl_res:
        return None
    status_code, raw_html = curl_res
    lower_html = raw_html.lower()
    if status_code in (404, 410) or "cette offre est expirée" in lower_html or "plus disponible" in lower_html:
        raise ExpiredOfferError(url)
    if status_code == 200:
        result = parse_jsonld_job_posting(raw_html, url)
        if result:
            if platform_override:
                result["ats_platform"] = platform_override
            logger.info(f"⚡ Extraction Zero-Token réussie ({log_label}): {result['poste']} - {result['entreprise']}")
            return result
        _check_non_content_html(raw_html, url)
    return None


async def extract_ats_or_jsonld_offer(
    url: str, client: Optional[httpx.AsyncClient] = None
) -> Optional[Dict[str, Any]]:
    """Tente une extraction Zero-Token directe via les APIs d'ATS ou Schema.org JSON-LD."""
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return None

    close_client = False
    if client is None:
        # URL éventuellement saisie par l'utilisateur : chaque saut doit rester public (SSRF)
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=DEFAULT_TIMEOUT,
            event_hooks={"request": [reject_non_public_request]},
            transport=public_only_transport(),
        )
        close_client = True

    router_mod = sys.modules[__name__]
    try:
        domain = urlparse(url).netloc.lower()
        for domain_needle, label, fn_name in _API_EXTRACTORS:
            if domain_needle in domain:
                result = await getattr(router_mod, fn_name)(url, client)
                if result:
                    logger.info(f"⚡ Extraction Zero-Token réussie ({label}): {result['poste']} - {result['entreprise']}")
                    return result

        if "cadremploi.fr" in domain:
            return await _try_curl_jsonld_fallback(url, platform_override="cadremploi", log_label="Cadremploi")

        resp = await client.get(url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            jsonld_result = parse_jsonld_job_posting(resp.text, url)
            if jsonld_result:
                for needle, platform in _JSONLD_PLATFORM_HINTS:
                    if needle in domain:
                        jsonld_result["ats_platform"] = platform
                        break
                logger.info(
                    f"⚡ Extraction Zero-Token réussie (JSON-LD/{jsonld_result.get('ats_platform', 'web')}): "
                    f"{jsonld_result['poste']} - {jsonld_result['entreprise']}"
                )
                return jsonld_result
            if _check_non_content_html(resp.text, url):
                return None
        elif resp.status_code in (403, 503):
            return await _try_curl_jsonld_fallback(url)

    except ExpiredOfferError:
        raise
    except Exception as e:
        logger.debug(f"Extraction Zero-Token non concluante pour {url}: {e}")
    finally:
        if close_client:
            await client.aclose()

    return None
