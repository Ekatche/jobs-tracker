# Filtrage "Selon mon profil" basé sur matching persistant — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le filtrage texte à la volée du bouton "Selon mon profil" par un champ persistant `matched_user_ids` sur chaque offre, calculé par un moteur de matching déterministe (rôle canonique + localisation normalisée) et tenu à jour après collecte, après modification des préférences, et via backfill.

**Architecture:** Un module de service unique (`backend/app/services/offer_profile_matcher.py`) porte toute la logique de comparaison offre/profil. Trois points d'entrée l'appellent : la fin du cycle de collecte (`tag_new_offers`), le hook de modification des préférences (`rematch_user` en tâche de fond FastAPI), et un script de backfill one-shot (`rematch_user` en boucle sur tous les profils). `GET /job-offers` gagne un paramètre `profile_only` qui ajoute une clause `matched_user_ids` au filtre d'agrégation existant, sans rien changer au reste du pipeline (dédup, pagination, interactions). Le frontend n'a plus besoin de construire de chaîne `keywords`/`location` dérivée du profil pour ce bouton précis.

**Tech Stack:** FastAPI + Motor (MongoDB async) côté backend, `BackgroundTasks` pour l'exécution différée (pas de file de tâches dédiée — hors de propos à l'échelle actuelle : 123 offres, 11 users, 2 profils avec préférences). Next.js/React côté frontend, pas de nouvelle dépendance.

**Spec:** `docs/superpowers/specs/2026-09-22-offres-selon-profil-design.md`

## Global Constraints

- `matched_user_ids` est un `list[str]` sur chaque document `job_offers`, convention `str(user_id)` — cohérente avec `offer_evaluations.user_id` déjà stocké en string dans ce projet.
- Absent par défaut sur les offres existantes : traité comme liste vide (`$addToSet`/`$pull` fonctionnent sur un champ absent, aucune migration de schéma requise avant le backfill).
- Pas de file de tâches distribuée (Celery, RQ, etc.) — uniquement `BackgroundTasks` FastAPI, déjà utilisé dans ce fichier pour `regenerate_cover_letter`.
- **Déviation documentée par rapport au texte littéral de la spec (section 4)** : le hook de rematch est branché sur `PUT /profile/candidate/preferences` (`update_candidate_preferences`), pas sur `PUT /profile/candidate` (`update_candidate_profile`). C'est le seul point d'entrée qui valide `target_roles`/`locations`/`remote_policy` via `CandidatePreferences.model_validate` — le endpoint générique ne touche ces champs qu'indirectement via un dict arbitraire, jamais validé comme préférences. Décision prise en lisant le code réel pendant la préparation de ce plan.
- **`profile_only` est additif, pas exclusif** : il s'ajoute au filtre d'agrégation MongoDB existant (`match_filter["matched_user_ids"] = ...`) au même titre que `keywords`/`location`/`company`, sans les désactiver. Le pipeline d'agrégation de `GET /job-offers` accepte déjà plusieurs filtres simultanés — c'est le comportement le plus simple et le plus cohérent avec le code existant, et il correspond à ce qui se passe déjà côté frontend (les badges de rôle/ville du profil restent cliquables indépendamment du bouton "Selon mon profil").
- Le frontend de ce repo n'a **aucun runner de test configuré** (pas de Jest/Vitest, aucun fichier `*.test.*`, aucun script `test` dans `package.json`). Les tâches frontend de ce plan se vérifient via `npm run lint` (type-check TypeScript via `next lint`) et un test manuel au navigateur — pas via un test automatisé écrit d'abord, contrairement aux tâches backend qui suivent strictement TDD.
- Le script de backfill suit la convention exacte de `backend/scripts/backfill_canonical_titles.py` déjà présent (`--dry-run`, connexion via `app.database.get_database()`, lancement via `docker exec jobtracker-backend python scripts/...`).
- Tests backend : `pytest` avec `asyncio_mode = auto` (pytest-asyncio, pas de fixture `event_loop` maison). Convention de mock déjà en place dans ce repo pour les fonctions qui touchent Mongo : `db` passé comme un simple `dict` `{"collection_name": mock_collection}`, `mock_collection = MagicMock()` avec `find_one`/`update_one`/`insert_one` en `AsyncMock`, `find(...)` retourne un `MagicMock` synchrone dont `.to_list` est un `AsyncMock`. Voir `backend/tests/test_job_offers_pipeline.py::test_save_offers_to_database_cross_source_dedup` comme référence.

---

## Task 1: Index MongoDB sur `matched_user_ids`

**Files:**
- Modify: `backend/app/database.py:64-93` (fonction `create_job_offers_indexes`)
- Test: `backend/tests/test_database_indexes.py` (nouveau fichier)

**Interfaces:**
- Consumes: rien (première tâche du plan)
- Produces: rien de nouveau côté API — juste un index en base, utilisé implicitement par les requêtes des tâches suivantes

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_database_indexes.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.database import create_job_offers_indexes


@pytest.mark.asyncio
async def test_create_job_offers_indexes_includes_matched_user_ids():
    mock_collection = MagicMock()
    mock_collection.create_index = AsyncMock()
    mock_db = {"job_offers": mock_collection}

    await create_job_offers_indexes(mock_db)

    called_fields = [call.args[0] for call in mock_collection.create_index.call_args_list]
    assert "matched_user_ids" in called_fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec jobtracker-backend pytest tests/test_database_indexes.py -v`
Expected: FAIL — `assert "matched_user_ids" in called_fields` échoue (liste ne contient pas ce champ)

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/database.py`, à la fin de `create_job_offers_indexes` (après la ligne `await collection.create_index([("localisation", 1), ("created_at", -1)])`), ajouter :

```python
    # Index sur le matching persistant profil <-> offre (filtre "Selon mon profil")
    await collection.create_index("matched_user_ids")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec jobtracker-backend pytest tests/test_database_indexes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py backend/tests/test_database_indexes.py
git commit -m "feat(job-offers): ajoute l'index matched_user_ids sur job_offers"
```

---

## Task 2: `offer_matches_criteria` — comparaison pure offre/critères

**Files:**
- Create: `backend/app/services/offer_profile_matcher.py`
- Test: `backend/tests/test_offer_profile_matcher.py` (nouveau fichier)

**Interfaces:**
- Consumes: rien
- Produces: `offer_matches_criteria(offer: dict, normalized_roles: set[str], normalized_locations: set[str], remote_policy: str) -> bool` — utilisé par les tâches 4, 5 et 12

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_offer_profile_matcher.py
from app.services.offer_profile_matcher import offer_matches_criteria


