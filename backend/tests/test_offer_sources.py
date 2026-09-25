import math

import httpx
import pytest

from app.services import sources
from app.services.sources import france_travail, geo, jobboards

LYON = {"nom": "Lyon", "code": "69123", "centre": {"type": "Point", "coordinates": [4.8351, 45.758]}}
VILLEURBANNE = {"nom": "Villeurbanne", "code": "69266", "centre": {"type": "Point", "coordinates": [4.8812, 45.7707]}}
PARIS = {"nom": "Paris", "code": "75056", "centre": {"type": "Point", "coordinates": [2.347, 48.8589]}}
MONTREAL_AUDE = {"nom": "Montréal", "code": "11254", "centre": {"type": "Point", "coordinates": [2.14, 43.2]}}


def geo_transport(communes: dict):
    """geo.api.gouv.fr simulé : premier résultat par nom normalisé, liste vide sinon."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.params["nom"]
        calls.append(name)
        commune = communes.get(geo.normalize_text(name))
        return httpx.Response(200, json=[commune] if commune else [])

    return httpx.MockTransport(handler), calls


@pytest.fixture(autouse=True)
def clear_commune_cache():
    geo._commune_cache.clear()
    yield
    geo._commune_cache.clear()


# ---------- geo ----------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("69 - Lyon 3e Arrondissement", "Lyon"),
        ("Lyon, Auvergne-Rhône-Alpes, France", "Lyon"),
        ("Toulouse Area", "Toulouse"),
        ("Paris (75)", "Paris"),
        ("Villeurbanne", "Villeurbanne"),
    ],
)
def test_clean_city_label(raw, expected):
    assert geo.clean_city_label(raw) == expected


def test_mentions_foreign_country():
    assert geo.mentions_foreign_country("Montréal, QC, Canada")
    assert geo.mentions_foreign_country("London, England, United Kingdom")
    assert not geo.mentions_foreign_country("Lyon, Auvergne-Rhône-Alpes, France")
    assert not geo.mentions_foreign_country("Montréal")  # commune de l'Aude


def test_foreign_url_locale_ignores_english_default():
    assert geo.foreign_url_locale("https://workday.wd5.myworkdayjobs.com/fr-CA/Workday/job/X") == "fr-CA"
    assert geo.foreign_url_locale("https://airbus.wd3.myworkdayjobs.com/en-US/Airbus/job/Toulouse") is None
    assert geo.foreign_url_locale("https://x.myworkdayjobs.com/fr-FR/site/job/Y") is None
    assert geo.foreign_url_locale("https://www.hellowork.com/fr-fr/emplois/1.html") is None


def test_haversine_lyon_paris():
    distance = geo.haversine_km((4.8351, 45.758), (2.347, 48.8589))
    assert 385 < distance < 400


@pytest.mark.asyncio
async def test_resolve_commune_requires_exact_name():
    transport, _ = geo_transport({"lyon": LYON, "toulouse area": {**LYON, "nom": "Toulouges"}})
    async with httpx.AsyncClient(transport=transport) as client:
        assert (await geo.resolve_commune("Lyon", client))["code"] == "69123"
        assert await geo.resolve_commune("Toulouse Area", client) is None


@pytest.mark.asyncio
async def test_resolve_commune_does_not_cache_network_errors():
    def failing(request):
        raise httpx.ConnectError("down")

    async with httpx.AsyncClient(transport=httpx.MockTransport(failing)) as client:
        assert await geo.resolve_commune("Lyon", client) is None
    assert "lyon" not in geo._commune_cache


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "localisation, url, rejected",
    [
        ("Non spécifié", "https://workday.wd5.myworkdayjobs.com/fr-CA/Workday/job/X", True),
        ("Non spécifié", "https://airbus.wd3.myworkdayjobs.com/en-US/Airbus/job/X", False),
        ("Montréal, QC, Canada", None, True),
        ("Paris", None, True),
        ("Villeurbanne", None, False),
        ("Lyon 7e Arrondissement", None, False),
        ("Télétravail", None, False),
        ("Pleasanton", None, False),  # non résolue : conservée
        ("Paris / Lyon, France", None, False),  # multi-sites citant la ville cible
        ("Paris, France", None, True),
    ],
)
async def test_location_rejection_reason(localisation, url, rejected):
    transport, _ = geo_transport({"lyon": LYON, "villeurbanne": VILLEURBANNE, "paris": PARIS})
    async with httpx.AsyncClient(transport=transport) as client:
        reason = await geo.location_rejection_reason(localisation, url, "Lyon", client)
    assert bool(reason) is rejected


@pytest.mark.asyncio
async def test_location_without_target_city_only_rejects_foreign():
    transport, calls = geo_transport({"paris": PARIS})
    async with httpx.AsyncClient(transport=transport) as client:
        assert await geo.location_rejection_reason("Paris", None, None, client) is None
        assert await geo.location_rejection_reason("Berlin, Germany", None, None, client)
    assert calls == []


# ---------- France Travail ----------


def test_map_france_travail_offer():
    item = {
        "id": "123ABCD",
        "intitule": "Data scientist H/F",
        "description": "Missions...",
        "dateCreation": "2026-09-20T10:00:00.000Z",
        "lieuTravail": {"libelle": "69 - Lyon 3e Arrondissement"},
        "typeContratLibelle": "Contrat à durée indéterminée",
        "salaire": {"libelle": "Annuel de 45000 Euros à 55000 Euros"},
        "competences": [{"libelle": "Python"}, {"code": "x"}],
    }
    offer = france_travail.map_france_travail_offer(item)
    assert offer["url"] == "https://candidat.francetravail.fr/offres/recherche/detail/123ABCD"
    assert offer["entreprise"] == "Entreprise anonyme (France Travail)"
    assert offer["localisation"] == "Lyon"
    assert offer["date"] == "2026-09-20"
    assert offer["competences_cles"] == ["Python"]
    assert offer["salaire"] == "Annuel de 45000 Euros à 55000 Euros"


@pytest.mark.asyncio
async def test_france_travail_skipped_without_credentials(monkeypatch):
    monkeypatch.delenv("FRANCE_TRAVAIL_CLIENT_ID", raising=False)

    def fail(request):
        raise AssertionError("aucun appel attendu")

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        assert await france_travail.fetch_france_travail_offers("Data Scientist", "Lyon", "cdi", client) == []


@pytest.mark.asyncio
async def test_france_travail_search_params(monkeypatch):
    monkeypatch.setenv("FRANCE_TRAVAIL_CLIENT_ID", "id")
    monkeypatch.setenv("FRANCE_TRAVAIL_CLIENT_SECRET", "secret")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "geo.api.gouv.fr":
            return httpx.Response(200, json=[LYON])
        if request.url.path.endswith("access_token"):
            return httpx.Response(200, json={"access_token": "tok"})
        seen["params"] = dict(request.url.params)
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(206, json={"resultats": [{"id": "1", "intitule": "Data Scientist"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        offers = await france_travail.fetch_france_travail_offers("Data Scientist (IA/ML)", "Lyon", "cdi", client)

    assert [o["poste"] for o in offers] == ["Data Scientist"]
    assert seen["auth"] == "Bearer tok"
    assert seen["params"]["commune"] == "69381"  # code d'arrondissement exigé
    assert seen["params"]["distance"] == "50"
    assert seen["params"]["typeContrat"] == "CDI"
    assert seen["params"]["motsCles"] == "Data Scientist  IA/ML"


@pytest.mark.asyncio
async def test_france_travail_no_content(monkeypatch):
    monkeypatch.setenv("FRANCE_TRAVAIL_CLIENT_ID", "id")
    monkeypatch.setenv("FRANCE_TRAVAIL_CLIENT_SECRET", "secret")

    def handler(request):
        if request.url.path.endswith("access_token"):
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await france_travail.fetch_france_travail_offers("Data Scientist", None, None, client) == []


# ---------- Indeed / LinkedIn (jobspy) ----------


def test_map_jobboard_row_handles_missing_values():
    row = {
        "site": "linkedin",
        "job_url": "https://www.linkedin.com/jobs/view/4300000001",
        "title": "Data Scientist H/F",
        "company": "Acme",
        "location": "Lyon, Auvergne-Rhône-Alpes, France",
        "date_posted": "2026-09-20",
        "job_type": "fulltime",
        "is_remote": False,
        "min_amount": float("nan"),
        "max_amount": math.nan,
        "description": "Missions",
    }
    offer = jobboards.map_jobboard_row(row)
    assert offer["localisation"] == "Lyon"
    assert offer["salaire"] == ""
    assert offer["mode_travail"] == ""
    assert offer["type_contrat"] == ""
    assert offer["ats_platform"] == "linkedin"


def test_map_jobboard_row_salary_and_internship():
    row = {
        "site": "indeed", "job_url": "https://fr.indeed.com/viewjob?jk=1", "title": "Stage Data",
        "company": "Acme", "location": "Lyon", "job_type": "internship", "is_remote": True,
        "min_amount": 40000.0, "max_amount": 50000.0, "currency": "EUR", "interval": "yearly",
    }
    offer = jobboards.map_jobboard_row(row)
    assert offer["salaire"] == "40000 - 50000 EUR / yearly"
    assert offer["type_contrat"] == "Stage"
    assert offer["mode_travail"] == "Télétravail total"


@pytest.mark.asyncio
async def test_fetch_jobboard_offers_isolates_site_failure_and_drops_internships(monkeypatch):
    def fake_scrape(site, role, city):
        if site == "linkedin":
            raise RuntimeError("429")
        return [
            {"poste": "Data Scientist", "type_contrat": "", "url": "u1"},
            {"poste": "Stage Data", "type_contrat": "Stage", "url": "u2"},
        ]

    monkeypatch.setattr(jobboards, "_scrape_site", fake_scrape)
    offers = await jobboards.fetch_jobboard_offers("Data Scientist", "Lyon", "cdi")
    assert [o["url"] for o in offers] == ["u1"]


# ---------- orchestrateur ----------


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def __aiter__(self):
        self._it = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs
        self.query = None

    def find(self, query, projection=None):
        self.query = query
        return FakeCursor(self.docs)


def test_offer_identity_matches_linkedin_variants():
    assert sources.offer_identity("https://www.linkedin.com/jobs/view/4312345678") == "linkedin:4312345678"
    assert (
        sources.offer_identity("https://fr.linkedin.com/jobs/view/data-scientist-h-f-at-acme-4312345678?trk=x")
        == "linkedin:4312345678"
    )
    assert sources.offer_identity("https://www.indeed.fr/viewjob?jk=1") == "https://www.indeed.fr/viewjob?jk=1"


def test_parse_query_contract():
    assert sources.parse_query_contract("Je recherche un poste de Data Scientist proche de Lyon (CDI)") == "cdi"
    assert sources.parse_query_contract("Je recherche un poste de Data Scientist") is None


@pytest.mark.asyncio
async def test_drop_known_offers_matches_linkedin_by_id_and_dedups():
    collection = FakeCollection(
        [{"url": "https://fr.linkedin.com/jobs/view/data-scientist-at-acme-4312345678", "alternative_urls": []}]
    )
    offers = [
        {"url": "https://www.linkedin.com/jobs/view/4312345678"},
        {"url": "https://www.indeed.fr/viewjob?jk=1"},
        {"url": "https://www.indeed.fr/viewjob?jk=1"},
    ]
    fresh = await sources.drop_known_offers(offers, {"job_offers": collection})
    assert [o["url"] for o in fresh] == ["https://www.indeed.fr/viewjob?jk=1"]
    assert any("$regex" in str(c) for c in collection.query["$or"])


@pytest.mark.asyncio
async def test_drop_known_offers_with_extra_known():
    collection = FakeCollection([])
    offers = [
        {"url": "https://www.linkedin.com/jobs/view/9999999999"},
        {"url": "https://example.com/fresh"},
    ]
    extra = {"linkedin:9999999999"}
    fresh = await sources.drop_known_offers(offers, {"job_offers": collection}, extra_known=extra)
    assert [o["url"] for o in fresh] == ["https://example.com/fresh"]


@pytest.mark.asyncio
async def test_drop_known_urls():
    collection = FakeCollection([{"url": "https://example.com/in-db", "alternative_urls": []}])
    urls = [
        "https://example.com/in-db",
        "https://www.linkedin.com/jobs/view/111222333",
        "https://example.com/new-job",
    ]
    extra = {"linkedin:111222333"}
    kept = await sources.drop_known_urls(urls, {"job_offers": collection}, extra_known=extra)
    assert kept == ["https://example.com/new-job"]


@pytest.mark.asyncio
async def test_keep_relevant_titles(monkeypatch):
    vectors = {"Data Scientist": [1.0, 0.0], "Data Analyst": [0.8, 0.6], "Comptable": [0.1, 0.99]}

    async def fake_aembedding(model, input):
        return {"data": [{"embedding": vectors[text]} for text in input]}

    import litellm

    monkeypatch.setattr(litellm, "aembedding", fake_aembedding)
    offers = [{"poste": "Data Analyst", "url": "a"}, {"poste": "Comptable", "url": "b"}]
    kept = await sources.keep_relevant_titles("Data Scientist", offers)
    assert [o["url"] for o in kept] == ["a"]


@pytest.mark.asyncio
async def test_keep_relevant_titles_fail_open(monkeypatch):
    async def broken(model, input):
        raise RuntimeError("quota")

    import litellm

    monkeypatch.setattr(litellm, "aembedding", broken)
    offers = [{"poste": "Comptable", "url": "b"}]
    assert await sources.keep_relevant_titles("Data Scientist", offers) == offers


@pytest.mark.asyncio
async def test_collect_structured_offers_ignores_failing_source(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(sources, "fetch_france_travail_offers", AsyncMock(side_effect=RuntimeError("401")))
    monkeypatch.setattr(
        sources, "fetch_jobboard_offers",
        AsyncMock(return_value=[{"poste": "Data Scientist", "url": "u1"}, {"poste": "", "url": "u2"}]),
    )
    monkeypatch.setattr(sources, "keep_relevant_titles", AsyncMock(side_effect=lambda role, offers: offers))
    monkeypatch.setattr(sources, "filter_offers_by_location", AsyncMock(side_effect=lambda offers, city: offers))

    offers = await sources.collect_structured_offers(
        "Je recherche un poste de Data Scientist proche de Lyon (CDI)", {"job_offers": FakeCollection([])}
    )

    assert [o["url"] for o in offers] == ["u1"]
    sources.fetch_jobboard_offers.assert_awaited_once_with("Data Scientist", "Lyon", "cdi")


@pytest.mark.asyncio
async def test_collect_structured_offers_skips_unparsable_query():
    assert await sources.collect_structured_offers("recherche libre", {"job_offers": FakeCollection([])}) == []
