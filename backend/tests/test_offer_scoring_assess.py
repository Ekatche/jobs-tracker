import pytest

from app.services.offer_scoring.assess import assess_offer, failed_conditions, hard_filter_reason
from app.services.offer_scoring.constants import CAP_SCORE
from app.services.offer_scoring.geo import departments_for_location
from app.services.offer_scoring.role_gate import role_terms
from app.services.offer_scoring.score import ProfileFeatures, build_skill_idf

ILE_DE_FRANCE_DEPARTMENTS = {"75", "77", "78", "91", "92", "93", "94", "95"}

DEFAULT_PREFERENCES = {
    "locations": ["Lyon"],
    "remote_policy": "hybrid",
    "contract_types": ["CDI"],
}


def make_features(preferences=None, **overrides) -> ProfileFeatures:
    defaults = dict(
        identity="",
        skills=frozenset(),
        seniority_levels=(),
        preferred_industries=(),
        preferred_company_sizes=(),
        preferences=preferences if preferences is not None else {},
    )
    defaults.update(overrides)
    return ProfileFeatures(**defaults)


def features_with(**pref_overrides) -> ProfileFeatures:
    prefs = {**DEFAULT_PREFERENCES, **pref_overrides}
    return make_features(preferences=prefs)


# ---------- departments_for_location ----------


@pytest.mark.parametrize(
    "location,expected",
    [
        ("Lyon", {"69"}),
        ("Lyon, Auvergne-Rhône-Alpes", {"69"}),
        ("69003 Lyon", {"69"}),
        ("Villeurbanne (69)", {"69"}),
        ("Paris 15e", {"75"}),
        ("Île-de-France", ILE_DE_FRANCE_DEPARTMENTS),
        ("Ajaccio", {"2A"}),
        ("La Défense", set()),
        ("Remote", set()),
        ("Non spécifié", set()),
        ("", set()),
        (None, set()),
        # M9 : code entre parenthèses limité à 01-95 / 2A-2B / 971-976 ;
        # un code hors plage (ex: 100) retombe sur la résolution par nom.
        ("Lyon (100)", {"69"}),
        ("Fort-de-France (972)", {"972"}),
        # M11 : un nom de région remplace les communes homonymes, pas de
        # fusion (Bretagne = exactement ses 4 départements ; La Réunion,
        # aussi commune du Lot-et-Garonne, reste la seule île).
        ("Bretagne", {"22", "29", "35", "56"}),
        ("La Réunion", {"974"}),
        # Un nom de département, lui, fusionne avec la commune homonyme :
        # Vienne (Isère) ne doit pas être éclipsée par le département 86.
        ("Vienne", {"38", "86"}),
        # Libellés LinkedIn anglais : l'enrobage « Greater … Area / Metropolitan
        # Region » est retiré ; la région parisienne couvre toute l'IDF.
        ("Greater Paris Metropolitan Region", ILE_DE_FRANCE_DEPARTMENTS),
        ("Greater Lyon Area", {"69"}),
        ("Greater Bordeaux Metropolitan Area", {"33"}),
    ],
)
def test_departments_for_location(location, expected):
    assert departments_for_location(location) == frozenset(expected)


def test_departments_for_location_saint_denis_keeps_homonym_communes():
    """Les communes homonymes entre elles restent fusionnées (sens permissif,
    cf. docstring de build_communes_index.py) : Saint-Denis contient toujours
    au moins la Seine-Saint-Denis (93) et La Réunion (974)."""
    assert {"93", "974"} <= departments_for_location("Saint-Denis")


# ---------- _load_index (M10, fail-open) ----------


def test_load_index_missing_file_fails_open(monkeypatch, caplog):
    from app.services.offer_scoring import geo

    monkeypatch.setattr(geo, "_INDEX_PATH", geo._INDEX_PATH.parent / "does-not-exist.json")
    geo._load_index.cache_clear()
    try:
        with caplog.at_level("ERROR"):
            assert geo._load_index() == {}
        assert any(record.levelname == "ERROR" for record in caplog.records)
    finally:
        geo._load_index.cache_clear()