def test_offer_matches_criteria_role_only():
    offer = {"canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, {"data engineer"}, set(), "flexible") is True
    assert offer_matches_criteria(offer, {"data scientist"}, set(), "flexible") is False


def test_offer_matches_criteria_location_only():
    offer = {"canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, set(), {"lyon"}, "flexible") is True
    assert offer_matches_criteria(offer, set(), {"paris"}, "flexible") is False


def test_offer_matches_criteria_role_and_location():
    offer = {"canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, {"data engineer"}, {"lyon"}, "flexible") is True
    assert offer_matches_criteria(offer, {"data engineer"}, {"paris"}, "flexible") is False
    assert offer_matches_criteria(offer, {"data scientist"}, {"lyon"}, "flexible") is False


def test_offer_matches_criteria_empty_profile_never_matches():
    offer = {"canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, set(), set(), "flexible") is False


def test_offer_matches_criteria_full_remote_with_teletravail_offer():
    offer = {"canonical_title": "Data Engineer", "localisation": "Paris", "mode_travail": "Télétravail total"}
    # Localisation ne matche pas ("lyon" attendu), mais l'offre est en télétravail total
    # et le profil est en full_remote -> doit matcher malgré tout.
    assert offer_matches_criteria(offer, {"data engineer"}, {"lyon"}, "full_remote") is True


def test_offer_matches_criteria_case_insensitive():
    offer = {"canonical_title": "DATA ENGINEER", "localisation": "LYON", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, {"data engineer"}, {"lyon"}, "flexible") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec jobtracker-backend pytest tests/test_offer_profile_matcher.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.offer_profile_matcher'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/offer_profile_matcher.py
"""Moteur de matching persistant entre un profil candidat et le stock d'offres.

Compare le canonical_title / localisation déjà normalisés sur chaque offre
(via normalize_role / normalize_city lors de la collecte) aux préférences
normalisées d'un profil, pour maintenir à jour job_offers.matched_user_ids.
"""

from bson import ObjectId

from app.services.normalization import normalize_city
from app.services.role_normalizer import normalize_role


def offer_matches_criteria(
    offer: dict,
    normalized_roles: set[str],
    normalized_locations: set[str],
    remote_policy: str,
) -> bool:
    """Pure, sans I/O. Un profil sans aucun critère exploitable (ni rôle ni
    localisation) ne matche jamais aucune offre, pour ne jamais afficher le
    stock entier comme s'il était filtré."""
    if not normalized_roles and not normalized_locations:
        return False

    canonical_title = (offer.get("canonical_title") or "").lower()
    role_match = not normalized_roles or canonical_title in normalized_roles

    localisation = (offer.get("localisation") or "").lower()
    loc_match = (
        not normalized_locations
        or localisation in normalized_locations
        or (remote_policy == "full_remote" and offer.get("mode_travail") == "Télétravail total")
    )

    return role_match and loc_match
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec jobtracker-backend pytest tests/test_offer_profile_matcher.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/offer_profile_matcher.py backend/tests/test_offer_profile_matcher.py
git commit -m "feat(job-offers): ajoute offer_matches_criteria pour le matching profil/offre"
```

---

## Task 3: `get_normalized_profile_criteria` — normalisation des préférences

**Files:**
- Modify: `backend/app/services/offer_profile_matcher.py` (ajout, fichier créé en Task 2)
- Test: `backend/tests/test_offer_profile_matcher.py` (ajout au fichier de la Task 2)

**Interfaces:**
- Consumes: `normalize_role(role: str, db=None) -> str` (async, `backend/app/services/role_normalizer.py:41`), `normalize_city(city: Optional[str]) -> str` (sync, `backend/app/services/normalization.py:29`)
- Produces: `get_normalized_profile_criteria(prefs: dict, db) -> tuple[set[str], set[str], str]` — utilisé par les tâches 4 et 5

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_offer_profile_matcher.py` :

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.offer_profile_matcher import get_normalized_profile_criteria


@pytest.mark.asyncio
async def test_get_normalized_profile_criteria_normalizes_roles_and_locations():
    prefs = {
        "target_roles": ["Ingénieur Data", "  "],
        "locations": ["69000 Lyon", "Paris"],
        "remote_policy": "hybrid",
    }

    async def fake_normalize_role(role, db=None):
        return {"Ingénieur Data": "Data Engineer"}.get(role, role)

    with patch(
        "app.services.offer_profile_matcher.normalize_role",
        AsyncMock(side_effect=fake_normalize_role),
    ):
        roles, locations, remote_policy = await get_normalized_profile_criteria(prefs, db=None)

    assert roles == {"data engineer"}
    assert locations == {"lyon", "paris"}
    assert remote_policy == "hybrid"


@pytest.mark.asyncio
async def test_get_normalized_profile_criteria_empty_prefs():
    with patch("app.services.offer_profile_matcher.normalize_role", AsyncMock()) as mock_role:
        roles, locations, remote_policy = await get_normalized_profile_criteria({}, db=None)

    assert roles == set()
    assert locations == set()
    assert remote_policy == "flexible"
    mock_role.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec jobtracker-backend pytest tests/test_offer_profile_matcher.py -k get_normalized_profile_criteria -v`
Expected: FAIL avec `ImportError: cannot import name 'get_normalized_profile_criteria'`

- [ ] **Step 3: Write minimal implementation**

Ajouter à `backend/app/services/offer_profile_matcher.py` (après `offer_matches_criteria`) :

```python
async def get_normalized_profile_criteria(
    prefs: dict, db
) -> tuple[set[str], set[str], str]:
    """Normalise target_roles (normalize_role, async, caché via role_aliases)
    et locations (normalize_city, sync) vers les mêmes formes canoniques que
    celles déjà stockées sur les offres. Retourne (roles, locations, remote_policy)."""
    target_roles = prefs.get("target_roles") or []
    locations = prefs.get("locations") or []
    remote_policy = prefs.get("remote_policy") or "flexible"

    normalized_roles: set[str] = set()
    for role in target_roles:
        if not role or not role.strip():
            continue
        canonical = await normalize_role(role, db=db)
        if canonical:
            normalized_roles.add(canonical.lower())

    normalized_locations = {normalize_city(loc).lower() for loc in locations if loc}

    return normalized_roles, normalized_locations, remote_policy
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec jobtracker-backend pytest tests/test_offer_profile_matcher.py -k get_normalized_profile_criteria -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/offer_profile_matcher.py backend/tests/test_offer_profile_matcher.py
git commit -m "feat(job-offers): ajoute get_normalized_profile_criteria"
```

---

## Task 4: `rematch_user` — recalcul du matching d'UN profil

**Files:**
- Modify: `backend/app/services/offer_profile_matcher.py` (ajout)
- Test: `backend/tests/test_offer_profile_matcher.py` (ajout)

**Interfaces:**
- Consumes: `get_normalized_profile_criteria` (Task 3), `offer_matches_criteria` (Task 2)
- Produces: `async def rematch_user(user_id: str, db) -> None` — utilisé par le hook de préférences (Task 8) et le script de backfill (Task 12)

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_offer_profile_matcher.py` :

```python
@pytest.mark.asyncio
async def test_rematch_user_addstoset_and_pull():
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.services.offer_profile_matcher import rematch_user

    user_id = "650000000000000000000001"

    matching_offer = {"_id": ObjectId("650000000000000000000010"), "canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    non_matching_offer = {"_id": ObjectId("650000000000000000000020"), "canonical_title": "Comptable", "localisation": "Nantes", "mode_travail": "Présentiel"}

    mock_profile_collection = MagicMock()
    mock_profile_collection.find_one = AsyncMock(
        return_value={"user_id": ObjectId(user_id), "preferences": {"target_roles": ["Data Engineer"], "locations": ["Lyon"], "remote_policy": "flexible"}}
    )

    mock_offers_cursor = MagicMock()
    mock_offers_cursor.to_list = AsyncMock(return_value=[matching_offer, non_matching_offer])

    mock_offers_collection = MagicMock()
    mock_offers_collection.find = MagicMock(return_value=mock_offers_cursor)
    mock_offers_collection.update_many = AsyncMock()

    mock_db = {"candidate_profile": mock_profile_collection, "job_offers": mock_offers_collection}

    with patch("app.services.offer_profile_matcher.normalize_role", AsyncMock(return_value="Data Engineer")):
        await rematch_user(user_id, mock_db)

    add_call = mock_offers_collection.update_many.call_args_list[0]
    assert add_call.args[0] == {"_id": {"$in": [matching_offer["_id"]]}}
    assert add_call.args[1] == {"$addToSet": {"matched_user_ids": user_id}}

    pull_call = mock_offers_collection.update_many.call_args_list[1]
    assert pull_call.args[0] == {"_id": {"$in": [non_matching_offer["_id"]]}}
    assert pull_call.args[1] == {"$pull": {"matched_user_ids": user_id}}


@pytest.mark.asyncio
async def test_rematch_user_no_profile_does_nothing():
    from unittest.mock import AsyncMock, MagicMock
    from app.services.offer_profile_matcher import rematch_user

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec jobtracker-backend pytest tests/test_offer_profile_matcher.py -k rematch_user -v`
Expected: FAIL avec `ImportError: cannot import name 'rematch_user'`

- [ ] **Step 3: Write minimal implementation**

Ajouter à `backend/app/services/offer_profile_matcher.py` :

```python
async def rematch_user(user_id: str, db) -> None:
    """Recalcule le matching d'UN user contre tout le stock actif.
    $addToSet sur les offres qui matchent désormais, $pull sur celles qui
    ne matchent plus. Idempotent : rejouer sans changement de préférences
    ne modifie pas matched_user_ids."""
    profile = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)})
    if not profile:
        return

    prefs = profile.get("preferences") or {}
    normalized_roles, normalized_locations, remote_policy = await get_normalized_profile_criteria(prefs, db)

    collection = db["job_offers"]
    offers = await collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)

    matching_ids = [
        offer["_id"]
        for offer in offers
        if offer_matches_criteria(offer, normalized_roles, normalized_locations, remote_policy)
    ]
    matching_id_set = set(matching_ids)
    non_matching_ids = [offer["_id"] for offer in offers if offer["_id"] not in matching_id_set]

    if matching_ids:
        await collection.update_many(
            {"_id": {"$in": matching_ids}},
            {"$addToSet": {"matched_user_ids": user_id}},
        )
    if non_matching_ids:
        await collection.update_many(
            {"_id": {"$in": non_matching_ids}},
            {"$pull": {"matched_user_ids": user_id}},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec jobtracker-backend pytest tests/test_offer_profile_matcher.py -k rematch_user -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/offer_profile_matcher.py backend/tests/test_offer_profile_matcher.py
git commit -m "feat(job-offers): ajoute rematch_user pour le recalcul du matching d'un profil"
```

---

## Task 5: `tag_new_offers` — recalcul de TOUS les profils contre un lot d'offres

**Files:**
- Modify: `backend/app/services/offer_profile_matcher.py` (ajout)
- Test: `backend/tests/test_offer_profile_matcher.py` (ajout)

**Interfaces:**
- Consumes: `get_normalized_profile_criteria` (Task 3), `offer_matches_criteria` (Task 2)
- Produces: `async def tag_new_offers(offer_ids: list, db) -> None` — utilisé par `collect_and_save_offers` (Task 7)

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_offer_profile_matcher.py` :

```python
@pytest.mark.asyncio
async def test_tag_new_offers_tags_multiple_matching_profiles():
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.services.offer_profile_matcher import tag_new_offers

    offer_id = ObjectId("650000000000000000000030")
    new_offer = {"_id": offer_id, "canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}

    mock_offers_cursor = MagicMock()
    mock_offers_cursor.to_list = AsyncMock(return_value=[new_offer])

    mock_offers_collection = MagicMock()
    mock_offers_collection.find = MagicMock(return_value=mock_offers_cursor)
    mock_offers_collection.update_many = AsyncMock()

    mock_profiles_cursor = MagicMock()
    mock_profiles_cursor.to_list = AsyncMock(
        return_value=[
            {"user_id": ObjectId("650000000000000000000001"), "preferences": {"target_roles": ["Data Engineer"], "locations": ["Lyon"], "remote_policy": "flexible"}},
            {"user_id": ObjectId("650000000000000000000002"), "preferences": {"target_roles": ["Comptable"], "locations": [], "remote_policy": "flexible"}},
        ]
    )

    mock_profile_collection = MagicMock()
    mock_profile_collection.find = MagicMock(return_value=mock_profiles_cursor)

    mock_db = {"job_offers": mock_offers_collection, "candidate_profile": mock_profile_collection}

    with patch("app.services.offer_profile_matcher.normalize_role", AsyncMock(side_effect=lambda role, db=None: role)):
        await tag_new_offers([offer_id], mock_db)

    assert mock_offers_collection.update_many.call_count == 1
    call = mock_offers_collection.update_many.call_args
    assert call.args[0] == {"_id": {"$in": [offer_id]}}
    assert call.args[1] == {"$addToSet": {"matched_user_ids": "650000000000000000000001"}}


@pytest.mark.asyncio
async def test_tag_new_offers_empty_list_does_nothing():
    from unittest.mock import AsyncMock, MagicMock
    from app.services.offer_profile_matcher import tag_new_offers

    mock_offers_collection = MagicMock()
    mock_offers_collection.find = MagicMock()
    mock_db = {"job_offers": mock_offers_collection}

    await tag_new_offers([], mock_db)

    mock_offers_collection.find.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec jobtracker-backend pytest tests/test_offer_profile_matcher.py -k tag_new_offers -v`
Expected: FAIL avec `ImportError: cannot import name 'tag_new_offers'`

- [ ] **Step 3: Write minimal implementation**

Ajouter à `backend/app/services/offer_profile_matcher.py` :

```python
async def tag_new_offers(offer_ids: list, db) -> None:
    """Recalcule le matching de TOUS les profils contre un lot d'offres
    fraîchement sauvegardées. Utilisé en fin de cycle de collecte."""
    if not offer_ids:
        return

    collection = db["job_offers"]
    offers = await collection.find({"_id": {"$in": offer_ids}}).to_list(length=None)
    if not offers:
        return

    profiles = await db["candidate_profile"].find({}).to_list(length=None)

    for profile in profiles:
        user_id = str(profile["user_id"])
        prefs = profile.get("preferences") or {}
        normalized_roles, normalized_locations, remote_policy = await get_normalized_profile_criteria(prefs, db)

        matching_ids = [
            offer["_id"]
            for offer in offers
            if offer_matches_criteria(offer, normalized_roles, normalized_locations, remote_policy)
        ]
        if matching_ids:
            await collection.update_many(
                {"_id": {"$in": matching_ids}},
                {"$addToSet": {"matched_user_ids": user_id}},
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec jobtracker-backend pytest tests/test_offer_profile_matcher.py -k tag_new_offers -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/offer_profile_matcher.py backend/tests/test_offer_profile_matcher.py
git commit -m "feat(job-offers): ajoute tag_new_offers pour le tagging multi-profils en fin de collecte"
```

---

## Task 6: `save_offers_to_database` retourne les `offer_ids`

**Files:**
- Modify: `backend/app/tasks/job_offers_collectors.py:405-518`
- Test: `backend/tests/test_job_offers_pipeline.py` (ajout)

**Interfaces:**
- Consumes: rien de nouveau (fonction déjà existante, `merge_multidiffusion_offers` déjà importée dans ce fichier)
- Produces: `save_offers_to_database(offers: list) -> dict` retourne désormais `{"saved": int, "updated": int, "offer_ids": list[ObjectId]}` — consommé par `collect_and_save_offers` (Task 7)

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_job_offers_pipeline.py` :

```python
@pytest.mark.asyncio
async def test_save_offers_to_database_returns_offer_ids_on_update(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.tasks.job_offers_collectors import save_offers_to_database

    existing_doc = {
        "_id": ObjectId("6aaa8ed40a4a13cc5c4a7b1f"),
        "poste": "Ai Engineer / Scientist Confirmé F/h",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://www.welcometothejungle.com/fr/companies/deloitte/jobs/ai-engineer-scientist-confirme-f-h_lyon",
        "unique_key": "deloitte|ai confirmé engineer scientist|lyon",
        "created_at": datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc),
    }

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=existing_doc)
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_collection.insert_one = AsyncMock()

    mock_db = {"job_offers": mock_collection}

    async def mock_get_database():
        return mock_db

    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", mock_get_database)

    incoming_offer = {
        "poste": "AI Engineer / Scientist confirmé",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://fr.linkedin.com/jobs/view/ai-engineer-scientist-confirm%C3%A9-f-h-at-deloitte-4463883002",
        "description": "Détails complets de l'offre LinkedIn",
    }

    res = await save_offers_to_database([incoming_offer])

    assert res["updated"] == 1
    assert res["offer_ids"] == [existing_doc["_id"]]


@pytest.mark.asyncio
async def test_save_offers_to_database_returns_offer_ids_on_insert(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.tasks.job_offers_collectors import save_offers_to_database

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=None)
    mock_find_cursor = MagicMock()
    mock_find_cursor.to_list = AsyncMock(return_value=[])
    mock_collection.find = MagicMock(return_value=mock_find_cursor)

    inserted_id = ObjectId("6aaa8ed40a4a13cc5c4a7b30")

    async def insert_one(doc):
        doc["_id"] = inserted_id
        return MagicMock()

    mock_collection.insert_one = AsyncMock(side_effect=insert_one)

    mock_db = {"job_offers": mock_collection}

    async def mock_get_database():
        return mock_db

    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", mock_get_database)

    incoming_offer = {
        "poste": "MLOps Engineer",
        "entreprise": "NewCompany",
        "localisation": "Paris",
        "url": "https://newcompany.com/jobs/99",
        "description": "Nouvelle offre",
    }

    res = await save_offers_to_database([incoming_offer])

    assert res["saved"] == 1
    assert res["offer_ids"] == [inserted_id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec jobtracker-backend pytest tests/test_job_offers_pipeline.py -k returns_offer_ids -v`
Expected: FAIL — `KeyError: 'offer_ids'`

- [ ] **Step 3: Write minimal implementation**

Remplacer le corps de `save_offers_to_database` dans `backend/app/tasks/job_offers_collectors.py:405-518` par :

```python
async def save_offers_to_database(offers: list) -> dict:
    """Étape 6: Sauvegarde en base de données avec réconciliation cross-sources et fusion intelligente"""
    logger.info(f"💾 Sauvegarde de {len(offers)} offres")

    if not offers:
        logger.warning("⚠️ Aucune offre à sauvegarder")
        return {"saved": 0, "updated": 0, "offer_ids": []}

    try:
        db = await get_database()
        collection = db["job_offers"]

        # 1. Déduplication multi-critères en mémoire sur le lot entrant
        consolidated_offers = deduplicate_and_merge_offers(offers)

        saved_count = 0
        updated_count = 0
        error_count = 0
        offer_ids: list = []

        for offer in consolidated_offers:
            try:
                offer_url = (offer.get("url") or "").strip()
                company = offer.get("entreprise", "")
                position = offer.get("poste", "")
                location = offer.get("localisation")

                unique_key = offer.get("unique_key") or compute_unique_key(
                    company=company,
                    position=position,
                    location=location,
                    url=offer_url,
                )
                offer["unique_key"] = unique_key

                # Recherche directe en base par clé unique ou URL (principale ou alternative)
                query_conditions = [{"unique_key": unique_key}]
                if offer_url:
                    query_conditions.append({"url": offer_url})
                    query_conditions.append({"alternative_urls": offer_url})
                if offer.get("alternative_urls"):
                    query_conditions.append({"url": {"$in": offer["alternative_urls"]}})

                existing_doc = await collection.find_one({"$or": query_conditions})

                # Si non trouvé directement, recherche sémantique parmi les offres de la même entreprise
                if not existing_doc and company:
                    norm_comp = normalize_company(company).lower()
                    if norm_comp and norm_comp != "non spécifié":
                        company_candidates = await collection.find(
                            {"entreprise": {"$regex": f"^{re.escape(norm_comp)}$", "$options": "i"}}
                        ).to_list(20)
                        for candidate in company_candidates:
                            if are_offers_duplicates(candidate, offer):
                                existing_doc = candidate
                                break

                if existing_doc:
                    # Fusion des offres avec conservation de la source prioritaire et des métadonnées
                    merged = merge_multidiffusion_offers(existing_doc, offer)
                    update_fields = {
                        k: v for k, v in merged.items()
                        if k not in {"_id", "created_at", "date_creation"}
                    }
                    update_fields["unique_key"] = unique_key
                    update_fields["updated_at"] = datetime.now(timezone.utc)

                    await collection.update_one(
                        {"_id": existing_doc["_id"]},
                        {"$set": update_fields}
                    )
                    offer_ids.append(existing_doc["_id"])
                    updated_count += 1
                else:
                    # Nouvelle offre
                    new_doc = dict(offer)
                    new_doc["unique_key"] = unique_key
                    new_doc["created_at"] = offer.get("created_at") or datetime.now(timezone.utc)
                    new_doc["updated_at"] = datetime.now(timezone.utc)
                    try:
                        await collection.insert_one(new_doc)
                        offer_ids.append(new_doc["_id"])
                        saved_count += 1
                    except Exception as ins_err:
                        # En cas de conflit rare d'index unique (ex: course concurrente), repli sur mise à jour
                        logger.warning(f"⚠️ Conflit d'insertion pour {unique_key}, repli sur update: {ins_err}")
                        fallback_filter = {"unique_key": unique_key}
                        if offer_url:
                            fallback_filter = {"$or": [{"url": offer_url}, {"unique_key": unique_key}]}
                        fallback_result = await collection.update_one(
                            fallback_filter,
                            {"$set": {k: v for k, v in new_doc.items() if k != "_id"}},
                            upsert=True,
                        )
                        if fallback_result.upserted_id:
                            offer_ids.append(fallback_result.upserted_id)
                        else:
                            fallback_doc = await collection.find_one(fallback_filter, {"_id": 1})
                            if fallback_doc:
                                offer_ids.append(fallback_doc["_id"])
                        updated_count += 1

            except Exception as e:
                logger.warning(f"⚠️ Erreur traitement offre {offer.get('poste')}: {e}")
                error_count += 1
                continue

        logger.info(
            f"✅ Sauvegarde terminée: {saved_count} créées, {updated_count} mises à jour"
        )

        if error_count > 0:
            logger.warning(f"⚠️ {error_count} erreurs lors de la sauvegarde")
            if saved_count == 0 and updated_count == 0:
                raise RuntimeError(
                    f"Sauvegarde totalement échouée: {error_count}/{len(offers)} offres perdues"
                )

        return {"saved": saved_count, "updated": updated_count, "offer_ids": offer_ids}

    except Exception as e:
        logger.error(f"💥 Erreur sauvegarde: {e}")
        raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec jobtracker-backend pytest tests/test_job_offers_pipeline.py -v`
Expected: PASS (tous les tests du fichier, y compris `test_save_offers_to_database_cross_source_dedup` déjà existant)

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/job_offers_collectors.py backend/tests/test_job_offers_pipeline.py
git commit -m "feat(job-offers): save_offers_to_database retourne les offer_ids créés/mis à jour"
```

---

## Task 7: `collect_and_save_offers` appelle `tag_new_offers`

**Files:**
- Modify: `backend/app/tasks/job_offers_collectors.py:1-30` (imports), `:557-567` (`collect_and_save_offers`)
- Test: `backend/tests/test_job_offers_pipeline.py` (ajout)

**Interfaces:**
- Consumes: `save_offers_to_database` retournant `offer_ids` (Task 6), `tag_new_offers(offer_ids: list, db) -> None` (Task 5)
- Produces: rien de nouveau — `collect_and_save_offers` garde sa signature `(query: str) -> dict`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_job_offers_pipeline.py` :

```python
@pytest.mark.asyncio
async def test_collect_and_save_offers_tags_new_offers(monkeypatch):
    from unittest.mock import AsyncMock
    from bson import ObjectId
    import app.tasks.job_offers_collectors as collectors

    fake_offer_ids = [ObjectId("650000000000000000000040")]

    monkeypatch.setattr(collectors, "get_urls_for_query", AsyncMock(return_value=["https://example.com/1"]))
    monkeypatch.setattr(collectors, "crawl_urls_for_offers", AsyncMock(return_value=[{"poste": "Data Engineer"}]))
    monkeypatch.setattr(collectors, "enrich_offers", AsyncMock(return_value=[{"poste": "Data Engineer"}]))
    monkeypatch.setattr(collectors, "clean_duplicate_offers", AsyncMock(return_value=[{"poste": "Data Engineer"}]))
    monkeypatch.setattr(
        collectors,
        "save_offers_to_database",
        AsyncMock(return_value={"saved": 1, "updated": 0, "offer_ids": fake_offer_ids}),
    )
    mock_tag_new_offers = AsyncMock()
    monkeypatch.setattr(collectors, "tag_new_offers", mock_tag_new_offers)
    monkeypatch.setattr(collectors, "cleanup_resources", AsyncMock())
    monkeypatch.setattr(collectors, "get_database", AsyncMock(return_value={"job_offers": None}))

    result = await collectors.collect_and_save_offers("data engineer lyon")

    assert result == {"saved": 1, "updated": 0, "offer_ids": fake_offer_ids}
    mock_tag_new_offers.assert_awaited_once()
    assert mock_tag_new_offers.call_args.args[0] == fake_offer_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec jobtracker-backend pytest tests/test_job_offers_pipeline.py -k tags_new_offers -v`
Expected: FAIL — `AttributeError: <module ...> does not have the attribute 'tag_new_offers'`

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/tasks/job_offers_collectors.py`, ajouter l'import après la ligne `from app.services.role_normalizer import normalize_role` (ligne 26) :

```python
from app.services.offer_profile_matcher import tag_new_offers
```

Remplacer `collect_and_save_offers` (lignes 557-567) par :

```python
async def collect_and_save_offers(query: str) -> dict:
    """Version asynchrone complète pour collecter, nettoyer et enregistrer les offres"""
    logger.info(f"🚀 Collecte async démarrée: {query}")
    try:
        urls = await get_urls_for_query(query)
        offers = await crawl_urls_for_offers(urls)
        enriched = await enrich_offers(offers, query)
        cleaned = await clean_duplicate_offers(enriched)
        result = await save_offers_to_database(cleaned)
        db = await get_database()
        await tag_new_offers(result["offer_ids"], db)
        return result
    finally:
        await cleanup_resources()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec jobtracker-backend pytest tests/test_job_offers_pipeline.py -v`
Expected: PASS (tous les tests du fichier)

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/job_offers_collectors.py backend/tests/test_job_offers_pipeline.py
git commit -m "feat(job-offers): collect_and_save_offers tague les nouvelles offres après collecte"
```

---

## Task 8: Hook `PUT /profile/candidate/preferences` → `rematch_user` en tâche de fond

**Files:**
- Modify: `backend/app/routers/cover_letters.py:1-27` (imports), `:408-427` (`update_candidate_preferences`)
- Test: `backend/tests/test_candidate_preferences.py` (ajout)

**Interfaces:**
- Consumes: `rematch_user(user_id: str, db) -> None` (Task 4)
- Produces: rien de nouveau — l'endpoint garde son contrat de réponse actuel

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_candidate_preferences.py` :

```python
def test_put_preferences_triggers_rematch_on_target_roles_change():
    from unittest.mock import AsyncMock, MagicMock, patch
    from bson import ObjectId
    from app.auth import get_current_user
    from app.database import get_database
    from main import app

    user_id = "60c72b2f9b1d8b2bad7f5678"
    stored = {"user_id": user_id, "headline": "Dev", "experiences": [], "sources": {}}

    async def find_one(_query):
        return dict(stored) if stored else None

    async def update_one(_filter, update, upsert=False):
        stored.update(update.get("$set", {}))
        stored.setdefault("_id", ObjectId())
        return MagicMock()

    collection = MagicMock()
    collection.find_one = AsyncMock(side_effect=find_one)
    collection.update_one = AsyncMock(side_effect=update_one)
    db = MagicMock()
    db.__getitem__.return_value = collection

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=user_id, username="tester", email="t3@example.com", hashed_password="x"
    )

    try:
        with patch("app.routers.cover_letters.rematch_user", AsyncMock()) as mock_rematch:
            payload = {"target_roles": ["Data Engineer"], "locations": ["Lyon"]}
            response = client_put = None
            from fastapi.testclient import TestClient
            test_client = TestClient(app)
            response = test_client.put("/profile/candidate/preferences", json=payload)
            assert response.status_code == 200
            mock_rematch.assert_called_once()
            assert mock_rematch.call_args.args[0] == user_id
    finally:
        app.dependency_overrides.clear()


def test_put_preferences_no_rematch_when_matching_fields_unchanged():
    from unittest.mock import AsyncMock, MagicMock, patch
    from bson import ObjectId
    from app.auth import get_current_user
    from app.database import get_database
    from main import app
    from fastapi.testclient import TestClient

    user_id = "60c72b2f9b1d8b2bad7f9999"
    initial_payload = {"target_roles": ["Data Engineer"], "locations": ["Lyon"], "notice_period": "1 mois"}
    stored = {
        "user_id": user_id,
        "headline": "Dev",
        "experiences": [],
        "sources": {"manual": {"preferences": dict(initial_payload)}},
    }

    async def find_one(_query):
        return dict(stored) if stored else None

    async def update_one(_filter, update, upsert=False):
        stored.update(update.get("$set", {}))
        stored.setdefault("_id", ObjectId())
        return MagicMock()

    collection = MagicMock()
    collection.find_one = AsyncMock(side_effect=find_one)
    collection.update_one = AsyncMock(side_effect=update_one)
    db = MagicMock()
    db.__getitem__.return_value = collection

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=user_id, username="tester", email="t4@example.com", hashed_password="x"
    )

    try:
        with patch("app.routers.cover_letters.rematch_user", AsyncMock()) as mock_rematch:
            # Seul notice_period change, pas target_roles/locations/remote_policy
            payload = {"target_roles": ["Data Engineer"], "locations": ["Lyon"], "notice_period": "3 mois"}
            test_client = TestClient(app)
            response = test_client.put("/profile/candidate/preferences", json=payload)
            assert response.status_code == 200
            mock_rematch.assert_not_called()
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec jobtracker-backend pytest tests/test_candidate_preferences.py -k rematch -v`
Expected: FAIL — `AttributeError: <module 'app.routers.cover_letters'> does not have the attribute 'rematch_user'`

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/routers/cover_letters.py`, ajouter l'import après la ligne `from app.services.usage_tracker import record_api_usage, require_user_quota` (ligne 26) :

```python
from app.services.offer_profile_matcher import rematch_user
```

Remplacer `update_candidate_preferences` (lignes 408-427) par :

```python
@cover_letters_router.put("/profile/candidate/preferences")
async def update_candidate_preferences(
    background_tasks: BackgroundTasks,
    preferences_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Mise à jour ciblée des critères de recherche et préférences du candidat."""
    try:
        from app.models import CandidatePreferences
        validated_pref = CandidatePreferences.model_validate(preferences_data)
        existing = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)}) or {}
        sources = dict(existing.get("sources") or {})
        manual = dict(sources.get("manual") or {})
        old_preferences = dict(manual.get("preferences") or {})
        manual["preferences"] = validated_pref.model_dump()
        result = await _store_source(db, str(current_user.id), "manual", manual)

        matching_fields_changed = any(
            old_preferences.get(field) != manual["preferences"].get(field)
            for field in ("target_roles", "locations", "remote_policy")
        )
        if matching_fields_changed:
            background_tasks.add_task(rematch_user, str(current_user.id), db)

        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec de la mise à jour des préférences pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="La mise à jour des préférences a échoué")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec jobtracker-backend pytest tests/test_candidate_preferences.py -v`
Expected: PASS (tous les tests du fichier, y compris `test_put_preferences_endpoint` déjà existant)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/cover_letters.py backend/tests/test_candidate_preferences.py
git commit -m "feat(profile): déclenche rematch_user en tâche de fond quand les critères de matching changent"
```

---

## Task 9: `GET /job-offers?profile_only=true`

**Files:**
- Modify: `backend/app/routers/job_offers.py:271-340`
- Test: `backend/tests/test_job_offers_pipeline.py` (ajout)

**Interfaces:**
- Consumes: rien de nouveau (le pipeline d'agrégation existant reste inchangé)
- Produces: rien de nouveau côté service — juste un paramètre de requête HTTP supplémentaire, consommé par le frontend (Task 10)

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_job_offers_pipeline.py` :

```python
def test_get_job_offers_profile_only_filters_by_matched_user(client):
    from unittest.mock import AsyncMock, MagicMock
    from app.auth import get_current_user_optional
    from app.database import get_database
    from main import app
    from app.models import UserModel

    user = UserModel(
        id="650000000000000000000099",
        username="tester",
        email="profileonly@example.com",
        hashed_password="x",
    )

    captured = {}

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])

    def aggregate_side_effect(pipeline):
        captured["match"] = pipeline[0]["$match"]
        return mock_cursor

    mock_offers_collection = MagicMock()
    mock_offers_collection.aggregate = MagicMock(side_effect=aggregate_side_effect)

    class FakeDB(dict):
        def __missing__(self, key):
            generic = MagicMock()
            generic_cursor = MagicMock()
            generic_cursor.to_list = AsyncMock(return_value=[])
            generic.find = MagicMock(return_value=generic_cursor)
            self[key] = generic
            return generic

    mock_db = FakeDB()
    mock_db["job_offers"] = mock_offers_collection

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user_optional] = lambda: user

    try:
        response = client.get("/job-offers/?profile_only=true")
        assert response.status_code == 200
        assert captured["match"]["matched_user_ids"] == str(user.id)
    finally:
        app.dependency_overrides.clear()


def test_get_job_offers_profile_only_ignored_when_anonymous(client):
    from unittest.mock import AsyncMock, MagicMock
    from app.auth import get_current_user_optional
    from app.database import get_database
    from main import app

    captured = {}

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])

    def aggregate_side_effect(pipeline):
        captured["match"] = pipeline[0]["$match"]
        return mock_cursor

    mock_offers_collection = MagicMock()
    mock_offers_collection.aggregate = MagicMock(side_effect=aggregate_side_effect)

    class FakeDB(dict):
        def __missing__(self, key):
            generic = MagicMock()
            generic_cursor = MagicMock()
            generic_cursor.to_list = AsyncMock(return_value=[])
            generic.find = MagicMock(return_value=generic_cursor)
            self[key] = generic
            return generic

    mock_db = FakeDB()
    mock_db["job_offers"] = mock_offers_collection

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user_optional] = lambda: None

    try:
        response = client.get("/job-offers/?profile_only=true")
        assert response.status_code == 200
        assert "matched_user_ids" not in captured["match"]
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec jobtracker-backend pytest tests/test_job_offers_pipeline.py -k profile_only -v`
Expected: FAIL — `assert "matched_user_ids" in captured["match"]` échoue (le paramètre `profile_only` n'existe pas encore, silencieusement ignoré par FastAPI)

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/routers/job_offers.py`, modifier la signature de `get_job_offers` (ligne 271) pour ajouter le paramètre après `min_score` :

```python
async def get_job_offers(
    keywords: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    contract_type: Optional[str] = Query(None),
    work_mode: Optional[str] = Query(None),
    days_recent: Optional[int] = Query(None),
    interaction_status: Optional[str] = Query(None),
    only_saved: bool = Query(False),
    include_hidden: bool = Query(False),
    min_score: Optional[float] = Query(None),
    profile_only: bool = Query(False),
    limit: int = Query(16, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db=Depends(get_database),
    current_user: Optional[UserModel] = Depends(get_current_user_optional),
):
```

Et ajouter, juste après le bloc `if work_mode:` (ligne 325-326), avant le bloc `if days_recent and days_recent > 0:` :

```python
        if profile_only and current_user:
            match_filter["matched_user_ids"] = str(current_user.id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec jobtracker-backend pytest tests/test_job_offers_pipeline.py -v`
Expected: PASS (tous les tests du fichier)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/job_offers.py backend/tests/test_job_offers_pipeline.py
git commit -m "feat(job-offers): ajoute le paramètre profile_only à GET /job-offers"
```

---

## Task 10: Frontend — `JobOfferFilter` et `jobOffersApi.getAll`

**Files:**
- Modify: `frontend/src/lib/api.ts:375-388` (`JobOfferFilter`), `:594-618` (`jobOffersApi.getAll`)

**Interfaces:**
- Consumes: rien de nouveau
- Produces: `JobOfferFilter.profile_only?: boolean` — consommé par `offers/page.tsx` (Task 11)

- [ ] **Step 1: Modifier l'interface `JobOfferFilter`**

Dans `frontend/src/lib/api.ts:375-388`, ajouter le champ :

```typescript
export interface JobOfferFilter {
  keywords?: string;
  location?: string;
  company?: string;
  contract_type?: string;
  work_mode?: string;
  days_recent?: number;
  interaction_status?: "saved" | "hidden" | "applied" | "dismissed" | "none";
  limit?: number;
  skip?: number;
  only_saved?: boolean;
  include_hidden?: boolean;
  min_score?: number;
  profile_only?: boolean;
}
```

- [ ] **Step 2: Modifier `jobOffersApi.getAll`**

Dans `frontend/src/lib/api.ts:594-618`, ajouter la ligne après `if (filters.min_score !== undefined ...)` :

```typescript
  getAll: async (filters: JobOfferFilter = {}) => {
    const params = new URLSearchParams();

    if (filters.keywords) params.append("keywords", filters.keywords);
    if (filters.location) params.append("location", filters.location);
    if (filters.company) params.append("company", filters.company);
    if (filters.contract_type) params.append("contract_type", filters.contract_type);
    if (filters.work_mode) params.append("work_mode", filters.work_mode);
    if (filters.days_recent !== undefined && filters.days_recent !== null) {
      params.append("days_recent", filters.days_recent.toString());
    }
    if (filters.interaction_status) params.append("interaction_status", filters.interaction_status);
    if (filters.only_saved) params.append("only_saved", "true");
    if (filters.include_hidden) params.append("include_hidden", "true");
    if (filters.min_score !== undefined && filters.min_score !== null) {
      params.append("min_score", filters.min_score.toString());
    }
    if (filters.profile_only) params.append("profile_only", "true");
    if (filters.limit) params.append("limit", filters.limit.toString());
    if (filters.skip) params.append("skip", filters.skip.toString());

    const endpoint = `/job-offers/?${params.toString()}`;
    return fetchApi<JobOffer[]>(endpoint, "GET");
  },
```

- [ ] **Step 3: Vérifier le typage**

Run: `cd frontend && npm run lint`
Expected: aucune nouvelle erreur TypeScript/ESLint sur `src/lib/api.ts`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(job-offers): ajoute profile_only à JobOfferFilter et jobOffersApi.getAll"
```

---

## Task 11: Frontend — `offers/page.tsx` bascule sur `profile_only`

**Files:**
- Modify: `frontend/src/app/offers/page.tsx:124-146` (`currentFilters`), `:282-321` (`handleApplyProfileCriteria`), `:1015-1056` (badges profil), `:1160-1176` (bouton "Effacer les filtres")

**Interfaces:**
- Consumes: `JobOfferFilter.profile_only` (Task 10)
- Produces: rien de nouveau — dernière tâche de la chaîne

- [ ] **Step 1: Ajouter un état pour le message "profil vide"**

Dans `frontend/src/app/offers/page.tsx`, juste après la ligne 284 (`const [isProfileFilterActive, setIsProfileFilterActive] = useState(false);`), ajouter :

```tsx
  const [profileEmpty, setProfileEmpty] = useState(false);
```

- [ ] **Step 2: Rendre `currentFilters` additif avec `profile_only`**

Remplacer le `useMemo` de `frontend/src/app/offers/page.tsx:124-146` par :

```tsx
  const currentFilters = useMemo((): JobOfferFilter => {
    const f: JobOfferFilter = {};
    if (searchTerm) f.keywords = searchTerm;
    if (locationFilter) f.location = locationFilter;
    if (companyFilter) f.company = companyFilter;
    if (contractTypeFilter) f.contract_type = contractTypeFilter;
    if (workModeFilter) f.work_mode = workModeFilter;
    if (daysRecentFilter !== undefined) f.days_recent = daysRecentFilter;
    if (onlySaved) f.only_saved = true;
    if (interactionStatus) f.interaction_status = interactionStatus;
    if (minScoreFilter !== undefined) f.min_score = minScoreFilter;
    if (isProfileFilterActive) f.profile_only = true;
    return f;
  }, [
    searchTerm,
    locationFilter,
    companyFilter,
    contractTypeFilter,
    workModeFilter,
    daysRecentFilter,
    onlySaved,
    interactionStatus,
    minScoreFilter,
    isProfileFilterActive,
  ]);
```

- [ ] **Step 3: Simplifier `handleApplyProfileCriteria`**

Remplacer `frontend/src/app/offers/page.tsx:282-321` par (la déclaration de `profileRoles`/`profileLocations`/`isProfileFilterActive` aux lignes 282-284 reste inchangée, seul le corps de la fonction change) :

```tsx
  // Appliquer automatiquement les critères enregistrés dans le profil du candidat.
  // Le matching (rôle canonique + localisation normalisée) est désormais calculé
  // côté backend et persisté sur chaque offre (matched_user_ids) ; on ne dérive
  // plus de recherche texte ici, seulement l'affichage des badges.
  const handleApplyProfileCriteria = useCallback(async () => {
    try {
      const [profile, suggested] = await Promise.all([
        coverLetterApi.getCandidateProfile(),
        coverLetterApi.getSuggestedRoles().catch(() => ({ roles: [] })),
      ]);
      if (!profile) return;

      const prefs = profile.preferences || {};
      const targetRoles = prefs.target_roles || [];
      const allRoles = targetRoles.length > 0 ? targetRoles : suggested.roles || [];
      const locs = prefs.locations || [];

      if (allRoles.length === 0 && locs.length === 0) {
        setProfileRoles([]);
        setProfileLocations([]);
        setIsProfileFilterActive(false);
        setProfileEmpty(true);
        return;
      }

      setProfileRoles(allRoles);
      setProfileLocations(locs);
      setIsProfileFilterActive(true);
      setProfileEmpty(false);

      // Réinitialiser les filtres annexes trop restrictifs
      setContractTypeFilter("");
      setCompanyFilter("");
      setWorkModeFilter("");
      setDaysRecentFilter(undefined);
      setMinScoreFilter(undefined);
      setOnlySaved(false);
      setInteractionStatus(undefined);
    } catch (err) {
      console.error("Erreur lors de la récupération des critères du profil:", err);
    }
  }, []);
```

- [ ] **Step 4: Afficher un message quand le profil n'a aucun critère**

Dans `frontend/src/app/offers/page.tsx`, juste après le bloc `{profileRoles.length > 0 && ( ... )}` qui se termine ligne 1056, ajouter :

```tsx
              {profileEmpty && (
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-800/80 text-xs text-amber-300">
                  <FiTarget className="w-3.5 h-3.5" />
                  <span>
                    Complétez vos postes ciblés ou vos villes dans votre profil pour utiliser le filtre &quot;Selon mon profil&quot;.
                  </span>
                </div>
              )}
```

- [ ] **Step 5: Réinitialiser le filtre profil dans "Effacer les filtres"**

Remplacer le contenu du bouton "Effacer les filtres" (`frontend/src/app/offers/page.tsx:1160-1175`) par :

```tsx
                <button
                  onClick={() => {
                    setSearchTerm("");
                    setLocationFilter("");
                    setCompanyFilter("");
                    setContractTypeFilter("");
                    setWorkModeFilter("");
                    setDaysRecentFilter(undefined);
                    setOnlySaved(false);
                    setInteractionStatus(undefined);
                    setMinScoreFilter(undefined);
                    setIsProfileFilterActive(false);
                    setProfileRoles([]);
                    setProfileLocations([]);
                    setProfileEmpty(false);
                  }}
                  className="text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors"
                >
                  Effacer les filtres
                </button>
```

- [ ] **Step 6: Vérifier le typage**

Run: `cd frontend && npm run lint`
Expected: aucune nouvelle erreur TypeScript/ESLint sur `src/app/offers/page.tsx`

- [ ] **Step 7: Vérification manuelle au navigateur**

Démarrer le stack (`docker compose up` ou équivalent selon ce projet), ouvrir `/offers` :
1. Au chargement, si le profil connecté a des `target_roles`/`locations`, les badges s'affichent et la liste ne montre que des offres taguées pour ce user (vérifier via l'onglet réseau que la requête part bien avec `profile_only=true` et sans `keywords`/`location`).
2. Cliquer un badge de rôle : la recherche texte se déclenche en plus (`keywords` apparaît dans la requête), `profile_only=true` reste présent.
3. Cliquer "Effacer les filtres" : la requête repart sans `profile_only` ni aucun autre filtre.
4. Sur un compte dont le profil n'a ni rôle ni ville en préférences : le message "Complétez vos postes ciblés..." s'affiche, aucune requête `profile_only=true` n'est envoyée.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/offers/page.tsx
git commit -m "feat(job-offers): bascule le bouton Selon mon profil sur le filtre profile_only persistant"
```

---

## Task 12: Script de backfill `backend/scripts/backfill_matched_user_ids.py`

**Files:**
- Create: `backend/scripts/backfill_matched_user_ids.py`

**Interfaces:**
- Consumes: `get_normalized_profile_criteria` (Task 3), `offer_matches_criteria` (Task 2)
- Produces: rien — script one-shot, dernier maillon de la chaîne

- [ ] **Step 1: Écrire le script**

```python
# backend/scripts/backfill_matched_user_ids.py
"""Backfill de `matched_user_ids` sur les offres déjà en base MongoDB.

Recalcule le matching persistant (canonical_title / localisation normalisés)
pour chaque profil candidat existant, contre tout le stock d'offres actif.
N'effectue aucun appel de collecte web ; peut néanmoins déclencher un appel
d'embedding via normalize_role() pour des rôles pas encore connus de
role_aliases (mode réel uniquement, pas en --dry-run).

Usage:
    docker exec jobtracker-backend python scripts/backfill_matched_user_ids.py --dry-run
    docker exec jobtracker-backend python scripts/backfill_matched_user_ids.py
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.services.offer_profile_matcher import get_normalized_profile_criteria, offer_matches_criteria

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def backfill_matched_user_ids(dry_run: bool) -> None:
    db = await get_database()

    profiles = await db["candidate_profile"].find({}).to_list(length=None)
    logger.info(f"🔍 {len(profiles)} profils candidats à traiter...")

    offers = await db["job_offers"].find({"is_deleted": {"$ne": True}}).to_list(length=None)
    logger.info(f"🔍 {len(offers)} offres actives en base...")

    total_tagged = 0

    for profile in profiles:
        user_id = str(profile["user_id"])
        prefs = profile.get("preferences") or {}
        normalized_roles, normalized_locations, remote_policy = await get_normalized_profile_criteria(prefs, db)

        matching_ids = [
            offer["_id"]
            for offer in offers
            if offer_matches_criteria(offer, normalized_roles, normalized_locations, remote_policy)
        ]

        logger.info(f"  - user {user_id} : {len(matching_ids)} offres matchées")
        total_tagged += len(matching_ids)

        if not dry_run and matching_ids:
            await db["job_offers"].update_many(
                {"_id": {"$in": matching_ids}},
                {"$addToSet": {"matched_user_ids": user_id}},
            )

    mode = "DRY-RUN (aucune écriture)" if dry_run else "RUN RÉEL"
    logger.info(
        f"✅ Backfill terminé [{mode}] !\n"
        f"  - Profils traités : {len(profiles)}\n"
        f"  - Offres actives analysées : {len(offers)}\n"
        f"  - Associations profil<->offre trouvées : {total_tagged}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les changements sans écrire en base",
    )
    args = parser.parse_args()
    asyncio.run(backfill_matched_user_ids(dry_run=args.dry_run))
```

- [ ] **Step 2: Vérification manuelle en `--dry-run` contre la base de test/dev**

Run: `docker exec jobtracker-backend python scripts/backfill_matched_user_ids.py --dry-run`
Expected: le script se termine avec le résumé `✅ Backfill terminé [DRY-RUN (aucune écriture)] !`, sans exception, et le nombre d'associations trouvées est cohérent avec les profils ayant des `target_roles`/`locations` renseignés (pas de test automatisé pour ce script — même convention que `backend/scripts/backfill_canonical_titles.py`, qui n'en a pas non plus).

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/backfill_matched_user_ids.py
git commit -m "feat(job-offers): ajoute le script de backfill matched_user_ids"
```

---

## Migration post-déploiement

Une fois les 12 tâches mergées et déployées, lancer une fois manuellement (pas de migration automatique au démarrage, cohérent avec `backfill_canonical_titles.py`) :

```bash
docker exec jobtracker-backend python scripts/backfill_matched_user_ids.py --dry-run
# vérifier le résumé, puis :
docker exec jobtracker-backend python scripts/backfill_matched_user_ids.py
```
