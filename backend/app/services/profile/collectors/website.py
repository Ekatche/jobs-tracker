"""Collecte du site personnel du candidat.

Un CV tient sur deux pages, un site n'a pas cette limite : c'est la source la
plus riche en expériences et en projets. On lit le sitemap pour savoir quoi
crawler plutôt que de deviner les chemins.

Le sitemap d'un site peut citer un domaine voisin de celui que l'utilisateur a
fourni (migration, environnement de build, alias historique...). On ne suit
jamais ce domaine-là : seuls les chemins sont conservés, puis reconstruits sur
le schéma et l'hôte de `base_url`. Suivre le domaine cité par le sitemap
ouvrirait une porte SSRF — le serveur irait chercher une page sur un hôte que
l'utilisateur n'a jamais donné.
"""

import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from litellm import acompletion

from app.services.profile.urls import validate_public_url_async

# `letter_llm` vit dans job_trackers/src/job_trackers, hors du package `app` :
# comme les autres consommateurs du monorepo (routers/applications.py,
# routers/cover_letters.py), on ajoute son répertoire à sys.path avant
# l'import plutôt que de deviner un chemin de package absolu ou d'inventer un
# préfixe `job_trackers.` que le reste du monorepo n'utilise pas.
_JOB_TRACKERS_SRC = Path(__file__).resolve().parents[4] / "job_trackers" / "src" / "job_trackers"
if str(_JOB_TRACKERS_SRC) not in sys.path:
    sys.path.insert(0, str(_JOB_TRACKERS_SRC))

from letter_llm import get_letter_llm, ROLE_TEMPERATURES  # noqa: E402

logger = logging.getLogger(__name__)

MAX_PAGES = 12
MAX_REDIRECTS = 5
FETCH_TIMEOUT = 10.0
FALLBACK_PATHS = ("", "/experience", "/work", "/projects", "/formation", "/competences", "/about")
SKIP_PATTERNS = ("/contact", "/mentions", "/legal", "/privacy", "/blog/tag")

# Doit rester en phase avec `CandidateProject.context` (Literal fermé,
# app/models.py). Le prompt d'extraction énumère déjà ces 4 valeurs, mais un
# prompt n'est pas une garantie : un LLM peut renvoyer une valeur hors
# énumération malgré la consigne.
_VALID_PROJECT_CONTEXTS = {"perso", "client", "recherche", "consortium"}


def _coerce_project_contexts(payload: Dict[str, Any]) -> None:
    """Force `context` à "perso" pour tout projet dont la valeur n'est pas
    l'une des 4 admises par le modèle Pydantic en aval.

    Sans cette coercition défensive, une valeur hors énumération (ex.
    "personnel", "freelance") fait échouer `CandidateProfile.model_validate`
    dans `_store_source` et retourne 502 sur l'import du site — la source la
    plus riche du profil. Modifie `payload` en place.
    """
    for project in payload.get("projects", []) or []:
        if project.get("context") not in _VALID_PROJECT_CONTEXTS:
            project["context"] = "perso"


