"""Regional job board extractors (Indeed mobile GraphQL and Welcome to the Jungle REST)."""

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from app.services.ats.common import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    ExpiredOfferError,
    clean_html_to_text,
    normalize_employment_type,
)

logger = logging.getLogger(__name__)

INDEED_GRAPHQL_URL = "https://apis.indeed.com/graphql"
INDEED_JOB_QUERY = """query {{ jobData(jobKeys: ["{key}"]) {{ results {{ job {{
  key title description {{ html }}
  location {{ city formatted {{ short }} }}
  employer {{ name }}
  attributes {{ label }}
}} }} }} }}"""
KNOWN_CONTRACTS = {"CDI", "CDD", "Stage", "Alternance", "Freelance", "Temps partiel"}


async def extract_indeed_job(
    url: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Extrait une offre Indeed via l'API GraphQL de l'app mobile (celle qu'utilise jobspy)."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    job_key = (params.get("jk") or params.get("vjk") or [None])[0]
    if not job_key or not re.fullmatch(r"[a-f0-9]+", job_key):
        return None

    try:
        from jobspy.indeed.constant import api_headers
    except ImportError:
        try:
            from jobspy.indeed.constant import headers as api_headers
        except ImportError:
            api_headers = {}

    headers = dict(api_headers)
    subdomain = parsed.netloc.lower().split(".")[0]
    if len(subdomain) == 2:
        headers["indeed-co"] = subdomain.upper()

    try:
        resp = await client.post(
            INDEED_GRAPHQL_URL,
            headers=headers,
            json={"query": INDEED_JOB_QUERY.format(key=job_key)},
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code != 200:
            return None

        results = ((resp.json().get("data") or {}).get("jobData") or {}).get("results") or []
        job = results[0].get("job") if results else None
        if not job or not job.get("title"):
            return None

        location = job.get("location") or {}
        labels = [a.get("label") for a in job.get("attributes") or [] if a.get("label")]
        contracts = [normalize_employment_type(label) for label in labels]
        contract = next((c for c in contracts if c in KNOWN_CONTRACTS), "Non spécifié")

        return {
            "poste": job["title"].strip(),
            "entreprise": ((job.get("employer") or {}).get("name") or "Non spécifié").strip(),
            "description": clean_html_to_text((job.get("description") or {}).get("html", "")),
            "localisation": (location.get("formatted") or {}).get("short") or location.get("city") or "Non spécifié",
            "type_contrat": contract,
            "url": url,
            "ats_platform": "indeed",
            "source_record": job,
        }
    except Exception as e:
        logger.debug(f"Échec parsing Indeed GraphQL pour {url}: {e}")
        return None


async def extract_wttj_job(
    url: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Extrait une offre Welcome to the Jungle via son API publique REST api.welcometothejungle.com."""
    match = re.search(
        r"welcometothejungle\.(?:com|fr)/(?:[a-z]{2}/)?companies/([^/]+)/jobs/([^/?#]+)",
        url,
    )
    if not match:
        return None

    org_slug, job_slug = match.group(1), match.group(2)
    api_url = f"https://api.welcometothejungle.com/api/v1/organizations/{org_slug}/jobs/{job_slug}"

    try:
        resp = await client.get(
            api_url,
            headers={"User-Agent": DEFAULT_HEADERS["User-Agent"], "Accept": "application/json"},
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code in (404, 410):
            raise ExpiredOfferError(url)
        if resp.status_code != 200:
            return None

        data = resp.json()
        job = data.get("job") or data
        title = job.get("name")
        if not title:
            return None

        org_data = job.get("organization") or {}
        company = org_data.get("name") or org_slug.replace("-", " ").title()
        office = job.get("office") or {}
        location = (
            office.get("city")
            or office.get("district")
            or office.get("local_city")
            or office.get("address")
            or "Non spécifié"
        )

        desc_parts = []
        if job.get("description"):
            desc_parts.append(clean_html_to_text(job["description"]))
        if job.get("profile"):
            desc_parts.append("### Profil recherché\n" + clean_html_to_text(job["profile"]))
        description = "\n\n".join(desc_parts) or "Description non disponible"

        return {
            "poste": str(title).strip(),
            "entreprise": str(company).strip(),
            "description": description,
            "localisation": str(location).strip(),
            "type_contrat": normalize_employment_type(job.get("contract_type")),
            "url": url,
            "ats_platform": "wttj",
            "source_record": job,
        }
    except ExpiredOfferError:
        raise
    except Exception as e:
        logger.debug(f"Échec parsing Welcome to the Jungle API pour {url}: {e}")
        return None
