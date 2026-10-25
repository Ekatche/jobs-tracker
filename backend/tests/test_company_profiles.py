import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.company_profiles import (
    COMPANY_SIZES,
    PREFERENCE_SECTORS,
    SECTORS,
    CompanyResolver,
    extract_native_attributes,
    infer_company_attributes,
    lookup_company_size,
    map_indeed_size,
    map_sector_label,
)


def test_taxonomy_keys():
    assert len(SECTORS) == 13
    assert SECTORS[-1] == "other"
    assert PREFERENCE_SECTORS == SECTORS[:-1]
    assert COMPANY_SIZES == ("startup_tpe", "pme", "eti", "grand_groupe")


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Services aux Entreprises", "consulting_services"),
        ("Secteur informatique, ESN", None),
        ("Santé, Social, Association", "healthcare_pharma"),
        ("Service public hospitalier", "healthcare_pharma"),
        ("Industrie Pharmaceutique, Biotechn., Chimie", "healthcare_pharma"),
        ("Immobilier", "construction_realestate"),
        ("Banque, Assurance, Finance", "finance_insurance"),
        ("Services aux Personnes, Particuliers", "other"),
        ("Tourisme, Hôtellerie, Loisirs", "other"),
        ("Enseignement, Formation", "public_education"),
        ("Service public d'état", "public_education"),
        ("Industrie high-tech, Telecom", "tech_it"),
        ("Retail", "retail_ecommerce"),
        ("Aerospace And Defense", "industry_aerospace"),
        ("Industrial Manufacturing", "industry_aerospace"),
        ("Real Estate", "construction_realestate"),
        ("Banks And Financial Services", "finance_insurance"),
        ("Insurance", "finance_insurance"),
        ("Agriculture And Extraction", "agri_food"),
        ("Consumer Goods And Services", None),
        ("Media News And Publishing", "media_communication"),
        ("Consulting And Business Services", "consulting_services"),
        ("Health Care", "healthcare_pharma"),
        ("Information Technology", None),
        ("Hospitality", "other"),
        ("Transformation digitale", None),
        ("Fintech", "finance_insurance"),
        ("Restaurants & Food Service", "other"),
        ("Food and Beverage Services", "other"),
        ("Production et distribution d'énergie", "energy_environment"),
        (None, None),
        ("", None),
    ],
)
def test_map_sector_label(label, expected):
    assert map_sector_label(label) == expected


@pytest.mark.parametrize(
    "label,expected",
    [
        ("1 to 10", "startup_tpe"),
        ("51 to 200", "pme"),
        ("501 to 1,000", "eti"),
        ("1,001 to 5,000", "eti"),
        ("5,001 to 10,000", "grand_groupe"),
        ("10,000+", "grand_groupe"),
        ("11 to 50", None),
        ("201 to 500", None),
        ("Decline to state", None),
        (None, None),
    ],
)
def test_map_indeed_size(label, expected):
    assert map_indeed_size(label) == expected


@pytest.mark.parametrize(
    "raw_data,expected",
    [
        (
            {"hellowork": {"company_industry": "Immobilier"}},
            {"sector": "construction_realestate", "company_size": None, "sector_label": "Immobilier"},
        ),
        (
            {"indeed": {"company_industry": "Insurance", "company_num_employees": "10,000+"}},
            {"sector": "finance_insurance", "company_size": "grand_groupe", "sector_label": "Insurance"},
        ),
        (
            {"hellowork": {"company_industry": "Secteur informatique, ESN"}},
            {"sector": None, "company_size": None, "sector_label": "Secteur informatique, ESN"},
        ),
        ({"linkedin": {"job_level": "Senior"}}, {"sector": None, "company_size": None, "sector_label": None}),
        ({}, {"sector": None, "company_size": None, "sector_label": None}),
        (None, {"sector": None, "company_size": None, "sector_label": None}),
    ],
)
def test_extract_native_attributes(raw_data, expected):
    assert extract_native_attributes(raw_data) == expected


# --- Taille par l'API Recherche d'entreprises ---


def _api_result(nom_complet="SANOFI (SANOFI)", sigle=None, siren="395030844", categorie="GE", tranche="11"):
    return {
        "results": [
            {
                "nom_complet": nom_complet,
                "sigle": sigle,
                "siren": siren,
                "categorie_entreprise": categorie,
                "tranche_effectif_salarie": tranche,
            }
        ]
    }


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _lookup(company, payload):
    async with _client(lambda request: httpx.Response(200, json=payload)) as client:
        return await lookup_company_size(company, client=client)


