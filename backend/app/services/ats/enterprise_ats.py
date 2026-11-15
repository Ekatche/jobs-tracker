"""Enterprise ATS extractors (Ashby posting API and Workday CXS JSON endpoint)."""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.services.ats.common import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    ExpiredOfferError,
    _is_safe_segment,
    clean_html_to_text,
    normalize_employment_type,
)

logger = logging.getLogger(__name__)

_WORKDAY_HOST_RE = re.compile(r"^(?P<tenant>[A-Za-z0-9-]+)\.(?P<shard>wd\d+)\.myworkdayjobs\.com$", re.IGNORECASE)
_LOCALE_SEGMENT_RE = re.compile(r"^[a-z]{2}(?:-[A-Za-z]{2})?$")


def _ashby_remote_policy(job: Dict[str, Any]) -> str:
    workplace = str(job.get("workplaceType") or "").strip().lower()
    if workplace == "remote":
        return "Full Remote"
    if workplace == "hybrid":
        return "Hybride"
    if workplace == "onsite":
        return "Présentiel"
    if job.get("isRemote") is True:
        return "Full Remote"
    if job.get("isRemote") is False:
        return "Présentiel"
    return "Non spécifié"


def _ashby_salary(job: Dict[str, Any]) -> str:
    comp = job.get("compensation")
    if not isinstance(comp, dict):
        return "Non spécifié"
    tier_summary = comp.get("compensationTierSummary")
    if isinstance(tier_summary, str) and tier_summary.strip():
        return tier_summary.strip()
    parts: List[str] = []
    for item in comp.get("summaryComponents") or []:
        if not isinstance(item, dict):
            continue
        label = item.get("label") or item.get("compensationType") or ""
        min_v, max_v = item.get("minValue"), item.get("maxValue")
        curr = item.get("currencyCode") or ""
        if min_v is not None and max_v is not None:
            parts.append(f"{label}: {min_v}-{max_v} {curr}".strip())
    return "; ".join(parts) if parts else "Non spécifié"


async def extract_ashby_job(url: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """Extract an Ashby job offer via the zero-token public posting API."""
    try:
        parsed = urlparse(url)
        if "ashbyhq.com" not in parsed.netloc.lower():
            return None
        segments = [p for p in parsed.path.split("/") if p]
        if len(segments) < 2:
            return None
        org, job_id = segments[0], segments[1]
        if not (_is_safe_segment(org) and _is_safe_segment(job_id)):
            return None

        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true"
        resp = await client.get(api_url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        if resp.status_code in (404, 410):
            raise ExpiredOfferError(f"Ashby board {org} introuvable ({resp.status_code})")
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            return None
        job = next(
            (
                j for j in data["jobs"]
                if isinstance(j, dict)
                and (str(j.get("id")) == job_id or str(j.get("jobUrl") or "").rstrip("/").endswith(f"/{job_id}"))
            ),
            None,
        )
        if not job or job.get("isListed") is False:
            raise ExpiredOfferError(f"Ashby offre {job_id} expirée ou non listée")

        desc_html = job.get("descriptionHtml") or ""
        description = clean_html_to_text(desc_html) if desc_html else (job.get("descriptionPlain") or "").strip()
        if not description or description == "Non spécifié":
            return None

        company_name = ((data.get("organization") or {}).get("name") or org.replace("-", " ").title()).strip()
        return {
            "poste": str(job.get("title") or "").strip() or "Non spécifié",
            "entreprise": company_name,
            "description": description,
            "localisation": str(job.get("location") or "Non spécifié").strip(),
            "type_contrat": normalize_employment_type(job.get("employmentType")),
            "politique_teletravail": _ashby_remote_policy(job),
            "salaire": _ashby_salary(job),
            "date_publication": job.get("publishedAt"),
            "url": url,
            "ats_platform": "ashby",
            "source_record": job,
        }
    except ExpiredOfferError:
        raise
    except Exception as e:
        logger.debug(f"Échec Ashby API pour {url}: {e}")
        return None


async def extract_workday_job(url: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """Extract a Workday job offer via the CXS JSON endpoint."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        host_match = _WORKDAY_HOST_RE.match(host)
        if not host_match:
            return None
        tenant = host_match.group("tenant")
        segments = [p for p in parsed.path.split("/") if p]
        if segments and _LOCALE_SEGMENT_RE.match(segments[0]):
            segments = segments[1:]
        if len(segments) < 3 or segments[1].lower() not in ("job", "details"):
            return None
        site, job_segments = segments[0], segments[2:]
        if not (_is_safe_segment(site) and all(_is_safe_segment(s) for s in job_segments)):
            return None

        api_url = f"https://{host}/wday/cxs/{tenant}/{site}/job/{'/'.join(job_segments)}"
        resp = await client.get(api_url, headers={**DEFAULT_HEADERS, "Accept": "application/json"}, timeout=DEFAULT_TIMEOUT)
        if resp.status_code in (404, 410):
            raise ExpiredOfferError(f"Workday offre expirée ({resp.status_code})")
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not isinstance(data, dict) or not isinstance(data.get("jobPostingInfo"), dict):
            return None
        info = data["jobPostingInfo"]
        raw_desc = info.get("jobDescription") or ""
        cleaned = clean_html_to_text(raw_desc) if raw_desc else ""
        if (not cleaned or cleaned == "Non spécifié") and info.get("canApply") is False:
            raise ExpiredOfferError("Workday offre fermée (canApply=False)")
        if not cleaned or cleaned == "Non spécifié":
            return None

        remote_raw = str(info.get("remoteType") or "").lower()
        remote_policy = "Full Remote" if "remote" in remote_raw else ("Hybride" if "hybrid" in remote_raw else "Non spécifié")
        return {
            "poste": str(info.get("title") or "").strip() or "Non spécifié",
            "entreprise": tenant.replace("-", " ").title(),
            "description": cleaned,
            "localisation": str(info.get("location") or "Non spécifié").strip(),
            "type_contrat": normalize_employment_type(info.get("timeType")),
            "politique_teletravail": remote_policy,
            "salaire": "Non spécifié",
            "date_publication": info.get("startDate"),
            "url": url,
            "ats_platform": "workday",
            "source_record": data,
        }
    except ExpiredOfferError:
        raise
    except Exception as e:
        logger.debug(f"Échec Workday CXS API pour {url}: {e}")
        return None
