import re
import string
from typing import Optional


def normalize_city(city: Optional[str]) -> str:
    """Normalise les noms de villes pour éviter les doublons"""
    if not city:
        return "Non spécifié"

    # Supprimer les codes postaux complets (ex: "44000 Nantes" -> "Nantes")
    city = re.sub(r"^\d{5}\s+", "", city)

    # Supprimer les codes postaux avec tiret (ex: "Nantes - 44" -> "Nantes")
    city = re.sub(r"\s*-\s*\d+.*$", "", city)

    # Supprimer les arrondissements avec tiret (ex: "Lyon - 01" -> "Lyon")
    city = re.sub(r"\s*-\s*\d{2}$", "", city)

    # Supprimer les arrondissements avec espace (ex: "LYON 01" -> "LYON")
    city = re.sub(r"\s+\d{2}$", "", city)

    # Supprimer les arrondissements avec "er", "ème", etc. (ex: "Lyon 1er" -> "Lyon")
    city = re.sub(r"\s+\d{1,2}(er|ème|e)?$", "", city, flags=re.IGNORECASE)

    # Supprimer les parenthèses et leur contenu (ex: "Lyon (Rhône)" -> "Lyon")
    city = re.sub(r"\s*\([^)]*\)", "", city)

    # Nettoyer les espaces multiples
    city = re.sub(r"\s+", " ", city.strip())

    return city.title() if city else "Non spécifié"


def normalize_company(company: Optional[str]) -> str:
    """Normalise les noms d'entreprises pour comparaison et déduplication"""
    if not company:
        return "Non spécifié"

    normalized = company.upper()

    # Supprimer les suffixes juridiques courants
    suffixes = [" SAS", " SA", " SARL", " EURL", " SNC", " SCOP", " SASU", " SCIC", " INC", " LLC", " LTD"]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    # Nettoyer les espaces multiples
    normalized = re.sub(r"\s+", " ", normalized.strip())

    return normalized if normalized else "Non spécifié"


def normalize_position(position: Optional[str]) -> str:
    """Normalise les intitulés de postes pour améliorer la détection de similarité"""
    if not position:
        return "Non spécifié"

    normalized = position.upper()

    # Supprimer les mentions H/F courantes avant de nettoyer la ponctuation
    mentions_hf = [r"\(H/F\)", r"\(F/H\)", r"\(H\s*F\)", r"\bH/F\b", r"\bF/H\b", r"\bHF\b", r"\bHOMME\s+FEMME\b", r"\bFEMME\s+HOMME\b"]
    for pattern in mentions_hf:
        normalized = re.sub(pattern, " ", normalized, flags=re.IGNORECASE)

    # Supprimer la ponctuation et caractères spéciaux
    normalized = normalized.translate(str.maketrans("", "", string.punctuation))

    # Nettoyer les espaces multiples
    normalized = re.sub(r"\s+", " ", normalized.strip())

    # Trier les mots significatifs pour rendre l'ordre non-bloquant
    words = [word for word in normalized.split() if len(word) > 1 and word.lower() not in {"de", "du", "des", "le", "la", "les", "un", "une", "en", "pour", "et", "ou"}]
    words.sort()

    return " ".join(words) if words else "Non spécifié"


def extract_domain(url: Optional[str]) -> str:
    """Extrait et normalise le domaine d'une URL"""
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


def compute_unique_key(company: str, position: str, location: Optional[str] = None, url: Optional[str] = None) -> str:
    """
    Génère une clé d'upsert robuste pour une offre d'emploi.
    Si une URL spécifique est présente, elle fait partie de l'unicité.
    Sinon, elle se base sur le triplet normalisé Entreprise | Poste | Localisation.
    """
    norm_comp = normalize_company(company).lower()
    norm_pos = normalize_position(position).lower()
    norm_loc = normalize_city(location).lower() if location else "non-specifie"

    if url and len(url.strip()) > 10:
        clean_url = url.strip().rstrip("/")
        return f"{norm_comp}|{norm_pos}|{clean_url}"

    return f"{norm_comp}|{norm_pos}|{norm_loc}"


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


def _clean_company_slug(slug: str) -> str:
    """Format and capitalize slugified company name."""
    cleaned = re.sub(r"[-_]+", " ", slug).strip()
    return cleaned.title()


