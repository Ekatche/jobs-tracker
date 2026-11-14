import asyncio
import html
import json
import logging
import re
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import parse_qs, urlparse

import httpx

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

from app.services.egress_guard import public_only_transport
from app.services.profile.urls import reject_non_public_request

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
            "source_record": data,
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
                        "source_record": j,
                    }
    except Exception as e:
        logger.debug(f"Échec Workable widget pour {url}: {e}")

    return None


async def extract_smartrecruiters_job(
    url: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """Extrait une offre SmartRecruiters via son API publique api.smartrecruiters.com/v1/companies/{company}/postings/{id}."""
    # Pattern: jobs.smartrecruiters.com/{company}/{posting_id} ou careers.smartrecruiters.com/{company}/{posting_id}
    # Exemple: https://jobs.smartrecruiters.com/ASIFR/744000138664100-ingenieur-ia-h-f-?trid=...
    match = re.search(r"smartrecruiters\.com/([^/]+)/([0-9a-zA-Z]+)", url)
    if not match:
        return None

    company_slug = match.group(1)
    posting_id = match.group(2)
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

        contract_raw = (data.get("typeOfEmployment") or {}).get("label") or (data.get("typeOfEmployment") or {}).get("id")
        contract = normalize_employment_type(contract_raw)

        # Assemblage des sections de description
        sections = (data.get("jobAd") or {}).get("sections") or {}
        desc_parts = []
        for sec_key in ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]:
            sec = sections.get(sec_key)
            if sec and sec.get("text"):
                sec_title = sec.get("title", sec_key)
                cleaned = clean_html_to_text(sec.get("text"))
                if cleaned and cleaned != "Non spécifié":
                    desc_parts.append(f"### {sec_title}\n{cleaned}")

        if not desc_parts:
            return None
        full_description = "\n\n".join(desc_parts)

        return {
            "poste": title.strip(),
            "entreprise": company.strip(),
            "description": full_description,
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


_SAFE_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_WORKDAY_HOST_RE = re.compile(r"^(?P<tenant>[A-Za-z0-9-]+)\.(?P<shard>wd\d+)\.myworkdayjobs\.com$", re.IGNORECASE)
_LOCALE_SEGMENT_RE = re.compile(r"^[a-z]{2}(?:-[A-Za-z]{2})?$")
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


def _is_safe_segment(segment: str) -> bool:
    return bool(segment and ".." not in segment and _SAFE_PATH_SEGMENT_RE.match(segment))


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
        jobs = data["jobs"]
        job = next(
            (
                j for j in jobs
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
        site = segments[0]
        job_segments = segments[2:]
        if not (_is_safe_segment(site) and all(_is_safe_segment(s) for s in job_segments)):
            return None

        api_url = f"https://{host}/wday/cxs/{tenant}/{site}/job/{'/'.join(job_segments)}"
        headers = {**DEFAULT_HEADERS, "Accept": "application/json"}
        resp = await client.get(api_url, headers=headers, timeout=DEFAULT_TIMEOUT)
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
    """Extrait une offre Indeed via l'API GraphQL de l'app mobile (celle qu'utilise jobspy).

    Les pages viewjob sont derrière une protection anti-bot : le navigateur headless
    n'atteint jamais `networkidle` et le crawl expire.
    """
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
    """Extrait une offre Welcome to the Jungle via son API publique REST api.welcometothejungle.com.

    Les pages HTML WTTJ bloquent les navigateurs headless avec un challenge AWS WAF (HTTP 202).
    L'API JSON publique fournit directement le titre, l'entreprise, le descriptif et le contrat.
    """
    match = re.search(
        r"welcometothejungle\.(?:com|fr)/(?:[a-z]{2}/)?companies/([^/]+)/jobs/([^/?#]+)",
        url,
    )
    if not match:
        return None

    org_slug = match.group(1)
    job_slug = match.group(2)
    api_url = f"https://api.welcometothejungle.com/api/v1/organizations/{org_slug}/jobs/{job_slug}"

    try:
        resp = await client.get(
            api_url,
            headers={
                "User-Agent": DEFAULT_HEADERS["User-Agent"],
                "Accept": "application/json",
            },
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code in (404, 410):
            # L'offre a été retirée ou expirée sur Welcome to the Jungle
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

        # Localisation : city, district ou adresse complète
        office = job.get("office") or {}
        location = (
            office.get("city")
            or office.get("district")
            or office.get("local_city")
            or office.get("address")
            or "Non spécifié"
        )

        # Description + Profil recherché
        desc_parts = []
        if job.get("description"):
            desc_parts.append(clean_html_to_text(job["description"]))
        if job.get("profile"):
            desc_parts.append("### Profil recherché\n" + clean_html_to_text(job["profile"]))
        description = "\n\n".join(desc_parts) or "Description non disponible"

        contract = normalize_employment_type(job.get("contract_type"))

        return {
            "poste": str(title).strip(),
            "entreprise": str(company).strip(),
            "description": description,
            "localisation": str(location).strip(),
            "type_contrat": contract,
            "url": url,
            "ats_platform": "wttj",
            "source_record": job,
        }
    except ExpiredOfferError:
        raise
    except Exception as e:
        logger.debug(f"Échec parsing Welcome to the Jungle API pour {url}: {e}")
        return None


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
                "source_record": item,
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
        # URL éventuellement saisie par l'utilisateur : chaque saut doit rester public (SSRF)
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=DEFAULT_TIMEOUT,
            event_hooks={"request": [reject_non_public_request]},
            transport=public_only_transport(),
        )
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

        # 4. SmartRecruiters direct API
        if "smartrecruiters.com" in domain:
            sr_result = await extract_smartrecruiters_job(url, client)
            if sr_result:
                logger.info(f"⚡ Extraction Zero-Token réussie (SmartRecruiters): {sr_result['poste']} - {sr_result['entreprise']}")
                return sr_result

        # 5. Indeed : API GraphQL mobile, la page web bloque les navigateurs headless
        if "indeed." in domain:
            indeed_result = await extract_indeed_job(url, client)
            if indeed_result:
                logger.info(f"⚡ Extraction Zero-Token réussie (Indeed): {indeed_result['poste']} - {indeed_result['entreprise']}")
                return indeed_result

        # 6. Welcome to the Jungle direct REST API
        if "welcometothejungle." in domain:
            wttj_result = await extract_wttj_job(url, client)
            if wttj_result:
                logger.info(f"⚡ Extraction Zero-Token réussie (WTTJ): {wttj_result['poste']} - {wttj_result['entreprise']}")
                return wttj_result

        # 7. Cadremploi : protégé par Cloudflare (HTTP 403 sur client standard)
        if "cadremploi.fr" in domain:
            curl_res = await asyncio.to_thread(_fetch_with_curl_cffi, url)
            if curl_res:
                c_status, c_html = curl_res
                if c_status in (404, 410) or "cette offre est expirée" in c_html.lower() or "plus disponible" in c_html.lower():
                    raise ExpiredOfferError(url)
                if c_status == 200:
                    jsonld_result = parse_jsonld_job_posting(c_html, url)
                    if jsonld_result:
                        jsonld_result["ats_platform"] = "cadremploi"
                        logger.info(f"⚡ Extraction Zero-Token réussie (Cadremploi): {jsonld_result['poste']} - {jsonld_result['entreprise']}")
                        return jsonld_result
                    if _check_non_content_html(c_html, url):
                        return None

        # 7b. Ashby direct public board API
        if "ashbyhq.com" in domain:
            ashby_result = await extract_ashby_job(url, client)
            if ashby_result:
                logger.info(f"⚡ Extraction Zero-Token réussie (Ashby): {ashby_result['poste']} - {ashby_result['entreprise']}")
                return ashby_result

        # 7c. Workday CXS JSON endpoint
        if "myworkdayjobs.com" in domain:
            wd_result = await extract_workday_job(url, client)
            if wd_result:
                logger.info(f"⚡ Extraction Zero-Token réussie (Workday): {wd_result['poste']} - {wd_result['entreprise']}")
                return wd_result

        # 8. Universal Schema.org JSON-LD fetch
        # Pour les job boards comme HelloWork, Meteojob, JobTeaser, Ashby, etc.
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
            if _check_non_content_html(resp.text, url):
                return None
        elif resp.status_code in (403, 503):
            # Tentative de repli via curl_cffi pour les sites protégés par Cloudflare
            curl_res = await asyncio.to_thread(_fetch_with_curl_cffi, url)
            if curl_res:
                c_status, c_html = curl_res
                if c_status in (404, 410) or "cette offre est expirée" in c_html.lower() or "plus disponible" in c_html.lower():
                    raise ExpiredOfferError(url)
                if c_status == 200:
                    jsonld_result = parse_jsonld_job_posting(c_html, url)
                    if jsonld_result:
                        logger.info(f"⚡ Extraction Zero-Token réussie (JSON-LD via curl_cffi): {jsonld_result['poste']} - {jsonld_result['entreprise']}")
                        return jsonld_result
                    if _check_non_content_html(c_html, url):
                        return None

    except ExpiredOfferError:
        raise
    except Exception as e:
        logger.debug(f"Extraction Zero-Token non concluante pour {url}: {e}")
    finally:
        if close_client:
            await client.aclose()

    return None
