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
from pymongo import DeleteOne

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
        if key == "$or":
            if not any(_matches(doc, sub_query) for sub_query in cond):
                return False
            continue
        value = doc.get(key)
        if isinstance(cond, dict):
            if "$ne" in cond and value == cond["$ne"]:
                return False
            if "$in" in cond and value not in cond["$in"]:
                return False
            if "$nin" in cond and value in cond["$nin"]:
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
            if "$set" in update:
                doc.update(update["$set"])
            if "$unset" in update:
                for field in update["$unset"]:
                    doc.pop(field, None)

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
            if isinstance(op, DeleteOne):
                self.docs = [d for d in self.docs if not _matches(d, op._filter)]
                continue
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
async def test_rematch_user_no_profile_does_nothing():
    from unittest.mock import AsyncMock, MagicMock

    mock_profile_collection = MagicMock()
    mock_profile_collection.find_one = AsyncMock(return_value=None)

    mock_offers_cursor = MagicMock()
    mock_offers_cursor.to_list = AsyncMock(return_value=[])

    mock_offers_collection = MagicMock()
    mock_offers_collection.find = MagicMock(return_value=mock_offers_cursor)
    mock_offers_collection.update_many = AsyncMock()

    mock_db = {"candidate_profile": mock_profile_collection, "job_offers": mock_offers_collection}

    await rematch_user("650000000000000000000099", mock_db)

    mock_offers_collection.update_many.assert_not_called()


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
        "matched_user_ids": [str(USER_ID)],
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
async def test_rematch_user_out_of_zone_offer_is_detached_despite_top_score():
    profile = make_profile(preferences={"locations": ["Lyon"]})
    paris_offer = {
        "_id": oid("31"),
        "poste": "Data Engineer",
        "description": "Poste data engineer parisien.",
        "competences_cles": ["Python"],
        "localisation": "Greater Paris Metropolitan Region",
        "type_contrat": "CDI",
        "matched_user_ids": [str(profile["user_id"])],
    }
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(paris_offer): vector_for_cosine(0.95),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile], offers=[paris_offer])

    summary = await rematch_user(str(profile["user_id"]), db, embed=fake_embed)

    assert db["job_offers"].update_many_calls == [
        (
            {"_id": {"$in": [paris_offer["_id"]]}},
            {"$pull": {"matched_user_ids": str(profile["user_id"])}},
        )
    ]
    assert summary.detached == 1
    assert offer_relevance.docs == []