def test_load_index_invalid_json_fails_open(tmp_path, monkeypatch, caplog):
    from app.services.offer_scoring import geo

    bad_file = tmp_path / "invalid.json"
    bad_file.write_text("{ceci n'est pas du json", encoding="utf-8")
    monkeypatch.setattr(geo, "_INDEX_PATH", bad_file)
    geo._load_index.cache_clear()
    try:
        with caplog.at_level("ERROR"):
            assert geo._load_index() == {}
        assert any(record.levelname == "ERROR" for record in caplog.records)
    finally:
        geo._load_index.cache_clear()


# ---------- hard_filter_reason ----------


@pytest.mark.parametrize(
    "excluded_keywords,poste,expected",
    [
        (["ENS"], "Stage ENS Lyon", "excluded_keyword"),
        (["ENS"], "Ensemble", None),
        (["ENS"], "sens du service", None),
        (["ENS"], "Responsable", None),
        (["Télévente"], "Conseiller televente", "excluded_keyword"),
    ],
)
def test_hard_filter_excluded_keyword_needs_word_boundary(excluded_keywords, poste, expected):
    features = features_with(excluded_keywords=excluded_keywords)
    offer = {"poste": poste, "type_contrat": "CDI"}
    assert hard_filter_reason(offer, features) == expected


@pytest.mark.parametrize(
    "contract_types,expected",
    [
        (["CDI"], "contract"),
        (["CDI", "Stage"], None),
        ([], None),
    ],
)
def test_hard_filter_internship_without_wish(contract_types, expected):
    features = features_with(contract_types=contract_types)
    offer = {"poste": "Data Analyst", "type_contrat": "Stage"}
    assert hard_filter_reason(offer, features) == expected


# ---------- hard_filter_reason : geo ----------
# Hors zone = filtre dur (offre détachée), comme l'ancienne règle de
# rattachement ; seul le télétravail total y échappe.


def test_geo_same_department_passes():
    offer = {"localisation": "Villeurbanne", "type_contrat": "CDI"}
    assert hard_filter_reason(offer, features_with()) is None


def test_geo_other_department_is_hard_filtered():
    offer = {"localisation": "Nantes", "type_contrat": "CDI"}
    assert hard_filter_reason(offer, features_with()) == "geo"
    assert failed_conditions(offer, features_with()) == []

    offer_marseille = {"localisation": "Marseille", "type_contrat": "CDI"}
    assert hard_filter_reason(offer_marseille, features_with(locations=["Lyon", "Paris"])) == "geo"


def test_geo_linkedin_paris_region_is_out_of_zone_for_lyon():
    offer = {"localisation": "Greater Paris Metropolitan Region", "type_contrat": "CDI"}
    assert hard_filter_reason(offer, features_with()) == "geo"
    assert hard_filter_reason(offer, features_with(locations=["Nanterre"])) is None


def test_geo_full_remote_offer_passes_unless_on_site():
    offer = {"localisation": "Nantes", "mode_travail": "Télétravail total", "type_contrat": "CDI"}
    assert hard_filter_reason(offer, features_with()) is None
    assert hard_filter_reason(offer, features_with(remote_policy="on_site")) == "geo"


def test_geo_full_remote_candidate():
    features = features_with(remote_policy="full_remote")

    offer_on_site = {"localisation": "Lyon", "mode_travail": "Présentiel", "type_contrat": "CDI"}
    assert hard_filter_reason(offer_on_site, features) == "geo"

    offer_remote = {"localisation": "Lyon", "mode_travail": "Télétravail total", "type_contrat": "CDI"}
    assert hard_filter_reason(offer_remote, features) is None

    offer_unknown_mode = {"localisation": "Lyon", "type_contrat": "CDI"}
    assert hard_filter_reason(offer_unknown_mode, features) is None


def test_geo_unresolved_location_never_filters():
    offer_unresolved = {"localisation": "La Défense", "type_contrat": "CDI"}
    assert hard_filter_reason(offer_unresolved, features_with()) is None

    offer_nantes = {"localisation": "Nantes", "type_contrat": "CDI"}
    assert hard_filter_reason(offer_nantes, features_with(locations=["St.-Denis"])) is None

    assert hard_filter_reason(offer_nantes, features_with(locations=[])) is None


