import importlib
import io
import sys

import pytest
from bson import ObjectId

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel
from main import app


def test_app_imports_without_pymupdf(monkeypatch):
    """L'absence de pymupdf ne doit pas empêcher l'API de démarrer."""
    monkeypatch.setitem(sys.modules, "fitz", None)
    for mod in ("app.services.cv_parser", "app.routers.cover_letters"):
        monkeypatch.delitem(sys.modules, mod, raising=False)
    module = importlib.import_module("app.services.cv_parser")
    assert hasattr(module, "extract_text_from_pdf")


USER_ID = "60c72b2f9b1d8b2bad7f1234"


@pytest.fixture
def profile_db(monkeypatch):
    """Base en mémoire pour la collection candidate_profile."""
    from unittest.mock import AsyncMock, MagicMock

    stored = {}

    async def find_one(_query):
        return dict(stored) if stored else None

    async def update_one(_filter, update, upsert=False):
        stored.update(update["$set"])
        stored.setdefault("_id", ObjectId())
        return MagicMock()

    collection = MagicMock()
    collection.find_one = AsyncMock(side_effect=find_one)
    collection.update_one = AsyncMock(side_effect=update_one)
    db = MagicMock()
    db.__getitem__.return_value = collection

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=USER_ID, username="tester", email="t@example.com", hashed_password="x"
    )
    yield stored
    app.dependency_overrides.clear()


def test_non_pdf_upload_is_rejected(client, profile_db):
    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("evil.pdf", io.BytesIO(b"MZ executable"), "application/pdf")},
    )
    assert res.status_code == 400
    assert "PDF" in res.json()["detail"]


def test_oversized_upload_is_rejected(client, profile_db):
    payload = b"%PDF-1.7" + b"0" * (11 * 1024 * 1024)
    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("cv.pdf", io.BytesIO(payload), "application/pdf")},
    )
    assert res.status_code == 413


def test_uploaded_file_is_deleted_after_parsing(client, profile_db, monkeypatch, tmp_path):
    import app.routers.cover_letters as router

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(router, "extract_text_from_pdf", lambda path: "texte du CV")

    async def fake_parse(_text):
        return {"headline": "Ingénieur Data", "experiences": []}

    monkeypatch.setattr(router, "parse_cv_with_llm", fake_parse)

    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.7 contenu"), "application/pdf")},
    )
    assert res.status_code == 200
    assert list(tmp_path.iterdir()) == []
    assert profile_db["sources"]["cv"]["headline"] == "Ingénieur Data"


def test_github_source_is_stored_and_profile_rebuilt(client, profile_db, monkeypatch):
    import app.routers.cover_letters as router

    async def fake_collect(url, client=None):
        return {"projects": [{"name": "WideDocs", "description": "Doc"}], "experiences": []}

    monkeypatch.setattr(router, "collect_github", fake_collect)
    res = client.post(
        "/profile/candidate/sources/github", json={"url": "https://github.com/Ekatche"}
    )
    assert res.status_code == 200
    assert res.json()["projects"][0]["name"] == "WideDocs"
    assert "github" in profile_db["sources"]


def test_private_url_is_refused_on_website_source(client, profile_db):
    res = client.post(
        "/profile/candidate/sources/website",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert res.status_code == 400


def test_reimporting_a_source_is_idempotent(client, profile_db, monkeypatch):
    import app.routers.cover_letters as router

    async def fake_collect(url, client=None):
        return {"projects": [{"name": "WideDocs", "description": "Doc"}], "experiences": []}

    monkeypatch.setattr(router, "collect_github", fake_collect)
    first = client.post("/profile/candidate/sources/github", json={"url": "https://github.com/Ekatche"})
    second = client.post("/profile/candidate/sources/github", json={"url": "https://github.com/Ekatche"})
    assert first.json()["projects"] == second.json()["projects"]


def test_manual_edits_survive_a_later_import(client, profile_db, monkeypatch):
    import app.routers.cover_letters as router

    client.put("/profile/candidate", json={"headline": "Lead Data Engineer"})

    async def fake_collect(url, client=None):
        return {"headline": "Ingénieur Data", "projects": [], "experiences": []}

    monkeypatch.setattr(router, "collect_github", fake_collect)
    res = client.post("/profile/candidate/sources/github", json={"url": "https://github.com/Ekatche"})
    assert res.json()["headline"] == "Lead Data Engineer"


def test_website_import_with_invalid_project_context_is_coerced_to_perso(
    client, profile_db, monkeypatch
):
    """`CandidateProject.context` est un Literal fermé ("perso"/"client"/"recherche"/
    "consortium"). `collect_website` applique désormais une coercition défensive
    (`_coerce_project_contexts`) : une sortie LLM hors énumération (ex: "stage")
    est remplacée par "perso" avant même d'atteindre `_store_source`, plutôt que
    de faire échouer la validation Pydantic et remonter 502 sur l'import de la
    source la plus riche du profil.

    Ce test mocke `collect_website` au niveau du routeur (comme les autres tests
    de ce fichier) mais applique la vraie fonction de coercition du module
    `website` pour refléter fidèlement ce que fait la fonction réelle — la
    couverture de la coercition elle-même (via un `extract` factice sur le
    vrai `collect_website`) vit dans `test_profile_collectors.py`.
    """
    import app.routers.cover_letters as router
    from app.services.profile.collectors.website import _coerce_project_contexts

    async def fake_collect(url):
        payload = {
            "projects": [
                {"name": "Stage RH", "description": "Mission de stage", "context": "stage"}
            ],
            "experiences": [],
        }
        _coerce_project_contexts(payload)
        return payload

    monkeypatch.setattr(router, "collect_website", fake_collect)
    # IP littérale : `validate_public_url` ne fait alors aucune résolution DNS
    # réelle, ce qui garde le test déterministe hors ligne.
    res = client.post(
        "/profile/candidate/sources/website", json={"url": "https://93.184.216.34"}
    )
    assert res.status_code == 200
    assert res.json()["projects"][0]["context"] == "perso"


def test_store_source_non_validation_failure_returns_502_not_500(
    client, profile_db, monkeypatch, caplog
):
    """Une exception dans `_store_source` qui n'est PAS une `ValidationError`
    (panne DB, bug dans `build_profile_from_sources`, données `sources`
    malformées) doit être attrapée par le `except Exception` du handler —
    pas remonter en 500 brut sans passer par `logger.exception`.
    """
    import logging

    import app.routers.cover_letters as router

    async def fake_collect(url, client=None):
        return {"projects": [], "experiences": []}

    def boom(_sources):
        raise RuntimeError("panne inattendue dans la fusion")

    monkeypatch.setattr(router, "collect_github", fake_collect)
    monkeypatch.setattr(router, "build_profile_from_sources", boom)

    with caplog.at_level(logging.ERROR, logger="app.routers.cover_letters"):
        res = client.post(
            "/profile/candidate/sources/github", json={"url": "https://github.com/Ekatche"}
        )

    assert res.status_code == 502
    assert "panne inattendue" not in res.json()["detail"]
    assert any(
        record.levelno == logging.ERROR and record.exc_info
        for record in caplog.records
    )
