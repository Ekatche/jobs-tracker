"""Tests de `scripts/rematch_all_users.py` : agrégation et reporting des
offres `semantic_unknown` (panne d'embedding) sur l'ensemble des profils, et
garde-fou M8 — aucun appel d'embedding sans `--confirm` ni `--apply`.

Base de données et `rematch_user` entièrement factices — aucun Motor ni
appel réseau réel.
"""

import logging

import pytest

from app.services.offer_profile_matcher import RematchSummary
from scripts import rematch_all_users as script


class _FakeCursor:
    """Cursor factice : support `to_list` (candidate_profile/job_offers) et
    l'itération asynchrone `async for` utilisée par `_estimate_embedding_cost`
    sur `offer_embeddings`."""

    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, length=None):
        return list(self.docs)

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for doc in self.docs:
            yield doc


class _FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query=None):
        return _FakeCursor(self.docs)


def _fake_db(profiles, offers, offer_embeddings=()):
    return {
        "candidate_profile": _FakeCollection(profiles),
        "job_offers": _FakeCollection(offers),
        "offer_embeddings": _FakeCollection(list(offer_embeddings)),
    }


@pytest.mark.asyncio
async def test_rematch_all_users_reports_semantic_unknown_and_fails(monkeypatch, caplog):
    profiles = [{"user_id": "u1"}]
    offers = [{"_id": "o1"}]
    fake_db = _fake_db(profiles, offers)

    async def fake_get_database():
        return fake_db

    async def fake_rematch_user(user_id, db, *, apply=True, embed=None, **kwargs):
        return RematchSummary(semantic_unknown=3)

    async def fake_estimate_cost(db, offers, *, apply, profile_count):
        return None

    monkeypatch.setattr(script, "get_database", fake_get_database)
    monkeypatch.setattr(script, "rematch_user", fake_rematch_user)
    monkeypatch.setattr(script, "_estimate_embedding_cost", fake_estimate_cost)

    with caplog.at_level(logging.INFO):
        total = await script.rematch_all_users(apply=False, confirm=True)

    assert total == 3
    messages = [r.message for r in caplog.records]
    assert any("semantic_unknown=3" in message for message in messages)
    error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_messages) == 1


@pytest.mark.asyncio
async def test_rematch_all_users_without_flags_makes_no_embedding_call(monkeypatch, caplog):
    """Sans `--apply` ni `--confirm` : seule l'estimation (lecture DB seule) tourne,
    `embed` et `rematch_user` ne sont jamais appelés (résolution M8)."""
    profiles = [{"user_id": "u1"}, {"user_id": "u2"}]
    offers = [{"_id": "o1", "poste": "Développeur", "description": "Une offre à embarquer."}]
    fake_db = _fake_db(profiles, offers)

    embed_calls = []
    rematch_calls = []

    async def fake_get_database():
        return fake_db

    async def spy_embed(texts):
        embed_calls.append(texts)
        return [[0.0] for _ in texts]

    async def spy_rematch_user(user_id, db, *, apply=True, embed=None, **kwargs):
        rematch_calls.append((user_id, apply))
        return RematchSummary()

    monkeypatch.setattr(script, "get_database", fake_get_database)
    monkeypatch.setattr(script, "embed_texts", spy_embed)
    monkeypatch.setattr(script, "rematch_user", spy_rematch_user)
    # `_estimate_embedding_cost` n'est PAS mocké : son exécution réelle (lecture DB
    # seule, aucun embed) fait partie de ce que ce test vérifie.

    with caplog.at_level(logging.INFO):
        total = await script.rematch_all_users(apply=False, confirm=False, embed=spy_embed)

    assert total == 0
    assert embed_calls == []
    assert rematch_calls == []
    messages = [r.message for r in caplog.records]
    assert any("1 offre(s) sans vecteur en cache" in message for message in messages)
    assert any("texte(s) à embarquer" in message for message in messages)
    assert any("Aucun appel" in message and "--confirm" in message and "--apply" in message for message in messages)


@pytest.mark.asyncio
async def test_rematch_all_users_confirm_without_apply_runs_dry_run(monkeypatch):
    """`--confirm` sans `--apply` : dry-run réel, `rematch_user` appelé avec `apply=False`."""
    profiles = [{"user_id": "u1"}]
    offers = [{"_id": "o1"}]
    fake_db = _fake_db(profiles, offers)

    rematch_calls = []

    async def fake_get_database():
        return fake_db

    async def spy_rematch_user(user_id, db, *, apply=True, embed=None, **kwargs):
        rematch_calls.append((user_id, apply))
        return RematchSummary()

    async def fake_estimate_cost(db, offers, *, apply, profile_count):
        return None

    monkeypatch.setattr(script, "get_database", fake_get_database)
    monkeypatch.setattr(script, "rematch_user", spy_rematch_user)
    monkeypatch.setattr(script, "_estimate_embedding_cost", fake_estimate_cost)

    total = await script.rematch_all_users(apply=False, confirm=True)

    assert total == 0
    assert rematch_calls == [("u1", False)]