async def _default_fetch(url: str, total_timeout: float = FETCH_TIMEOUT) -> Optional[str]:
    """Récupère `url`, en validant manuellement chaque redirection.

    `follow_redirects=True` d'httpx suivrait une redirection transparente vers
    n'importe quelle adresse — y compris une IP privée ou l'endpoint de
    métadonnées cloud — avant que ce code n'ait la moindre chance de la
    contrôler. `validate_public_url` n'aurait alors servi qu'à valider
    `base_url`, pas la destination réelle de la requête. On suit donc les
    redirections nous-mêmes, en revalidant l'hôte à chaque saut, plafonné à
    `MAX_REDIRECTS` pour ne jamais boucler indéfiniment. Une redirection
    rejetée ou une boucle trop longue rend `None` (échec de fetch, pas une
    exception) : le sitemap est optionnel, `discover_pages` doit pouvoir
    retomber sur ses chemins par défaut.

    `total_timeout` borne la durée de la chaîne entière, pas chaque requête
    isolément : passer `timeout=10.0` à `httpx.AsyncClient` ne borne que
    chaque `get()` pris séparément, donc une chaîne de `MAX_REDIRECTS` sauts
    lents-mais-sous-la-limite pouvait auparavant prendre jusqu'à
    `(MAX_REDIRECTS + 1) × 10s` — six fois le budget prévu. Un budget total
    (`deadline`) est donc calculé une fois avant la boucle, et le temps
    restant est reporté comme timeout de chaque requête individuelle ; le
    budget épuisé avant même de tenter un saut supplémentaire coupe court
    immédiatement plutôt que de laisser la boucle continuer.
    """
    current = url
    deadline = time.monotonic() + total_timeout
    try:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.info("budget de temps épuisé pour %s", url)
                    return None
                response = await client.get(current, timeout=remaining)
                if response.status_code == 200:
                    return response.text
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        return None
                    next_url = urljoin(current, location)
                    try:
                        current = await validate_public_url_async(next_url)
                    except ValueError as exc:
                        logger.info(
                            "redirection refusée depuis %s vers %s : %s",
                            current,
                            next_url,
                            exc,
                        )
                        return None
                    continue
                return None
    except httpx.HTTPError as exc:
        logger.info("sitemap indisponible sur %s: %s", url, exc)
        return None
    logger.info("trop de redirections depuis %s (plafond %s)", url, MAX_REDIRECTS)
    return None


_STATIC_ASSET_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".mjs", ".pdf", ".zip", ".tar", ".gz",
    ".mp4", ".mov", ".avi", ".mp3", ".wav", ".woff", ".woff2", ".ttf", ".eot",
)


def _extract_internal_links_from_html(html: str, base_url: str) -> List[str]:
    """Extrait tous les liens href d'une page HTML appartenant au même domaine."""
    if not html:
        return []
    base_parsed = urlparse(base_url)
    raw_hrefs = re.findall(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    discovered_paths: List[str] = []
    for href in raw_hrefs:
        clean_href = href.strip()
        if not clean_href or clean_href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        joined = urljoin(base_url + "/", clean_href)
        parsed = urlparse(joined)
        # Ne conserver que les liens internes au même domaine
        if parsed.netloc.lower() != base_parsed.netloc.lower():
            continue
        path = parsed.path or "/"
        clean_path = path.lower()
        if any(clean_path.endswith(ext) for ext in _STATIC_ASSET_EXTENSIONS):
            continue
        if any(skip in clean_path for skip in SKIP_PATTERNS):
            continue
        if path not in discovered_paths:
            discovered_paths.append(path)
    return discovered_paths


async def discover_pages(
    base_url: str,
    fetch: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
) -> List[str]:
    """Liste les pages à crawler, plafonnée à MAX_PAGES.

    Les chemins viennent du sitemap quand il existe, mais aussi des liens HTML
    découverts sur la page d'accueil pour couvrir les portfolios dynamiques
    ou statiques sans sitemap. Si aucun lien n'est trouvé, on retombe sur la
    liste de chemins usuels (FALLBACK_PATHS).
    """
    base = (await validate_public_url_async(base_url)).rstrip("/")
    fetch = fetch or _default_fetch

    sitemap = await fetch(f"{base}/sitemap.xml")
    paths: List[str] = []
    if sitemap:
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap):
            path = urlparse(loc).path or "/"
            if path not in paths:
                paths.append(path)

    # Extraction des liens internes depuis la page d'accueil
    root_html = await fetch(base)
    if root_html:
        for p in _extract_internal_links_from_html(root_html, base):
            if p not in paths:
                paths.append(p)

    if not paths:
        paths = list(FALLBACK_PATHS)

    pages: List[str] = []
    for path in paths:
        if any(skip in path.lower() for skip in SKIP_PATTERNS):
            continue
        url = base if path in ("", "/") else urljoin(base + "/", path.lstrip("/"))
        if url not in pages:
            pages.append(url)
        if len(pages) >= MAX_PAGES:
            break
    return pages