@pytest.mark.asyncio
async def test_rematch_user_capped_offer_stays_attached():
    profile = make_profile(preferences={"locations": ["Lyon"], "contract_types": ["CDI"]})
    capped_offer = {
        "_id": oid("30"),
        "poste": "Data Engineer",
        "description": "Poste data engineer lyonnais.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDD",
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
    assert doc["failed_conditions"] == ["contract"]


@pytest.mark.asyncio
@pytest.mark.parametrize("guard_kind", ["applications", "interaction"])
async def test_rematch_user_keeps_applied_offer_below_floor(guard_kind, caplog):
    """Une offre DÉJÀ rattachée qui tombe sous FLOOR mais que le candidat a
    gardée/postulée n'est pas détachée : `kept_by_guard` compte le maintien,
    `kept_below_floor` liste l'offre. Une offre jamais rattachée n'aurait
    rien à « garder » (cf. test_rematch_user_empty_profile_attaches_nothing)."""
    profile = make_profile()
    offer = {
        "_id": oid("40"),
        "poste": "Comptable",
        "description": "Gestion comptable quotidienne.",
        "competences_cles": [],
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "matched_user_ids": [str(profile["user_id"])],
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
    assert summary.kept_below_floor == [offer_id_str]
    assert any("sous FLOOR" in record.message and offer_id_str in record.message for record in caplog.records)
    assert summary.kept_hard_filtered == []
    # l'offre reste scorée (sous FLOOR), même si non rattachée.
    assert offer_relevance.docs[0]["offer_id"] == offer_id_str


@pytest.mark.asyncio
@pytest.mark.parametrize("status,should_guard", [("none", False), ("saved", True)])
async def test_rematch_user_interaction_status_none_does_not_guard(status, should_guard):
    """`status: "none"` (écrit par set_offer_seen pour une simple vue, job_offers.py:666)
    n'est pas une interaction réelle et ne doit pas protéger du détachement ;
    `status: "saved"` protège, comme les autres statuts réels."""
    profile = make_profile()
    offer = {
        "_id": oid("45"),
        "poste": "Comptable",
        "description": "Gestion comptable quotidienne.",
        "competences_cles": [],
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "matched_user_ids": [str(profile["user_id"])],
    }
    offer_id_str = str(offer["_id"])
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(offer): vector_for_cosine(0.62),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    interactions = [{"user_id": str(profile["user_id"]), "offer_id": offer_id_str, "status": status}]
    db, offer_relevance = make_db(profiles=[profile], offers=[offer], interactions=interactions)

    summary = await rematch_user(str(profile["user_id"]), db, embed=fake_embed)

    offers_collection = db["job_offers"]
    pulled = any("$pull" in update for _filter, update in offers_collection.update_many_calls)
    if should_guard:
        assert not pulled
        assert summary.kept_by_guard == 1
        assert summary.detached == 0
    else:
        assert pulled
        assert summary.kept_by_guard == 0
        assert summary.detached == 1


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
        "matched_user_ids": [str(profile["user_id"])],
    }
    offer_id_str = str(offer["_id"])
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(offer): vector_for_cosine(0.9),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile], offers=[offer])
    # document offer_relevance périmé : l'offre était scorée avant de devenir
    # filtrée dur (ex. contract_types restreint après coup) ; il doit disparaître.
    offer_relevance.docs.append(
        {"user_id": str(profile["user_id"]), "offer_id": offer_id_str, "score": 80, "level": "strong"}
    )

    summary = await rematch_user(str(profile["user_id"]), db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert offers_collection.update_many_calls == [
        ({"_id": {"$in": [offer["_id"]]}}, {"$pull": {"matched_user_ids": str(profile["user_id"])}})
    ]
    assert offer_relevance.docs == []
    assert summary.detached == 1
    assert summary.attached == 0


@pytest.mark.asyncio
async def test_rematch_user_keeps_hard_filtered_offer_when_guarded(caplog):
    """Même offre que ci-dessus (devenue filtrée dur), mais protégée par une
    interaction `saved` : gardée (pas de $pull), comptée dans
    `kept_hard_filtered` (pas `kept_below_floor`, elle n'a pas de score), avec
    un warning qui cite la raison du filtre dur."""
    profile = make_profile(preferences={"contract_types": ["CDI"]})
    offer = {
        "_id": oid("51"),
        "poste": "Data Analyst",
        "description": "Stage de 6 mois en data, Python au quotidien.",
        "type_contrat": "Stage",
        "localisation": "Lyon",
        "competences_cles": [],
        "matched_user_ids": [str(profile["user_id"])],
    }
    offer_id_str = str(offer["_id"])
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(offer): vector_for_cosine(0.9),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    interactions = [{"user_id": str(profile["user_id"]), "offer_id": offer_id_str, "status": "saved"}]
    db, offer_relevance = make_db(profiles=[profile], offers=[offer], interactions=interactions)

    with caplog.at_level(logging.WARNING):
        summary = await rematch_user(str(profile["user_id"]), db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert offers_collection.update_many_calls == []
    assert offer_relevance.docs == []
    assert summary.detached == 0
    assert summary.kept_by_guard == 1
    assert summary.kept_hard_filtered == [offer_id_str]
    assert summary.kept_below_floor == []
    assert any("filtrée dur" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_rematch_user_embedding_down_detaches_nothing_new():
    """Panne d'embedding (profil non vide, cos indisponible) : les offres non
    filtrées dur ne sont pas évaluées ce tour-ci — ni $addToSet, ni $pull, ni
    écriture offer_relevance. Le stock entier reste dans l'état où il était."""
    profile = make_profile()
    unattached_offer = {
        "_id": oid("60"),
        "poste": "Comptable",
        "description": "Gestion comptable quotidienne.",
        "competences_cles": [],
        "localisation": "Nantes",
        "type_contrat": "CDI",
    }
    attached_offer = {
        "_id": oid("61"),
        "poste": "Data Engineer",
        "description": "Poste data engineer.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "matched_user_ids": [str(profile["user_id"])],
    }

    async def failing_embed(texts):
        raise RuntimeError("quota exceeded")

    db, offer_relevance = make_db(profiles=[profile], offers=[unattached_offer, attached_offer])

    summary = await rematch_user(str(profile["user_id"]), db, embed=failing_embed)

    offers_collection = db["job_offers"]
    assert offers_collection.update_many_calls == []
    assert offer_relevance.docs == []
    assert summary.semantic_unknown == 2
    assert summary.attached == 0
    assert summary.detached == 0
    assert str(profile["user_id"]) not in (unattached_offer.get("matched_user_ids") or [])
    assert str(profile["user_id"]) in attached_offer["matched_user_ids"]


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
    """Garde sur une offre NON rattachée (ni avant ni après ce rematch) :
    `kept_by_guard` ne doit rien compter — il n'y a rien à « garder », l'offre
    n'a jamais été attachée. Seule une offre déjà rattachée peut être gardée
    ou détachée (cf. test_rematch_user_keeps_applied_offer_below_floor)."""
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
    assert summary.kept_by_guard == 0
    assert summary.kept_below_floor == []
    assert summary.kept_hard_filtered == []


@pytest.mark.asyncio
async def test_rematch_user_counts_only_real_changes():
    """`attached`/`detached` ne comptent (et n'écrivent) que les changements
    réels : une offre déjà rattachée toujours au-dessus de FLOOR ne redéclenche
    pas un $addToSet ; une offre jamais rattachée et sous FLOOR ne déclenche
    pas un $pull inutile."""
    profile = make_profile()
    already_attached_strong_offer = {
        "_id": oid("65"),
        "poste": "Data Engineer",
        "description": "Poste data chez une scale-up lyonnaise.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "matched_user_ids": [str(profile["user_id"])],
    }
    never_attached_weak_offer = {
        "_id": oid("66"),
        "poste": "Comptable",
        "description": "Gestion comptable quotidienne.",
        "competences_cles": [],
        "localisation": "Nantes",
        "type_contrat": "CDI",
    }
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(already_attached_strong_offer): vector_for_cosine(0.95),
        offer_embedding_text(never_attached_weak_offer): vector_for_cosine(0.62),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(
        profiles=[profile], offers=[already_attached_strong_offer, never_attached_weak_offer]
    )

    summary = await rematch_user(str(profile["user_id"]), db, embed=fake_embed)

    assert db["job_offers"].update_many_calls == []
    assert summary.attached == 0
    assert summary.detached == 0


# ---------- tag_new_offers ----------


@pytest.mark.asyncio
async def test_tag_new_offers_scores_batch_for_every_profile():
    profile_a = make_profile(
        user_id=oid("1"),
        headline="Data Engineer",
        skills={"tech": ["Python"]},
        preferences={"contract_types": ["CDI"]},
    )
    profile_b = make_profile(
        user_id=oid("2"),
        headline="Java Developer",
        skills={"tech": ["Java"]},
        preferences={"contract_types": ["CDI"]},
    )
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
    # Filtrée dur (contrat exclu) pour les deux profils (contract_types=["CDI"]
    # ci-dessus) : ne doit jamais être rattachée ni scorée, quel que soit le profil.
    excluded_offer = {
        "_id": oid("92"),
        "poste": "Data Analyst",
        "description": "Stage de 6 mois en data.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "Stage",
    }
    excluded_offer_id_str = str(excluded_offer["_id"])
    vector_by_text = {
        identity_for(profile_a): [1.0, 0.0],
        identity_for(profile_b): [0.0, 1.0],
        offer_embedding_text(offer1): [1.0, 0.0],
        offer_embedding_text(offer2): [0.0, 1.0],
        offer_embedding_text(excluded_offer): [1.0, 0.0],
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile_a, profile_b], offers=[offer1, offer2, excluded_offer])

    await tag_new_offers([offer1["_id"], offer2["_id"], excluded_offer["_id"]], db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert all("$pull" not in update for _filter, update in offers_collection.update_many_calls)
    assert not any(
        excluded_offer["_id"] in filter_["_id"]["$in"] for filter_, _update in offers_collection.update_many_calls
    )

    calls_by_user = {
        update["$addToSet"]["matched_user_ids"]: filter_ for filter_, update in offers_collection.update_many_calls
    }
    assert calls_by_user[str(profile_a["user_id"])] == {"_id": {"$in": [offer1["_id"]]}}
    assert calls_by_user[str(profile_b["user_id"])] == {"_id": {"$in": [offer2["_id"]]}}
    assert len(offer_relevance.docs) == 4
    assert not any(d["offer_id"] == excluded_offer_id_str for d in offer_relevance.docs)


@pytest.mark.asyncio
async def test_tag_new_offers_embedding_down_skips_offers(caplog):
    """Panne d'embedding pendant tag_new_offers : l'offre hors sujet n'est pas
    évaluée ce tour (pas de $addToSet, pas de document offer_relevance), elle
    est marquée scoring_pending pour être rejouée, avec un seul enregistrement
    de niveau ERROR agrégé par appel (jamais de texte d'offre)."""
    profile = make_profile()
    offer = {
        "_id": oid("93"),
        "poste": "Comptable",
        "description": "Gestion comptable quotidienne.",
        "competences_cles": [],
        "localisation": "Nantes",
        "type_contrat": "CDI",
    }

    async def failing_embed(texts):
        raise RuntimeError("quota exceeded")

    db, offer_relevance = make_db(profiles=[profile], offers=[offer])

    with caplog.at_level(logging.WARNING):
        await tag_new_offers([offer["_id"]], db, embed=failing_embed)

    offers_collection = db["job_offers"]
    assert not any("$addToSet" in update for _filter, update in offers_collection.update_many_calls)
    assert offer_relevance.docs == []
    assert offer.get("scoring_pending") is True
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_records) == 1
    message = error_records[0].message
    assert offer["poste"] not in message and offer["description"] not in message


@pytest.mark.asyncio
async def test_tag_new_offers_replays_pending_offer_when_embedding_recovers():
    """Une offre laissée `scoring_pending` par une panne d'embedding
    précédente est rejouée dès que l'embedding fonctionne à nouveau, même
    sans figurer dans `offer_ids`."""
    profile = make_profile()
    offer = {
        "_id": oid("94"),
        "poste": "Data Engineer",
        "description": "Poste Python.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "scoring_pending": True,
    }
    vector_by_text = {
        identity_for(profile): [1.0, 0.0],
        offer_embedding_text(offer): [1.0, 0.0],
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile], offers=[offer])

    await tag_new_offers([], db, embed=fake_embed)

    offers_collection = db["job_offers"]
    addtoset_calls = [
        (filter_, update) for filter_, update in offers_collection.update_many_calls if "$addToSet" in update
    ]
    assert len(addtoset_calls) == 1
    assert addtoset_calls[0][0] == {"_id": {"$in": [offer["_id"]]}}
    assert len(offer_relevance.docs) == 1
    assert offer_relevance.docs[0]["offer_id"] == str(offer["_id"])
    assert offer.get("scoring_pending") is None


@pytest.mark.asyncio
async def test_tag_new_offers_does_not_mark_offer_without_text_pending():
    """Une offre sans intitulé ni description n'est jamais embarquable : elle
    ne doit pas rester scoring_pending éternellement."""
    profile = make_profile()
    offer = {
        "_id": oid("95"),
        "poste": "Non spécifié",
        "description": None,
        "competences_cles": [],
        "localisation": "Lyon",
        "type_contrat": "CDI",
    }

    async def failing_embed(texts):
        raise RuntimeError("quota exceeded")

    db, offer_relevance = make_db(profiles=[profile], offers=[offer])

    await tag_new_offers([offer["_id"]], db, embed=failing_embed)

    assert offer.get("scoring_pending") is None
    assert offer_relevance.docs == []


@pytest.mark.asyncio
async def test_tag_new_offers_empty_list_does_nothing():
    db, offer_relevance = make_db(profiles=[make_profile()], offers=[])

    await tag_new_offers([], db)

    offers_collection = db["job_offers"]
    assert offers_collection.update_many_calls == []
    assert offer_relevance.docs == []


@pytest.mark.asyncio
async def test_tag_new_offers_detaches_offer_that_becomes_hard_filtered():
    """`tag_new_offers` applique la même décision que `rematch_user` (M7) :
    une offre déjà rattachée qui devient filtrée dur (ex. contract_types
    restreint après coup) est détachée, pas seulement laissée telle quelle."""
    profile = make_profile(preferences={"contract_types": ["CDI"]})
    offer = {
        "_id": oid("96"),
        "poste": "Data Analyst",
        "description": "Stage de 6 mois en data, Python au quotidien.",
        "type_contrat": "Stage",
        "localisation": "Lyon",
        "competences_cles": [],
        "matched_user_ids": [str(profile["user_id"])],
    }
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(offer): vector_for_cosine(0.9),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    db, offer_relevance = make_db(profiles=[profile], offers=[offer])
    offer_relevance.docs.append(
        {"user_id": str(profile["user_id"]), "offer_id": str(offer["_id"]), "score": 80, "level": "strong"}
    )

    await tag_new_offers([offer["_id"]], db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert offers_collection.update_many_calls == [
        ({"_id": {"$in": [offer["_id"]]}}, {"$pull": {"matched_user_ids": str(profile["user_id"])}})
    ]
    assert offer_relevance.docs == []


@pytest.mark.asyncio
async def test_tag_new_offers_keeps_hard_filtered_offer_with_saved_interaction():
    """La même offre devenue filtrée dur mais avec une interaction `saved`
    reste rattachée (garde d'interaction, `interacted_offer_ids` par
    profil)."""
    profile = make_profile(preferences={"contract_types": ["CDI"]})
    offer = {
        "_id": oid("97"),
        "poste": "Data Analyst",
        "description": "Stage de 6 mois en data, Python au quotidien.",
        "type_contrat": "Stage",
        "localisation": "Lyon",
        "competences_cles": [],
        "matched_user_ids": [str(profile["user_id"])],
    }
    offer_id_str = str(offer["_id"])
    vector_by_text = {
        identity_for(profile): PROFILE_VECTOR,
        offer_embedding_text(offer): vector_for_cosine(0.9),
    }
    fake_embed, _calls = make_fake_embed(vector_by_text)
    interactions = [{"user_id": str(profile["user_id"]), "offer_id": offer_id_str, "status": "saved"}]
    db, offer_relevance = make_db(profiles=[profile], offers=[offer], interactions=interactions)

    await tag_new_offers([offer["_id"]], db, embed=fake_embed)

    offers_collection = db["job_offers"]
    assert not any("$pull" in update for _filter, update in offers_collection.update_many_calls)
    assert str(profile["user_id"]) in offer["matched_user_ids"]


@pytest.mark.asyncio
async def test_tag_new_offers_embedding_down_keeps_attached_offer():
    """Offre déjà rattachée non évaluée ce tour faute de cosinus (panne
    d'embedding) : jamais détachée, comme dans `rematch_user`. Elle est
    marquée `scoring_pending` pour être rejouée."""
    profile = make_profile()
    offer = {
        "_id": oid("98"),
        "poste": "Data Engineer",
        "description": "Poste data engineer.",
        "competences_cles": ["Python"],
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "matched_user_ids": [str(profile["user_id"])],
    }

    async def failing_embed(texts):
        raise RuntimeError("quota exceeded")

    db, offer_relevance = make_db(profiles=[profile], offers=[offer])

    await tag_new_offers([offer["_id"]], db, embed=failing_embed)

    offers_collection = db["job_offers"]
    assert not any("$pull" in update for _filter, update in offers_collection.update_many_calls)
    assert str(profile["user_id"]) in offer["matched_user_ids"]
    assert offer.get("scoring_pending") is True
    assert offer_relevance.docs == []


# ---------- tag_new_offers : (re)création des index de scoring (M21-index) ----------


@pytest.mark.asyncio
async def test_tag_new_offers_creates_scoring_indexes_on_real_db(test_db):
    """`tag_new_offers` (ré)applique `create_offer_scoring_indexes` en tête
    d'appel, avant même le early return sur `offer_ids` vide — c'est le seul
    point d'entrée du chemin de collecte en prod (Airflow), qui ne passe pas
    par le `lifespan` FastAPI. Contre la vraie base de test : on part d'une
    collection sans index applicatif, on appelle `tag_new_offers([], ...)`,
    et les deux index attendus doivent exister à la sortie."""
    fake_embed, _calls = make_fake_embed({})

    for name in ("offer_relevance", "offer_embeddings"):
        for index_name in list((await test_db[name].index_information()).keys()):
            if index_name != "_id_":
                await test_db[name].drop_index(index_name)

    await tag_new_offers([], test_db, embed=fake_embed)

    relevance_indexes = set(
        (await test_db["offer_relevance"].index_information()).keys()
    )
    embeddings_indexes = set(
        (await test_db["offer_embeddings"].index_information()).keys()
    )

    assert "user_id_1_offer_id_1" in relevance_indexes
    assert "offer_id_1_model_1" in embeddings_indexes
