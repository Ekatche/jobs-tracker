"""Tests de `scripts/rematch_all_users.py` : agrégation et reporting des
offres `semantic_unknown` (panne d'embedding) sur l'ensemble des profils.

Base de données et `rematch_user` entièrement factices — aucun Motor ni
appel réseau réel.
"""

import logging

import pytest

from app.services.offer_profile_matcher import RematchSummary
from scripts import rematch_all_users as script


class _FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, length=None):
        return list(self.docs)


class _FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query=None):
        return _FakeCursor(self.docs)


def _fake_db(profiles, offers):
    return {
        "candidate_profile": _FakeCollection(profiles),
        "job_offers": _FakeCollection(offers),
    }


@pytest.mark.asyncio
async def test_rematch_all_users_reports_semantic_unknown_and_fails(monkeypatch, caplog):
    profiles = [{"user_id": "u1"}]
    offers = [{"_id": "o1"}]
    fake_db = _fake_db(profiles, offers)

    async def fake_get_database():
        return fake_db

    async def fake_rematch_user(user_id, db, *, apply=True, **kwargs):
        return RematchSummary(semantic_unknown=3)

    async def fake_estimate_cost(db, offers, *, apply, profile_count):
        return None

    monkeypatch.setattr(script, "get_database", fake_get_database)
    monkeypatch.setattr(script, "rematch_user", fake_rematch_user)
    monkeypatch.setattr(script, "_estimate_embedding_cost", fake_estimate_cost)

    with caplog.at_level(logging.INFO):
        total = await script.rematch_all_users(apply=False)

    assert total == 3
    messages = [r.message for r in caplog.records]
    assert any("semantic_unknown=3" in message for message in messages)
    error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_messages) == 1