def extract_company_from_url(url: Optional[str]) -> Optional[str]:
    """
    Extract company name from job posting URL as fallback when missing from DOM.
    Handles ATS platforms (Workday, Greenhouse, Lever, SmartRecruiters, WTTJ, etc.)
    and corporate career subdomains. Returns None for generic job aggregators.
    """
    from urllib.parse import urlparse

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

        # Ignore aggregators
        if any(hostname == agg or hostname.endswith("." + agg) for agg in AGGREGATOR_DOMAINS):
            return None

        # 1. Workday: <company>.wd*.myworkdayjobs.com
        workday_match = re.match(r"^([a-z0-9-]+)\.wd\d+\.myworkdayjobs\.com$", hostname)
        if workday_match:
            return _clean_company_slug(workday_match.group(1))

        # 2. Greenhouse: boards.greenhouse.io/<company>/... or job-boards.greenhouse.io/<company>/...
        if "greenhouse.io" in hostname:
            parts = [p for p in path.split("/") if p]
            if parts and parts[0] not in ("embed", "jobs"):
                return _clean_company_slug(parts[0])
            elif len(parts) > 1 and parts[0] == "embed":
                return _clean_company_slug(parts[1])

        # 3. Lever: jobs.lever.co/<company>/...
        if "lever.co" in hostname:
            parts = [p for p in path.split("/") if p]
            if parts:
                return _clean_company_slug(parts[0])

        # 4. SmartRecruiters: jobs.smartrecruiters.com/<company>/...
        if "smartrecruiters.com" in hostname:
            parts = [p for p in path.split("/") if p]
            if parts:
                return _clean_company_slug(parts[0])

        # 5. Welcome to the Jungle: welcometothejungle.com/.../companies/<company>/...
        if "welcometothejungle.com" in hostname:
            wttj_match = re.search(r"/companies/([^/]+)", path)
            if wttj_match:
                return _clean_company_slug(wttj_match.group(1))

        # 6. Specific ATS subdomains: <company>.(recruitee.com|teamtailor.com|breezy.hr|flatchr.io|workable.com)
        ats_domains = [
            "recruitee.com",
            "teamtailor.com",
            "breezy.hr",
            "flatchr.io",
            "workable.com",
            "personio.de",
            "personio.com",
        ]
        for ats in ats_domains:
            if hostname.endswith("." + ats):
                sub = hostname[: -len("." + ats)]
                prefix = sub.split(".")[-1]
                if prefix and prefix not in ("jobs", "careers", "www"):
                    return _clean_company_slug(prefix)

        # 7. Career subdomains: (carrieres|recrutement|jobs|careers|talent).<company>.(com|fr|...)
        parts = hostname.split(".")
        if len(parts) >= 3 and parts[0] in ("carrieres", "recrutement", "jobs", "careers", "talent"):
            return _clean_company_slug(parts[1])

        # 8. Standard corporate domain: www.<company>.(com|fr|org|...)
        if len(parts) >= 2:
            main_idx = -2
            if len(parts) >= 3 and parts[-2] in ("co", "com", "asso", "org", "gov") and len(parts[-1]) <= 3:
                main_idx = -3
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

    # 1. LinkedIn : conversion vers l'API publique guest
    if "linkedin.com" in url_clean:
        if "/jobs-guest/jobs/api/jobPosting/" in url_clean:
            return url_clean
        m = re.search(r"/jobs/view/(?:[a-zA-Z0-9\-_]+-)?(\d+)", url_clean)
        if m:
            job_id = m.group(1)
            return f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    # 2. Indeed : conversion vers la vue mobile statique sans challenge Cloudflare
    if "indeed.com" in url_clean or "indeed.fr" in url_clean:
        if "/m/viewjob" in url_clean:
            return url_clean
        m = re.search(r"[?&]jk=([a-zA-Z0-9]+)", url_clean)
        if m:
            jk = m.group(1)
            if "fr.indeed.com" in url_clean or "indeed.fr" in url_clean:
                base = "https://fr.indeed.com"
            else:
                base = "https://www.indeed.com"
            return f"{base}/m/viewjob?jk={jk}"

    return url_clean


def restore_canonical_job_url(url: Optional[str]) -> str:
    """
    Restaure une URL conviviale et navigable pour l'utilisateur final à partir
    d'une URL optimisée pour le crawling.
    - https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/123456 -> https://www.linkedin.com/jobs/view/123456
    - https://fr.indeed.com/m/viewjob?jk=abc123 -> https://fr.indeed.com/viewjob?jk=abc123
    """
    if not url:
        return ""

    url_clean = url.strip()

    # Restauration LinkedIn
    m_li = re.search(r"/jobs-guest/jobs/api/jobPosting/(\d+)", url_clean)
    if m_li:
        job_id = m_li.group(1)
        return f"https://www.linkedin.com/jobs/view/{job_id}"

    # Restauration Indeed mobile -> standard viewjob
    m_ind = re.search(r"(https?://[^/]+)/m/viewjob\?jk=([a-zA-Z0-9]+)", url_clean)
    if m_ind:
        base = m_ind.group(1)
        jk = m_ind.group(2)
        return f"{base}/viewjob?jk={jk}"

    return url_clean