async def _extract_with_llm(pages_markdown: Dict[str, str]) -> Dict[str, Any]:
    llm = get_letter_llm("site_extractor")
    corpus = "\n\n".join(
        f"### Page : {url}\n{markdown[:6000]}" for url, markdown in pages_markdown.items()
    )
    prompt = f"""Voici le contenu de plusieurs pages du site personnel d'un candidat.
Extrais les faits, sans rien inventer et sans reformuler en langage commercial.

{corpus}

Réponds uniquement par un objet JSON avec ces clés :
- "identity": {{"headline": titre professionnel, "summary": résumé factuel}}
- "experiences": [{{"company", "role", "location", "contract", "start", "end", "missions": [], "stack": [], "achievements": []}}]
- "projects": [{{"name", "description", "context" (une valeur EXACTE parmi: "perso", "client", "recherche", "consortium"), "stack": [], "url"}}]
- "education": [{{"school", "degree", "years"}}]
- "certifications": [{{"name", "issuer", "year"}}]
- "skills": {{"catégorie": ["compétence"]}}
Pour "start" et "end", recopie la date telle qu'écrite sur la page.
Si une information est absente, rends une liste vide."""

    response = await acompletion(
        model=llm.model,
        api_key=llm.api_key,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=ROLE_TEMPERATURES["site_extractor"],
        drop_params=True,
    )
    content = response.choices[0].message.content.strip()
    content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
    return json.loads(content)


async def collect_website(
    base_url: str,
    crawler=None,
    extract: Optional[Callable[[Dict[str, str]], Awaitable[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Rend un payload de source prêt à être rangé dans `sources.website`.

    `crawler` et `extract` ne sont résolus vers leurs implémentations réelles
    (Crawl4AI, LLM) qu'à l'intérieur de la fonction : importer Crawl4AI au
    chargement du module rendrait la suite de tests dépendante d'un
    navigateur.
    """
    pages = await discover_pages(base_url)
    extract = extract or _extract_with_llm

    if crawler is None:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler(verbose=False) as instance:
            results = await instance.arun_many(pages)
    else:
        results = await crawler.arun_many(pages)

    markdown_by_url: Dict[str, str] = {}
    for result in results:
        markdown = getattr(result, "markdown", None)
        if not markdown:
            continue
        url = getattr(result, "url", "")
        # Crawl4AI suit ses propres redirections internes sans repasser par
        # `validate_public_url` : `result.url` peut donc différer de l'URL
        # déjà validée dans `pages`. Sans cette revalidation, une page qui
        # redirige vers une IP privée ou l'endpoint de métadonnées cloud
        # contournerait le filtre anti-SSRF appliqué partout ailleurs dans ce
        # fichier. Un rejet ici est un fetch manqué (comme un fetch qui a
        # échoué), pas une exception qui interrompt la boucle.
        try:
            url = await validate_public_url_async(url)
        except ValueError as exc:
            logger.info("page crawlée rejetée (URL finale non publique) %s : %s", url, exc)
            continue
        markdown_by_url[url] = str(markdown)

    if not markdown_by_url:
        raise ValueError("Aucune page exploitable sur ce site")

    payload = await extract(markdown_by_url)
    _coerce_project_contexts(payload)

    # Le prompt LLM niche "headline"/"summary" sous "identity" (forme
    # d'extraction raisonnable), mais `build_profile_from_sources` (merge.py)
    # les lit à la racine du dict de source via `_first_non_empty("headline",
    # ...)` / `_first_non_empty("summary", ...)`. Sans cet aplatissement, les
    # deux champs seraient silencieusement perdus pour la source "website".
    identity = payload.pop("identity", {}) or {}
    payload["headline"] = identity.get("headline", "")
    payload["summary"] = identity.get("summary", "")

    payload["_pages"] = list(markdown_by_url)
    return payload
