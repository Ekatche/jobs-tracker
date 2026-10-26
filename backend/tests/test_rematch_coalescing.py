"""Tests de coalescence des rematchs concurrents par utilisateur (M20).

`_safe_rematch_user` est lancé en tâche de fond à chaque mise à jour des
préférences candidat. Sans verrou, deux mises à jour rapprochées déclenchent
deux `rematch_user` en parallèle sur le même utilisateur. Ces tests vérifient
que les appels concurrents fusionnent en au plus un tour supplémentaire,
jamais en parallèle, et que le verrou est toujours libéré même après une
exception.
"""

import asyncio

import app.routers.cover_letters as cover_letters_module
import pytest
from app.routers.cover_letters import _safe_rematch_user


@pytest.fixture(autouse=True)
def _clean_rematch_state():
    """Les ensembles module doivent rester vides entre les tests."""
    cover_letters_module._rematch_running.clear()
    cover_letters_module._rematch_rerun.clear()
    yield
    assert cover_letters_module._rematch_running == set()
    assert cover_letters_module._rematch_rerun == set()
    cover_letters_module._rematch_running.clear()
    cover_letters_module._rematch_rerun.clear()


class _FakeRematch:
    """Coroutine factice comptant les appels et la concurrence max atteinte."""

    def __init__(self):
        self.calls = []
        self.current_concurrency = 0
        self.max_concurrency = 0
        self.hold_first_call = asyncio.Event()
        self.hold_enabled = False

    async def __call__(self, user_id, db):
        self.current_concurrency += 1
        self.max_concurrency = max(self.max_concurrency, self.current_concurrency)
        self.calls.append(user_id)
        if self.hold_enabled and len(self.calls) == 1:
            await self.hold_first_call.wait()
        else:
            # Laisse d'autres tâches s'exécuter pour mesurer la concurrence.
            await asyncio.sleep(0)
        self.current_concurrency -= 1


@pytest.mark.asyncio
async def test_two_concurrent_calls_produce_two_runs_never_parallel(monkeypatch):
    """Un second appel pendant le tour en cours se fusionne : 2 exécutions, jamais en parallèle."""
    fake = _FakeRematch()
    fake.hold_enabled = True
    monkeypatch.setattr(cover_letters_module, "rematch_user", fake)
    user_id = "user-1"
    db = object()

    task = asyncio.create_task(_safe_rematch_user(user_id, db))
    # Laisse le premier tour entrer dans rematch_user et s'y suspendre.
    await asyncio.sleep(0)

    # Second appel pendant que le premier tour est encore ouvert : il doit se
    # contenter de marquer "à relancer" et rendre la main immédiatement.
    await _safe_rematch_user(user_id, db)

    fake.hold_first_call.set()
    await task

    assert fake.calls == [user_id, user_id]
    assert fake.max_concurrency == 1


@pytest.mark.asyncio
async def test_three_calls_during_open_round_coalesce_into_two_runs(monkeypatch):
    """Trois appels pendant un même tour ouvert ne déclenchent qu'un seul tour supplémentaire."""
    fake = _FakeRematch()
    fake.hold_enabled = True
    monkeypatch.setattr(cover_letters_module, "rematch_user", fake)
    user_id = "user-1"
    db = object()

    task = asyncio.create_task(_safe_rematch_user(user_id, db))
    await asyncio.sleep(0)

    await _safe_rematch_user(user_id, db)
    await _safe_rematch_user(user_id, db)
    await _safe_rematch_user(user_id, db)

    fake.hold_first_call.set()
    await task

    assert fake.calls == [user_id, user_id]
    assert fake.max_concurrency == 1


@pytest.mark.asyncio
async def test_exception_on_first_round_frees_the_user(monkeypatch):
    """Une exception au premier tour libère l'utilisateur ; l'appel suivant s'exécute."""
    calls = []

    async def fake_rematch_raise_once(user_id, db):
        calls.append(user_id)
        if len(calls) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(cover_letters_module, "rematch_user", fake_rematch_raise_once)
    user_id = "user-1"
    db = object()

    await _safe_rematch_user(user_id, db)

    assert user_id not in cover_letters_module._rematch_running
    assert user_id not in cover_letters_module._rematch_rerun

    await _safe_rematch_user(user_id, db)

    assert calls == [user_id, user_id]


@pytest.mark.asyncio
async def test_different_users_do_not_block_each_other(monkeypatch):
    """Le verrou est par utilisateur : deux utilisateurs différents tournent en parallèle."""
    fake = _FakeRematch()
    monkeypatch.setattr(cover_letters_module, "rematch_user", fake)
    db = object()

    await asyncio.gather(
        _safe_rematch_user("user-1", db),
        _safe_rematch_user("user-2", db),
    )

    assert sorted(fake.calls) == ["user-1", "user-2"]
    assert fake.max_concurrency == 2