async def test_lookup_size_grand_groupe_from_category():
    assert await _lookup("Sanofi", _api_result()) == ("grand_groupe", "395030844")


async def test_lookup_size_eti():
    payload = _api_result(nom_complet="DANONE PRODUITS FRAIS", siren="111", categorie="ETI", tranche="42")
    assert await _lookup("Danone Produits Frais", payload) == ("eti", "111")


async def test_lookup_size_pme_split_by_tranche():
    assert await _lookup("Acme", _api_result(nom_complet="ACME", siren="1", categorie="PME", tranche="11")) == (
        "startup_tpe",
        "1",
    )
    assert await _lookup("Acme", _api_result(nom_complet="ACME", siren="1", categorie="PME", tranche="12")) == (
        "pme",
        "1",
    )
    assert await _lookup("Acme", _api_result(nom_complet="ACME", siren="1", categorie="PME", tranche=None)) == (
        None,
        None,
    )
    assert await _lookup("Acme", _api_result(nom_complet="ACME", siren="1", categorie="PME", tranche="NN")) == (
        None,
        None,
    )


async def test_lookup_size_rejects_name_mismatch():
    assert await _lookup("Orange", _api_result(nom_complet="ORANGE BANK", siren="2")) == (None, None)


async def test_lookup_size_accepts_sigle_match():
    payload = _api_result(nom_complet="BNP PARIBAS (BNP)", sigle="BNP", siren="662042449")
    assert await _lookup("BNP", payload) == ("grand_groupe", "662042449")


async def test_lookup_size_retries_once_after_429():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=_api_result())

    async with _client(handler) as client:
        assert await lookup_company_size("Sanofi", client=client) == ("grand_groupe", "395030844")
    assert len(calls) == 2


async def test_lookup_size_gives_up_after_second_429():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "0"})

    async with _client(handler) as client:
        assert await lookup_company_size("Sanofi", client=client) == (None, None)
    assert len(calls) == 2


async def test_lookup_size_network_error_returns_none():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    async with _client(handler) as client:
        assert await lookup_company_size("Sanofi", client=client) == (None, None)


async def test_lookup_size_sends_query_params():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_api_result())

    async with _client(handler) as client:
        await lookup_company_size("Sanofi", client=client)
    params = seen[0].url.params
    assert params["q"] == "Sanofi"
    assert params["per_page"] == "1"
    assert params["minimal"] == "true"
    assert seen[0].headers.get("user-agent")
    assert not seen[0].headers["user-agent"].startswith("python-httpx")



# --- Repli LLM ---

ESN_RULE = (
    "une ESN ou un cabinet de conseil IT relève de `consulting_services`, même si son code NAF est en 62.0x ; "
    "`tech_it` est réservé aux entreprises qui vendent leur propre produit ou plateforme"
)


def _llm_response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _patch_llm(content=None, side_effect=None):
    mock = AsyncMock(return_value=_llm_response(content), side_effect=side_effect)
    return patch("app.services.company_profiles.acompletion", mock)


async def test_infer_returns_taxonomy_values():
    with _patch_llm(json.dumps({"sector": "consulting_services", "company_size": "eti"})) as mock:
        result = await infer_company_attributes(
            "Sopra Steria", poste="Data Engineer", description="Mission chez un client", sector_label="Secteur informatique, ESN"
        )
    assert result == {"sector": "consulting_services", "company_size": "eti"}
    kwargs = mock.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["drop_params"] is True
    prompt = kwargs["messages"][0]["content"]
    assert ESN_RULE in prompt
    assert "Secteur informatique, ESN" in prompt
    assert "Sopra Steria" in prompt


async def test_infer_rejects_values_outside_taxonomy():
    with _patch_llm(json.dumps({"sector": "fintech", "company_size": "huge"})):
        assert await infer_company_attributes("Qonto") == {"sector": None, "company_size": None}


async def test_infer_accepts_other_and_null():
    with _patch_llm(json.dumps({"sector": "other", "company_size": None})):
        assert await infer_company_attributes("Club Med") == {"sector": "other", "company_size": None}


async def test_infer_returns_none_on_invalid_json():
    with _patch_llm("je ne sais pas"):
        assert await infer_company_attributes("Acme") is None


async def test_infer_returns_none_on_exception():
    with _patch_llm(side_effect=Exception("boom")):
        assert await infer_company_attributes("Acme") is None


async def test_infer_omits_temperature_for_gpt5(monkeypatch):
    monkeypatch.setenv("SUMMARY_MODEL", "gpt-5-nano")
    with _patch_llm(json.dumps({"sector": None, "company_size": None})) as mock:
        await infer_company_attributes("Acme")
    assert "temperature" not in mock.call_args.kwargs
    assert mock.call_args.kwargs["model"] == "gpt-5-nano"


