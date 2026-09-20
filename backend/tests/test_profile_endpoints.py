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


def test_saving_profile_does_not_wipe_preferences(client, profile_db):
    """PUT /profile/candidate écrit une source "manual" séparée de PUT
    /profile/candidate/preferences, mais les deux partagent la même clé
    `sources.manual` en base. `_store_source` remplaçant tout le contenu de
    cette clé, un remplacement naïf de "manual" par le seul payload du
    formulaire profil (qui ne connaît pas `preferences`) effaçait les
    préférences de ciblage à chaque sauvegarde de profil.
    """
    res = client.put(
        "/profile/candidate/preferences",
        json={"target_roles": ["Data Engineer"], "locations": ["Paris"]},
    )
    assert res.status_code == 200
    assert res.json()["preferences"]["target_roles"] == ["Data Engineer"]

    res = client.put("/profile/candidate", json={"headline": "Lead Data Engineer"})
    assert res.status_code == 200
    assert res.json()["headline"] == "Lead Data Engineer"
    assert res.json()["preferences"]["target_roles"] == ["Data Engineer"]
    assert res.json()["preferences"]["locations"] == ["Paris"]


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


async def _no_llm_suggestions(profile, model=None):
    return {"roles": [], "_usage": None}


def test_suggested_roles_returns_canonical_deduplicated_titles(client, profile_db, monkeypatch):
    """Les suggestions de rôles doivent passer par le même pipeline de
    canonicalisation (clean_job_title_syntax + match_taxonomy_role) que les
    requêtes de recherche générées pour le collecteur d'offres, afin que
    cliquer une suggestion corresponde à un métier réellement recherché.
    """
    import app.routers.cover_letters as router

    profile_db["_id"] = ObjectId()
    profile_db["headline"] = "Dev Backend"
    profile_db["experiences"] = [
        {"role": "Développeur Backend", "company": "Acme"},
        {"role": "Developpeur backend", "company": "Beta"},  # doit fusionner avec la headline
        {"role": "", "company": "Gamma"},  # rôle vide ignoré
    ]

    canonical_map = {
        "dev backend": "Développeur Backend",
        "développeur backend": "Développeur Backend",
        "developpeur backend": "Développeur Backend",
    }

    async def fake_match_taxonomy_role(role, db=None):
        return canonical_map.get(role.lower(), role)

    monkeypatch.setattr(router, "match_taxonomy_role", fake_match_taxonomy_role)
    monkeypatch.setattr(router, "suggest_role_titles_from_profile", _no_llm_suggestions)

    res = client.get("/profile/candidate/suggested-roles")
    assert res.status_code == 200
    assert res.json()["roles"] == ["Développeur Backend"]


def test_suggested_roles_include_related_variants_from_role_aliases(
    client, profile_db, monkeypatch
):
    """Les suggestions incluent aussi les intitulés liés (variants) déjà
    rattachés au même rôle canonique par d'autres CV, pour élargir la
    recherche au-delà des seuls intitulés présents sur ce CV.
    """
    import app.routers.cover_letters as router

    profile_db["_id"] = ObjectId()
    profile_db["headline"] = "Développeur Backend"
    profile_db["experiences"] = []
    profile_db.role_aliases.append(
        {
            "canonical": "Développeur Backend",
            "variants": ["développeur backend", "ingénieur backend", "backend engineer"],
        }
    )

    async def fake_match_taxonomy_role(role, db=None):
        return "Développeur Backend"

    monkeypatch.setattr(router, "match_taxonomy_role", fake_match_taxonomy_role)
    monkeypatch.setattr(router, "suggest_role_titles_from_profile", _no_llm_suggestions)

    res = client.get("/profile/candidate/suggested-roles")
    assert res.status_code == 200
    roles = res.json()["roles"]
    assert roles[0] == "Développeur Backend"
    assert "Ingénieur Backend" in roles
    assert "Backend Engineer" in roles
    # le variant identique au canonique (juste une casse différente) n'est pas dupliqué
    assert roles.count("Développeur Backend") == 1


def test_suggested_roles_empty_when_profile_missing(client, profile_db, monkeypatch):
    import app.routers.cover_letters as router

    async def fake_match_taxonomy_role(role, db=None):
        return role

    monkeypatch.setattr(router, "match_taxonomy_role", fake_match_taxonomy_role)
    monkeypatch.setattr(router, "suggest_role_titles_from_profile", _no_llm_suggestions)

    res = client.get("/profile/candidate/suggested-roles")
    assert res.status_code == 200
    assert res.json()["roles"] == []
