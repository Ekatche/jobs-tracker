import pytest
import asyncio
import os
import uuid
import pathlib
import motor.motor_asyncio
import pymongo
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from main import app
from app.database import get_database

dotenv_path = pathlib.Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

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


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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


@pytest.fixture(scope="session", autouse=True)
def cleanup_database():
    """Nettoie la base de données de test après tous les tests."""
    yield
    client = pymongo.MongoClient(MONGO_URI)
    client.drop_database(DATABASE_NAME)
    client.close()


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
