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
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from litellm import acompletion

from app.services.profile.urls import validate_public_url

logger = logging.getLogger(__name__)

MAX_PAGES = 12
FALLBACK_PATHS = ("", "/experience", "/work", "/projects", "/formation", "/competences", "/about")
SKIP_PATTERNS = ("/contact", "/mentions", "/legal", "/privacy", "/blog/tag")
MODEL = "gemini/gemini-3.8-flash"


async def _default_fetch(url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.text
    except httpx.HTTPError as exc:
        logger.info("sitemap indisponible sur %s: %s", url, exc)
    return None


async def discover_pages(
    base_url: str,
    fetch: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
) -> List[str]:
    """Liste les pages à crawler, plafonnée à MAX_PAGES.

    Les chemins viennent du sitemap quand il existe, mais toujours résolus sur
    le domaine demandé : un sitemap peut citer un domaine voisin. Si le
    sitemap est absent ou inexploitable, on retombe sur une liste de chemins
    usuels plutôt que de renvoyer une liste vide — un site sans sitemap doit
    quand même produire des pages.
    """
    base = validate_public_url(base_url).rstrip("/")
    fetch = fetch or _default_fetch

    sitemap = await fetch(f"{base}/sitemap.xml")
    paths: List[str] = []
    if sitemap:
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap):
            path = urlparse(loc).path or "/"
            paths.append(path)
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
    corpus = "\n\n".join(
        f"### Page : {url}\n{markdown[:6000]}" for url, markdown in pages_markdown.items()
    )
    prompt = f"""Voici le contenu de plusieurs pages du site personnel d'un candidat.
Extrais les faits, sans rien inventer et sans reformuler en langage commercial.

{corpus}

Réponds uniquement par un objet JSON avec ces clés :
- "identity": {{"headline": titre professionnel, "summary": résumé factuel}}
- "experiences": [{{"company", "role", "location", "contract", "start", "end", "missions": [], "stack": [], "achievements": []}}]
- "projects": [{{"name", "description", "context", "stack": [], "url"}}]
- "education": [{{"school", "degree", "years"}}]
- "certifications": [{{"name", "issuer", "year"}}]
- "skills": {{"catégorie": ["compétence"]}}
Pour "start" et "end", recopie la date telle qu'écrite sur la page.
Si une information est absente, rends une liste vide."""

    response = await acompletion(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
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
        if markdown:
            markdown_by_url[getattr(result, "url", "")] = str(markdown)

    if not markdown_by_url:
        raise ValueError("Aucune page exploitable sur ce site")

    payload = await extract(markdown_by_url)
    payload["_pages"] = list(markdown_by_url)
    return payload
