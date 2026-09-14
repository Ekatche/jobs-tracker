"""Tests pour le collecteur du site personnel du candidat.

Comme pour `test_profile_urls.py`, `socket.getaddrinfo` est remplacé par un
faux résolveur en mémoire (fixture autouse) afin qu'aucun test ne dépende du
DNS ou du réseau réel. `discover_pages` et `collect_website` reçoivent en plus
de fausses implémentations de `fetch` / `crawler` / `extract` pour ne jamais
émettre de vraie requête HTTP.
"""

import ipaddress
import socket
from types import SimpleNamespace

import pytest

from app.services.profile.collectors.website import collect_website, discover_pages

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://elielkatche.dev</loc></url>
  <url><loc>https://elielkatche.dev/work</loc></url>
  <url><loc>https://elielkatche.dev/experience</loc></url>
  <url><loc>https://elielkatche.dev/formation</loc></url>
  <url><loc>https://elielkatche.dev/competences</loc></url>
  <url><loc>https://elielkatche.dev/contact</loc></url>
</urlset>
"""

# Mêmes hôtes de test que test_profile_urls.py : table DNS en mémoire, tout
# hôte absent échoue explicitement comme un vrai DNS pour un nom inconnu.
_FAKE_DNS = {
    "www.elielkatche.me": "76.76.21.21",
    "example.com": "93.184.216.34",
}


@pytest.fixture(autouse=True)
def fake_resolver(monkeypatch):
    """Remplace socket.getaddrinfo par un résolveur en mémoire, sans réseau."""

    def fake_getaddrinfo(host, *args, **kwargs):
        bare_host = host.strip("[]") if host else host
        try:
            ip = ipaddress.ip_address(bare_host)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (str(ip), 0))]
        except ValueError:
            pass
        if host in _FAKE_DNS:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_FAKE_DNS[host], 0))]
        raise socket.gaierror(f"faux DNS : hôte inconnu {host}")

    monkeypatch.setattr("app.services.profile.urls.socket.getaddrinfo", fake_getaddrinfo)


@pytest.mark.asyncio
async def test_sitemap_paths_are_rewritten_on_the_requested_domain():
    """Le sitemap du site cite un autre domaine : on ne doit pas le suivre."""

    async def fake_fetch(url):
        return SITEMAP if url.endswith("sitemap.xml") else None

    pages = await discover_pages("https://www.elielkatche.me", fetch=fake_fetch)
    assert all(p.startswith("https://www.elielkatche.me") for p in pages)
    assert "https://www.elielkatche.me/experience" in pages
    assert "https://www.elielkatche.me/contact" not in pages  # page sans substance


@pytest.mark.asyncio
async def test_fallback_paths_when_no_sitemap():
    async def fake_fetch(url):
        return None

    pages = await discover_pages("https://example.com", fetch=fake_fetch)
    assert "https://example.com" in pages
    assert "https://example.com/experience" in pages


@pytest.mark.asyncio
async def test_page_count_is_capped():
    many = "".join(
        f"<url><loc>https://example.com/p{i}</loc></url>" for i in range(50)
    )

    async def fake_fetch(url):
        return f"<urlset>{many}</urlset>"

    pages = await discover_pages("https://example.com", fetch=fake_fetch)
    assert len(pages) <= 12


@pytest.mark.asyncio
async def test_discovered_urls_are_deduplicated_and_ordered():
    """Le sitemap peut citer deux fois le même chemin ; l'ordre doit rester stable."""

    sitemap_with_duplicate = """<urlset>
      <url><loc>https://elielkatche.dev/experience</loc></url>
      <url><loc>https://elielkatche.dev/work</loc></url>
      <url><loc>https://elielkatche.dev/experience</loc></url>
    </urlset>"""

    async def fake_fetch(url):
        return sitemap_with_duplicate

    pages = await discover_pages("https://www.elielkatche.me", fetch=fake_fetch)
    assert pages == [
        "https://www.elielkatche.me/experience",
        "https://www.elielkatche.me/work",
    ]


class FakeCrawler:
    """Simule `AsyncWebCrawler.arun_many` sans navigateur ni réseau."""

    def __init__(self, results):
        self._results = results
        self.called_with = None

    async def arun_many(self, urls):
        self.called_with = list(urls)
        return self._results


@pytest.mark.asyncio
async def test_collect_website_passes_extracted_markdown_and_adds_pages(monkeypatch):
    """`collect_website` doit renvoyer tel quel le payload de `extract`, en y
    ajoutant `_pages` (les URLs réellement exploitées, pas juste découvertes)."""

    async def fake_fetch(url):
        return None  # pas de sitemap -> chemins de repli

    monkeypatch.setattr(
        "app.services.profile.collectors.website._default_fetch", fake_fetch
    )

    results = [
        SimpleNamespace(url="https://example.com", markdown="# Accueil"),
        SimpleNamespace(url="https://example.com/experience", markdown="# Expérience"),
        SimpleNamespace(url="https://example.com/work", markdown=None),  # page vide
    ]
    crawler = FakeCrawler(results)

    expected_payload = {
        "identity": {"headline": "Développeur", "summary": "Résumé factuel"},
        "experiences": [{"company": "Acme", "role": "Dev", "start": "2021"}],
        "projects": [{"name": "Projet X", "description": "Un projet", "stack": ["Python"]}],
        "education": [],
        "certifications": [],
        "skills": {"langages": ["Python"]},
    }

    captured_markdown = {}

    async def fake_extract(markdown_by_url):
        captured_markdown.update(markdown_by_url)
        return dict(expected_payload)

    payload = await collect_website(
        "https://example.com", crawler=crawler, extract=fake_extract
    )

    assert crawler.called_with is not None  # arun_many a bien reçu les pages découvertes
    assert captured_markdown == {
        "https://example.com": "# Accueil",
        "https://example.com/experience": "# Expérience",
    }
    for key, value in expected_payload.items():
        assert payload[key] == value
    assert payload["_pages"] == [
        "https://example.com",
        "https://example.com/experience",
    ]


@pytest.mark.asyncio
async def test_collect_website_raises_when_no_page_has_markdown(monkeypatch):
    async def fake_fetch(url):
        return None

    monkeypatch.setattr(
        "app.services.profile.collectors.website._default_fetch", fake_fetch
    )

    results = [
        SimpleNamespace(url="https://example.com", markdown=None),
        SimpleNamespace(url="https://example.com/experience", markdown=""),
    ]
    crawler = FakeCrawler(results)

    async def fake_extract(markdown_by_url):
        raise AssertionError("extract ne doit pas être appelé sans page exploitable")

    with pytest.raises(ValueError):
        await collect_website(
            "https://example.com", crawler=crawler, extract=fake_extract
        )
