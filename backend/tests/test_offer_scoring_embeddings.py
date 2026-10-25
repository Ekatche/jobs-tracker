import pytest

from app.services.offer_scoring.constants import EMBEDDING_MODEL
from app.services.offer_scoring.embeddings import (
    embed_texts,
    get_offer_vectors,
    get_profile_vector,
    offer_embedding_text,
    text_hash,
)


# ---------- fake DB model (mirrors FakeCollection in test_offer_sources.py:332,
# extended with update_one/upsert since offer_embeddings is a write-through cache) ----------


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


class FakeOfferEmbeddingsCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.update_one_calls = []

    @staticmethod
    def _matches(doc, query):
        for key, cond in query.items():
            value = doc.get(key)
            if isinstance(cond, dict) and "$in" in cond:
                if value not in cond["$in"]:
                    return False
            elif value != cond:
                return False
        return True

    def find(self, query):
        return FakeCursor([d for d in self.docs if self._matches(d, query)])

    async def update_one(self, filter_, update, upsert=False):
        self.update_one_calls.append((filter_, update, upsert))
        for doc in self.docs:
            if self._matches(doc, filter_):
                doc.update(update.get("$set", {}))
                return
        if upsert:
            new_doc = dict(filter_)
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)


def make_fake_db(docs=None):
    collection = FakeOfferEmbeddingsCollection(docs)
    return {"offer_embeddings": collection}, collection


def make_counting_embed(vector=None):
    calls = []

    async def fake_embed(texts):
        calls.append(list(texts))
        return [list(vector or [1.0, 0.0]) for _ in texts]

    return fake_embed, calls


# ---------- offer_embedding_text ----------


def test_offer_embedding_text_excludes_competences_cles():
    offer = {
        "poste": "Data Engineer",
        "description": "Rejoignez notre équipe data au quotidien.",
        "competences_cles": ["Kubernetes"],
    }
    text = offer_embedding_text(offer)
    assert "Kubernetes" not in text


def test_offer_embedding_text_truncates_and_collapses_spaces():
    # Un bloc de run de retours à la ligne entre deux mots longs : collapse-puis-tronque
    # et tronque-puis-collapse donnent un nombre de "B" différent dans les 1000
    # premiers caractères — le test échoue sous l'ordre erroné (tronquer avant de
    # collapser), ce qui le distingue d'une simple absence de "\n"/double espace.
    description = "A" * 600 + "\n\n\n" + "B" * 600
    offer = {"poste": "Data Analyst", "description": description}

    text = offer_embedding_text(offer)

    # Ordre requis (calibration COS_FLOOR/COS_CEIL) : collapse d'abord, tronque ensuite.
    expected_desc = " ".join(description.split())[:1000]
    assert text == f"Data Analyst. {expected_desc}"
    assert "\n" not in text
    assert "  " not in text


def test_offer_embedding_text_empty_offer_is_none():
    assert offer_embedding_text({"poste": "Non spécifié", "description": None}) is None


@pytest.mark.asyncio
async def test_get_offer_vectors_skips_none_text_offer():
    db, _collection = make_fake_db()
    fake_embed, calls = make_counting_embed()
    offers = [{"_id": "empty-1", "poste": "Non spécifié", "description": None}]

    vectors = await get_offer_vectors(offers, db, embed=fake_embed)

    assert vectors == {}
    assert calls == []


# ---------- get_offer_vectors ----------


@pytest.mark.asyncio
async def test_get_offer_vectors_uses_cache_and_embeds_only_missing():
    offer_cached = {"_id": "cached-1", "poste": "Data Engineer", "description": "Desc A"}
    offer_missing = {"_id": "missing-1", "poste": "Data Analyst", "description": "Desc B"}
    cached_doc = {
        "offer_id": "cached-1",
        "model": EMBEDDING_MODEL,
        "text_hash": text_hash(offer_embedding_text(offer_cached)),
        "vector": [0.1, 0.2],
    }
    db, collection = make_fake_db([cached_doc])
    fake_embed, calls = make_counting_embed([9.0, 9.0])

    vectors = await get_offer_vectors([offer_cached, offer_missing], db, embed=fake_embed)

    assert calls == [[offer_embedding_text(offer_missing)]]
    assert vectors["cached-1"] == [0.1, 0.2]
    assert vectors["missing-1"] == [9.0, 9.0]
    assert {d["offer_id"] for d in collection.docs} == {"cached-1", "missing-1"}


