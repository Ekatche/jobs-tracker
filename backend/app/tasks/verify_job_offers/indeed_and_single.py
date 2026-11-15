"""Indeed GraphQL batch verifier and two-level single-offer dispatcher."""

import asyncio
import json
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import httpx

INDEED_GRAPHQL_URL = "https://apis.indeed.com/graphql"
INDEED_JOB_KEY_RE = re.compile(r"^[0-9a-f]{16}$")


def extract_indeed_job_key(url: str) -> Optional[str]:
    """Extract the 16-char hex `jk` job key from an indeed.* URL, or None."""
    parsed = urlparse(url or "")
    if "indeed" not in (parsed.hostname or "").split("."):
        return None
    jk = (parse_qs(parsed.query).get("jk") or [""])[0].lower()
    return jk if INDEED_JOB_KEY_RE.match(jk) else None


def _map_indeed_batch_verdicts(batch: List[str], jobs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    verdicts: Dict[str, Dict[str, Any]] = {}
    for key in batch:
        job = jobs.get(key)
        if job is None:
            verdicts[key] = {"status": "unknown", "is_valid": None, "reason": "indeed_api_job_not_found"}
        elif job.get("expired"):
            verdicts[key] = {"status": "closed", "is_valid": False, "reason": "indeed_api_expired"}
        else:
            verdicts[key] = {"status": "valid", "is_valid": True, "reason": "indeed_api_active"}
    return verdicts


async def check_indeed_jobs(
    job_keys: List[str], client: httpx.AsyncClient, batch_size: int = 50
) -> Dict[str, Dict[str, Any]]:
    """
    Check Indeed job status via the mobile GraphQL API in batches.
    Failed batches yield no verdicts; missing keys remain unknown.
    """
    pkg = sys.modules["app.tasks.verify_job_offers"]
    if not job_keys:
        return {}
    try:
        from jobspy.indeed.constant import headers as indeed_api_headers
    except ImportError:
        pkg.logger.warning("jobspy introuvable : vérification Indeed par l'API ignorée.")
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    for start in range(0, len(job_keys), batch_size):
        batch = job_keys[start : start + batch_size]
        query = f"query {{ jobData(jobKeys: {json.dumps(batch)}) {{ results {{ job {{ key expired }} }} }} }}"
        try:
            response = await client.post(
                INDEED_GRAPHQL_URL, json={"query": query}, headers=indeed_api_headers
            )
            payload = response.json() if response.status_code == 200 else {}
            if payload.get("errors") or "data" not in payload:
                raise ValueError(f"HTTP {response.status_code}, errors={payload.get('errors')}")
            jobs = {
                item["job"]["key"]: item["job"]
                for item in payload["data"]["jobData"]["results"]
                if item.get("job")
            }
        except Exception as e:
            pkg.logger.warning(f"⚠️ API Indeed en échec sur un lot de {len(batch)} offres : {e}")
            continue
        results.update(_map_indeed_batch_verdicts(batch, jobs))
    return results


async def verify_single_offer(
    offer: Dict[str, Any],
    semaphore: asyncio.Semaphore,
    http_client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Verify one offer using level-1 HTTP followed by optional level-2 headless JS rendering.
    """
    pkg = sys.modules["app.tasks.verify_job_offers"]
    offer_id = str(offer.get("_id", ""))
    url = offer.get("url") or offer.get("source_url")

    if not url:
        return {
            "offer_id": offer_id,
            "status": "closed",
            "is_valid": False,
            "reason": "missing_url",
            "url": None,
        }

    fast_result = await pkg.check_url_http_fast(url, client=http_client)

    if fast_result.get("status") == "unknown" or fast_result.get("valid") is None:
        return {
            "offer_id": offer_id,
            "status": "unknown",
            "is_valid": None,
            "reason": fast_result["reason"],
            "url": url,
        }
    if fast_result.get("status") == "closed" or fast_result.get("valid") is False:
        return {
            "offer_id": offer_id,
            "status": "closed",
            "is_valid": False,
            "reason": fast_result["reason"],
            "url": url,
        }

    host_labels = (urlparse(url).hostname or "").split(".")

    # HelloWork renders closure server-side; HTTP 200 without closure banner avoids headless timeout
    if "hellowork" in host_labels and fast_result.get("status_code") == 200:
        return {
            "offer_id": offer_id,
            "status": "valid",
            "is_valid": True,
            "reason": "static_render_domain_ok",
            "url": url,
        }

    # Indeed returns HTTP 401 Cloudflare or times out in headless browser
    if "indeed" in host_labels:
        return {
            "offer_id": offer_id,
            "status": "unknown",
            "is_valid": None,
            "reason": "headless_skipped_antibot_domain",
            "url": url,
        }

    if fast_result.get("requires_js_check", True):
        async with semaphore:
            js_result = await pkg.check_url_headless_js(url)
            return {
                "offer_id": offer_id,
                "status": js_result.get("status", "valid"),
                "is_valid": js_result.get("valid"),
                "reason": js_result.get("reason", "unknown"),
                "url": url,
            }

    return {
        "offer_id": offer_id,
        "status": "valid",
        "is_valid": True,
        "reason": fast_result["reason"],
        "url": url,
    }