# --- CompanyResolver ---


class FakeProfiles:
    """Collection company_profiles en mémoire : find_one sur le nom normalisé, update_one avec upsert."""

    def __init__(self, docs=()):
        self.docs = {d["company_name_normalized"]: dict(d) for d in docs}
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.update_one = AsyncMock(side_effect=self._update_one)

    async def _find_one(self, query, *args, **kwargs):
        doc = self.docs.get(query["company_name_normalized"])
        return dict(doc) if doc else None

    async def _update_one(self, query, update, upsert=False):
        key = query["company_name_normalized"]
        if key not in self.docs:
            if not upsert:
                return
            self.docs[key] = {"company_name_normalized": key, **update.get("$setOnInsert", {})}
        self.docs[key].update(update.get("$set", {}))


@pytest.fixture
def externals(monkeypatch):
    lookup = AsyncMock(return_value=(None, None))
    infer = AsyncMock(return_value={"sector": None, "company_size": None})
    monkeypatch.setattr("app.services.company_profiles.lookup_company_size", lookup)
    monkeypatch.setattr("app.services.company_profiles.infer_company_attributes", infer)
    return SimpleNamespace(lookup=lookup, infer=infer)


def _resolver(profiles, **kwargs):
    return CompanyResolver({"company_profiles": profiles}, **kwargs)


async def test_resolver_uses_native_values_without_external_calls(externals):
    profiles = FakeProfiles()
    offer = {
        "entreprise": "Foncia",
        "raw_data": {"indeed": {"company_industry": "Real Estate", "company_num_employees": "10,000+"}},
    }
    await _resolver(profiles).resolve(offer)
    assert offer["sector"] == "construction_realestate"
    assert offer["company_size"] == "grand_groupe"
    externals.lookup.assert_not_awaited()
    externals.infer.assert_not_awaited()
    profile = profiles.docs["FONCIA"]
    assert profile["sector"] == "construction_realestate"
    assert profile["sector_source"] == profile["size_source"] == "native_source"
    assert profile["company_name_raw"] == "Foncia"


async def test_resolver_cache_hit_makes_no_external_call(externals):
    profiles = FakeProfiles(
        [
            {
                "company_name_normalized": "ACME",
                "sector": "tech_it",
                "sector_source": "native_source",
                "company_size": "pme",
                "size_source": "api_entreprises",
            }
        ]
    )
    offer = {"entreprise": "Acme"}
    await _resolver(profiles).resolve(offer)
    assert (offer["sector"], offer["company_size"]) == ("tech_it", "pme")
    externals.lookup.assert_not_awaited()
    externals.infer.assert_not_awaited()


async def test_resolver_api_size_then_llm_for_sector_only(externals):
    externals.lookup.return_value = ("eti", "123456789")
    externals.infer.return_value = {"sector": "agri_food", "company_size": "pme"}
    profiles = FakeProfiles()
    offer = {"entreprise": "Bonduelle", "poste": "Contrôleur de gestion"}
    await _resolver(profiles).resolve(offer)
    assert (offer["sector"], offer["company_size"]) == ("agri_food", "eti")
    profile = profiles.docs["BONDUELLE"]
    assert profile["size_source"] == "api_entreprises"
    assert profile["siren"] == "123456789"
    assert profile["company_size"] == "eti"
    assert profile["sector_source"] == "llm_inferred"
    assert profile["sector"] == "agri_food"


async def test_resolver_marks_llm_attempt_even_when_null(externals):
    profiles = FakeProfiles()
    resolver = _resolver(profiles)
    for _ in range(2):
        await resolver.resolve({"entreprise": "Inconnue SAS"})
    assert externals.lookup.await_count == 1
    assert externals.infer.await_count == 1
    profile = profiles.docs["INCONNUE"]
    assert profile["sector_source"] == profile["size_source"] == "llm_inferred"
    assert profile["sector"] is None and profile["company_size"] is None


async def test_resolver_never_overwrites_known_value_with_none(externals):
    externals.infer.return_value = {"sector": None, "company_size": "pme"}
    offer = {"entreprise": "Acme", "sector": "finance_insurance"}
    await _resolver(FakeProfiles()).resolve(offer)
    assert (offer["sector"], offer["company_size"]) == ("finance_insurance", "pme")

    profiles = FakeProfiles([{"company_name_normalized": "BETA", "sector": "tech_it", "sector_source": "native_source"}])
    offer = {"entreprise": "Beta"}
    await _resolver(profiles).resolve(offer)
    assert offer["sector"] == "tech_it"
    assert profiles.docs["BETA"]["sector"] == "tech_it"
    assert profiles.docs["BETA"]["sector_source"] == "native_source"


