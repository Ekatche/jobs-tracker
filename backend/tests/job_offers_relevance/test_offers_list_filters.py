# ruff: noqa: F811  (fixtures importées depuis relevance_fixtures : le paramètre de test les « redéfinit »)
"""API offres : filtres secteur, taille, mots-clés, ville et entreprise (base Mongo de test)."""
from datetime import datetime, timezone

import pytest

from tests.job_offers_relevance.relevance_fixtures import (  # noqa: F401
    _insert_offer,
    as_user_a,
    db,
    requires_mongo,
    seeded_offers,
)


@requires_mongo
def test_filter_by_sector_and_company_size(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/", params={"sector": "tech_it", "company_size": "pme"})
    assert res.status_code == 200, res.text
    assert [o["poste"] for o in res.json()] == ["A3"]

    count_res = client.get(
        "/job-offers/count/", params={"sector": "tech_it", "company_size": "pme"}
    )
    assert count_res.json() == {"total": 1}

    invalid_res = client.get("/job-offers/", params={"sector": "fintech"})
    assert invalid_res.status_code == 422


@requires_mongo
def test_response_has_no_internal_fields(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/", params={"sort": "relevance"})

    assert res.status_code == 200, res.text
    for offer in res.json():
        assert not any(key.startswith("_") for key in offer)


@requires_mongo
def test_sector_filter_multi_value_is_union(client, db, as_user_a):
    """M21 : plusieurs valeurs de `sector` se combinent en `$in` (union), déjà
    correct via `_build_sector_filter`, figé ici."""
    o1 = _insert_offer(db, poste="SEC-IT", created_at=datetime.now(timezone.utc), sector="tech_it")
    o2 = _insert_offer(
        db, poste="SEC-FIN", created_at=datetime.now(timezone.utc), sector="finance_insurance"
    )
    try:
        res = client.get(
            "/job-offers/", params=[("sector", "tech_it"), ("sector", "finance_insurance")]
        )
        assert res.status_code == 200, res.text
        postes = {o["poste"] for o in res.json()}
        assert {"SEC-IT", "SEC-FIN"} <= postes
    finally:
        db.job_offers.delete_many({"_id": {"$in": [o1, o2]}})


@requires_mongo
def test_invalid_sector_and_company_size_return_422_on_list_and_count(client, db, as_user_a):
    """M21 : 422 déjà renvoyé par la validation `Literal[*SECTORS]` / `Literal[*COMPANY_SIZES]`
    sur la liste ET le count, comportement déjà correct, figé ici."""
    assert client.get("/job-offers/", params={"sector": "inconnu"}).status_code == 422
    assert client.get("/job-offers/count/", params={"sector": "inconnu"}).status_code == 422
    assert client.get("/job-offers/", params={"company_size": "inconnu"}).status_code == 422
    assert client.get("/job-offers/count/", params={"company_size": "inconnu"}).status_code == 422


@requires_mongo
@pytest.mark.parametrize(
    "keywords",
    ["ingenieur donnees", "INGÉNIEUR DONNÉES", "Ingénieur", "ingénieur données", "developpeur", "DÉVELOPPEUR"],
)
def test_keywords_search_ignores_accents_and_case(client, db, as_user_a, keywords):
    """Recherche plein texte : « ingenieur » trouve « Ingénieur », en majuscules
    accentuées comme sans accent, sur la liste comme sur le count."""
    now = datetime.now(timezone.utc)
    ids = [
        _insert_offer(db, poste="Ingénieur Données / Développeur ETL", created_at=now),
        _insert_offer(db, poste="Comptable", created_at=now),
    ]
    try:
        res = client.get("/job-offers/", params={"keywords": keywords})
        assert res.status_code == 200, res.text
        assert [o["poste"] for o in res.json()] == ["Ingénieur Données / Développeur ETL"]
        assert client.get("/job-offers/count/", params={"keywords": keywords}).json() == {"total": 1}
    finally:
        db.job_offers.delete_many({"_id": {"$in": ids}})


@requires_mongo
@pytest.mark.parametrize("location", ["orleans", "ORLÉANS", "Orléans (45)"])
def test_location_filter_ignores_accents_and_case(client, db, as_user_a, location):
    """Filtre ville : « orleans » trouve « Orléans (45) », et les parenthèses
    saisies sont du texte, pas un groupe regex ; sur la liste comme sur le count."""
    now = datetime.now(timezone.utc)
    ids = [
        _insert_offer(db, poste="Comptable Orléans", created_at=now, localisation="Orléans (45)"),
        _insert_offer(db, poste="Comptable Paris", created_at=now, localisation="Paris"),
    ]
    try:
        res = client.get("/job-offers/", params={"location": location})
        assert res.status_code == 200, res.text
        assert [o["poste"] for o in res.json()] == ["Comptable Orléans"]
        assert client.get("/job-offers/count/", params={"location": location}).json() == {"total": 1}
    finally:
        db.job_offers.delete_many({"_id": {"$in": ids}})


@requires_mongo
def test_company_filter_treats_regex_characters_as_text(client, db, as_user_a):
    """« C++ » est un nom saisi, pas une regex invalide (500 avant)."""
    now = datetime.now(timezone.utc)
    ids = [
        _insert_offer(db, poste="Dev", created_at=now, entreprise="C++ Factory"),
        _insert_offer(db, poste="Dev", created_at=now, entreprise="Acme"),
    ]
    try:
        res = client.get("/job-offers/", params={"company": "c++"})
        assert res.status_code == 200, res.text
        assert [o["entreprise"] for o in res.json()] == ["C++ Factory"]
    finally:
        db.job_offers.delete_many({"_id": {"$in": ids}})
