"""Public ATS board API extractors (Greenhouse, Lever, Workable, SmartRecruiters)."""

import logging
import re
from typing import Any, Dict, Optional

import httpx

from app.services.ats.common import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    ExpiredOfferError,
    clean_html_to_text,
    normalize_employment_type,
)

logger = logging.getLogger(__name__)


async def extract_greenhouse_job(
    url: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Extrait une offre Greenhouse via son API publique boards-api.greenhouse.io."""
    match = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if not match:
        return None

    board_token, job_id = match.group(1), match.group(2)
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"

    try:
        resp = await client.get(api_url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 404:
            # Offre retirée : la page redirige vers la liste des postes du board,
            # que le crawl de repli extrairait comme autant d'offres hors sujet.
            raise ExpiredOfferError(url)
        if resp.status_code != 200:
            return None

        data = resp.json()
        title = data.get("title")
        if not title:
            return None

        location = data.get("location", {}).get("name") if isinstance(data.get("location"), dict) else "Non spécifié"
        description = clean_html_to_text(data.get("content", ""))
        company = data.get("company_name") or board_token.replace("-", " ").title()

        return {
            "poste": title.strip(),
            "entreprise": company.strip(),
            "description": description,
            "localisation": location.strip() if location else "Non spécifié",
            "type_contrat": "CDI",
            "url": url,
            "ats_platform": "greenhouse",
            "source_record": data,
        }
    except ExpiredOfferError:
        raise
    except Exception as e:
        logger.debug(f"Échec parsing Greenhouse API pour {url}: {e}")
        return None


async def extract_lever_job(
    url: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Extrait une offre Lever via son API publique api.lever.co/v0/postings/{company}/{id}."""
    match = re.search(r"jobs\.lever\.co/([^/]+)/([a-f0-9\-]+)", url)
    if not match:
        return None

    company_slug, posting_id = match.group(1), match.group(2)
    api_url = f"https://api.lever.co/v0/postings/{company_slug}/{posting_id}"

    try:
        resp = await client.get(api_url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        if resp.status_code != 200:
            return None

        data = resp.json()
        title = data.get("text")
        if not title:
            return None

        categories = data.get("categories") or {}
        location = categories.get("location") or "Non spécifié"
        contract = normalize_employment_type(categories.get("commitment"))
        description = data.get("descriptionPlain") or clean_html_to_text(data.get("description", ""))
        company = company_slug.replace("-", " ").title()

        return {
            "poste": title.strip(),
            "entreprise": company.strip(),
            "description": description,
            "localisation": location.strip() if location else "Non spécifié",
            "type_contrat": contract,
            "url": url,
            "ats_platform": "lever",
            "source_record": data,
        }
    except Exception as e:
        logger.debug(f"Échec parsing Lever API pour {url}: {e}")
        return None


async def extract_workable_job(
    url: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Extrait une offre Workable via l'API publique widget ou posting."""
    match = re.search(r"apply\.workable\.com/([^/]+)/j/([a-zA-Z0-9]+)", url)
    if not match:
        return None

    company_slug, shortcode = match.group(1), match.group(2)
    api_url = f"https://apply.workable.com/api/v1/widget/accounts/{company_slug}"

    try:
        resp = await client.get(api_url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        if resp.status_code != 200:
            return None
        jobs = resp.json().get("jobs") or []
        for j in jobs:
            if j.get("shortcode") == shortcode:
                city = j.get("city") or j.get("location") or "Non spécifié"
                return {
                    "poste": j.get("title").strip(),
                    "entreprise": company_slug.replace("-", " ").title(),
                    "description": clean_html_to_text(j.get("description", "")),
                    "localisation": city.strip() if city else "Non spécifié",
                    "type_contrat": normalize_employment_type(j.get("employment_type")),
                    "url": url,
                    "ats_platform": "workable",
                    "source_record": j,
                }
    except Exception as e:
        logger.debug(f"Échec Workable widget pour {url}: {e}")

    return None


async def extract_smartrecruiters_job(
    url: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Extrait une offre SmartRecruiters via son API publique api.smartrecruiters.com/v1/companies/{company}/postings/{id}."""
    match = re.search(r"smartrecruiters\.com/([^/]+)/([0-9a-zA-Z]+)", url)
    if not match:
        return None

    company_slug, posting_id = match.group(1), match.group(2)
    api_url = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings/{posting_id}"

    try:
        resp = await client.get(api_url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        if resp.status_code in (404, 410):
            raise ExpiredOfferError(f"SmartRecruiters: Offre {posting_id} retirée (HTTP {resp.status_code})")
        if resp.status_code != 200:
            return None

        data = resp.json()
        title = data.get("name")
        if not title:
            return None

        company = data.get("company", {}).get("name") or company_slug.replace("-", " ").title()
        loc_obj = data.get("location") or {}
        location = loc_obj.get("fullLocation") or loc_obj.get("city") or "Non spécifié"
        if loc_obj.get("hybrid"):
            location = f"{location} (Hybride)"
        elif loc_obj.get("remote"):
            location = f"{location} (Télétravail total)"

        emp = data.get("typeOfEmployment") or {}
        contract = normalize_employment_type(emp.get("label") or emp.get("id"))

        sections = (data.get("jobAd") or {}).get("sections") or {}
        desc_parts = []
        for sec_key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
            sec = sections.get(sec_key)
            if sec and sec.get("text"):
                cleaned = clean_html_to_text(sec.get("text"))
                if cleaned and cleaned != "Non spécifié":
                    desc_parts.append(f"### {sec.get('title', sec_key)}\n{cleaned}")

        if not desc_parts:
            return None

        return {
            "poste": title.strip(),
            "entreprise": company.strip(),
            "description": "\n\n".join(desc_parts),
            "localisation": location.strip(),
            "type_contrat": contract,
            "url": url,
            "ats_platform": "smartrecruiters",
            "source_record": data,
        }
    except ExpiredOfferError:
        raise
    except Exception as e:
        logger.debug(f"Échec SmartRecruiters API pour {url}: {e}")
        return None
