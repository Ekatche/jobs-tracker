"""URL parsing, ATS company extraction, and crawl URL optimization helpers."""

import re
from typing import Optional
from urllib.parse import urlparse

AGGREGATOR_DOMAINS = {
    "linkedin.com",
    "apec.fr",
    "francetravail.fr",
    "pole-emploi.fr",
    "indeed.com",
    "indeed.fr",
    "monster.fr",
    "hellowork.com",
    "meteojob.com",
    "cadremploi.fr",
    "glassdoor.fr",
    "glassdoor.com",
    "jobteaser.com",
    "apec.asso.fr",
}

_SUBDOMAIN_ATS_DOMAINS = (
    ".jobs2web.com",
    ".taleo.net",
    ".bamboohr.com",
    ".recruitee.com",
    ".teamtailor.com",
    ".breezy.hr",
    ".flatchr.io",
)
_GENERIC_PREFIXES = ("jobs", "careers", "www")


def extract_domain(url: Optional[str]) -> str:
    """Extrait et normalise le domaine d'une URL."""
    if not url:
        return "Non spécifié"

    try:
        if "://" in url:
            domain = url.split("://")[1].split("/")[0]
        else:
            domain = url.split("/")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain.lower().strip()
    except Exception:
        return "Non spécifié"


def _clean_company_slug(slug: str) -> str:
    """Format and capitalize slugified company name."""
    cleaned = re.sub(r"[-_]+", " ", slug).strip()
    return cleaned.title()


def _extract_subdomain_prefix(hostname: str, suffix: str) -> Optional[str]:
    if not hostname.endswith(suffix):
        return None
    sub = hostname[: -len(suffix)]
    prefix = sub.split(".")[-1]
    if prefix and prefix not in _GENERIC_PREFIXES:
        return _clean_company_slug(prefix)
    return None


def _extract_path_based_ats(hostname: str, path: str) -> Optional[str]:
    path_parts = [p for p in path.split("/") if p]
    if "greenhouse.io" in hostname:
        if path_parts and path_parts[0] not in ("embed", "jobs"):
            return _clean_company_slug(path_parts[0])
        if len(path_parts) > 1 and path_parts[0] == "embed":
            return _clean_company_slug(path_parts[1])
        return None
    if "lever.co" in hostname or "smartrecruiters.com" in hostname or "ashbyhq.com" in hostname:
        return _clean_company_slug(path_parts[0]) if path_parts else None
    if "welcometothejungle.com" in hostname:
        wttj_match = re.search(r"/companies/([^/]+)", path)
        return _clean_company_slug(wttj_match.group(1)) if wttj_match else None
    return None


def _extract_ats_company(hostname: str, path: str) -> Optional[str]:
    workday_match = re.match(r"^([a-z0-9-]+)\.wd\d+\.myworkdayjobs\.com$", hostname)
    if workday_match:
        return _clean_company_slug(workday_match.group(1))

    path_result = _extract_path_based_ats(hostname, path)
    if path_result is not None:
        return path_result

    if "workable.com" in hostname:
        if hostname.startswith("apply.") or hostname == "workable.com":
            parts = [p for p in path.split("/") if p]
            return _clean_company_slug(parts[0]) if parts else None
        return _extract_subdomain_prefix(hostname.replace(".workable.com", ".workable_tmp"), ".workable_tmp")

    if "personio.de" in hostname or "personio.com" in hostname:
        parts = [p for p in path.split("/") if p]
        if parts and parts[0] not in ("job", "jobs", "careers"):
            return _clean_company_slug(parts[0])
        for base in (".jobs.personio.de", ".jobs.personio.com", ".personio.de", ".personio.com"):
            found = _extract_subdomain_prefix(hostname, base)
            if found:
                return found

    if hostname.endswith(".icims.com"):
        sub = hostname[: -len(".icims.com")]
        prefix = re.sub(r"^(careers?-|jobs?-)|(-careers?|-jobs?)$", "", sub.split(".")[-1], flags=re.IGNORECASE)
        return _clean_company_slug(prefix) if prefix and prefix not in _GENERIC_PREFIXES else None

    for suffix in _SUBDOMAIN_ATS_DOMAINS:
        found = _extract_subdomain_prefix(hostname, suffix)
        if found:
            return found
    return None


