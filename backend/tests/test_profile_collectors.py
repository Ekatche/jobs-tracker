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

import app.services.profile.collectors.website as website
from app.services.profile.collectors.github import collect_github, parse_github_username
from app.services.profile.collectors.website import (
    _default_fetch,
    collect_website,
    discover_pages,
)

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
        if key == "identity":
            continue  # aplati à la racine, voir assertions ci-dessous
        assert payload[key] == value
    assert payload["_pages"] == [
        "https://example.com",
        "https://example.com/experience",
    ]

    # headline/summary doivent être aplatis à la racine du payload : c'est ce
    # que `build_profile_from_sources` (merge.py) lit réellement — un
    # "identity" niché serait silencieusement ignoré en aval.
    assert "identity" not in payload
    assert payload["headline"] == "Développeur"
    assert payload["summary"] == "Résumé factuel"


@pytest.mark.asyncio
async def test_collect_website_flattens_identity_even_without_other_fields(monkeypatch):
    """Régression : le payload de `extract` peut ne contenir que `identity`."""

    async def fake_fetch(url):
        return None

    monkeypatch.setattr(website, "_default_fetch", fake_fetch)

    results = [SimpleNamespace(url="https://example.com", markdown="# Accueil")]
    crawler = FakeCrawler(results)

    async def fake_extract(markdown_by_url):
        return {"identity": {"headline": "X", "summary": "Y"}}

    payload = await collect_website(
        "https://example.com", crawler=crawler, extract=fake_extract
    )

    assert payload["headline"] == "X"
    assert payload["summary"] == "Y"
    assert "identity" not in payload


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


class _FakeResponse:
    def __init__(self, status_code, headers=None, text=""):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text


def _fake_async_client_factory(responses_by_url, calls=None):
    """Fabrique un faux `httpx.AsyncClient` piloté par une table URL -> réponse.

    `calls`, si fourni, accumule chaque URL réellement demandée : ça permet à
    un test d'affirmer qu'une URL n'a *jamais* été atteinte, pas seulement que
    le résultat final est `None`.
    """

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, **kwargs):
            if calls is not None:
                calls.append(url)
            if url not in responses_by_url:
                raise AssertionError(f"URL inattendue demandée : {url}")
            return responses_by_url[url]

    return _FakeAsyncClient


@pytest.mark.asyncio
async def test_default_fetch_follows_redirect_to_public_url(monkeypatch):
    responses = {
        "https://example.com/sitemap.xml": _FakeResponse(
            302, headers={"location": "https://example.com/sitemap-final.xml"}
        ),
        "https://example.com/sitemap-final.xml": _FakeResponse(
            200, text="<urlset></urlset>"
        ),
    }
    monkeypatch.setattr(website.httpx, "AsyncClient", _fake_async_client_factory(responses))

    result = await _default_fetch("https://example.com/sitemap.xml")
    assert result == "<urlset></urlset>"


@pytest.mark.asyncio
async def test_default_fetch_rejects_redirect_to_private_ip(monkeypatch):
    """Une redirection vers une IP privée/loopback ne doit jamais être suivie
    ni faire fuiter la réponse finale : c'est exactement le cas SSRF que
    `validate_public_url` doit bloquer, y compris au milieu d'une chaîne de
    redirections initiée par un hôte par ailleurs public."""

    calls: list[str] = []
    responses = {
        "https://example.com/sitemap.xml": _FakeResponse(
            302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
        ),
        # Si le code suivait la redirection, il demanderait cette URL et
        # obtiendrait ces "métadonnées" : la présence de cette entrée sert à
        # prouver qu'elle n'est jamais consultée, pas juste que le retour est vide.
        "http://169.254.169.254/latest/meta-data/": _FakeResponse(
            200, text="secret-metadata"
        ),
    }
    monkeypatch.setattr(
        website.httpx, "AsyncClient", _fake_async_client_factory(responses, calls)
    )

    result = await _default_fetch("https://example.com/sitemap.xml")

    assert result is None
    assert "http://169.254.169.254/latest/meta-data/" not in calls


@pytest.mark.asyncio
async def test_default_fetch_stops_after_max_redirects(monkeypatch):
    """Une boucle de redirection ne doit ni bloquer indéfiniment ni lever,
    juste échouer proprement (le sitemap est optionnel)."""

    responses = {
        "https://example.com/a": _FakeResponse(
            302, headers={"location": "https://example.com/b"}
        ),
        "https://example.com/b": _FakeResponse(
            302, headers={"location": "https://example.com/a"}
        ),
    }
    monkeypatch.setattr(website.httpx, "AsyncClient", _fake_async_client_factory(responses))

    result = await _default_fetch("https://example.com/a")
    assert result is None


