# ruff: noqa: F811  (fixtures importées depuis relevance_fixtures : le paramètre de test les « redéfinit »)
"""API offres : liste, tri par pertinence, niveaux et détail d'une offre (base Mongo de test)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.services.offer_scoring.assess import assess_offer
from app.services.offer_scoring.score import ProfileFeatures, build_skill_idf
from tests.job_offers_relevance.relevance_fixtures import (  # noqa: F401
    USER_A_ID,
    _insert_offer,
    _insert_relevance,
    as_user_a,
    as_user_b,
    db,
    requires_mongo,
    seeded_offers,
)


@requires_mongo
def test_list_defaults_to_recent_order(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/")

    assert res.status_code == 200, res.text
    postes = [o["poste"] for o in res.json()]
    assert postes == ["A4", "A3", "A2", "A1"]


@requires_mongo
def test_sort_relevance_orders_by_score_then_recency(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/", params={"sort": "relevance"})

    assert res.status_code == 200, res.text
    postes = [o["poste"] for o in res.json()]
    assert postes == ["A1", "A2", "A3", "A4"]


@requires_mongo
def test_failed_conditions_exposed(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/")

    assert res.status_code == 200, res.text
    by_poste = {o["poste"]: o for o in res.json()}
    assert by_poste["A3"]["failed_conditions"] == ["contract"]
    assert by_poste["A4"]["failed_conditions"] == []
    assert by_poste["A3"]["unknown_components"] == ["sector"]
    assert by_poste["A4"]["unknown_components"] == []


@requires_mongo
def test_count_returns_total(client, db, as_user_a, seeded_offers):
    assert client.get("/job-offers/count/").json() == {"total": 4}
    assert client.get("/job-offers/count/", params={"sort": "relevance"}).json() == {"total": 4}


@requires_mongo
def test_relevance_is_per_user(client, db, as_user_b, seeded_offers):
    """B est rattaché aux mêmes offres mais n'a aucun document offer_relevance."""
    res = client.get("/job-offers/")
    assert res.status_code == 200, res.text
    assert all(o["failed_conditions"] == [] for o in res.json())

    res_rel = client.get("/job-offers/", params={"sort": "relevance"})
    assert res_rel.status_code == 200, res_rel.text
    postes = [o["poste"] for o in res_rel.json()]
    assert postes == ["A4", "A3", "A2", "A1"]


@requires_mongo
def test_get_single_offer_exposes_failed_conditions(client, db, as_user_a, seeded_offers):
    """M4 : la route détail doit lire `offer_relevance`, pas seulement la liste."""
    res = client.get(f"/job-offers/{seeded_offers['a3']}")

    assert res.status_code == 200, res.text
    assert res.json()["failed_conditions"] == ["contract"]
    assert res.json()["unknown_components"] == ["sector"]


@requires_mongo
def test_get_single_offer_defaults_failed_conditions_to_empty_list(client, db, as_user_a, seeded_offers):
    """A4 n'a pas de document `offer_relevance` : `failed_conditions` reste `[]`."""
    res = client.get(f"/job-offers/{seeded_offers['a4']}")

    assert res.status_code == 200, res.text
    assert res.json()["failed_conditions"] == []
    assert res.json()["unknown_components"] == []


@requires_mongo
def test_unknown_components_from_real_scoring_reach_the_api(client, db, as_user_a):
    """Seul maillon non couvert ailleurs : le résultat réel d'`assess_offer` (une offre
    sans secteur face à un profil qui en vise un) est écrit dans `offer_relevance` puis
    restitué tel quel par l'API."""
    features = ProfileFeatures(
        identity="data scientist", skills=frozenset(), seniority_levels=(),
        preferred_industries=("tech_it",), preferred_company_sizes=(), preferences={},
    )
    offer_id = _insert_offer(db, poste="Sans secteur", created_at=datetime.now(timezone.utc))
    try:
        _, result = assess_offer({"poste": "Sans secteur"}, features, cos=0.8, idf=build_skill_idf([[]]))
        assert "sector" in result.unknown_components
        _insert_relevance(db, USER_A_ID, offer_id, result.score, unknown_components=result.unknown_components)

        res = client.get(f"/job-offers/{offer_id}")

        assert res.status_code == 200, res.text
        assert res.json()["unknown_components"] == result.unknown_components
    finally:
        db.job_offers.delete_many({"_id": offer_id})
        db.offer_relevance.delete_many({"offer_id": str(offer_id)})


