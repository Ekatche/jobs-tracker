"""Sources Indeed France et LinkedIn via python-jobspy (scraping des pages publiques).

Chaque site est interrogé séparément : un blocage (429 LinkedIn, Cloudflare
Indeed) ne prive pas l'autre de ses résultats.
"""

import asyncio
import logging
import math
from typing import Optional

from app.services.sources.geo import GEO_RADIUS_KM, clean_city_label

logger = logging.getLogger(__name__)

JOBBOARD_SITES = ("indeed", "linkedin")
JOBBOARD_MAX_RESULTS = 25
JOBBOARD_HOURS_OLD = 24 * 14
KM_PER_MILE = 1.609

JOB_TYPE_LABELS = {"internship": "Stage", "parttime": "Temps partiel"}


def _value(row, key: str):
    """Valeur exploitable d'une cellule pandas (NaN / NaT / None -> None)."""
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return None if text.lower() in ("", "nan", "nat", "none") else value


def _salary_label(row) -> str:
    low, high = _value(row, "min_amount"), _value(row, "max_amount")
    if low is None and high is None:
        return ""
    amounts = " - ".join(f"{int(a)}" for a in (low, high) if a is not None)
    return f"{amounts} {_value(row, 'currency') or ''} / {_value(row, 'interval') or ''}".strip(" /")


def map_jobboard_row(row) -> dict:
    url = str(_value(row, "job_url") or "")
    date = _value(row, "date_posted")
    return {
        "poste": str(_value(row, "title") or ""),
        "entreprise": str(_value(row, "company") or ""),
        "description": str(_value(row, "description") or ""),
        "localisation": clean_city_label(str(_value(row, "location") or "")),
        "date": str(date)[:10] if date is not None else "",
        "type_contrat": JOB_TYPE_LABELS.get(str(_value(row, "job_type") or ""), ""),
        "salaire": _salary_label(row),
        "mode_travail": "Télétravail total" if _value(row, "is_remote") else "",
        "competences_cles": [],
        "url": url,
        "source_url": url,
        "ats_platform": str(_value(row, "site") or ""),
    }


def _scrape_site(site: str, role: str, city: Optional[str]) -> list[dict]:
    from jobspy import scrape_jobs

    jobs = scrape_jobs(
        site_name=[site],
        search_term=role,
        location=f"{city}, France" if city else "France",
        distance=round(GEO_RADIUS_KM / KM_PER_MILE),
        hours_old=JOBBOARD_HOURS_OLD,
        results_wanted=JOBBOARD_MAX_RESULTS,
        country_indeed="france",
        linkedin_fetch_description=True,
        description_format="markdown",
        verbose=0,
    )
    return [map_jobboard_row(row) for row in jobs.to_dict("records")]


async def fetch_jobboard_offers(role: str, city: Optional[str], contract: Optional[str]) -> list[dict]:
    results = await asyncio.gather(
        *[asyncio.to_thread(_scrape_site, site, role, city) for site in JOBBOARD_SITES],
        return_exceptions=True,
    )
    offers: list[dict] = []
    for site, result in zip(JOBBOARD_SITES, results):
        if isinstance(result, Exception):
            logger.warning(f"⚠️ {site} indisponible pour '{role}': {result}")
            continue
        logger.info(f"📥 {site}: {len(result)} offres pour '{role}' ({city or 'France'})")
        offers.extend(result)

    # Un stage ne répond pas à une recherche en CDI/CDD/freelance.
    if contract and contract not in ("stage", "alternance"):
        offers = [o for o in offers if o["type_contrat"] != "Stage"]
    return offers