@pytest.mark.asyncio
async def test_default_fetch_enforces_total_time_budget_across_redirect_chain(monkeypatch):
    """Le budget de temps doit courir sur toute la chaîne, pas requête par
    requête : `httpx.AsyncClient(timeout=10.0)` ne borne que chaque `get()`
    pris isolément, donc une chaîne de redirections individuellement rapides
    (sous la limite par requête) pouvait auparavant accumuler jusqu'à
    `(MAX_REDIRECTS + 1) x 10s`, six fois le budget prévu.

    Une horloge factice avance de 4s "simulées" à chaque requête (au lieu
    d'un vrai `asyncio.sleep`, pour que le test reste instantané et
    déterministe). Avec un budget total de 10s, la boucle doit s'arrêter
    après 3 requêtes (temps simulé : 0s, 4s, 8s -> la 4e tentative voit un
    temps restant négatif et retourne `None` immédiatement) plutôt que
    d'exécuter les 6 sauts que `MAX_REDIRECTS` autoriserait à lui seul.
    """

    class _FakeClock:
        def __init__(self):
            self.now = 0.0

        def monotonic(self):
            return self.now

        def advance(self, seconds):
            self.now += seconds

    clock = _FakeClock()
    monkeypatch.setattr(website.time, "monotonic", clock.monotonic)

    calls: list[str] = []
    # Boucle A -> B -> A -> ... qui ne se résout jamais : sans le budget de
    # temps, seul MAX_REDIRECTS (5) bornerait la boucle, soit 6 requêtes.
    responses = {
        "https://example.com/a": _FakeResponse(
            302, headers={"location": "https://example.com/b"}
        ),
        "https://example.com/b": _FakeResponse(
            302, headers={"location": "https://example.com/a"}
        ),
    }

    class _SlowFakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, **kwargs):
            calls.append(url)
            clock.advance(4.0)  # chaque saut "coûte" 4s de temps simulé
            return responses[url]

    monkeypatch.setattr(website.httpx, "AsyncClient", _SlowFakeAsyncClient)

    result = await _default_fetch("https://example.com/a", total_timeout=10.0)

    assert result is None
    # Sans budget total, la boucle irait jusqu'à MAX_REDIRECTS + 1 = 6
    # requêtes ; avec le budget, le temps simulé dépasse 10s dès la 3e.
    assert len(calls) == 3


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://github.com/Ekatche", "Ekatche"),
        ("https://github.com/Ekatche/", "Ekatche"),
        ("github.com/Ekatche", "Ekatche"),
        ("Ekatche", "Ekatche"),
    ],
)
def test_parse_github_username(raw, expected):
    assert parse_github_username(raw) == expected


@pytest.mark.parametrize("raw", ["https://github.com/", "", "https://gitlab.com/x"])
def test_parse_github_username_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_github_username(raw)


class FakeGitHubClient:
    """Répond comme l'API REST GitHub, sans réseau."""

    def __init__(self):
        self.calls = []

    async def get_repos(self, username):
        self.calls.append(("repos", username))
        return [
            {
                "name": "WideDocs",
                "description": "Plateforme documentaire pour avocats",
                "language": "Python",
                "topics": ["fastapi", "ocr"],
                "html_url": "https://github.com/Ekatche/WideDocs",
                "fork": False,
                "archived": False,
                "pushed_at": "2026-09-01T00:00:00Z",
                "stargazers_count": 3,
            },
            {
                "name": "transformerlab-app",
                "description": "Fork amont",
                "language": "TypeScript",
                "topics": [],
                "html_url": "https://github.com/Ekatche/transformerlab-app",
                "fork": True,
                "archived": False,
                "pushed_at": "2026-01-01T00:00:00Z",
                "stargazers_count": 0,
            },
        ]

    async def get_readme(self, username, repo):
        self.calls.append(("readme", repo))
        return "# WideDocs\n\nImport et OCR de dossiers, anonymisation RGPD."


@pytest.mark.asyncio
async def test_forks_are_excluded():
    payload = await collect_github("https://github.com/Ekatche", client=FakeGitHubClient())
    names = {p["name"] for p in payload["projects"]}
    assert names == {"WideDocs"}


@pytest.mark.asyncio
async def test_readme_feeds_the_description_and_language_feeds_the_stack():
    payload = await collect_github("Ekatche", client=FakeGitHubClient())
    project = payload["projects"][0]
    assert "OCR" in project["description"]
    assert "Python" in project["stack"]
    assert project["url"] == "https://github.com/Ekatche/WideDocs"


@pytest.mark.asyncio
async def test_github_never_produces_experiences():
    """GitHub documente des projets, pas des emplois : ne pas inventer d'expérience."""
    payload = await collect_github("Ekatche", client=FakeGitHubClient())
    assert payload.get("experiences", []) == []