def extract_company_from_url(url: Optional[str]) -> Optional[str]:
    """
    Extract company name from job posting URL as fallback when missing from DOM.
    Handles ATS platforms (Workday, Greenhouse, Lever, SmartRecruiters, WTTJ, etc.)
    and corporate career subdomains. Returns None for generic job aggregators.
    """
    if not url or not isinstance(url, str):
        return None

    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url

    try:
        parsed = urlparse(clean_url)
        hostname = (parsed.hostname or "").lower()
        path = parsed.path or ""
        if not hostname:
            return None
        if any(hostname == agg or hostname.endswith("." + agg) for agg in AGGREGATOR_DOMAINS):
            return None

        ats_company = _extract_ats_company(hostname, path)
        if ats_company:
            return ats_company

        parts = hostname.split(".")
        if len(parts) >= 3 and parts[0] in ("carrieres", "recrutement", "jobs", "careers", "talent"):
            return _clean_company_slug(parts[1])

        if len(parts) >= 2:
            main_idx = -3 if (len(parts) >= 3 and parts[-2] in ("co", "com", "asso", "org", "gov") and len(parts[-1]) <= 3) else -2
            candidate = parts[main_idx]
            if candidate not in ("jobs", "careers", "recrutement", "www", "app", "portal", "candidate"):
                return _clean_company_slug(candidate)
        return None
    except Exception:
        return None


def optimize_crawl_url(url: Optional[str]) -> str:
    """
    Optimise les URLs de job boards pour contourner les protections anti-bot
    et maximiser la fidélité de l'extraction par Crawl4AI :
    - LinkedIn: convertit les URLs /jobs/view/ en endpoint guest public SEO
      (évite les redirections vers /authwall et les captchas en headless).
    - Indeed: convertit les URLs /viewjob?jk= en endpoint mobile /m/viewjob?jk=
      (évite les timeouts Cloudflare Turnstile de 45s sur la vue bureau).
    """
    if not url:
        return ""
    url_clean = url.strip()

    if "linkedin.com" in url_clean:
        if "/jobs-guest/jobs/api/jobPosting/" in url_clean:
            return url_clean
        m = re.search(r"/jobs/view/(?:[a-zA-Z0-9\-_]+-)?(\d+)", url_clean)
        if m:
            return f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}"

    if "indeed.com" in url_clean or "indeed.fr" in url_clean:
        if "/m/viewjob" in url_clean:
            return url_clean
        m = re.search(r"[?&]jk=([a-zA-Z0-9]+)", url_clean)
        if m:
            base = "https://fr.indeed.com" if ("fr.indeed.com" in url_clean or "indeed.fr" in url_clean) else "https://www.indeed.com"
            return f"{base}/m/viewjob?jk={m.group(1)}"

    return url_clean


def restore_canonical_job_url(url: Optional[str]) -> str:
    """
    Restaure une URL conviviale et navigable pour l'utilisateur final à partir
    d'une URL optimisée pour le crawling.
    """
    if not url:
        return ""
    url_clean = url.strip()

    m_li = re.search(r"/jobs-guest/jobs/api/jobPosting/(\d+)", url_clean)
    if m_li:
        return f"https://www.linkedin.com/jobs/view/{m_li.group(1)}"

    m_ind = re.search(r"(https?://[^/]+)/m/viewjob\?jk=([a-zA-Z0-9]+)", url_clean)
    if m_ind:
        return f"{m_ind.group(1)}/viewjob?jk={m_ind.group(2)}"

    return url_clean