@requires_mongo
def test_recent_sort_with_skip_still_exposes_failed_conditions_same_order(
    client, db, as_user_a, seeded_offers
):
    """M2 : déplacer le lookup après `$skip`/`$limit` en tri `recent` ne doit ni
    changer l'ordre de la page 2 ni vider `failed_conditions`."""
    res = client.get("/job-offers/", params={"skip": 1})

    assert res.status_code == 200, res.text
    postes = [o["poste"] for o in res.json()]
    assert postes == ["A3", "A2", "A1"]
    by_poste = {o["poste"]: o for o in res.json()}
    assert by_poste["A3"]["failed_conditions"] == ["contract"]


@requires_mongo
def test_relevance_sort_tiebreaks_by_recency_on_equal_score(client, db, as_user_a):
    """M21 : à score égal, le tri `relevance` départage par date décroissante
    (comportement déjà correct, figé ici)."""
    base = datetime.now(timezone.utc) - timedelta(days=5)
    older = _insert_offer(db, poste="TIE-OLD", created_at=base)
    newer = _insert_offer(db, poste="TIE-NEW", created_at=base + timedelta(days=1))
    _insert_relevance(db, USER_A_ID, older, 50)
    _insert_relevance(db, USER_A_ID, newer, 50)
    try:
        res = client.get("/job-offers/", params={"sort": "relevance"})
        assert res.status_code == 200, res.text
        postes = [o["poste"] for o in res.json() if o["poste"].startswith("TIE-")]
        assert postes == ["TIE-NEW", "TIE-OLD"]
    finally:
        db.job_offers.delete_many({"_id": {"$in": [older, newer]}})
        db.offer_relevance.delete_many({"offer_id": {"$in": [str(older), str(newer)]}})


@requires_mongo
def test_relevance_level_exposed_on_list_and_detail(client, db, as_user_a, seeded_offers):
    """Badge de niveau : forte (A1, 82), moyenne (A2, 65), faible (A3, 30),
    aucun niveau sans document `offer_relevance` (A4)."""
    res = client.get("/job-offers/")

    assert res.status_code == 200, res.text
    levels = {o["poste"]: o["relevance_level"] for o in res.json()}
    assert levels == {"A1": "strong", "A2": "medium", "A3": "weak", "A4": None}

    detail = client.get(f"/job-offers/{seeded_offers['a2']}")
    assert detail.json()["relevance_level"] == "medium"
    assert client.get(f"/job-offers/{seeded_offers['a4']}").json()["relevance_level"] is None


@requires_mongo
@pytest.mark.parametrize("sort", ["recent", "relevance"])
def test_filter_by_relevance_level_on_list_and_count(client, db, as_user_a, seeded_offers, sort):
    """Plusieurs niveaux se combinent en union ; une offre sans score n'a aucun
    niveau et sort donc de toute sélection par niveau."""
    params = [("relevance_level", "strong"), ("relevance_level", "medium"), ("sort", sort)]

    res = client.get("/job-offers/", params=params)
    assert res.status_code == 200, res.text
    assert sorted(o["poste"] for o in res.json()) == ["A1", "A2"]

    assert client.get("/job-offers/count/", params=params).json() == {"total": 2}
    assert client.get("/job-offers/count/", params={"relevance_level": "weak"}).json() == {"total": 1}


@requires_mongo
def test_invalid_relevance_level_returns_422_on_list_and_count(client, db, as_user_a):
    assert client.get("/job-offers/", params={"relevance_level": "top"}).status_code == 422
    assert client.get("/job-offers/count/", params={"relevance_level": "top"}).status_code == 422