async def test_resolver_native_value_replaces_llm_inferred_in_profile(externals):
    profiles = FakeProfiles(
        [
            {
                "company_name_normalized": "AXA",
                "sector": "other",
                "sector_source": "llm_inferred",
                "company_size": "grand_groupe",
                "size_source": "api_entreprises",
            }
        ]
    )
    offer = {"entreprise": "AXA", "raw_data": {"indeed": {"company_industry": "Insurance"}}}
    await _resolver(profiles).resolve(offer)
    assert offer["sector"] == "finance_insurance"
    assert profiles.docs["AXA"]["sector"] == "finance_insurance"
    assert profiles.docs["AXA"]["sector_source"] == "native_source"


async def test_resolver_never_replaces_manual(externals):
    manual = {
        "company_name_normalized": "FNAC",
        "sector": "media_communication",
        "sector_source": "manual",
        "company_size": "grand_groupe",
        "size_source": "manual",
    }
    profiles = FakeProfiles([manual])
    offer = {"entreprise": "Fnac", "raw_data": {"indeed": {"company_industry": "Retail"}}}
    await _resolver(profiles).resolve(offer)
    assert offer["sector"] == "retail_ecommerce"
    assert profiles.docs["FNAC"] == manual


@pytest.mark.parametrize(
    "company",
    [
        "Confidentiel",
        "Entreprise confidentielle",
        "Non spécifié",
        "Non communiqué",
        "Non disponible",
        "Non précisé",
        "Inconnu",
        "N/A",
        "Notre client",
        "Client final",
        "Stealth startup",
        "",
        None,
    ],
)
async def test_resolver_skips_placeholder_company(externals, company):
    profiles = FakeProfiles()
    offer = {"entreprise": company, "raw_data": {"hellowork": {"company_industry": "Immobilier"}}}
    await _resolver(profiles).resolve(offer)
    assert offer["sector"] == "construction_realestate"
    profiles.find_one.assert_not_awaited()
    profiles.update_one.assert_not_awaited()
    externals.lookup.assert_not_awaited()
    externals.infer.assert_not_awaited()


async def test_resolver_stops_calling_llm_after_budget(externals):
    externals.infer.return_value = {"sector": "other", "company_size": None}
    profiles = FakeProfiles()
    resolver = _resolver(profiles, max_llm_calls=1)
    await resolver.resolve({"entreprise": "Alpha"})
    await resolver.resolve({"entreprise": "Gamma"})
    assert externals.infer.await_count == 1
    assert resolver.llm_calls == 1
    assert profiles.docs["ALPHA"]["sector_source"] == "llm_inferred"
    gamma = profiles.docs.get("GAMMA", {})
    assert gamma.get("sector_source") is None
    assert gamma.get("size_source") is None


async def test_resolver_llm_failure_leaves_source_unmarked(externals):
    externals.infer.return_value = None
    profiles = FakeProfiles()
    offer = {"entreprise": "Delta"}
    await _resolver(profiles).resolve(offer)
    assert offer.get("sector") is None
    assert profiles.docs.get("DELTA", {}).get("sector_source") is None


async def test_resolver_tries_remote_once_per_company_per_batch(externals):
    # API sans correspondance et LLM en échec : rien n'est mis en cache pour l'entreprise
    externals.infer.return_value = None
    resolver = _resolver(FakeProfiles())
    for _ in range(3):
        await resolver.resolve({"entreprise": "Delta"})
    assert externals.lookup.await_count == 1
    assert externals.infer.await_count == 1


async def _hang(*args, **kwargs):
    await asyncio.sleep(5)


@pytest.mark.parametrize("slow_call", ["lookup", "infer"])
async def test_resolver_stops_remote_calls_after_time_budget(externals, slow_call):
    getattr(externals, slow_call).side_effect = _hang
    resolver = _resolver(FakeProfiles(), time_budget_seconds=0.05)
    started = time.monotonic()
    await resolver.resolve({"entreprise": "Alpha"})
    await resolver.resolve({"entreprise": "Gamma"})
    assert time.monotonic() - started < 1
    # Le premier appel lent est coupé à l'échéance ; ensuite, plus aucun appel externe
    assert externals.lookup.await_count + externals.infer.await_count == 1 + (slow_call == "infer")
    assert externals.lookup.await_count == 1