def test_geo_mixed_resolved_and_unresolved_locations_never_filters():
    offer_nanterre = {"localisation": "Nanterre", "type_contrat": "CDI"}
    assert hard_filter_reason(offer_nanterre, features_with(locations=["Lyon", "La Défense"])) is None


# ---------- failed_conditions : contract ----------


def test_contract_condition():
    offer_cdd = {"localisation": "Lyon", "type_contrat": "CDD"}
    assert failed_conditions(offer_cdd, features_with()) == ["contract"]

    offer_unknown_contract = {"localisation": "Lyon", "type_contrat": "Temps partiel"}
    assert failed_conditions(offer_unknown_contract, features_with()) == []

    assert failed_conditions(offer_cdd, features_with(contract_types=[])) == []


# ---------- assess_offer ----------


def test_assess_offer_capped_offer_keeps_raw_score():
    features = make_features(
        identity="Data Engineer",
        skills=frozenset({"python"}),
        seniority_levels=("senior",),
        preferred_industries=("tech",),
        preferred_company_sizes=("pme",),
        preferences=DEFAULT_PREFERENCES,
    )
    offer = {
        "localisation": "Lyon",
        "type_contrat": "CDD",
        "competences_cles": ["Python"],
        "seniority_level": "senior",
        "sector": "tech",
        "company_size": "pme",
    }
    idf = build_skill_idf([["Python"]])

    reason, result = assess_offer(offer, features, cos=0.83, idf=idf)

    assert reason is None
    assert result.failed_conditions == ["contract"]
    assert result.score == CAP_SCORE
    assert result.breakdown["raw_score"] > CAP_SCORE


def test_assess_offer_out_of_zone_is_filtered_even_with_top_score():
    features = make_features(
        identity="Data Engineer",
        skills=frozenset({"python"}),
        preferences=DEFAULT_PREFERENCES,
    )
    offer = {"localisation": "Nantes", "type_contrat": "CDI", "competences_cles": ["Python"]}
    idf = build_skill_idf([["Python"]])

    reason, result = assess_offer(offer, features, cos=0.83, idf=idf)

    assert reason == "geo"
    assert result is None


def test_assess_offer_filtered_returns_reason():
    features = features_with(contract_types=["CDI"])
    offer = {"localisation": "Lyon", "type_contrat": "Stage", "poste": "Data Analyst"}
    idf = build_skill_idf([[]])

    reason, result = assess_offer(offer, features, cos=None, idf=idf)

    assert reason == "contract"
    assert result is None


def test_assess_offer_empty_identity_excludes_semantic():
    """Ruling R1 : composante `semantic` hors dénominateur si `features.identity` est vide."""
    features = make_features(
        skills=frozenset({"python"}),
        preferences={"locations": [], "remote_policy": "flexible", "contract_types": []},
    )
    offer = {"localisation": "Lyon", "type_contrat": "CDI", "competences_cles": ["Python"]}
    idf = build_skill_idf([["Python"]])

    reason, result = assess_offer(offer, features, cos=0.9, idf=idf)

    assert reason is None
    assert "semantic" not in result.breakdown


# ---------- hard_filter_reason : role ----------
# Le cosinus absolu ne sépare pas les métiers d'un profil à l'autre : sans
# garde sur l'intitulé, tout le stock data était rattaché à une animatrice.


def test_role_mismatch_is_hard_filtered():
    features = make_features(role_terms=role_terms(["Animateur socioculturel", "Coordinateur de projets jeunesse"]))
    offer = {"poste": "Gestionnaire actif passif - Responsable de projets ALM", "type_contrat": "CDI"}

    assert hard_filter_reason(offer, features) == "role"
    assert assess_offer(offer, features, cos=0.9, idf=build_skill_idf([[]])) == ("role", None)


def test_role_match_passes():
    features = make_features(role_terms=role_terms(["Animateur socioculturel"]))
    offer = {"poste": "Animatrice périscolaire H/F", "type_contrat": "CDI"}

    assert hard_filter_reason(offer, features) is None


def test_profile_without_role_terms_has_no_role_filter():
    offer = {"poste": "Contrôleur de gestion", "type_contrat": "CDI"}
    assert hard_filter_reason(offer, make_features()) is None
