"""Tests de `offer_profile_matcher` : rattachement par score hybride (Task 6).

Base de données et `embed` entièrement factices, en mémoire — aucun Motor ni
appel réseau réel. Les vecteurs factices sont choisis pour produire des
cosinus connus (`cosine_similarity` est un simple produit scalaire/normes,
cf. `role_normalizer.py`), afin de calibrer précisément les scores attendus
contre les constantes réelles de `offer_scoring.constants`.
"""

import logging
import math

import pytest
from bson import ObjectId

from app.services.offer_profile_matcher import rematch_user, tag_new_offers
from app.services.offer_scoring.constants import SCORING_VERSION
from app.services.offer_scoring.embeddings import offer_embedding_text
from app.services.offer_scoring.score import profile_features

# ---------- identifiants ----------


def oid(suffix: str) -> ObjectId:
    return ObjectId(suffix.rjust(24, "0"))


# ---------- fake DB (en mémoire, aucun Motor réel) ----------


def _matches(doc, query):
    for key, cond in query.items():
        value = doc.get(key)
        if isinstance(cond, dict):
            if "$ne" in cond and value == cond["$ne"]:
                return False
            if "$in" in cond and value not in cond["$in"]:
                return False
        elif value != cond:
            return False
    return True


class FakeListCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return list(self._docs)


class FakeAsyncIterCursor:
    def __init__(self, docs):
        self._docs = docs

    def __aiter__(self):
        self._it = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class FakeJobOffersCollection:
    def __init__(self, docs):
        self.docs = docs
        self.update_many_calls = []

    def find(self, query):
        return FakeListCursor([d for d in self.docs if _matches(d, query)])

    async def update_many(self, filter_, update):
        self.update_many_calls.append((filter_, update))
        ids = filter_["_id"]["$in"]
        for doc in self.docs:
            if doc["_id"] not in ids:
                continue
            if "$addToSet" in update:
                for field, value in update["$addToSet"].items():
                    current = doc.setdefault(field, [])
                    if value not in current:
                        current.append(value)
            if "$pull" in update:
                for field, value in update["$pull"].items():
                    current = doc.get(field, [])
                    doc[field] = [v for v in current if v != value]

    def aggregate(self, pipeline):
        out = []
        for doc in self.docs:
            if doc.get("is_deleted"):
                continue
            skills = doc.get("competences_cles") or []
            unique = list(dict.fromkeys(skills)) if skills else [None]
            out.append({"_id": doc["_id"], "skills": unique})
        return FakeAsyncIterCursor(out)


class FakeCandidateProfileCollection:
    def __init__(self, profiles):
        self.profiles = profiles

    async def find_one(self, query):
        user_id = query.get("user_id")
        for p in self.profiles:
            if p.get("user_id") == user_id:
                return p
        return None

    def find(self, query):
        return FakeListCursor(list(self.profiles))


class FakeOfferEmbeddingsCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def find(self, query):
        return FakeAsyncIterCursor([d for d in self.docs if _matches(d, query)])

    async def update_one(self, filter_, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, filter_):
                doc.update(update.get("$set", {}))
                return
        if upsert:
            new_doc = dict(filter_)
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)


class FakeOfferRelevanceCollection:
    def __init__(self):
        self.docs = []
        self.bulk_write_calls = []

    async def bulk_write(self, ops):
        self.bulk_write_calls.append(ops)
        for op in ops:
            existing = next((d for d in self.docs if _matches(d, op._filter)), None)
            if existing is not None:
                existing.update(op._doc.get("$set", {}))
            elif op._upsert:
                new_doc = dict(op._filter)
                new_doc.update(op._doc.get("$set", {}))
                self.docs.append(new_doc)


class FakeSimpleCollection:
    """`user_offer_interactions` / `applications` : `find().to_list()` seulement."""

    def __init__(self, docs):
        self.docs = docs

    def find(self, query):
        return FakeListCursor([d for d in self.docs if _matches(d, query)])


