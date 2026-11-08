import copy
import pytest
import os
import uuid
import pathlib
import motor.motor_asyncio
import pymongo
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from main import app
from app.database import get_database
from app.auth import get_current_user
from app.models import UserModel
from bson import ObjectId
from unittest.mock import MagicMock

dotenv_path = pathlib.Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# En environnement de test, neutraliser INVITATION_CODE pour permettre l'exécution des tests standards
os.environ["INVITATION_CODE"] = ""
os.environ.setdefault("TAVILY_API_KEY", "tvly-test-dummy-key")

MONGO_USER = os.getenv("MONGO_TEST_USER")
MONGO_PASSWORD = os.getenv("MONGO_TEST_PASSWORD")
DATABASE_NAME = os.getenv("DATABASE_NAME_TEST")
TEST_ENV = os.getenv("TEST_ENV", "local")

if TEST_ENV == "docker":
    MONGO_HOST = os.getenv("MONGO_TEST_HOST")
    MONGO_PORT = 27017
elif TEST_ENV == "github":
    MONGO_HOST = os.getenv("MONGO_LOCAL_TEST_HOST", "localhost")
    MONGO_PORT = 27017
else:
    MONGO_HOST = os.getenv("MONGO_LOCAL_TEST_HOST", "localhost")
    MONGO_PORT = 27018

MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/{DATABASE_NAME}?authSource=admin"


# Pas de fixture event_loop maison : dépréciée depuis pytest-asyncio 0.23, elle
# fait échouer le setup du premier test async ("OSError: could not get source
# code" dans plugin.py lors de l'inspection de la fixture). Avec
# asyncio_mode = auto (pytest.ini), pytest-asyncio fournit la boucle lui-même.


async def get_test_database():
    """Retourne une connexion à la base de données de test."""
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    try:
        yield client[DATABASE_NAME]
    finally:
        client.close()


def override_dependencies():
    """Remplace les dépendances de l'application par celles de test."""
    app.dependency_overrides[get_database] = get_test_database


@pytest.fixture
async def test_db():
    """Base de test partagée par l'app (override) et le seed du test."""
    override_dependencies()
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    try:
        yield client[DATABASE_NAME]
    finally:
        client.close()


@pytest.fixture(scope="session", autouse=True)
def cleanup_database():
    """Nettoie la base de données de test après tous les tests."""
    yield
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.drop_database(DATABASE_NAME)
        client.close()
    except Exception:
        pass


@pytest.fixture
def client():
    """Retourne un client de test FastAPI configuré."""
    override_dependencies()
    return TestClient(app)


@pytest.fixture
def test_user():
    """Crée un utilisateur avec un nom et email uniques."""
    unique_id = uuid.uuid4().hex[:8]
    return {
        "username": f"testuser_{unique_id}",
        "email": f"test.user_{unique_id}@example.com",
        "password": "TestPassword123",
        "full_name": f"Test User {unique_id}",
    }


@pytest.fixture
def registered_user(client, test_user):
    """
    Fixture qui enregistre un utilisateur et retourne ses données.
    """
    response = client.post("auth/register", json=test_user)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def auth_headers(client, registered_user):
    """
    Fixture qui retourne les en-têtes d'authentification pour un utilisateur enregistré.
    """
    login_response = client.post(
        "auth/token",
        data={
            "username": registered_user["username"],
            "password": "TestPassword123",
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


USER_ID = "60c72b2f9b1d8b2bad7f1234"


class _StoredProfile(dict):
    """Dict de secours pour candidate_profile, avec les docs role_aliases
    attachés en attribut pour que les tests puissent les préremplir."""

    role_aliases: list


@pytest.fixture
def profile_db(monkeypatch):
    """Base en mémoire pour les collections candidate_profile et role_aliases."""
    from unittest.mock import AsyncMock, MagicMock

    stored = _StoredProfile()
    stored.role_aliases = []

    async def find_one(_query):
        return dict(stored) if stored else None

    async def update_one(_filter, update, upsert=False):
        stored.update(update["$set"])
        stored.setdefault("_id", ObjectId())
        return MagicMock()

    profile_collection = MagicMock()
    profile_collection.find_one = AsyncMock(side_effect=find_one)
    profile_collection.update_one = AsyncMock(side_effect=update_one)

    def fake_aliases_find(query):
        canonicals = set(query.get("canonical", {}).get("$in", []))
        matched = [doc for doc in stored.role_aliases if doc.get("canonical") in canonicals]
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=matched)
        return cursor

    aliases_collection = MagicMock()
    aliases_collection.find = MagicMock(side_effect=fake_aliases_find)

    def get_collection(name):
        return aliases_collection if name == "role_aliases" else profile_collection

    db = MagicMock()
    db.__getitem__.side_effect = get_collection

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=USER_ID, username="tester", email="t@example.com", hashed_password="x"
    )
    yield stored
    app.dependency_overrides.clear()


