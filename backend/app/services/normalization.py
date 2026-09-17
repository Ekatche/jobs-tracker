import html
import re
import string
from typing import Optional, List, Dict, Any, Set
from difflib import SequenceMatcher


def clean_html_entities_and_tags(text: Optional[str]) -> str:
    """Nettoie les entités HTML (ex: &amp; -> &) et supprime les balises HTML résiduelles."""
    if not text:
        return ""
    val = str(text)
    # 1. Supprimer les balises HTML réelles d'abord (ex: <b>, <h3>, <p>, <br/>, <div ...>)
    # pour ne pas détruire les brackets légitimes issus de &lt;...&gt;
    val = re.sub(r"<(?:/[a-zA-Z][a-zA-Z0-9]*|[a-zA-Z][a-zA-Z0-9]*(?:\s+[^>]*)?)>", " ", val)
    # 2. Remplacer les espaces insécables et caractères invisibles
    val = val.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    # 3. Décoder les entités HTML (jusqu'à 2 passes pour le double encodage ex: &amp;amp;)
    for _ in range(2):
        unescaped = html.unescape(val)
        if unescaped == val:
            break
        val = unescaped
    val = re.sub(r"\s+", " ", val)
    return val.strip()



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
    Génère une clé d'unicité canonique et sémantique pour une offre d'emploi.
    La clé est basée sur le triplet normalisé Entreprise | Poste | Localisation,
    permettant la réconciliation cross-plateformes (ex: Welcome to the Jungle vs LinkedIn).
    """
    norm_comp = normalize_company(company).lower()
    norm_pos = normalize_position(position).lower()
    norm_loc = normalize_city(location).lower() if location else "non-specifie"

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

        # 6. Ashby: jobs.ashbyhq.com/<company>/... or ashbyhq.com/<company>/...
        if "ashbyhq.com" in hostname:
            parts = [p for p in path.split("/") if p]
            if parts:
                return _clean_company_slug(parts[0])

        # 7. Workable: apply.workable.com/<company>/... or <company>.workable.com
        if "workable.com" in hostname:
            if hostname.startswith("apply.") or hostname == "workable.com":
                parts = [p for p in path.split("/") if p]
                if parts:
                    return _clean_company_slug(parts[0])
            elif hostname.endswith(".workable.com"):
                sub = hostname[: -len(".workable.com")]
                prefix = sub.split(".")[-1]
                if prefix and prefix not in ("jobs", "careers", "www", "apply"):
                    return _clean_company_slug(prefix)

        # 8. Personio: <company>.jobs.personio.de, <company>.personio.de, jobs.personio.de/<company>/...
        if "personio.de" in hostname or "personio.com" in hostname:
            parts = [p for p in path.split("/") if p]
            if parts and parts[0] not in ("job", "jobs", "careers"):
                return _clean_company_slug(parts[0])
            for base_domain in (".jobs.personio.de", ".jobs.personio.com", ".personio.de", ".personio.com"):
                if hostname.endswith(base_domain):
                    sub = hostname[: -len(base_domain)]
                    prefix = sub.split(".")[-1]
                    if prefix and prefix not in ("jobs", "careers", "www"):
                        return _clean_company_slug(prefix)

        # 9. SAP SuccessFactors: <company>.jobs2web.com
        if hostname.endswith(".jobs2web.com"):
            sub = hostname[: -len(".jobs2web.com")]
            prefix = sub.split(".")[-1]
            if prefix and prefix not in ("jobs", "careers", "www"):
                return _clean_company_slug(prefix)

        # 10. Oracle Taleo: <company>.taleo.net/...
        if hostname.endswith(".taleo.net"):
            sub = hostname[: -len(".taleo.net")]
            prefix = sub.split(".")[-1]
            if prefix and prefix not in ("jobs", "careers", "www"):
                return _clean_company_slug(prefix)

        # 11. iCIMS: <company>.icims.com, careers-<company>.icims.com, <company>-careers.icims.com
        if hostname.endswith(".icims.com"):
            sub = hostname[: -len(".icims.com")]
            prefix = sub.split(".")[-1]
            prefix = re.sub(r"^(careers?-|jobs?-)|(-careers?|-jobs?)$", "", prefix, flags=re.IGNORECASE)
            if prefix and prefix not in ("jobs", "careers", "www"):
                return _clean_company_slug(prefix)

        # 12. Specific ATS subdomains: <company>.(bamboohr.com|recruitee.com|teamtailor.com|breezy.hr|flatchr.io)
        ats_domains = [
            "bamboohr.com",
            "recruitee.com",
            "teamtailor.com",
            "breezy.hr",
            "flatchr.io",
        ]
        for ats in ats_domains:
            if hostname.endswith("." + ats):
                sub = hostname[: -len("." + ats)]
                prefix = sub.split(".")[-1]
                if prefix and prefix not in ("jobs", "careers", "www"):
                    return _clean_company_slug(prefix)

        # 13. Career subdomains: (carrieres|recrutement|jobs|careers|talent).<company>.(com|fr|...)
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


# =====================================================================
# PIPELINE DE NORMALISATION EN 4 COUCHES & DÉDUPLICATION MULTI-CRITÈRES
# =====================================================================

def clean_job_title_syntax(title: Optional[str]) -> str:
    """Couche 1 : Nettoyage syntaxique déterministe de l'intitulé de poste.

    Déséchappe les entités HTML (ex: &amp; -> &), supprime les mentions légales (H/F),
    types de contrat (CDI, CDD), balises marketing/crochets ([Paris], [CDI]),
    parenthèses orphelines et ponctuation résiduelle.
    """
    if not title or not isinstance(title, str):
        return "Non spécifié"

    # 0. Déséchapper les entités HTML (2 passes pour &amp;amp;) et supprimer balises
    cleaned = clean_html_entities_and_tags(title)
    if not cleaned:
        return "Non spécifié"

    # 1. Emojis et caractères décoratifs Unicode
    emoji_pattern = re.compile(
        "["
        "\U0001F1E0-\U0001F1FF"  # drapeaux
        "\U0001F300-\U0001F5FF"  # symboles & pictogrammes
        "\U0001F600-\U0001F64F"  # smileys
        "\U0001F680-\U0001F6FF"  # transport & cartes
        "\U0001F700-\U0001F77F"  # formes géométriques
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U00002600-\U000026FF"  # symboles météo/divers
        "]+",
        flags=re.UNICODE,
    )
    cleaned = emoji_pattern.sub(" ", cleaned)

    # 2. Mentions marketing & buzzwords entre crochets ou isolés
    marketing_patterns = [
        r"\[(?:urgent|top mission|super opportunit[ée]|exclusivit[ée]|nouveau|hot|asap|recrutement|imm[ée]diat)\]",
        r"\b(?:urgent|top mission|super opportunit[ée]|exclusivit[ée]|asap)\b",
    ]
    for pat in marketing_patterns:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)

    # 3. Mentions légales H/F, F/H, M/F/D, H/F/NB, F/H/NB, etc.
    legal_patterns = [
        r"\(\s*(?:h|f|m)\s*[\/\-]?\s*(?:h|f|w)(?:\s*[\/\-]\s*(?:[dxn]|nb|non[\s\-]binaire))?\s*\)",
        r"\b(?:h\/f\/nb|f\/h\/nb|h\/f\/d|f\/h\/d|h\/f\/x|f\/h\/x|h\/f\/n|f\/h\/n)\b",
        r"\b(?:h\/f|f\/h|hf|fh|h\-f|f\-h|m\/f|m\/w\/d|m\/f\/d)\b",
        r"\b(?:homme\s*[\/\-]?\s*femme|femme\s*[\/\-]?\s*homme)\b",
        r"\(\s*[\/\-]\s*(?:nb|non[\s\-]binaire|[dxn])?\s*\)",  # parenthèses résiduelles commençant par un slash/tiret ex: ( /NB)
        r"\s*[\/\-–—]\s*(?:nb|non[\s\-]binaire|n)\b",  # suffixe orphelin /NB ou /N
    ]
    for pat in legal_patterns:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)

    # 4. Balises entre crochets résiduelles (ex: [Lyon], [CDI], [Remote], [Tech], [Ref 1234])
    cleaned = re.sub(r"\[[^\]]*\]", " ", cleaned)

    # 5. Types de contrat dans l'intitulé
    contract_patterns = [
        r"\b(?:cdi\s*[\-–—]?\s*cdd|cdd\s*[\-–—]?\s*cdi)\b",
        r"\b(?:cdi\s*int[ée]rimaire|contrat\s*pro(?:fessionnalisation)?)\b",
        r"\b(?:cdi|cdd|freelance|stage|stagiaire|alternance|alternant|alternante|apprentissage|apprenti|apprentie|int[ée]rim)\b",
    ]
    for pat in contract_patterns:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)

    # 6. Suffixes / Séparateurs de localisation ou remote résiduels
    loc_remote_patterns = [
        r"\s*[\-–—\|\/]\s*(?:paris|lyon|marseille|toulouse|bordeaux|nantes|lille|strasbourg|rennes|nice|montpellier|grenoble|france|remote|t[ée]l[ée]travail|full[\s\-]remote|hybride)\b.*$",
        r"\(\s*(?:paris|lyon|marseille|toulouse|bordeaux|nantes|lille|strasbourg|rennes|nice|montpellier|grenoble|france|remote|t[ée]l[ée]travail|full[\s\-]remote|hybride)\s*\)",
    ]
    for pat in loc_remote_patterns:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)

    # 7. Nettoyage des parenthèses/crochets vides ou orphelins (ex: "()", "( )", "[]", "{}")
    cleaned = re.sub(r"\(\s*\)", " ", cleaned)
    cleaned = re.sub(r"\[\s*\]", " ", cleaned)
    cleaned = re.sub(r"\{\s*\}", " ", cleaned)

    # 8. Normaliser les guillemets et tirets typographiques
    cleaned = cleaned.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    cleaned = cleaned.replace("–", "-").replace("—", "-")

    # 9. Nettoyage de ponctuation résiduelle en début/fin et espaces multiples
    cleaned = re.sub(r"^[\s\-–—\|\/,\.:;]+|[\s\-–—\|\/,\.:;]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned if cleaned else (title.strip() or "Non spécifié")


def normalize_offer_fields(offer: Dict[str, Any]) -> Dict[str, Any]:
    """Nettoie et normalise l'ensemble des champs d'une offre (titre, entreprise, ville, contrat, etc.) hors IA."""
    if not offer or not isinstance(offer, dict):
        return offer

    cleaned = dict(offer)

    # 1. Intitulé de poste
    if "poste" in cleaned and cleaned["poste"]:
        cleaned["poste"] = clean_job_title_syntax(cleaned["poste"])

    # 2. Entreprise
    if "entreprise" in cleaned and cleaned["entreprise"]:
        ent = clean_html_entities_and_tags(str(cleaned["entreprise"]))
        cleaned["entreprise"] = ent if ent else "Non spécifié"

    # 3. Localisation
    if "localisation" in cleaned and cleaned["localisation"]:
        loc = clean_html_entities_and_tags(str(cleaned["localisation"]))
        cleaned["localisation"] = normalize_city(loc) if loc else "Non spécifié"

    # 4. Type de contrat, salaire, mode de travail
    for field in ("type_contrat", "salaire", "mode_travail"):
        if field in cleaned and cleaned[field]:
            val = clean_html_entities_and_tags(str(cleaned[field]))
            cleaned[field] = val if val else "Non spécifié"

    # 5. Description
    if "description" in cleaned and cleaned["description"]:
        desc = str(cleaned["description"])
        if "<" in desc or "&" in desc:
            from app.services.ats.router import clean_html_to_text
            cleaned["description"] = clean_html_to_text(desc)

    # 6. Recalcul de la clé unique
    cleaned["unique_key"] = compute_unique_key(
        company=cleaned.get("entreprise", ""),
        position=cleaned.get("poste", ""),
        location=cleaned.get("localisation"),
        url=cleaned.get("url"),
    )

    return cleaned



def extract_seniority(title: Optional[str], description: Optional[str] = None) -> Optional[str]:
    """Couche 2 : Extraction du niveau de séniorité standardisé.

    Ordre de priorité:
    - intern: Stage, Alternance, Apprentissage, Intern
    - director: Director, Directeur, VP, Head of, Chief, CTO
    - lead: Lead, Principal, Staff, Tech Lead, Architecte
    - senior: Senior, Sr, Confirmé+, 5+ ans
    - junior: Junior, Jr, Débutant, Graduate, Entry-level
    - mid: Confirmé, Intermédiaire, Mid
    """
    text_to_check = (title or "").lower()

    patterns = [
        ("intern", r"\b(stage|stagiaire|alternance|alternant|alternante|apprenti|apprentie|apprentissage|intern|internship)\b"),
        ("director", r"\b(director|directeur|directrice|head of|vp|chief|cto|cpo|ceo|coo)\b"),
        ("lead", r"\b(lead|principal|staff|tech lead|architecte|architect|team lead)\b"),
        ("senior", r"\b(senior|sr\.?|exp[ée]riment[ée]|5\+?\s*ans)\b"),
        ("junior", r"\b(junior|jr\.?|d[ée]butant|d[ée]butante|graduate|entry[\s\-]level|0[\s\-]2\s*ans)\b"),
        ("mid", r"\b(mid|confirm[ée]|interm[ée]diaire|2[\s\-]5\s*ans)\b"),
    ]

    for level, pat in patterns:
        if re.search(pat, text_to_check, flags=re.IGNORECASE):
            return level

    if description and isinstance(description, str):
        desc_snippet = description[:500].lower()
        for level, pat in patterns:
            if re.search(pat, desc_snippet, flags=re.IGNORECASE):
                return level

    return None


FRENCH_ENGLISH_STOPWORDS: Set[str] = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "en", "pour", "et", "ou",
    "qui", "que", "dans", "sur", "avec", "par", "au", "aux", "ce", "cette", "ces",
    "est", "sont", "nous", "vous", "ils", "elles", "notre", "votre", "leur", "plus",
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "by",
    "is", "are", "we", "you", "they", "our", "your", "their", "of", "from", "as",
}


def jaccard_description_similarity(desc1: Optional[str], desc2: Optional[str]) -> float:
    """Couche 3 : Calcule la similarité de Jaccard sur les tokens signifiants des descriptions."""
    if not desc1 or not desc2:
        return 0.0

    def tokenize(text: str) -> Set[str]:
        words = re.findall(r"\b[a-zA-ZÀ-ÿ0-9]{3,}\b", text.lower())
        return {w for w in words if w not in FRENCH_ENGLISH_STOPWORDS}

    tokens1 = tokenize(desc1)
    tokens2 = tokenize(desc2)

    if len(tokens1) < 15 or len(tokens2) < 15:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return intersection / union if union > 0 else 0.0


def are_offers_duplicates(
    offer1: Dict[str, Any],
    offer2: Dict[str, Any],
    title_similarity_threshold: float = 0.82,
    jaccard_threshold: float = 0.65,
) -> bool:
    """Couche 3 : Évalue si deux offres représentent le même poste (multidiffusion ou repost)."""
    # 1. URLs identiques
    url1 = (offer1.get("url") or "").strip()
    url2 = (offer2.get("url") or "").strip()
    if url1 and url2 and url1 == url2:
        return True

    # 2. Vérification entreprise
    c1 = normalize_company(offer1.get("entreprise", "")).lower()
    c2 = normalize_company(offer2.get("entreprise", "")).lower()
    if not c1 or not c2 or c1 == "non spécifié" or c2 == "non spécifié":
        return False

    c_match = (c1 == c2) or (SequenceMatcher(None, c1, c2).ratio() >= 0.85)
    if not c_match:
        return False

    # 3. Vérification compatibilité ville / localisation
    loc1 = normalize_city(offer1.get("localisation", "")).lower()
    loc2 = normalize_city(offer2.get("localisation", "")).lower()
    non_spec = {"non spécifié", "france", "télétravail", "remote"}
    if loc1 not in non_spec and loc2 not in non_spec and loc1 != loc2:
        return False

    # 4. Similarité sur l'intitulé de poste nettoyé (Couche 1)
    p1 = clean_job_title_syntax(offer1.get("poste", "")).lower()
    p2 = clean_job_title_syntax(offer2.get("poste", "")).lower()

    if p1 == p2 and p1 != "non spécifié":
        return True

    ratio_title = SequenceMatcher(None, p1, p2).ratio()
    if ratio_title >= title_similarity_threshold:
        return True

    # 5. Similarité textuelle sur description (Jaccard)
    d1 = offer1.get("description") or ""
    d2 = offer2.get("description") or ""
    jaccard = jaccard_description_similarity(d1, d2)
    if jaccard >= jaccard_threshold and ratio_title >= 0.45:
        return True

    return False


def get_source_priority(url: Optional[str]) -> int:
    """Couche 4 : Hiérarchie de confiance et de pérennité des sources.

    100 = ATS direct entreprise (Greenhouse, Lever, Workable, Ashby, etc.)
     80 = Job boards qualifiés (Welcome to the Jungle, Apec, France Travail)
     50 = Agrégateurs généralistes (LinkedIn, HelloWork, Indeed, Cadremploi)
     20 = Autre / Inconnu
    """
    if not url:
        return 20
    url_lower = url.lower()

    ats_indicators = [
        "greenhouse.io", "lever.co", "workable.com", "ashbyhq.com",
        "teamtailor.com", "recruitee.com", "personio", "myworkdayjobs.com",
        "smartrecruiters.com", "taleo.net", "icims.com", "bamboohr.com",
        "breezy.hr", "flatchr.io", "jobs2web.com",
    ]
    if any(ats in url_lower for ats in ats_indicators):
        return 100

    if any(jb in url_lower for jb in ("welcometothejungle.com", "apec.fr", "francetravail.fr")):
        return 80

    if any(agg in url_lower for agg in ("linkedin.com", "hellowork.com", "indeed.com", "cadremploi.fr", "meteojob.com", "glassdoor")):
        return 50

    return 20


def merge_multidiffusion_offers(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    """Couche 4 : Fusionne deux offres doublons en conservant les données les plus riches."""
    p_copy = dict(primary)
    s_copy = dict(secondary)

    # 1. Sélection de l'URL primaire selon la hiérarchie de priorité
    p_url = p_copy.get("url") or ""
    s_url = s_copy.get("url") or ""

    p_prio = get_source_priority(p_url)
    s_prio = get_source_priority(s_url)

    if s_prio > p_prio:
        chosen_primary_url = s_url
        other_url = p_url
        p_copy["poste"] = clean_job_title_syntax(s_copy.get("poste") or p_copy.get("poste"))
    else:
        chosen_primary_url = p_url or s_url
        other_url = s_url if s_url != chosen_primary_url else ""
        p_copy["poste"] = clean_job_title_syntax(p_copy.get("poste") or s_copy.get("poste"))

    p_copy["url"] = chosen_primary_url

    # 2. Consolidation des URLs alternatives
    existing_alts = set(p_copy.get("alternative_urls") or [])
    if s_copy.get("alternative_urls"):
        existing_alts.update(s_copy["alternative_urls"])
    if other_url and other_url != chosen_primary_url:
        existing_alts.add(other_url)
    existing_alts.discard(chosen_primary_url)
    p_copy["alternative_urls"] = sorted(list(existing_alts))

    # 3. Consolidation du salaire
    p_sal = str(p_copy.get("salaire") or "").strip()
    s_sal = str(s_copy.get("salaire") or "").strip()
    if p_sal in ("", "None", "Non spécifié") and s_sal not in ("", "None", "Non spécifié"):
        p_copy["salaire"] = s_sal

    # 4. Consolidation du type de contrat
    p_contrat = str(p_copy.get("type_contrat") or "").strip()
    s_contrat = str(s_copy.get("type_contrat") or "").strip()
    if p_contrat in ("", "None", "Non spécifié") and s_contrat not in ("", "None", "Non spécifié"):
        p_copy["type_contrat"] = s_contrat

    # 5. Consolidation de la localisation
    p_loc = str(p_copy.get("localisation") or "").strip()
    s_loc = str(s_copy.get("localisation") or "").strip()
    if p_loc in ("", "None", "Non spécifié", "France") and s_loc not in ("", "None", "Non spécifié"):
        p_copy["localisation"] = s_loc

    # 6. Description : garder la plus détaillée
    p_desc = str(p_copy.get("description") or "").strip()
    s_desc = str(s_copy.get("description") or "").strip()
    if len(s_desc) > len(p_desc):
        p_copy["description"] = s_desc

    # 7. Compétences clés : union
    p_skills = set(p_copy.get("competences_cles") or [])
    s_skills = set(s_copy.get("competences_cles") or [])
    combined_skills = p_skills | s_skills
    if combined_skills:
        p_copy["competences_cles"] = sorted(list(combined_skills))

    # 8. Séniorité et Titre canonique
    if not p_copy.get("seniority_level"):
        p_copy["seniority_level"] = s_copy.get("seniority_level") or extract_seniority(
            p_copy.get("poste"), p_copy.get("description")
        )
    if not p_copy.get("canonical_title"):
        p_copy["canonical_title"] = s_copy.get("canonical_title")

    # 9. Horodatages : plus ancien created_at
    if s_copy.get("created_at") and p_copy.get("created_at"):
        try:
            p_copy["created_at"] = min(p_copy["created_at"], s_copy["created_at"])
        except Exception:
            pass

    # 10. Préservation de l'évaluation / scoring
    if not p_copy.get("evaluation") and s_copy.get("evaluation"):
        p_copy["evaluation"] = s_copy["evaluation"]

    # 11. Préservation de l'interaction utilisateur (favori, archivé, postulé)
    if not p_copy.get("user_interaction") and s_copy.get("user_interaction"):
        p_copy["user_interaction"] = s_copy["user_interaction"]

    # 12. Clé canonique d'unicité garantie
    p_copy["unique_key"] = compute_unique_key(
        company=p_copy.get("entreprise", ""),
        position=p_copy.get("poste", ""),
        location=p_copy.get("localisation"),
    )

    return p_copy


def deduplicate_and_merge_offers(
    offers: List[Dict[str, Any]],
    title_similarity_threshold: float = 0.82,
    jaccard_threshold: float = 0.65,
) -> List[Dict[str, Any]]:
    """Couche 4 : Déduplication multi-critères et fusion des offres multidiffusées."""
    if not offers:
        return []

    company_groups: Dict[str, List[Dict[str, Any]]] = {}
    for offer in offers:
        comp_key = normalize_company(offer.get("entreprise", "")).lower()
        if not comp_key or comp_key == "non spécifié":
            comp_key = f"unknown_{id(offer)}"
        company_groups.setdefault(comp_key, []).append(offer)

    consolidated_offers: List[Dict[str, Any]] = []

    for _comp_key, group in company_groups.items():
        if len(group) == 1:
            consolidated_offers.append(group[0])
            continue

        survivors: List[Dict[str, Any]] = []
        for candidate in group:
            matched_idx = -1
            for idx, existing in enumerate(survivors):
                if are_offers_duplicates(
                    candidate,
                    existing,
                    title_similarity_threshold=title_similarity_threshold,
                    jaccard_threshold=jaccard_threshold,
                ):
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                survivors[matched_idx] = merge_multidiffusion_offers(survivors[matched_idx], candidate)
            else:
                survivors.append(candidate)

        consolidated_offers.extend(survivors)

    return consolidated_offers