def make_db(*, profiles=None, offers=None, embeddings=None, interactions=None, applications=None):
    offer_relevance = FakeOfferRelevanceCollection()
    db = {
        "candidate_profile": FakeCandidateProfileCollection(profiles or []),
        "job_offers": FakeJobOffersCollection(offers or []),
        "offer_embeddings": FakeOfferEmbeddingsCollection(embeddings),
        "offer_relevance": offer_relevance,
        "user_offer_interactions": FakeSimpleCollection(interactions or []),
        "applications": FakeSimpleCollection(applications or []),
    }
    return db, offer_relevance


def vector_for_cosine(cos: float) -> list:
    """Vecteur unitaire dont le cosinus avec PROFILE_VECTOR == [1.0, 0.0] est `cos`."""
    return [cos, math.sqrt(max(0.0, 1 - cos * cos))]


PROFILE_VECTOR = [1.0, 0.0]


def make_fake_embed(vector_by_text: dict):
    calls = []

    async def fake_embed(texts):
        calls.append(list(texts))
        return [vector_by_text[t] for t in texts]

    return fake_embed, calls


def identity_for(profile: dict) -> str:
    return profile_features(profile).identity


# ---------- profil candidat ----------

USER_ID = oid("1")

DEFAULT_PREFERENCES = {
    "target_roles": ["Data Engineer"],
    "seniority_levels": [],
    "preferred_industries": [],
    "preferred_company_sizes": [],
    "locations": [],
    "remote_policy": "flexible",
    "contract_types": [],
    "excluded_keywords": [],
}


def make_profile(*, user_id=None, headline="Data Engineer", skills=None, preferences=None):
    return {
        "user_id": user_id if user_id is not None else USER_ID,
        "headline": headline,
        "skills": skills if skills is not None else {"tech": ["Python"]},
        "preferences": {**DEFAULT_PREFERENCES, **(preferences or {})},
    }


# ---------- rematch_user ----------