class FakeCollection:
    """Collection en mémoire : find_one/insert_one/update_one($set, $push)/delete_many."""

    def __init__(self):
        self.docs = []

    @staticmethod
    def _match(doc, query):
        return all(doc.get(k) == v for k, v in query.items())

    async def find_one(self, query):
        found = next((d for d in self.docs if self._match(d, query)), None)
        return copy.deepcopy(found) if found else None

    async def insert_one(self, doc):
        doc.setdefault("_id", ObjectId())
        self.docs.append(copy.deepcopy(doc))
        return MagicMock(inserted_id=doc["_id"])

    async def update_one(self, query, update, upsert=False):
        doc = next((d for d in self.docs if self._match(d, query)), None)
        if doc is not None:
            doc.update(update.get("$set", {}))
            for key, value in update.get("$push", {}).items():
                doc.setdefault(key, []).append(value)
        return MagicMock()

    async def delete_many(self, query):
        self.docs[:] = [d for d in self.docs if not self._match(d, query)]


class FakeDb:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


@pytest.fixture
def letter_db(client):
    """Base en mémoire + utilisateur courant simulé pour les tests de lettres."""
    db = FakeDb()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=USER_ID, username="tester", email="t@example.com", hashed_password="x"
    )
    yield db
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _isolated_llm_budget_ledger(tmp_path, monkeypatch):
    """Aucun test n'écrit dans le vrai registre `scripts/data/llm_budget.jsonl`."""
    from scripts import llm_budget

    monkeypatch.setattr(llm_budget, "LEDGER_PATH", tmp_path / "llm_budget.jsonl")


_LLM_ENTRYPOINTS = ("acompletion", "completion", "aembedding", "embedding")


@pytest.fixture(autouse=True)
def _forbid_real_llm_calls(monkeypatch):
    """Aucun test n'atteint un fournisseur LLM réel (réseau, facturé).

    Patche `litellm.*` et les noms importés directement dans les modules
    déjà chargés. Un patch posé par le test lui-même passe après cette
    fixture et reste prioritaire. Chaque déclenchement du garde est compté :
    un appel avalé par un `except` de production fait quand même échouer le test.

    Limites : ne couvre ni les alias d'import chargés avant la fixture, ni les
    modules de `site-packages` qui importent le nom directement, ni le SDK
    openai (`ChatOpenAI`, `import openai`).
    """
    import sys

    import litellm

    message = "Appel LLM réel interdit en test : patchez l'appelant"

    triggered = []

    def _forbidden_sync(*args, **kwargs):
        triggered.append(1)
        raise RuntimeError(message)

    # Async pour les points d'entrée async : `patch()` choisit AsyncMock
    # d'après la nature de la cible, un garde sync casserait ces patchs.
    async def _forbidden_async(*args, **kwargs):
        triggered.append(1)
        raise RuntimeError(message)

    originals = {}
    guards = {}
    for name in _LLM_ENTRYPOINTS:
        original = getattr(litellm, name, None)
        if original is not None:
            originals[name] = original
            guards[name] = _forbidden_async if name.startswith("a") else _forbidden_sync
            monkeypatch.setattr(litellm, name, guards[name])
    for mod in list(sys.modules.values()):
        if mod is litellm or "site-packages" in (getattr(mod, "__file__", None) or "site-packages"):
            continue
        for name, original in originals.items():
            if vars(mod).get(name) is original:
                monkeypatch.setattr(mod, name, guards[name])
    yield
    if triggered:
        pytest.fail("Appel LLM réel tenté : patchez l'appelant")
