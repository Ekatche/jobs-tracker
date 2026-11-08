"""Fixtures et utilitaires partagés pour les tests Interview Prep (Service & API)."""

import json
import uuid
from unittest.mock import AsyncMock
from bson import ObjectId
import pytest

# Re-export root conftest symbols to prevent sys.modules['conftest'] collision in pytest
try:
    from tests.conftest import DATABASE_NAME, MONGO_URI
except ImportError:
    pass

from app.auth import get_current_user
from app.models import (
    AnticipatedQuestion,
    BankStory,
    StarRStory,
    StoryOrigin,
    UserModel,
    utcnow_with_timezone,
)
from main import app

mock_user_id = "650000000000000000000001"
mock_user = UserModel(
    id=mock_user_id,
    username="testcandidate",
    email="candidate@test.com",
    hashed_password="fakehashpassword",
)


@pytest.fixture
def override_auth():
    """Override l'authentification FastAPI pour injecter mock_user."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_bank_story(db, **overrides):
    """Insère une histoire de la banque directement en base ; renvoie son dict brut."""
    now = utcnow_with_timezone()
    story = {
        "id": str(uuid.uuid4()),
        "user_id": mock_user_id,
        "title": "Histoire banque",
        "theme": "Général",
        "situation": "S",
        "task": "T",
        "action": "A",
        "result": "R",
        "reflection": "",
        "key_tags": [],
        "experience": None,
        "origin": {"kind": "manual", "offer_id": None},
        "discarded_versions": [],
        "not_duplicate_of": [],
        "created_at": now,
        "updated_at": now,
    }
    story.update(overrides)
    await db.star_stories.insert_one(story)
    return story


def _slot_dict(story_id, requirement="Exigence", slot_id=None, fit="strong", **overrides):
    """Une ligne `story_slots` brute, prête à être insérée dans `interview_preps`."""
    slot = {
        "id": slot_id or str(uuid.uuid4()),
        "requirement": requirement,
        "story_id": story_id,
        "fit": fit,
        "angle": "",
        "angle_edited": False,
    }
    slot.update(overrides)
    return slot


def make_bank_story_model(offer_id, **overrides):
    """Instancie un BankStory pour les tests avec des valeurs par défaut."""
    defaults = dict(
        user_id=mock_user_id,
        title="Histoire",
        situation="S",
        task="T",
        action="A",
        result="R",
        origin=StoryOrigin(kind="generated", offer_id=str(offer_id)),
    )
    defaults.update(overrides)
    return BankStory(**defaults)



def make_practice_llm_response(payload):
    """Génère un mock acompletion standard avec choices et token usage."""
    mock_resp = AsyncMock()
    mock_resp.choices = [AsyncMock(message=AsyncMock(content=json.dumps(payload)))]
    mock_resp.usage = AsyncMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    return mock_resp


# Constantes partagées de test
TEST_PRACTICE_QUESTION = AnticipatedQuestion(
    category="behavioral",
    question="Parlez-moi d'une migration difficile.",
    why_it_will_be_asked="Exigence Kubernetes",
    key_points_to_cover=["Gestion du risque de coupure"],
)

TEST_PRACTICE_STORY = StarRStory(
    title="Migration K8s",
    theme="Architecture",
    target_requirement="Kubernetes",
    situation="Cluster legacy de 40 services",
    task="Migrer sans coupure",
    action="Bascule progressive",
    result="Zéro incident",
    reflection="Automatiser plus tôt",
)

TEST_RAW_STORY = {
    "title": "[Agilité] Titre percutant",
    "theme": "Architecture",
    "situation": "Situation détaillée",
    "task": "Tâche précise",
    "action": "Action concrète",
    "result": "Résultat de −60 % et zéro incident",
    "reflection": "Enseignement tiré",
    "key_tags": ["x"],
}

TEST_PROFILE = {"experiences": [{"company": "Alpha Corp", "role": "Data Engineer", "start": "2022-01"}]}

TEST_OFFER = {"_id": ObjectId(), "poste": "Lead Data", "entreprise": "Acme", "description": "Fiabiliser la plateforme data."}

TEST_BANK_STORY_1 = BankStory(
    id="s1",
    user_id="u",
    title="Fiabilisation du pipeline nocturne",
    situation="Chez Acme, le pipeline nocturne échouait une nuit sur deux.",
    task="Fiabiliser le traitement sans régression.",
    action="J'ai ajouté des reprises idempotentes et un monitoring.",
    result="−60 % de temps de traitement et zéro incident depuis 3 mois.",
    reflection="Automatiser les tests de charge plus tôt.",
    key_tags=["data", "fiabilité"],
    origin=StoryOrigin(kind="manual"),
)