@pytest.mark.asyncio
async def test_get_offer_vectors_ignores_other_model_and_stale_hash():
    offer_other_model = {"_id": "other-model", "poste": "Data Engineer", "description": "Desc A"}
    offer_stale = {"_id": "stale", "poste": "Data Analyst", "description": "Desc B"}
    other_model_doc = {
        "offer_id": "other-model",
        "model": "text-embedding-3-small",
        "text_hash": text_hash(offer_embedding_text(offer_other_model)),
        "vector": [1.0, 1.0],
    }
    stale_doc = {
        "offer_id": "stale",
        "model": EMBEDDING_MODEL,
        "text_hash": "stale-hash-not-matching",
        "vector": [2.0, 2.0],
    }
    db, collection = make_fake_db([other_model_doc, stale_doc])
    fake_embed, calls = make_counting_embed([9.0, 9.0])

    vectors = await get_offer_vectors([offer_other_model, offer_stale], db, embed=fake_embed)

    assert set(calls[0]) == {
        offer_embedding_text(offer_other_model),
        offer_embedding_text(offer_stale),
    }
    assert vectors == {"other-model": [9.0, 9.0], "stale": [9.0, 9.0]}

    # l'ancien document de l'autre modèle n'est ni lu ni écrasé
    untouched = next(
        d for d in collection.docs if d["offer_id"] == "other-model" and d["model"] == "text-embedding-3-small"
    )
    assert untouched["vector"] == [1.0, 1.0]

    # un nouveau document est écrit pour EMBEDDING_MODEL
    fresh = next(d for d in collection.docs if d["offer_id"] == "other-model" and d["model"] == EMBEDDING_MODEL)
    assert fresh["vector"] == [9.0, 9.0]


@pytest.mark.asyncio
async def test_get_offer_vectors_fail_open():
    offer_cached = {"_id": "cached-1", "poste": "Data Engineer", "description": "Desc A"}
    offer_missing = {"_id": "missing-1", "poste": "Data Analyst", "description": "Desc B"}
    cached_doc = {
        "offer_id": "cached-1",
        "model": EMBEDDING_MODEL,
        "text_hash": text_hash(offer_embedding_text(offer_cached)),
        "vector": [0.5, 0.5],
    }
    db, _collection = make_fake_db([cached_doc])

    async def failing_embed(texts):
        raise RuntimeError("quota exceeded")

    vectors = await get_offer_vectors([offer_cached, offer_missing], db, embed=failing_embed)

    assert vectors == {"cached-1": [0.5, 0.5]}


@pytest.mark.asyncio
async def test_get_offer_vectors_no_cache_write_when_cache_false():
    offer = {"_id": "1", "poste": "Data Engineer", "description": "Desc"}
    db, collection = make_fake_db()
    fake_embed, _calls = make_counting_embed([3.0, 3.0])

    vectors = await get_offer_vectors([offer], db, embed=fake_embed, cache=False)

    assert vectors == {"1": [3.0, 3.0]}
    assert collection.docs == []


# ---------- get_profile_vector ----------


@pytest.mark.asyncio
async def test_get_profile_vector_empty_identity_is_none():
    assert await get_profile_vector("") is None
    assert await get_profile_vector("   ") is None


@pytest.mark.asyncio
async def test_get_profile_vector_returns_vector():
    fake_embed, calls = make_counting_embed([1.0, 2.0])

    vector = await get_profile_vector("Data Engineer", embed=fake_embed)

    assert vector == [1.0, 2.0]
    assert calls == [["Data Engineer"]]


@pytest.mark.asyncio
async def test_get_profile_vector_fail_open():
    async def failing_embed(texts):
        raise RuntimeError("down")

    assert await get_profile_vector("Data Engineer", embed=failing_embed) is None


# ---------- embed_texts : retry par lot ----------


@pytest.mark.asyncio
async def test_embed_texts_retries_transient_batch_failure(monkeypatch):
    calls = []

    async def flaky_aembedding(model, input):
        calls.append(list(input))
        if len(calls) == 1:
            raise RuntimeError("transient failure")
        return {"data": [{"embedding": [1.0, 0.0]} for _ in input]}

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("litellm.aembedding", flaky_aembedding)
    monkeypatch.setattr("app.services.offer_scoring.embeddings.asyncio.sleep", fake_sleep)

    vectors = await embed_texts(["a", "b"])

    assert vectors == [[1.0, 0.0], [1.0, 0.0]]
    assert len(calls) == 2
    assert sleep_calls == [1]


@pytest.mark.asyncio
async def test_embed_texts_raises_after_three_failed_attempts(monkeypatch):
    calls = []

    async def always_failing_aembedding(model, input):
        calls.append(list(input))
        raise RuntimeError("quota exceeded")

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("litellm.aembedding", always_failing_aembedding)
    monkeypatch.setattr("app.services.offer_scoring.embeddings.asyncio.sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="quota exceeded"):
        await embed_texts(["a"])

    assert len(calls) == 3
    assert sleep_calls == [1, 2]
