import html
import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

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


class ExpiredOfferError(Exception):
    """L'ATS confirme que l'offre n'existe plus : aucun crawl de repli ne doit être tenté."""


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
    # Normalise les sauts de lignes multiples
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip() or "Non spécifié"


def normalize_employment_type(emp_type: Any) -> str:
    """Normalise les types de contrats standards (schema.org et ATS) en français."""
    if not emp_type:
        return "Non spécifié"
    raw = str(emp_type).upper().replace("-", "_").replace(" ", "_")
    if "FULL_TIME" in raw or "CDI" in raw or "PERMANENT" in raw:
        return "CDI"
    if "PART_TIME" in raw:
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


async def extract_greenhouse_job(
    url: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Extrait une offre Greenhouse via son API publique boards-api.greenhouse.io."""
    # Pattern: boards.greenhouse.io/{board}/jobs/{job_id} ou job-boards.greenhouse.io/{board}/jobs/{job_id}
    match = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if not match:
        return None

    board_token = match.group(1)
    job_id = match.group(2)
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
        content_html = data.get("content", "")
        description = clean_html_to_text(content_html)
        company = data.get("company_name") or board_token.replace("-", " ").title()

        return {
            "poste": title.strip(),
            "entreprise": company.strip(),
            "description": description,
            "localisation": location.strip() if location else "Non spécifié",
            "type_contrat": "CDI",
            "url": url,
            "ats_platform": "greenhouse",
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
    # Pattern: jobs.lever.co/{company}/{posting_id}
    match = re.search(r"jobs\.lever\.co/([^/]+)/([a-f0-9\-]+)", url)
    if not match:
        return None

    company_slug = match.group(1)
    posting_id = match.group(2)
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
        commitment = categories.get("commitment")
        contract = normalize_employment_type(commitment)

        description = (
            data.get("descriptionPlain")
            or clean_html_to_text(data.get("description", ""))
        )
        company = company_slug.replace("-", " ").title()

        return {
            "poste": title.strip(),
            "entreprise": company.strip(),
            "description": description,
            "localisation": location.strip() if location else "Non spécifié",
            "type_contrat": contract,
            "url": url,
            "ats_platform": "lever",
        }
    except Exception as e:
        logger.debug(f"Échec parsing Lever API pour {url}: {e}")
        return None


async def extract_workable_job(
    url: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Extrait une offre Workable via l'API publique widget ou posting."""
    # Pattern: apply.workable.com/{company}/j/{shortcode}/
    match = re.search(r"apply\.workable\.com/([^/]+)/j/([a-zA-Z0-9]+)", url)
    if not match:
        return None

    company_slug = match.group(1)
    shortcode = match.group(2)
    api_url = f"https://apply.workable.com/api/v1/widget/accounts/{company_slug}"

    try:
        resp = await client.get(api_url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            jobs = data.get("jobs") or []
            for j in jobs:
                if j.get("shortcode") == shortcode:
                    title = j.get("title")
                    city = j.get("city") or j.get("location") or "Non spécifié"
                    description = clean_html_to_text(j.get("description", ""))
                    contract = normalize_employment_type(j.get("employment_type"))
                    return {
                        "poste": title.strip(),
                        "entreprise": company_slug.replace("-", " ").title(),
                        "description": description,
                        "localisation": city.strip() if city else "Non spécifié",
                        "type_contrat": contract,
                        "url": url,
                        "ats_platform": "workable",
                    }
    except Exception as e:
        logger.debug(f"Échec Workable widget pour {url}: {e}")

    return None


def parse_jsonld_job_posting(html_content: str, url: str) -> Optional[Dict[str, Any]]:
    """Parse universel des balises Schema.org `<script type="application/ld+json">` avec `@type: JobPosting`."""
    if not html_content or "JobPosting" not in html_content:
        return None

    scripts = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    for script_text in scripts:
        try:
            data = json.loads(script_text.strip())
        except Exception:
            continue

        items: List[dict] = []
        if isinstance(data, dict):
            if data.get("@type") == "JobPosting":
                items.append(data)
            elif "@graph" in data and isinstance(data["@graph"], list):
                items.extend(
                    elem for elem in data["@graph"] if isinstance(elem, dict) and elem.get("@type") == "JobPosting"
                )
        elif isinstance(data, list):
            items.extend(
                elem for elem in data if isinstance(elem, dict) and elem.get("@type") == "JobPosting"
            )

        for item in items:
            title = item.get("title") or item.get("name")
            if not title:
                continue

            # Entreprise
            org = item.get("hiringOrganization")
            company = "Non spécifié"
            if isinstance(org, dict):
                company = org.get("name") or "Non spécifié"
            elif isinstance(org, str):
                company = org

            # Localisation
            location = "Non spécifié"
            job_loc = item.get("jobLocation")
            if isinstance(job_loc, dict):
                addr = job_loc.get("address")
                if isinstance(addr, dict):
                    location = addr.get("addressLocality") or addr.get("addressRegion") or "Non spécifié"
                elif isinstance(addr, str):
                    location = addr
                elif job_loc.get("addressLocality"):
                    location = job_loc.get("addressLocality")
            elif isinstance(job_loc, list) and job_loc:
                first = job_loc[0]
                if isinstance(first, dict):
                    addr = first.get("address")
                    if isinstance(addr, dict):
                        location = addr.get("addressLocality") or "Non spécifié"

            # Télétravail
            if item.get("jobLocationType") == "TELECOMMUTE" or "telecommute" in str(item).lower():
                if location == "Non spécifié":
                    location = "Télétravail"

            description = clean_html_to_text(item.get("description", ""))
            contract = normalize_employment_type(item.get("employmentType"))

            return {
                "poste": str(title).strip(),
                "entreprise": str(company).strip(),
                "description": description,
                "localisation": str(location).strip(),
                "type_contrat": contract,
                "url": url,
                "ats_platform": "json_ld",
            }

    return None


async def extract_ats_or_jsonld_offer(
    url: str, client: Optional[httpx.AsyncClient] = None
) -> Optional[Dict[str, Any]]:
    """Tente une extraction Zero-Token directe via les APIs d'ATS ou Schema.org JSON-LD.

    Retourne un dict d'offre compatible avec `JobOffer` si succès, ou `None` en cas d'échec
    pour permettre le basculement en cascade sur Crawl4AI + LLM.
    Lève `ExpiredOfferError` si l'ATS confirme que l'offre a été retirée.
    """
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return None

    close_client = False
    if client is None:
        client = httpx.AsyncClient(follow_redirects=True, timeout=DEFAULT_TIMEOUT)
        close_client = True

    try:
        domain = urlparse(url).netloc.lower()

        # 1. Greenhouse direct API
        if "greenhouse.io" in domain:
            gh_result = await extract_greenhouse_job(url, client)
            if gh_result:
                logger.info(f"⚡ Extraction Zero-Token réussie (Greenhouse): {gh_result['poste']} - {gh_result['entreprise']}")
                return gh_result

        # 2. Lever direct API
        if "lever.co" in domain:
            lever_result = await extract_lever_job(url, client)
            if lever_result:
                logger.info(f"⚡ Extraction Zero-Token réussie (Lever): {lever_result['poste']} - {lever_result['entreprise']}")
                return lever_result

        # 3. Workable direct API
        if "workable.com" in domain:
            workable_result = await extract_workable_job(url, client)
            if workable_result:
                logger.info(f"⚡ Extraction Zero-Token réussie (Workable): {workable_result['poste']} - {workable_result['entreprise']}")
                return workable_result

        # 4. Universal Schema.org JSON-LD fetch
        # Pour les job boards comme HelloWork, Cadremploi, Meteojob, JobTeaser, Ashby, etc.
        resp = await client.get(url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            jsonld_result = parse_jsonld_job_posting(resp.text, url)
            if jsonld_result:
                # Spécifier la plateforme si détectable
                if "ashbyhq.com" in domain:
                    jsonld_result["ats_platform"] = "ashby"
                elif "hellowork.com" in domain:
                    jsonld_result["ats_platform"] = "hellowork"
                elif "jobteaser.com" in domain:
                    jsonld_result["ats_platform"] = "jobteaser"
                elif "francetravail.fr" in domain:
                    jsonld_result["ats_platform"] = "francetravail"

                logger.info(f"⚡ Extraction Zero-Token réussie (JSON-LD/{jsonld_result.get('ats_platform', 'web')}): {jsonld_result['poste']} - {jsonld_result['entreprise']}")
                return jsonld_result

    except ExpiredOfferError:
        raise
    except Exception as e:
        logger.debug(f"Extraction Zero-Token non concluante pour {url}: {e}")
    finally:
        if close_client:
            await client.aclose()

    return None