@pytest.mark.asyncio
async def test_rematch_user_attaches_by_score_and_writes_relevance():
    profile = make_profile()
    good_offer = {
        "_id": oid("10"),
        "poste": "Data Engineer",
        "description": "Poste data chez une scale-up lyonnaise.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
    }
    bad_offer = {
        "_id": oid("20"),
        "poste": "Comptable",
        "description": "Gestion comptable quotidienne.",
        "competences_cles": [],
        "localisation": "Nantes",
        "type_contrat": "CDI",
    }
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(good_offer): vector_for_cosine(0.95),
        offer_embedding_text(bad_offer): vector_for_cosine(0.62),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile], offers=[good_offer, bad_offer])

    summary = await rematch_user(str(profile["user_id"]), db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert offers_collection.update_many_calls[0] == (
        {"_id": {"$in": [good_offer["_id"]]}},
        {"$addToSet": {"matched_user_ids": str(profile["user_id"])}},
    )
    assert offers_collection.update_many_calls[1] == (
        {"_id": {"$in": [bad_offer["_id"]]}},
        {"$pull": {"matched_user_ids": str(profile["user_id"])}},
    )
    assert summary.attached == 1
    assert summary.detached == 1

    relevance_by_offer = {d["offer_id"]: d for d in offer_relevance.docs}
    assert set(relevance_by_offer) == {str(good_offer["_id"]), str(bad_offer["_id"])}
    good_doc = relevance_by_offer[str(good_offer["_id"])]
    assert good_doc["user_id"] == str(profile["user_id"])
    assert good_doc["level"] == "strong"
    assert good_doc["scoring_version"] == SCORING_VERSION
    assert "breakdown" in good_doc
    assert "unknown_components" in good_doc
    assert "failed_conditions" in good_doc
    assert "updated_at" in good_doc


@pytest.mark.asyncio
async def test_rematch_user_capped_offer_stays_attached():
    profile = make_profile(preferences={"locations": ["Lyon"]})
    capped_offer = {
        "_id": oid("30"),
        "poste": "Data Engineer",
        "description": "Poste data engineer parisien.",
        "competences_cles": ["Python"],
        "localisation": "Paris 15e",
        "type_contrat": "CDI",
    }
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(capped_offer): vector_for_cosine(0.95),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile], offers=[capped_offer])

    summary = await rematch_user(str(profile["user_id"]), db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert offers_collection.update_many_calls == [
        (
            {"_id": {"$in": [capped_offer["_id"]]}},
            {"$addToSet": {"matched_user_ids": str(profile["user_id"])}},
        )
    ]
    assert summary.attached == 1
    assert summary.detached == 0

    doc = offer_relevance.docs[0]
    assert doc["level"] == "weak"
    assert doc["failed_conditions"] == ["geo"]


@pytest.mark.asyncio
@pytest.mark.parametrize("guard_kind", ["applications", "interaction"])
async def test_rematch_user_keeps_applied_offer_below_floor(guard_kind, caplog):
    profile = make_profile()
    offer = {
        "_id": oid("40"),
        "poste": "Comptable",
        "description": "Gestion comptable quotidienne.",
        "competences_cles": [],
        "localisation": "Lyon",
        "type_contrat": "CDI",
    }
    offer_id_str = str(offer["_id"])
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(offer): vector_for_cosine(0.62),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)

    applications = []
    interactions = []
    if guard_kind == "applications":
        applications.append({"user_id": ObjectId(str(profile["user_id"])), "offer_id": offer_id_str})
    else:
        interactions.append({"user_id": str(profile["user_id"]), "offer_id": offer_id_str, "status": "hidden"})

    db, offer_relevance = make_db(
        profiles=[profile], offers=[offer], interactions=interactions, applications=applications
    )

    with caplog.at_level(logging.WARNING):
        summary = await rematch_user(str(profile["user_id"]), db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert not any("$pull" in update for _filter, update in offers_collection.update_many_calls)
    assert summary.kept_by_guard == 1
    assert summary.applied_below_floor == [offer_id_str]
    assert any("FLOOR" in record.message for record in caplog.records)
    # l'offre reste scorée (sous FLOOR), même si non rattachée.
    assert offer_relevance.docs[0]["offer_id"] == offer_id_str


@pytest.mark.asyncio
async def test_rematch_user_hard_filtered_offer_detached():
    profile = make_profile(preferences={"contract_types": ["CDI"]})
    offer = {
        "_id": oid("50"),
        "poste": "Data Analyst",
        "description": "Stage de 6 mois en data, Python au quotidien.",
        "type_contrat": "Stage",
        "localisation": "Lyon",
        "competences_cles": [],
    }
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(offer): vector_for_cosine(0.9),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile], offers=[offer])

    summary = await rematch_user(str(profile["user_id"]), db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert offers_collection.update_many_calls == [
        ({"_id": {"$in": [offer["_id"]]}}, {"$pull": {"matched_user_ids": str(profile["user_id"])}})
    ]
    assert offer_relevance.docs == []
    assert summary.detached == 1
    assert summary.attached == 0


@pytest.mark.asyncio
async def test_rematch_user_embedding_down_detaches_nothing_new():
    profile = make_profile()
    offer = {
        "_id": oid("60"),
        "poste": "Data Engineer",
        "description": "Poste data engineer.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
    }

    async def failing_embed(texts):
        raise RuntimeError("quota exceeded")

    db, offer_relevance = make_db(profiles=[profile], offers=[offer])

    summary = await rematch_user(str(profile["user_id"]), db, embed=failing_embed)

    offers_collection = db["job_offers"]
    assert offers_collection.update_many_calls == [
        (
            {"_id": {"$in": [offer["_id"]]}},
            {"$addToSet": {"matched_user_ids": str(profile["user_id"])}},
        )
    ]
    assert summary.attached == 1
    assert summary.detached == 0
    relevance_doc = offer_relevance.docs[0]
    assert relevance_doc["breakdown"]["semantic"] == 22.5
    assert "semantic" in relevance_doc["unknown_components"]


@pytest.mark.asyncio
async def test_rematch_user_dry_run_writes_nothing():
    profile = make_profile()
    offer = {
        "_id": oid("70"),
        "poste": "Data Engineer",
        "description": "Poste data engineer.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
    }
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(offer): vector_for_cosine(0.95),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile], offers=[offer])
    embeddings_collection = db["offer_embeddings"]

    summary = await rematch_user(str(profile["user_id"]), db, apply=False, embed=fake_embed)

    assert db["job_offers"].update_many_calls == []
    assert offer_relevance.docs == []
    assert embeddings_collection.docs == []
    assert summary.attached == 1
    assert summary.detached == 0


