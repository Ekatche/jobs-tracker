"""Tests de l'API offres : tri optionnel par pertinence, conditions non remplies,
filtres secteur et taille (Task 7).

Seed direct dans `job_offers` et `offer_relevance` sur la base de test locale
(127.0.0.1:27018, cf. conftest.py) — pas de passage par le matcher (Task 6).
Le module est marqué `skipif` si cette base ne répond pas, sauf le premier
test, qui est pur (aucune connexion Mongo)."""
import uuid
from datetime import datetime, timedelta, timezone

import pymongo
import pytest
from bson import ObjectId

from app.auth import get_current_user
from app.models import UserModel, UserRole
from app.routers.job_offers import _build_list_pipeline, relevance_lookup_stages
from conftest import DATABASE_NAME, MONGO_URI
from main import app


def _mongo_test_db_available() -> bool:
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


requires_mongo = pytest.mark.skipif(
    not _mongo_test_db_available(),
    reason="Base Mongo de test indisponible (127.0.0.1:27018, container job-tracker-mongo_test-1)",
)


USER_A_ID = str(ObjectId())
USER_B_ID = str(ObjectId())


def _make_user(user_id):
    return UserModel(
        id=user_id,
        username=f"user_{user_id[:6]}",
        email=f"{user_id[:6]}@test.com",
        hashed_password="x",
        role=UserRole.USER,
    )


def _override_user(user_id):
    app.dependency_overrides[get_current_user] = lambda: _make_user(user_id)


@pytest.fixture
def db():
    mongo = pymongo.MongoClient(MONGO_URI)
    yield mongo[DATABASE_NAME]
    mongo.close()


@pytest.fixture
def as_user_a():
    _override_user(USER_A_ID)
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def as_user_b():
    _override_user(USER_B_ID)
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _insert_offer(db, *, poste, created_at, sector=None, company_size=None):
    key = uuid.uuid4().hex
    doc = {
        "poste": poste,
        "entreprise": "Acme",
        "url": f"https://example.com/offre/{key}",
        "unique_key": key,
        "created_at": created_at,
        # Les offres A sont aussi rattachées à B : B n'a simplement pas de
        # document offer_relevance (cf. test_relevance_is_per_user).
        "matched_user_ids": [USER_A_ID, USER_B_ID],
    }
    if sector is not None:
        doc["sector"] = sector
    if company_size is not None:
        doc["company_size"] = company_size
    return db.job_offers.insert_one(doc).inserted_id


def _insert_relevance(db, user_id, offer_id, score, failed_conditions=None):
    db.offer_relevance.insert_one(
        {
            "user_id": user_id,
            "offer_id": str(offer_id),
            "score": score,
            "level": "x",
            "failed_conditions": failed_conditions or [],
            "breakdown": {},
            "unknown_components": [],
            "updated_at": datetime.now(timezone.utc),
        }
    )


@pytest.fixture
def seeded_offers(db):
    """A1 (score 82, la plus ancienne) .. A4 (sans offer_relevance, la plus récente).

    Nettoyage en teardown : la base de test est partagée entre tous les tests du
    module (pas de reset par test), et la liste `/job-offers/` ne filtre pas sur
    autre chose que `matched_user_ids` — sans ce nettoyage, les offres d'un test
    polluent le suivant.
    """
    base = datetime.now(timezone.utc) - timedelta(days=10)
    a1 = _insert_offer(db, poste="A1", created_at=base)
    a2 = _insert_offer(db, poste="A2", created_at=base + timedelta(days=1))
    a3 = _insert_offer(
        db, poste="A3", created_at=base + timedelta(days=2), sector="tech_it", company_size="pme"
    )
    a4 = _insert_offer(db, poste="A4", created_at=base + timedelta(days=3))

    _insert_relevance(db, USER_A_ID, a1, 82)
    _insert_relevance(db, USER_A_ID, a2, 65)
    _insert_relevance(db, USER_A_ID, a3, 30, failed_conditions=["geo"])
    # A4 : pas de document offer_relevance (garde d'interaction / avant premier rematch).

    offer_ids = [a1, a2, a3, a4]
    try:
        yield {"a1": a1, "a2": a2, "a3": a3, "a4": a4}
    finally:
        db.job_offers.delete_many({"_id": {"$in": offer_ids}})
        db.offer_relevance.delete_many({"offer_id": {"$in": [str(oid) for oid in offer_ids]}})


def test_relevance_lookup_filters_by_current_user():
    """Pure : le sous-pipeline du $lookup filtre bien sur l'utilisateur courant."""
    stages = relevance_lookup_stages("u1")
    lookup_stage = next(s for s in stages if "$lookup" in s)
    assert lookup_stage["$lookup"]["from"] == "offer_relevance"
    sub_pipeline = lookup_stage["$lookup"]["pipeline"]
    match_stage = next(s for s in sub_pipeline if "$match" in s)
    assert match_stage["$match"] == {"user_id": "u1"}


def test_build_list_pipeline_recent_sort_places_lookup_after_limit():
    """M2 (structurel) : en tri `recent`, le lookup de pertinence n'est pas requis
    par le tri final, il peut donc être reporté après `$skip`/`$limit`."""
    pipeline = _build_list_pipeline(
        {}, sort="recent", current_user=_make_user(USER_A_ID), skip=0, limit=10
    )
    limit_index = next(i for i, stage in enumerate(pipeline) if "$limit" in stage)
    lookup_index = next(i for i, stage in enumerate(pipeline) if "$lookup" in stage)
    assert lookup_index > limit_index


def test_build_list_pipeline_relevance_sort_places_lookup_before_sort():
    """M2 : en tri `relevance`, `_score_sort` dépend du lookup, qui doit donc le
    précéder."""
    pipeline = _build_list_pipeline(
        {}, sort="relevance", current_user=_make_user(USER_A_ID), skip=0, limit=10
    )
    sort_on_score_index = next(
        i
        for i, stage in enumerate(pipeline)
        if "$sort" in stage and "_score_sort" in stage["$sort"]
    )
    lookup_index = next(i for i, stage in enumerate(pipeline) if "$lookup" in stage)
    assert lookup_index < sort_on_score_index


def test_build_list_pipeline_ends_with_unset_of_internal_fields():
    """M21 : preuve structurelle, sur le pipeline construit et pas sur la réponse,
    que les champs internes du lookup ne survivent jamais à la construction."""
    pipeline = _build_list_pipeline(
        {}, sort="relevance", current_user=_make_user(USER_A_ID), skip=0, limit=10
    )
    assert pipeline[-1] == {"$unset": ["_relevance", "_oid_str", "_score_sort"]}


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
    assert by_poste["A3"]["failed_conditions"] == ["geo"]
    assert by_poste["A4"]["failed_conditions"] == []


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
def test_get_single_offer_exposes_failed_conditions(client, db, as_user_a, seeded_offers):
    """M4 : la route détail doit lire `offer_relevance`, pas seulement la liste."""
    res = client.get(f"/job-offers/{seeded_offers['a3']}")

    assert res.status_code == 200, res.text
    assert res.json()["failed_conditions"] == ["geo"]


@requires_mongo
def test_get_single_offer_defaults_failed_conditions_to_empty_list(client, db, as_user_a, seeded_offers):
    """A4 n'a pas de document `offer_relevance` : `failed_conditions` reste `[]`."""
    res = client.get(f"/job-offers/{seeded_offers['a4']}")

    assert res.status_code == 200, res.text
    assert res.json()["failed_conditions"] == []


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
    assert by_poste["A3"]["failed_conditions"] == ["geo"]


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