@pytest.mark.asyncio
async def test_rematch_user_empty_profile_attaches_nothing():
    profile = make_profile(headline="", skills={}, preferences={"target_roles": []})
    offer = {
        "_id": oid("80"),
        "poste": "Data Engineer",
        "description": "Poste data engineer.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
    }
    offer_id_str = str(offer["_id"])
    interactions = [{"user_id": str(profile["user_id"]), "offer_id": offer_id_str, "status": "seen"}]

    async def dummy_embed(texts):
        return [[1.0, 0.0] for _ in texts]

    db, offer_relevance = make_db(profiles=[profile], offers=[offer], interactions=interactions)

    summary = await rematch_user(str(profile["user_id"]), db, embed=dummy_embed)

    assert db["job_offers"].update_many_calls == []
    assert offer_relevance.docs == []
    assert summary.attached == 0
    assert summary.kept_by_guard == 1
    assert summary.applied_below_floor == []


# ---------- tag_new_offers ----------


@pytest.mark.asyncio
async def test_tag_new_offers_scores_batch_for_every_profile():
    profile_a = make_profile(user_id=oid("1"), headline="Data Engineer", skills={"tech": ["Python"]})
    profile_b = make_profile(user_id=oid("2"), headline="Java Developer", skills={"tech": ["Java"]})
    offer1 = {
        "_id": oid("90"),
        "poste": "Data Engineer",
        "description": "Poste Python.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
    }
    offer2 = {
        "_id": oid("91"),
        "poste": "Java Developer",
        "description": "Poste Java.",
        "competences_cles": ["Java"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
    }
    vector_by_text = {
        identity_for(profile_a): [1.0, 0.0],
        identity_for(profile_b): [0.0, 1.0],
        offer_embedding_text(offer1): [1.0, 0.0],
        offer_embedding_text(offer2): [0.0, 1.0],
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile_a, profile_b], offers=[offer1, offer2])

    await tag_new_offers([offer1["_id"], offer2["_id"]], db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert all("$pull" not in update for _filter, update in offers_collection.update_many_calls)

    calls_by_user = {
        update["$addToSet"]["matched_user_ids"]: filter_ for filter_, update in offers_collection.update_many_calls
    }
    assert calls_by_user[str(profile_a["user_id"])] == {"_id": {"$in": [offer1["_id"]]}}
    assert calls_by_user[str(profile_b["user_id"])] == {"_id": {"$in": [offer2["_id"]]}}
    assert len(offer_relevance.docs) == 4


@pytest.mark.asyncio
async def test_tag_new_offers_empty_list_does_nothing():
    from unittest.mock import AsyncMock, MagicMock

    mock_offers_collection = MagicMock()
    mock_offers_collection.find = MagicMock()
    mock_db = {"job_offers": mock_offers_collection}

    await tag_new_offers([], mock_db)

    mock_offers_collection.find.assert_not_called()
