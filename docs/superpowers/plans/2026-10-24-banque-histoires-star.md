# Banque d'histoires STAR+R commune — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** remplacer les histoires STAR+R recopiées dans chaque kit par une banque par utilisateur, que chaque kit référence par des lignes « exigence → histoire → adéquation », sans perdre aucune histoire existante.

**Architecture :** nouvelle collection `star_stories` (les faits) et nouveau champ `interview_preps.story_slots` (l'angle propre à l'offre). Les kits existants migrent paresseusement au premier accès, par une fonction idempotente que le script de remplissage réutilise. La génération passe par deux appels à l'IA : une association avec la banque (`story_match`), puis une écriture réduite aux manques (`stories`). Les fonctions pures (rattachement à une expérience, doublons) vivent à part des opérations MongoDB.

**Tech Stack :** FastAPI, Motor (MongoDB), Pydantic v2, LiteLLM (`acompletion`), pytest + pytest-asyncio (Mongo de test sur le port 27018), Next.js 15 / React / TypeScript, Tailwind.

**Spec :** `docs/superpowers/specs/2026-10-24-banque-histoires-star-design.md` (maquette : `docs/superpowers/specs/2026-10-24-banque-histoires-star-maquette.html`). Lire la spec avant chaque tâche ; le texte de la spec fait foi sur la maquette.

## Global Constraints

- Isolation : toute lecture ou écriture de `star_stories` et de `interview_preps` est filtrée par `user_filter(user_id)` (motif `$or` chaîne/`ObjectId`). Une histoire d'un autre utilisateur se comporte comme une histoire absente : 404 côté API, `None` côté service.
- Quota : tout appel à l'IA est précédé de `require_user_quota(db, user_id, ApiUsageAction.INTERVIEW_PREP)` dans le routeur et suivi de `record_api_usage` avec `sub_action` `"story_match"` (association) ou `"stories"` (écriture).
- Annulation : après un appel à l'IA, `_generation_cancelled(request, module)` vrai → `Response(status_code=499)` et aucune écriture (ni banque, ni kit).
- Garde des chiffres : tout `angle` rédigé par l'IA passe par `_mask_invented_numbers(angle, sources)` où `sources` sont les faits de l'histoire (`situation`, `task`, `action`, `result`, `reflection`, `title`). Un nombre absent devient `[à chiffrer]`.
- Le nouveau code n'écrit jamais `interview_preps.stories` (copie de sûreté). Il ne le lit que dans `ensure_prep_migrated` et dans le script de remplissage.
- La génération ne supprime jamais une histoire de la banque. Seuls `DELETE /star-stories/{id}` et la fusion d'un doublon en retirent.
- Plafond : 5 lignes par kit (`MAX_STORY_SLOTS = 5`).
- Valeurs de `fit` : `strong`, `partial`, `transferable`, `gap`, `no_experience`, `manual`.
- Libellés d'interface repris tels quels de la spec : « Ce que l'offre demande », « Ton histoire », « Adéquation », « Toute ma banque (N) », « ✓ dans ce kit », « Utiliser pour… », « Écrire avec l'IA », « L'écrire moi-même », « Sans expérience rattachée », « pas d'expérience dans ton profil », « transférable », « corrige aussi dans les N autres kits qui utilisent cette histoire ».
- Libellés d'adéquation (choix du plan) : strong « forte », partial « partielle », transferable « transférable », gap « manque », no_experience « pas d'expérience dans ton profil », manual « choisie ».
- Tests : règles du `CLAUDE.md` du projet (invariants métier, isolation, gardes IA ; pas de test qui ne vérifie qu'un mock). Commande : `cd backend && .venv/bin/python -m pytest tests/<fichier> -v`. Frontend : `cd frontend && npm run lint && npm run build`.
- Aucune exécution sur la production. Lancer `migrate_star_stories_to_bank.py --apply` en production revient à l'utilisateur, après une sauvegarde.
- Commits : uniquement si l'utilisateur a autorisé les commits pour cette exécution. `git add` avec des chemins explicites, jamais `-A` ni `.`. Ne jamais indexer les fichiers modifiés par l'autre session en cours (notamment `backend/app/services/normalization.py`, `backend/app/routers/applications.py`, `docs/SYSTEM_ARCHITECTURE.md`, `frontend/src/types/application.ts`). `normalization.py` est seulement importé.

## Review Focus

1. **Kit jamais rouvert depuis le déploiement, régénéré directement** (premier appel = `POST .../generate/stories`) : ses histoires d'origine doivent entrer dans la banque avant que ses lignes soient remplacées. Test : Task 7, `test_generate_stories_on_unmigrated_kit_keeps_legacy_stories_in_bank`.
2. **L'IA d'association renvoie un `story_id` inconnu ou appartenant à un autre utilisateur** : traité comme « aucune histoire » (la ligne part à l'écriture des manques), jamais enregistré. Test : Task 5, `test_match_ignores_story_id_outside_bank`.
3. **Histoire de kit ancienne sans `id`, ou sans `reflection`/`key_tags`/`theme`** : migrée avec des valeurs par défaut, sans exception, et le kit garde autant de lignes. Test : Task 1, `test_migration_tolerates_legacy_story_without_id_or_optional_fields`.
4. **Fusion de doublons dans les cas limites** : même id des deux côtés (400), double clic (le second appel trouve B absent : 404, rien de perdu), kit qui contient A et B (les deux lignes pointent vers A). Tests : Task 4, `test_merge_same_id_is_400`, `test_merge_twice_is_404_and_keeps_data`, `test_merge_kit_holding_both_points_both_rows_to_kept`.
5. **L'IA d'écriture renvoie moins d'éléments que d'exigences, ou une expérience absente du profil** : les exigences sans élément deviennent `gap` (couverte) ou `no_experience` (non couverte) ; l'expérience inconnue devient `None`. Tests : Task 6, `test_writer_fewer_items_than_requirements`, `test_writer_drops_experience_not_in_profile`.

---

## Structure des fichiers

| Fichier | Rôle |
|---|---|
| `backend/app/models.py` (modifié, après `StarRStory` ~l.767 et dans `InterviewPrep` ~l.847) | Modèles `StoryFacts`, `BankStory`, `StorySlot`, etc. `StarRStory` reste (lecture héritée). |
| `backend/app/services/star_bank_rules.py` (nouveau) | Règles pures, sans base : rattachement d'une histoire à une expérience du profil, libellé d'expérience, détection des doublons. |
| `backend/app/services/star_bank.py` (nouveau) | Opérations MongoDB sur la banque : migration paresseuse, lecture hydratée d'un kit, usage, modification, suppression, fusion, restauration. |
| `backend/app/services/interview_prep_service.py` (modifié) | Sélection des exigences, appel d'association, appel d'écriture, assemblage des lignes. `generate_star_stories` disparaît. |
| `backend/app/llm/prompts/interview/story_match.md` (nouveau) | Prompt d'association. |
| `backend/app/llm/prompts/interview/star_stories.md` (réécrit) | Prompt d'écriture des seuls manques. |
| `backend/app/routers/star_stories.py` (nouveau) | Routes de la banque (`/star-stories…`). |
| `backend/app/routers/interview_prep.py` (modifié) | Migration paresseuse, lignes du kit, génération branchée sur la banque, lecteurs existants. |
| `backend/app/routers/__init__.py`, `backend/main.py`, `backend/app/database.py` (modifiés) | Enregistrement du routeur, index `star_stories`. |
| `backend/migrate_star_stories_to_bank.py` (nouveau) | Remplissage en masse, simulation par défaut. |
| `frontend/src/types/interview.ts`, `frontend/src/lib/api.ts` (modifiés) | Types et appels de la banque et des lignes. |
| `frontend/src/components/interview/StorySlotsTable.tsx` (nouveau) | Tableau du kit et détail de la ligne sélectionnée. |
| `frontend/src/components/interview/StoryBankPanel.tsx` (nouveau) | Panneau « Toute ma banque ». |
| `frontend/src/components/interview/DuplicateResolver.tsx` (nouveau) | Bandeau de doublon et vue côte à côte. |
| `frontend/src/components/interview/StarStoryCard.tsx`, `InterviewPrepTab.tsx` (modifiés) | Faits d'une histoire de la banque ; branchement de la section Histoires. |

Tests backend : `tests/test_star_bank_rules.py`, `tests/test_star_bank.py`, `tests/test_star_stories_api.py`, `tests/test_migrate_star_stories_to_bank.py` (nouveaux) ; `tests/test_interview_prep_service.py`, `tests/test_interview_prep_api.py` (modifiés).

---

### Task 1 : Modèles, migration paresseuse et lecture hydratée d'un kit

**Files :**
- Modify : `backend/app/models.py` (après `StarRStory`, et `InterviewPrep`)
- Create : `backend/app/services/star_bank_rules.py`, `backend/app/services/star_bank.py`
- Modify : `backend/app/routers/interview_prep.py` (`_get_prep_or_empty` l.51, `get_interview_prep` l.103)
- Modify : `backend/app/database.py` (nouvelle `create_star_stories_indexes`), `backend/main.py` (appel dans `lifespan`, après `create_job_offers_indexes`)
- Test : `backend/tests/test_star_bank_rules.py`, `backend/tests/test_star_bank.py`

**Interfaces :**
- Produces (modèles, `app/models.py`) :
  - `StoryFit = Literal["strong", "partial", "transferable", "gap", "no_experience", "manual"]`
  - `StoryExperience(BaseModel)` : `company: str`, `role: Optional[str] = None`, `start: Optional[str] = None`
  - `StoryFacts(BaseModel)` : `title: str`, `theme: str = "Général"`, `situation: str`, `task: str`, `action: str`, `result: str`, `reflection: str = ""`, `key_tags: List[str] = []`
  - `StoryOrigin(BaseModel)` : `kind: Literal["migrated", "generated", "manual"]`, `offer_id: Optional[str] = None`
  - `DiscardedStoryVersion(BaseModel)` : `id: str` (uuid4 par défaut), `facts: StoryFacts`, `source_story_id: str`, `discarded_at: datetime` (`utcnow_with_timezone`)
  - `BankStory(StoryFacts)` : `id: str` (uuid4 par défaut), `user_id: str`, `experience: Optional[StoryExperience] = None`, `origin: StoryOrigin`, `discarded_versions: List[DiscardedStoryVersion] = []`, `not_duplicate_of: List[str] = []`, `created_at`, `updated_at`
  - `StorySlot(BaseModel)` : `id: str` (uuid4), `requirement: str`, `story_id: Optional[str] = None`, `fit: StoryFit = "gap"`, `angle: str = ""`, `angle_edited: bool = False`
  - `InterviewPrep.story_slots: Optional[List[StorySlot]] = None`
- Produces (routeur `interview_prep.py`) : `async _prep_response(db, prep: Dict[str, Any], user_id: str) -> Dict[str, Any]` = `serialize_mongodb_doc(await hydrate_prep(db, prep, user_id))`. Toutes les routes qui renvoient le kit passent par elle (aujourd'hui 8 `return serialize_mongodb_doc(...)`, l.110 à l.467), sinon le `setPrep` du frontend perd les faits joints après une génération ou un entraînement.
- Produces (`star_bank_rules.py`, pur) :
  - `guess_experience(situation: str, experiences: List[Dict[str, Any]]) -> Optional[StoryExperience]`
  - `match_profile_experience(experience: Optional[StoryExperience], experiences: List[Dict[str, Any]]) -> Optional[int]`
  - `experience_label(experience: StoryExperience) -> str` : `"{role} · {company}"`, ou `company` seul sans rôle.
- Produces (`star_bank.py`) :
  - `user_filter(user_id: str) -> Dict[str, Any]`
  - `async ensure_prep_migrated(db, prep: Dict[str, Any]) -> Dict[str, Any]`
  - `async load_bank(db, user_id: str) -> List[BankStory]` (tri `updated_at` décroissant)
  - `async get_bank_story(db, user_id: str, story_id: Optional[str]) -> Optional[BankStory]`
  - `async story_usage_counts(db, user_id: str) -> Dict[str, int]` (nombre de kits distincts dont une ligne pointe vers l'histoire)
  - `async slots_with_stories(db, user_id: str, slots: List[Dict[str, Any]]) -> List[Tuple[StorySlot, Optional[BankStory]]]`
  - `async hydrate_prep(db, prep: Dict[str, Any], user_id: str) -> Dict[str, Any]` : ajoute à chaque ligne `story` (`BankStory` sérialisée + `used_in_kits`, ou `None`), et au kit `bank_count` et `duplicates` (liste vide jusqu'à la Task 4).

- [ ] **Step 1 : écrire les tests qui échouent**

`tests/test_star_bank_rules.py` :

```python
PROFILE_EXPS = [
    {"company": "Alpha Corp", "role": "Data Engineer", "start": "2022-01"},
    {"company": "Beta SAS", "role": "Data Analyst", "start": "2020-01"},
]

def test_guess_experience_single_company_found():
    exp = guess_experience("Chez alpha corp, le pipeline était lent.", PROFILE_EXPS)
    assert exp == StoryExperience(company="Alpha Corp", role="Data Engineer", start="2022-01")

def test_guess_experience_two_companies_is_none():
    assert guess_experience("Entre Alpha Corp et Beta SAS…", PROFILE_EXPS) is None

def test_guess_experience_no_company_is_none():
    assert guess_experience("Un pipeline lent.", PROFILE_EXPS) is None

def test_match_profile_experience_normalizes_company_and_role():
    assert match_profile_experience(StoryExperience(company="ALPHA CORP", role="data engineer"), PROFILE_EXPS) == 0
    assert match_profile_experience(StoryExperience(company="Gamma"), PROFILE_EXPS) is None
    assert match_profile_experience(None, PROFILE_EXPS) is None
```

`tests/test_star_bank.py` (helpers locaux `_legacy_story(**overrides) -> dict` et `async _seed_prep(db, user_id, offer_id, stories, questions=()) -> dict`) :

```python
async def test_migration_keeps_ids_and_creates_slots(test_db):
    # kit avec 2 histoires héritées (target_requirement "Piloter", "Fiabiliser") et une question liée à la 1re
    prep = await ensure_prep_migrated(test_db, seeded)
    bank_ids = {s.id for s in await load_bank(test_db, uid)}
    assert bank_ids == {s1["id"], s2["id"]}
    assert [(s["requirement"], s["story_id"], s["fit"], s["angle"]) for s in prep["story_slots"]] == [
        ("Piloter", s1["id"], "strong", ""), ("Fiabiliser", s2["id"], "strong", "")]
    stored = await test_db.interview_preps.find_one({"_id": seeded["_id"]})
    assert stored["stories"] == seeded["stories"]                      # copie de sûreté intacte
    assert stored["anticipated_questions"][0]["mapped_story_id"] == s1["id"]
    assert (await get_bank_story(test_db, uid, s1["id"])).origin.kind == "migrated"

async def test_migration_is_idempotent(test_db):
    await ensure_prep_migrated(test_db, seeded)
    again = await test_db.interview_preps.find_one({"_id": seeded["_id"]})
    await ensure_prep_migrated(test_db, again)
    assert await test_db.star_stories.count_documents({"user_id": uid}) == 2
    assert len((await test_db.interview_preps.find_one({"_id": seeded["_id"]}))["story_slots"]) == 2

async def test_migration_tolerates_legacy_story_without_id_or_optional_fields(test_db):
    legacy = {"title": "Ancienne", "situation": "S", "task": "T", "action": "A", "result": "R"}  # ni id, ni theme, ni reflection, ni key_tags
    prep = await ensure_prep_migrated(test_db, await _seed_prep(test_db, uid, oid, [legacy]))
    assert len(prep["story_slots"]) == 1 and prep["story_slots"][0]["story_id"]
    story = await get_bank_story(test_db, uid, prep["story_slots"][0]["story_id"])
    assert (story.theme, story.reflection, story.key_tags) == ("Général", "", [])

async def test_migration_attaches_experience_from_situation(test_db):
    # profil : Alpha Corp ; situation : "Chez Alpha Corp, …"
    assert story.experience.company == "Alpha Corp"

async def test_hydrate_joins_facts_and_counts_kits(test_db):
    # deux kits migrés dont les lignes pointent vers la même histoire (id partagé inséré à la main dans le 2e kit)
    hydrated = await hydrate_prep(test_db, prep_a, uid)
    row = hydrated["story_slots"][0]
    assert row["story"]["result"] == "−60 %" and row["story"]["used_in_kits"] == 2
    assert hydrated["bank_count"] == 1

async def test_hydrate_hides_other_users_story(test_db):
    # ligne qui pointe vers une histoire insérée avec user_id d'un autre utilisateur
    assert (await hydrate_prep(test_db, prep, uid))["story_slots"][0]["story"] is None
```

Dans `tests/test_interview_prep_api.py`, adapter `test_get_interview_prep_empty` : `assert data["story_slots"] == []` en plus des assertions existantes.

- [ ] **Step 2 : lancer les tests, vérifier l'échec**

Run : `cd backend && .venv/bin/python -m pytest tests/test_star_bank_rules.py tests/test_star_bank.py -v`
Expected : FAIL à l'import (`ModuleNotFoundError: app.services.star_bank_rules`).

- [ ] **Step 3 : implémenter**

- `guess_experience` : une entreprise du profil est « trouvée » si `re.search(r"\b" + re.escape(company.casefold()) + r"\b", situation.casefold())`. On compte les entreprises distinctes par `normalize_company` (`app.services.normalization`). Exactement une → instantané `company`/`role`/`start` de la première expérience du profil à cette entreprise.
- `match_profile_experience` : égalité `normalize_company` ; si `experience.role` est renseigné, égalité `normalize_position` en plus ; sinon, l'entreprise seule doit désigner une seule expérience du profil.
- `ensure_prep_migrated` : ne fait rien si `"story_slots" in prep` ou si le kit n'a pas d'`_id` (coquille vide). Sinon, charge `candidate_profile.experiences` de l'utilisateur. Pour chaque histoire héritée : id conservé (uuid neuf s'il manque), titre par défaut « Histoire sans titre », champs absents à leurs valeurs par défaut, `experience = guess_experience(situation, experiences)`, `origin = {"kind": "migrated", "offer_id": str(prep["offer_id"])}`. Écriture par `update_one({"id": id}, {"$setOnInsert": doc}, upsert=True)`, en ignorant `DuplicateKeyError` (upsert concurrent). Ensuite `update_one({"_id": prep["_id"], "story_slots": {"$exists": False}}, {"$set": {"story_slots": slots}})`, puis relire et renvoyer le kit.
- `_get_prep_or_empty` appelle `ensure_prep_migrated` sur un kit trouvé ; la coquille vide reçoit `"story_slots": []`. Les 8 retours du routeur passent par `_prep_response`.
- `create_star_stories_indexes(db)` : index unique sur `id`, index sur `user_id`.

- [ ] **Step 4 : lancer les tests, vérifier le succès**

Run : `cd backend && .venv/bin/python -m pytest tests/test_star_bank_rules.py tests/test_star_bank.py tests/test_interview_prep_api.py -v`
Expected : PASS (les tests existants de l'API restent verts).
Run : `ast-grep -p 'serialize_mongodb_doc($X)' -l python backend/app/routers/interview_prep.py`
Expected : une seule occurrence, dans `_prep_response`.

- [ ] **Step 5 : commit (si autorisé)**

```bash
git add backend/app/models.py backend/app/services/star_bank_rules.py backend/app/services/star_bank.py backend/app/routers/interview_prep.py backend/app/database.py backend/main.py backend/tests/test_star_bank_rules.py backend/tests/test_star_bank.py backend/tests/test_interview_prep_api.py
git commit -m "feat(star-bank): bank models, lazy kit migration and hydrated prep"
```

---

### Task 2 : Script de remplissage `migrate_star_stories_to_bank.py`

**Files :**
- Create : `backend/migrate_star_stories_to_bank.py`
- Test : `backend/tests/test_migrate_star_stories_to_bank.py`

**Interfaces :**
- Consumes : `ensure_prep_migrated`, `user_filter`, `load_bank` (Task 1).
- Produces :
  - `class MigrationInvariantError(RuntimeError)`
  - `async migrate(db, apply: bool) -> Dict[str, Dict[str, int]]` : rapport par `user_id` avec les clés `kit_stories` (histoires héritées de tous ses kits), `kits_to_migrate` (kits sans `story_slots` au début du run), puis, lus en fin de run, `bank_stories`, `kits_with_slots` et `possible_duplicates` (0 jusqu'à la Task 4, qui le branche sur `find_duplicate_pairs`).
  - `async check_invariant(db, preps: List[Dict[str, Any]]) -> None` : pour chaque kit, chaque id d'histoire héritée existe dans la banque de son utilisateur et `len(story_slots) == len(stories)` ; sinon `MigrationInvariantError` avec l'`_id` du kit.
  - `main()` : `apply = "--apply" in sys.argv[1:]`, `db = await get_database()`, affiche le rapport et le mode, comme `backend/backfill_contract_types.py`.

- [ ] **Step 1 : écrire les tests qui échouent**

```python
async def test_dry_run_writes_nothing(test_db):
    # kit hérité de l'utilisateur uid avec 2 histoires
    report = await migrate(test_db, apply=False)
    assert report[uid]["kits_to_migrate"] == 1 and report[uid]["kit_stories"] == 2
    assert await test_db.star_stories.count_documents({"user_id": uid}) == 0
    assert "story_slots" not in await test_db.interview_preps.find_one({"_id": prep_id})

async def test_apply_migrates_and_reports(test_db):
    report = await migrate(test_db, apply=True)
    assert (report[uid]["kits_to_migrate"], report[uid]["bank_stories"], report[uid]["kits_with_slots"]) == (1, 2, 1)

async def test_apply_twice_creates_nothing_more(test_db):
    await migrate(test_db, apply=True)
    second = await migrate(test_db, apply=True)
    assert second[uid]["bank_stories"] == 2 and second[uid]["kits_to_migrate"] == 0

async def test_check_invariant_raises_when_story_missing_from_bank(test_db):
    # kit avec story_slots posé à la main mais histoire héritée absente de star_stories
    with pytest.raises(MigrationInvariantError):
        await check_invariant(test_db, [prep])
```

Les assertions portent sur l'entrée `uid` du rapport : la base de test est partagée avec les autres tests.

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && .venv/bin/python -m pytest tests/test_migrate_star_stories_to_bank.py -v`
Expected : FAIL (`ModuleNotFoundError: migrate_star_stories_to_bank`).

- [ ] **Step 3 : implémenter**

En mode `apply`, `migrate` appelle `ensure_prep_migrated` sur chaque kit sans `story_slots`, puis `check_invariant` sur ces seuls kits (une fusion ou une suppression ultérieure retire légitimement des histoires de la banque). En simulation, aucun appel d'écriture : on compte seulement.

- [ ] **Step 4 : vérifier le succès**

Run : `cd backend && .venv/bin/python -m pytest tests/test_migrate_star_stories_to_bank.py -v`
Expected : PASS.

- [ ] **Step 5 : commit (si autorisé)**

```bash
git add backend/migrate_star_stories_to_bank.py backend/tests/test_migrate_star_stories_to_bank.py
git commit -m "feat(star-bank): idempotent backfill script with invariant check"
```

---

### Task 3 : API de la banque et lignes du kit

**Files :**
- Create : `backend/app/routers/star_stories.py`
- Modify : `backend/app/routers/__init__.py`, `backend/main.py` (`app.include_router(star_stories_router)`)
- Modify : `backend/app/services/star_bank.py`, `backend/app/routers/interview_prep.py`
- Test : `backend/tests/test_star_stories_api.py`

**Interfaces :**
- Consumes : Task 1 (`user_filter`, `load_bank`, `get_bank_story`, `story_usage_counts`, `hydrate_prep`, `match_profile_experience`, `experience_label`).
- Produces (`star_bank.py`) :
  - `async story_usage(db, user_id: str, story_id: str) -> List[Dict[str, str]]` : `[{"offer_id", "company", "role"}]`, entreprise et poste lus avec `_offer_role_and_company` (`interview_prep_service`).
  - `async update_story_facts(db, user_id: str, story_id: str, changes: Dict[str, Any]) -> Optional[BankStory]` (met `updated_at` à jour ; `None` si absente).
  - `async delete_bank_story(db, user_id: str, story_id: str) -> Optional[int]` : nombre de kits touchés, `None` si absente. Les lignes concernées passent à `story_id=None`, `fit="gap"`, `angle=""`, `angle_edited=False` ; les questions perdent `mapped_story_id` ; puis suppression.
- Produces (routes) :
  - `GET /star-stories` → `{"groups": [{"label", "experience", "stories": [BankStory + "used_in_kits"]}], "experiences": [{"company", "role", "start", "label"}], "count"}`. Groupes dans l'ordre du profil, seulement ceux qui ont des histoires, puis le groupe « Sans expérience rattachée » (`experience: null`).
  - `PATCH /star-stories/{story_id}` corps `UpdateStoryRequest` (tous les champs de `StoryFacts` optionnels, plus `experience: Optional[StoryExperience]`) ; seuls les champs envoyés sont écrits (`model_dump(exclude_unset=True)`) → `BankStory`.
  - `GET /star-stories/{story_id}/usage` → `{"kits": [...]}`.
  - `DELETE /star-stories/{story_id}` → `{"affected_kits": int}`.
  - `PUT /offers/{offer_id}/interview-prep/slots/{slot_id}` corps `UpdateStorySlotRequest{story_id?, requirement?, angle?}` → kit hydraté. `story_id` : doit exister dans la banque de l'utilisateur (sinon 404), met `fit="manual"`, `angle=""`, `angle_edited=False` sauf si `angle` est aussi envoyé. `angle` envoyé → `angle_edited=True`.
  - `DELETE /offers/{offer_id}/interview-prep/slots/{slot_id}` → kit hydraté ; la banque et les questions ne changent pas.
  - Toute route : histoire ou ligne absente, ou appartenant à un autre utilisateur → 404.

- [ ] **Step 1 : écrire les tests qui échouent**

`tests/test_star_stories_api.py` reprend le motif `mock_user` / `override_auth` de `tests/test_interview_prep_api.py:17-30` avec un utilisateur propre au fichier. Les kits sont créés migrés (avec `story_slots`) par un helper local.

```python
async def test_list_groups_by_profile_experience(client, override_auth, test_db):
    # profil : Alpha Corp / Data Engineer ; histoires : une rattachée ("alpha corp", "data engineer"), une sans expérience
    body = client.get("/star-stories").json()
    assert [g["label"] for g in body["groups"]] == ["Data Engineer · Alpha Corp", "Sans expérience rattachée"]
    assert body["count"] == 2

async def test_patch_facts_propagates_to_other_kits_without_llm(client, override_auth, test_db):
    # deux kits dont une ligne pointe vers la même histoire
    with patch("app.services.interview_prep_service.acompletion") as llm:
        assert client.patch(f"/star-stories/{sid}", json={"result": "−45 %"}).status_code == 200
    llm.assert_not_called()
    for offer in (offer_a, offer_b):
        assert client.get(f"/offers/{offer}/interview-prep").json()["story_slots"][0]["story"]["result"] == "−45 %"

async def test_patch_experience_attaches_story(client, override_auth, test_db):
    client.patch(f"/star-stories/{sid}", json={"experience": {"company": "Alpha Corp", "role": "Data Engineer"}})
    assert client.get("/star-stories").json()["groups"][0]["stories"][0]["id"] == sid

async def test_usage_lists_kits(client, override_auth, test_db):
    assert {k["offer_id"] for k in client.get(f"/star-stories/{sid}/usage").json()["kits"]} == {offer_a, offer_b}

async def test_delete_turns_rows_into_gap_and_unlinks_questions(client, override_auth, test_db):
    assert client.delete(f"/star-stories/{sid}").json() == {"affected_kits": 2}
    row = client.get(f"/offers/{offer_a}/interview-prep").json()["story_slots"][0]
    assert (row["story_id"], row["fit"], row["angle"], row["story"]) == (None, "gap", "", None)
    # question liée : mapped_story_id None ; autre histoire de la banque : toujours présente
    assert await test_db.star_stories.count_documents({"id": other_sid}) == 1

async def test_other_users_story_is_404_everywhere(client, override_auth, test_db):
    # histoire insérée avec user_id d'un autre utilisateur
    assert client.patch(f"/star-stories/{foreign}", json={"result": "x"}).status_code == 404
    assert client.get(f"/star-stories/{foreign}/usage").status_code == 404
    assert client.delete(f"/star-stories/{foreign}").status_code == 404
    assert client.put(f"/offers/{offer_a}/interview-prep/slots/{slot_id}", json={"story_id": foreign}).status_code == 404
    assert (await test_db.star_stories.find_one({"id": foreign}))["result"] != "x"

async def test_put_slot_story_sets_manual_and_resets_angle(client, override_auth, test_db):
    row = client.put(f"/offers/{offer_a}/interview-prep/slots/{slot_id}", json={"story_id": sid2}).json()["story_slots"][0]
    assert (row["story_id"], row["fit"], row["angle"], row["angle_edited"]) == (sid2, "manual", "", False)

async def test_put_slot_angle_and_requirement_touch_only_the_row(client, override_auth, test_db):
    row = client.put(f"/offers/{offer_a}/interview-prep/slots/{slot_id}",
                     json={"angle": "Coordination", "requirement": "Piloter 5 personnes"}).json()["story_slots"][0]
    assert (row["angle"], row["angle_edited"], row["requirement"]) == ("Coordination", True, "Piloter 5 personnes")
    assert (await test_db.star_stories.find_one({"id": sid}))["updated_at"] == story_before["updated_at"]

async def test_delete_slot_keeps_bank_story(client, override_auth, test_db):
    assert client.delete(f"/offers/{offer_a}/interview-prep/slots/{slot_id}").json()["story_slots"] == []
    assert await test_db.star_stories.count_documents({"id": sid}) == 1
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && .venv/bin/python -m pytest tests/test_star_stories_api.py -v`
Expected : FAIL (404 sur `/star-stories`).

- [ ] **Step 3 : implémenter** les fonctions et routes listées dans Interfaces. Les mises à jour de lignes par `PUT`/`DELETE` lisent le kit, modifient la liste `story_slots` en Python puis la réécrivent par `$set`. La suppression d'histoire passe par `update_many` avec `array_filters` sur `story_slots.$[s]` et `anticipated_questions.$[q]`.

- [ ] **Step 4 : vérifier le succès**

Run : `cd backend && .venv/bin/python -m pytest tests/test_star_stories_api.py tests/test_star_bank.py tests/test_interview_prep_api.py -v`
Expected : PASS.

- [ ] **Step 5 : commit (si autorisé)**

```bash
git add backend/app/routers/star_stories.py backend/app/routers/__init__.py backend/main.py backend/app/services/star_bank.py backend/app/routers/interview_prep.py backend/tests/test_star_stories_api.py
git commit -m "feat(star-bank): bank edit/delete API and kit slot endpoints"
```

---

### Task 4 : Doublons — détection, fusion, « histoires différentes », restauration

**Files :**
- Modify : `backend/app/services/star_bank_rules.py`, `backend/app/services/star_bank.py`, `backend/app/routers/star_stories.py`, `backend/migrate_star_stories_to_bank.py` (`possible_duplicates`)
- Test : `backend/tests/test_star_bank_rules.py`, `backend/tests/test_star_stories_api.py`

**Interfaces :**
- Produces (`star_bank_rules.py`) : `find_duplicate_pairs(stories: List[BankStory]) -> List[Tuple[str, str]]` (paires `(a.id, b.id)` dans l'ordre d'entrée, `a` avant `b`).
- Produces (`star_bank.py`) :
  - `class StoryNotFoundError(LookupError)`
  - `async merge_stories(db, user_id: str, keep_id: str, discard_id: str) -> BankStory`
  - `async mark_not_duplicate(db, user_id: str, story_id: str, other_id: str) -> BankStory`
  - `async restore_discarded_version(db, user_id: str, story_id: str, version_id: str) -> BankStory`
  - `hydrate_prep` remplit `duplicates: [{"story_id": <id dans ce kit>, "other_story": <BankStory + used_in_kits>}]` pour chaque paire dont au moins une histoire est dans les lignes du kit (une seule entrée si les deux y sont).
- Produces (routes) : `POST /star-stories/{keep_id}/merge {discard_id}`, `POST /star-stories/{story_id}/not-duplicate {other_id}`, `POST /star-stories/{story_id}/restore {version_id}` → `BankStory`. `keep_id == discard_id` → 400 ; histoire ou version absente ou d'un autre utilisateur → 404.

Heuristique (choix du plan, la spec la laisse au constructeur et demande de pencher vers « proposer plus ») :

```python
# Même groupe : les deux sans expérience, ou normalize_company égal.
# Et au moins un des deux :
#   - Jaccard des mots du titre >= 0.5 (préfixe "[Thème] " retiré, casefold, accents retirés,
#     découpage sur les non-alphanumériques, mots de 3 caractères ou plus) ;
#   - un nombre d'au moins 2 chiffres commun aux deux `result` (re.findall(r"\d{2,}")).
# Paire exclue si l'un des ids figure dans le not_duplicate_of de l'autre.
```

- [ ] **Step 1 : écrire les tests qui échouent**

`tests/test_star_bank_rules.py` (helper `_story(id, title, result, company=None, not_dup=())`) :

```python
def test_close_titles_same_company_is_pair():
    a = _story("a", "[Scalabilité] Migration du pipeline de facturation", "−45 %", "Alpha Corp")
    b = _story("b", "Migration pipeline facturation", "−60 %", "ALPHA CORP")
    assert find_duplicate_pairs([a, b]) == [("a", "b")]

def test_shared_result_number_is_pair():
    a = _story("a", "Refonte du batch nocturne", "−60 % de temps")
    b = _story("b", "Accélérer la facturation", "temps réduit de 60 %")
    assert find_duplicate_pairs([a, b]) == [("a", "b")]

def test_different_companies_never_pair():
    assert find_duplicate_pairs([_story("a", "Migration pipeline", "x", "Alpha"), _story("b", "Migration pipeline", "x", "Beta")]) == []

def test_unrelated_stories_not_pair():
    assert find_duplicate_pairs([_story("a", "Incident de production du lundi", "45 min"), _story("b", "Migration du pipeline", "−6 %")]) == []

def test_not_duplicate_of_excludes_pair():
    a = _story("a", "Migration pipeline facturation", "x", not_dup=["b"])
    assert find_duplicate_pairs([a, _story("b", "Migration pipeline facturation", "y")]) == []
```

`tests/test_star_stories_api.py` :

```python
async def test_merge_moves_discarded_facts_and_redirects(client, override_auth, test_db):
    # A dans le kit 1, B dans le kit 2 ; une question du kit 2 liée à B
    kept = client.post(f"/star-stories/{a}/merge", json={"discard_id": b}).json()
    assert kept["discarded_versions"][0]["facts"]["result"] == "−45 %"
    assert kept["discarded_versions"][0]["source_story_id"] == b
    assert await test_db.star_stories.count_documents({"id": b}) == 0
    kit2 = client.get(f"/offers/{offer2}/interview-prep").json()
    assert kit2["story_slots"][0]["story_id"] == a
    assert kit2["anticipated_questions"][0]["mapped_story_id"] == a

async def test_merge_same_id_is_400(client, override_auth, test_db):
    assert client.post(f"/star-stories/{a}/merge", json={"discard_id": a}).status_code == 400

async def test_merge_twice_is_404_and_keeps_data(client, override_auth, test_db):
    client.post(f"/star-stories/{a}/merge", json={"discard_id": b})
    assert client.post(f"/star-stories/{a}/merge", json={"discard_id": b}).status_code == 404
    assert len((await test_db.star_stories.find_one({"id": a}))["discarded_versions"]) == 1

async def test_merge_kit_holding_both_points_both_rows_to_kept(client, override_auth, test_db):
    client.post(f"/star-stories/{a}/merge", json={"discard_id": b})
    assert [r["story_id"] for r in client.get(f"/offers/{offer1}/interview-prep").json()["story_slots"]] == [a, a]

async def test_not_duplicate_hides_pair(client, override_auth, test_db):
    assert client.get(f"/offers/{offer1}/interview-prep").json()["duplicates"] != []
    client.post(f"/star-stories/{a}/not-duplicate", json={"other_id": b})
    assert client.get(f"/offers/{offer1}/interview-prep").json()["duplicates"] == []

async def test_restore_discarded_version_swaps_facts(client, override_auth, test_db):
    kept = client.post(f"/star-stories/{a}/merge", json={"discard_id": b}).json()
    vid = kept["discarded_versions"][0]["id"]
    restored = client.post(f"/star-stories/{a}/restore", json={"version_id": vid}).json()
    assert restored["result"] == "−45 %"
    assert [v["facts"]["result"] for v in restored["discarded_versions"]] == ["−60 %"]
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && .venv/bin/python -m pytest tests/test_star_bank_rules.py tests/test_star_stories_api.py -v`
Expected : FAIL (`ImportError: find_duplicate_pairs`, 404/405 sur `/merge`).

- [ ] **Step 3 : implémenter.** Les faits d'une histoire s'extraient par `StoryFacts.model_validate(story.model_dump(include=set(StoryFacts.model_fields)))`. Ordre de `merge_stories`, pour qu'une interruption ne perde rien : (1) ajouter à `A.discarded_versions` les faits de B puis les `discarded_versions` de B ; (2) rediriger lignes et questions de tous les kits de l'utilisateur avec `array_filters` ; (3) supprimer B. Brancher `possible_duplicates` du script sur `len(find_duplicate_pairs(bank))`.

- [ ] **Step 4 : vérifier le succès**

Run : `cd backend && .venv/bin/python -m pytest tests/test_star_bank_rules.py tests/test_star_stories_api.py tests/test_migrate_star_stories_to_bank.py -v`
Expected : PASS.

- [ ] **Step 5 : commit (si autorisé)**

```bash
git add backend/app/services/star_bank_rules.py backend/app/services/star_bank.py backend/app/routers/star_stories.py backend/migrate_star_stories_to_bank.py backend/tests/test_star_bank_rules.py backend/tests/test_star_stories_api.py
git commit -m "feat(star-bank): duplicate detection, merge, not-duplicate and restore"
```

---

### Task 5 : Sélection des exigences et appel d'association

**Files :**
- Modify : `backend/app/services/interview_prep_service.py`
- Create : `backend/app/llm/prompts/interview/story_match.md`
- Test : `backend/tests/test_interview_prep_service.py`

**Interfaces :**
- Consumes : `BankStory`, `StorySlot` (Task 1), `_mask_invented_numbers` (l.410), `_offer_role_and_company` (l.131), `_clean_json_output` (l.44), `build_completion_kwargs`, `record_api_usage`.
- Produces :
  - `WEIGHT_RANK = {"critical": 0, "high": 1, "meaningful": 2}`, `MAX_STORY_SLOTS = 5`, `BANK_SUMMARY_LIMIT = 60`
  - `class RequirementPick(BaseModel)` : `requirement: str`, `weight: str = "high"`, `covered: Optional[bool] = None` (`True` : `matched_requirements`, `False` : `missing_requirements`, `None` : sans évaluation)
  - `select_requirements(evaluation: Optional[Dict[str, Any]], limit: int = MAX_STORY_SLOTS) -> List[RequirementPick]` : `bloc_b.matched_requirements` puis `bloc_b.missing_requirements`, tri stable par `WEIGHT_RANK` (poids inconnu en dernier), coupé à `limit` ; `[]` sans évaluation ou sans exigence.
  - `format_requirements_block(picks: Optional[List[RequirementPick]]) -> str` : lignes `"{i}. {requirement}"` numérotées à partir de 1 ; `None` → consigne d'extraire au plus 5 exigences clés de la description.
  - `format_bank_summary(bank: List[BankStory], limit: int = BANK_SUMMARY_LIMIT) -> str` : une ligne par histoire, `"[{id}] {title} | {experience_label ou 'sans expérience'} | {result[:160]} | {', '.join(key_tags)}"`.
  - `async match_bank_stories(db, user_id: str, offer: Dict[str, Any], picks: Optional[List[RequirementPick]], bank: List[BankStory]) -> List[Tuple[RequirementPick, Optional[StorySlot]]]`

Contrat de sortie du prompt `story_match.md` (variables : `{target_company}`, `{target_role}`, `{offer_description}`, `{requirements_block}`, `{bank_summary}` ; accolades JSON doublées) :

```json
{"matches": [{"requirement_index": 1, "requirement": "…", "story_id": "<id de la liste> ou null", "fit": "strong|partial|transferable", "angle": "ce qu'il faut mettre en avant pour cette offre, sans nouveau chiffre"}]}
```

Règles de `match_bank_stories` : `sub_action="story_match"`. Avec `picks`, chaque élément est rattaché par `requirement_index` ; sans `picks`, les exigences viennent des `requirement` renvoyés (5 au plus, `covered=None`). `story_id` absent de `bank` ou `null` → slot `None`. `fit` : `covered is False` → `"transferable"` ; sinon la valeur de l'IA parmi `strong`/`partial` (`transferable` accepté si `covered is None`), `"partial"` par défaut. `angle` masqué par `_mask_invented_numbers` contre les faits de l'histoire choisie. Une exigence sans élément renvoyé → slot `None`.

- [ ] **Step 1 : écrire les tests qui échouent** (réponse de l'IA construite avec `_practice_llm_response(payload)`, `tests/test_interview_prep_service.py:352`)

```python
EVAL = {"bloc_b": {
    "matched_requirements": [{"requirement": "SQL", "weight": "meaningful"}, {"requirement": "Piloter une équipe", "weight": "critical"}],
    "missing_requirements": [{"requirement": "GCP", "weight": "critical"}, {"requirement": "Airflow", "weight": "high"}]}}

def test_select_requirements_orders_by_weight_then_bloc_b_order():
    assert [(p.requirement, p.covered) for p in select_requirements(EVAL)] == [
        ("Piloter une équipe", True), ("GCP", False), ("Airflow", False), ("SQL", True)]

def test_select_requirements_caps_at_limit():
    assert len(select_requirements(EVAL, limit=2)) == 2

def test_select_requirements_without_evaluation_is_empty():
    assert select_requirements(None) == [] and select_requirements({"bloc_b": {}}) == []

async def test_match_maps_by_index_and_masks_invented_numbers():
    # banque : histoire s1 dont le résultat est "−60 % de temps de traitement"
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "Gain de 75 % et −60 %"}]}
    [(pick, slot)] = await match_bank_stories(None, "u", OFFER, [RequirementPick(requirement="Fiabiliser", covered=True)], [s1])
    assert (slot.story_id, slot.fit, slot.requirement) == ("s1", "strong", "Fiabiliser")
    assert "75" not in slot.angle and "[à chiffrer]" in slot.angle and "60" in slot.angle

async def test_match_ignores_story_id_outside_bank():
    payload = {"matches": [{"requirement_index": 1, "story_id": "story-of-someone-else", "fit": "strong", "angle": "x"}]}
    assert (await match_bank_stories(None, "u", OFFER, [pick], [s1]))[0][1] is None

async def test_match_uncovered_requirement_is_transferable():
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "Pont AWS vers GCP"}]}
    assert (await match_bank_stories(None, "u", OFFER, [RequirementPick(requirement="GCP", covered=False)], [s1]))[0][1].fit == "transferable"

async def test_match_records_story_match_usage():
    # record_api_usage patché : metadata["sub_action"] == "story_match"
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && .venv/bin/python -m pytest tests/test_interview_prep_service.py -v -k "select_requirements or match_"`
Expected : FAIL (`ImportError: select_requirements`).

- [ ] **Step 3 : implémenter** les constantes, `RequirementPick`, les trois fonctions de formatage et `match_bank_stories` ; écrire `story_match.md` (règles : ne jamais citer un chiffre absent des faits, `null` si aucune histoire ne répond, une même histoire peut servir deux exigences).

- [ ] **Step 4 : vérifier le succès**

Run : `cd backend && .venv/bin/python -m pytest tests/test_interview_prep_service.py -v`
Expected : PASS.

- [ ] **Step 5 : commit (si autorisé)**

```bash
git add backend/app/services/interview_prep_service.py backend/app/llm/prompts/interview/story_match.md backend/tests/test_interview_prep_service.py
git commit -m "feat(star-bank): requirement selection and bank matching call"
```

---

### Task 6 : Écriture des manques et assemblage des lignes

**Files :**
- Modify : `backend/app/services/interview_prep_service.py` (supprime `generate_star_stories` l.138)
- Modify : `backend/app/llm/prompts/interview/star_stories.md` (réécrit)
- Test : `backend/tests/test_interview_prep_service.py`

**Interfaces :**
- Consumes : Task 5 (`RequirementPick`, `select_requirements`, `format_requirements_block`, `match_bank_stories`), `match_profile_experience` (Task 1), `format_candidate_profile_context`, `format_evaluation_context`.
- Produces :
  - `async write_stories_for_requirements(db, user_id: str, profile: Dict[str, Any], offer: Dict[str, Any], evaluation: Optional[Dict[str, Any]], picks: Optional[List[RequirementPick]]) -> List[Tuple[StorySlot, Optional[BankStory]]]` : même longueur et même ordre que `picks` ; sans `picks`, les exigences extraites (5 au plus).
  - `carry_over_edited_angles(previous: List[StorySlot], new: List[StorySlot]) -> List[StorySlot]`
  - `async build_story_slots(db, user_id: str, profile: Dict[str, Any], offer: Dict[str, Any], evaluation: Optional[Dict[str, Any]], bank: List[BankStory], previous_slots: List[StorySlot]) -> Tuple[List[StorySlot], List[BankStory]]` : les lignes, et les nouvelles histoires à insérer (le service n'écrit rien en base).

Contrat de sortie de `star_stories.md` (garde `{candidate_profile}`, `{target_company}`, `{target_role}`, `{offer_description}`, `{evaluation_context}` ; ajoute `{requirements_block}` ; accolades JSON doublées ; consigne : une histoire vraie tirée du profil, ou une histoire transférable sur une expérience voisine pour une exigence non couverte, sinon `null`) :

```json
{"items": [{"requirement_index": 1, "requirement": "…", "fit": "strong|partial", "angle": "…",
            "experience": {"company": "…", "role": "…"} ou null,
            "story": {"title": "…", "theme": "…", "situation": "…", "task": "…", "action": "…", "result": "…", "reflection": "…", "key_tags": ["…"]} ou null}]}
```

Règles de `write_stories_for_requirements` (`sub_action="stories"`) :
- `story` nul ou élément absent : `fit="gap"` si `covered is True`, sinon `"no_experience"` ; aucune histoire créée.
- `story` présent : `covered is False` → `"transferable"` ; sinon la valeur de l'IA parmi `strong`/`partial`, `"strong"` par défaut. Nouvelle `BankStory` avec `origin={"kind": "generated", "offer_id": str(offer["_id"])}`, et la ligne pointe vers son id.
- `experience` : conservée seulement si `match_profile_experience` la retrouve dans `profile["experiences"]` ; l'instantané reprend alors `company`/`role`/`start` du profil. Sinon `None`.
- `angle` masqué contre les faits de la nouvelle histoire.

`build_story_slots` : `picks = select_requirements(evaluation) or None`. Banque vide → pas d'appel d'association. Exigences sans histoire après association → un seul appel d'écriture ; aucune → pas d'appel d'écriture. Banque vide et sans évaluation → écriture en mode extraction (`picks=None`). Les lignes gardent l'ordre des exigences. `carry_over_edited_angles` s'applique en dernier : une nouvelle ligne avec la même exigence (comparaison `casefold`) et le même `story_id` non nul reprend `angle` et `angle_edited=True` de l'ancienne.

- [ ] **Step 1 : écrire les tests qui échouent**

Remplacer `test_generate_star_stories_mocked` et `test_star_stories_prompt_uses_job_offer_poste_and_entreprise` par leurs équivalents sur `write_stories_for_requirements` (le prompt contient toujours le poste et l'entreprise de l'offre) ; dans `test_generators_omit_temperature_for_models_that_reject_it` (l.318), appeler `write_stories_for_requirements` à la place de `generate_star_stories`, sans changer le nombre d'appels attendus.

```python
PROFILE = {"experiences": [{"company": "Alpha Corp", "role": "Data Engineer", "start": "2022-01"}]}

async def test_writer_uncovered_without_neighbor_gives_no_experience():
    payload = {"items": [{"requirement_index": 1, "story": None, "experience": None, "fit": "strong", "angle": ""}]}
    [(slot, story)] = await write_stories_for_requirements(None, "u", PROFILE, OFFER, None, [RequirementPick(requirement="GCP", covered=False)])
    assert (slot.fit, slot.story_id, story) == ("no_experience", None, None)

async def test_writer_uncovered_with_neighbor_gives_transferable():
    # story présent, experience Alpha Corp
    assert slot.fit == "transferable" and story.origin.kind == "generated" and slot.story_id == story.id

async def test_writer_fewer_items_than_requirements():
    # 2 picks (covered True, covered False), l'IA ne renvoie que l'élément 1 avec une histoire
    assert [s.fit for s, _ in result] == ["strong", "no_experience"]

async def test_writer_drops_experience_not_in_profile():
    # experience {"company": "Inconnue SA"} → story.experience is None
    # experience {"company": "alpha corp"} → story.experience == StoryExperience(company="Alpha Corp", role="Data Engineer", start="2022-01")

async def test_writer_masks_numbers_absent_from_new_story():
    # angle "−90 %" alors que result dit "−60 %" → "[à chiffrer]" dans l'angle

def test_carry_over_keeps_edited_angle_for_same_pair():
    old = StorySlot(requirement="Piloter une équipe", story_id="s1", angle="Mon angle", angle_edited=True)
    [kept] = carry_over_edited_angles([old], [StorySlot(requirement="piloter une équipe", story_id="s1", angle="IA")])
    assert (kept.angle, kept.angle_edited) == ("Mon angle", True)

def test_carry_over_drops_angle_when_story_changes():
    [new] = carry_over_edited_angles([old], [StorySlot(requirement="Piloter une équipe", story_id="s2", angle="IA")])
    assert (new.angle, new.angle_edited) == ("IA", False)

async def test_build_with_empty_bank_skips_match_call():
    # acompletion patché ; un seul appel, record_api_usage avec sub_action "stories"

async def test_build_with_no_gap_skips_writer_call():
    # banque qui couvre toutes les exigences : un seul appel, sub_action "story_match" ; new_stories == []
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && .venv/bin/python -m pytest tests/test_interview_prep_service.py -v`
Expected : FAIL (`ImportError: write_stories_for_requirements`).

- [ ] **Step 3 : implémenter** les trois fonctions, réécrire `star_stories.md`, supprimer `generate_star_stories`. Les appelants du routeur cassent jusqu'à la Task 7 : le test d'API se lance à la tâche suivante.

- [ ] **Step 4 : vérifier le succès et l'absence d'orphelin**

Run : `cd backend && .venv/bin/python -m pytest tests/test_interview_prep_service.py -v`
Expected : PASS.
Run : `ast-grep -p 'generate_star_stories' -l python backend/app backend/tests`
Expected : seulement les appels du routeur, que la Task 7 remplace.

- [ ] **Step 5 : commit (si autorisé, ou regroupé avec la Task 7 pour ne pas laisser un commit au routeur cassé)**

```bash
git add backend/app/services/interview_prep_service.py backend/app/llm/prompts/interview/star_stories.md backend/tests/test_interview_prep_service.py
git commit -m "feat(star-bank): gap-only story writer and slot assembly"
```

---

### Task 7 : Routes de génération branchées sur la banque

**Files :**
- Modify : `backend/app/routers/interview_prep.py` (`generate_stories_endpoint` l.114, `generate_all_endpoint` l.315, nouvelles routes de ligne)
- Test : `backend/tests/test_interview_prep_api.py`

**Interfaces :**
- Consumes : `build_story_slots`, `write_stories_for_requirements`, `RequirementPick` (Tasks 5-6) ; `load_bank`, `hydrate_prep`, `ensure_prep_migrated` (via `_get_prep_or_empty`) ; `guess_experience` (Task 1).
- Produces (routes, toutes renvoient le kit hydraté) :
  - `POST /offers/{offer_id}/interview-prep/generate/stories` et la partie histoires de `POST .../generate/all`
  - `POST /offers/{offer_id}/interview-prep/slots/{slot_id}/write` : seulement si `fit == "gap"`, sinon 409 ; quota ; annulation ; `write_stories_for_requirements` avec `[RequirementPick(requirement=slot.requirement, covered=True)]`.
  - `POST /offers/{offer_id}/interview-prep/slots/{slot_id}/manual-story`, corps `StoryFacts` : seulement si la ligne n'a pas d'histoire (sinon 409), sans appel à l'IA ; `origin.kind="manual"`, `experience=guess_experience(situation, profil)`, `fit="manual"`, `angle=""`.

Enchaînement des deux routes de génération : (1) `_get_prep_or_empty` d'abord, ce qui migre les histoires héritées avant tout remplacement ; (2) `load_bank` ; (3) `build_story_slots` avec les anciennes lignes ; (4) `_generation_cancelled` → 499 sans rien écrire ; (5) `insert_many` des nouvelles histoires ; (6) les questions dont `mapped_story_id` n'est plus dans les `story_id` des lignes perdent leur lien ; (7) `$set story_slots` (jamais `stories`), `$setOnInsert` sans `stories`.

- [ ] **Step 1 : écrire les tests qui échouent**

Réécrire `test_generate_stories_endpoint` et `test_generate_stories_clears_stale_story_links` en patchant `app.routers.interview_prep.build_story_slots` (retour `(slots, new_stories)`). Ajouter :

```python
async def test_generate_stories_on_unmigrated_kit_keeps_legacy_stories_in_bank(client, override_auth, test_db):
    # kit hérité SANS story_slots, 2 histoires ; build_story_slots patché renvoie une seule ligne neuve
    client.post(f"/offers/{oid}/interview-prep/generate/stories")
    assert await test_db.star_stories.count_documents({"id": {"$in": [s1["id"], s2["id"]]}}) == 2
    assert (await test_db.interview_preps.find_one({"_id": prep_id}))["stories"] == legacy_stories

async def test_regenerate_never_deletes_bank_story(client, override_auth, test_db):
    # kit migré avec une ligne vers s1 ; build_story_slots renvoie une ligne vers une nouvelle histoire n1
    assert await test_db.star_stories.count_documents({"id": s1["id"]}) == 1
    assert await test_db.star_stories.count_documents({"id": n1.id}) == 1

async def test_generate_cancelled_writes_nothing(client, override_auth, test_db):
    # _generation_cancelled patché à True
    assert res.status_code == 499
    assert await test_db.star_stories.count_documents({"id": n1.id}) == 0
    assert stored_prep["story_slots"] == before["story_slots"]

async def test_generate_all_sets_story_slots_not_stories(client, override_auth, test_db):
    # kit migré, stories hérité ["X"] ; tous les générateurs patchés
    assert stored["stories"] == before["stories"] and stored["story_slots"][0]["story_id"] == n1.id

async def test_write_slot_only_on_gap(client, override_auth, test_db):
    assert client.post(f"/offers/{oid}/interview-prep/slots/{strong_slot}/write").status_code == 409

async def test_write_slot_fills_gap_and_adds_story_to_bank(client, override_auth, test_db):
    # write_stories_for_requirements patché renvoie (slot strong vers n1, n1)
    row = next(r for r in res.json()["story_slots"] if r["id"] == gap_slot)
    assert (row["story_id"], row["fit"]) == (n1.id, "strong")
    assert (await test_db.star_stories.find_one({"id": n1.id}))["origin"]["kind"] == "generated"

async def test_manual_story_on_no_experience_row(client, override_auth, test_db):
    res = client.post(f"/offers/{oid}/interview-prep/slots/{noexp_slot}/manual-story", json=FACTS)
    row = next(r for r in res.json()["story_slots"] if r["id"] == noexp_slot)
    assert row["fit"] == "manual" and row["story"]["origin"]["kind"] == "manual"
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && .venv/bin/python -m pytest tests/test_interview_prep_api.py -v`
Expected : FAIL (`ImportError: generate_star_stories` au chargement du routeur, puis assertions).

- [ ] **Step 3 : implémenter** l'enchaînement ci-dessus et les deux routes de ligne.

- [ ] **Step 4 : vérifier le succès et l'absence d'orphelin**

Run : `cd backend && .venv/bin/python -m pytest tests/test_interview_prep_api.py tests/test_interview_prep_service.py tests/test_star_stories_api.py -v`
Expected : PASS.
Run : `ast-grep -p 'generate_star_stories' -l python backend`
Expected : aucun résultat.

- [ ] **Step 5 : commit (si autorisé)**

```bash
git add backend/app/routers/interview_prep.py backend/tests/test_interview_prep_api.py
git commit -m "feat(star-bank): bank-first story generation and per-row write/manual endpoints"
```

---

### Task 8 : Lecteurs existants (entraînement, export, questions, PUT)

**Files :**
- Modify : `backend/app/routers/interview_prep.py` (questions l.216, practice l.386, PUT l.428 et `UpdateInterviewPrepRequest` l.37, export l.471)
- Modify : `backend/app/services/interview_prep_service.py` (`generate_anticipated_questions` l.277, `evaluate_practice_answer` l.419, `export_interview_prep_markdown` l.508)
- Test : `backend/tests/test_interview_prep_api.py`, `backend/tests/test_interview_prep_service.py`

**Interfaces :**
- Consumes : `get_bank_story`, `slots_with_stories` (Task 1).
- Produces :
  - `generate_anticipated_questions(db, user_id, profile, offer, evaluation=None, stories: Optional[List[BankStory]] = None)` (seul le type de `stories` change) ; la route questions lui passe les histoires des lignes du kit (`slots_with_stories`, sans `None`, sans doublon).
  - `evaluate_practice_answer(db, user_id, offer, evaluation, question, answer, story: Optional[BankStory] = None)` (seul le type de `story` change) ; la route lit l'histoire par `get_bank_story(db, user_id, question["mapped_story_id"])`.
  - `export_interview_prep_markdown(prep: InterviewPrep, offer: Dict[str, Any], slots: List[Tuple[StorySlot, Optional[BankStory]]]) -> str` : par ligne, l'exigence, l'adéquation (libellé français), l'angle, puis les faits ; ligne sans histoire → « Aucune histoire pour cette exigence. ». La route utilise `_get_prep_or_empty`.
  - `UpdateInterviewPrepRequest` perd `stories` ; l'import `StarRStory` du routeur disparaît s'il n'a plus d'usage.

- [ ] **Step 1 : écrire les tests qui échouent**

```python
async def test_practice_reads_up_to_date_facts_from_bank(client, override_auth, test_db):
    # kit migré, question liée à s1 ; PATCH /star-stories/s1 {"result": "−45 %"} ; evaluate_practice_answer patché (AsyncMock)
    assert mock_eval.await_args.kwargs["story"].result == "−45 %"

async def test_questions_receive_slot_stories(client, override_auth, test_db):
    # generate_anticipated_questions patché
    assert [s.id for s in mock_q.await_args.kwargs["stories"]] == [s1["id"]]

def test_export_markdown_uses_slots_and_bank_facts():
    md = export_interview_prep_markdown(prep, OFFER, [(StorySlot(requirement="Piloter", story_id="s1", fit="strong", angle="Coordination"), s1),
                                                     (StorySlot(requirement="GCP", fit="no_experience"), None)])
    assert "Piloter" in md and "Coordination" in md and "−60 %" in md
    assert "pas d'expérience dans ton profil" in md and "Aucune histoire pour cette exigence." in md
```

Réécrire `test_update_and_export_interview_prep` (l.132) : le PUT ne porte plus `stories` ; l'export contient l'exigence et le résultat d'une ligne du kit. Adapter `test_export_interview_prep_markdown` (l.198) à la nouvelle signature.

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && .venv/bin/python -m pytest tests/test_interview_prep_api.py tests/test_interview_prep_service.py -v`
Expected : FAIL.

- [ ] **Step 3 : implémenter.** Aucun lecteur ne lit plus `prep.stories`.

- [ ] **Step 4 : vérifier le succès, l'absence de lecture héritée et la suite complète**

Run : `ast-grep -p '$X.get("stories")' -l python backend/app` puis `ast-grep -p 'prep.stories' -l python backend/app`
Expected : seulement `ensure_prep_migrated` (`star_bank.py`).
Run : `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected : aucune régression par rapport à la suite d'avant la Task 1 (noter l'état de base avant de commencer).

- [ ] **Step 5 : commit (si autorisé)**

```bash
git add backend/app/routers/interview_prep.py backend/app/services/interview_prep_service.py backend/tests/test_interview_prep_api.py backend/tests/test_interview_prep_service.py
git commit -m "feat(star-bank): practice, questions and export read facts from the bank"
```

---

### Task 9 : Frontend — types, API, tableau du kit

**Files :**
- Modify : `frontend/src/types/interview.ts`, `frontend/src/lib/api.ts` (`interviewPrepApi` l.898, objet agrégé l.1024)
- Create : `frontend/src/components/interview/StorySlotsTable.tsx`
- Modify : `frontend/src/components/interview/StarStoryCard.tsx`, `frontend/src/components/interview/InterviewPrepTab.tsx` (l.62, l.69-92, l.139-144, l.330-367)

**Interfaces :**
- Consumes : routes des Tasks 1, 3, 7.
- Produces (types) : `StoryFit`, `StoryExperience`, `StoryFacts`, `DiscardedStoryVersion`, `BankStory` (avec `used_in_kits?: number`), `StorySlot` (avec `story: BankStory | null`), `StoryDuplicate {story_id, other_story}`, `BankGroup {label, experience, stories}`, `BankExperience {company, role, start, label}` ; `InterviewPrep` gagne `story_slots`, `duplicates`, `bank_count` et perd `stories` ; `UpdateInterviewPrepPayload` perd `stories`. `StarRStory` disparaît s'il n'a plus d'usage.
- Produces (API) : `starBankApi.list()`, `updateFacts(id, changes)`, `usage(id)`, `remove(id)`, `merge(keepId, discardId)`, `markDifferent(id, otherId)`, `restore(id, versionId)` ; `interviewPrepApi.updateSlot(offerId, slotId, data)`, `deleteSlot(offerId, slotId)`, `writeSlot(offerId, slotId, signal?)`, `createManualStory(offerId, slotId, facts)`. Exposer `starBank: starBankApi` dans l'objet agrégé.
- Produces (composants) : `StorySlotsTable({ prep, offerId, onPrepUpdated, onOpenBank })` ; `StarStoryCard({ story, usedInKits, onSaveFacts, onRestoreVersion?, onDelete? })`, utilisée dans le détail de la ligne.

Comportement attendu :
- Tableau à trois colonnes « Ce que l'offre demande / Ton histoire / Adéquation », pastille de couleur par adéquation (couleurs de la maquette : forte vert, partielle et transférable ambre, manque et pas d'expérience rose, choisie indigo).
- Ligne `gap` : boutons « Écrire avec l'IA » (`writeSlot`, annulable comme les autres générations) et « L'écrire moi-même ». Ligne `no_experience` : « L'écrire moi-même » seulement. « L'écrire moi-même » ouvre un formulaire vide des faits.
- Ligne avec histoire : un clic l'affiche sous le tableau. On y voit l'exigence modifiable, l'« Angle pour cette offre » modifiable (`updateSlot`), et les faits (`StarStoryCard`). Le bouton « Modifier » des faits porte « corrige aussi dans les N autres kits qui utilisent cette histoire » avec N = `used_in_kits − 1`, au singulier pour 1 (« dans l'autre kit qui utilise cette histoire »), et rien pour 0.
- Une action « Retirer la ligne » appelle `deleteSlot`.
- Bouton « Toute ma banque (N) » avec N = `prep.bank_count` ; il appelle `onOpenBank` (le panneau arrive à la Task 10).
- `InterviewPrepTab` : `storiesCount = prep?.story_slots?.length ?? 0`. Avant de régénérer « stories » ou « all », si des lignes ont `angle_edited`, le message de confirmation ajoute : « Les angles rédigés à la main pour : {exigences} seront perdus si la même histoire n'est pas reprise. »

- [ ] **Step 1 : implémenter types, API et composants.**
- [ ] **Step 2 : vérifier la compilation**

Run : `cd frontend && npm run lint && npm run build`
Expected : exit 0, aucune erreur TypeScript ni ESLint.

- [ ] **Step 3 : vérification manuelle dans le navigateur** (backend et frontend locaux, `http://localhost:3875`, sur un kit hérité de la base locale)
  - Le kit hérité affiche ses lignes (aucune histoire perdue) avec « forte ».
  - Modifier le résultat d'une histoire, ouvrir un autre kit qui l'utilise : le résultat y est corrigé.
  - Rédiger un angle, puis régénérer : la confirmation cite l'exigence.
  - Une ligne « pas d'expérience dans ton profil » ne propose pas « Écrire avec l'IA ».

- [ ] **Step 4 : commit (si autorisé)**

```bash
git add frontend/src/types/interview.ts frontend/src/lib/api.ts frontend/src/components/interview/StorySlotsTable.tsx frontend/src/components/interview/StarStoryCard.tsx frontend/src/components/interview/InterviewPrepTab.tsx
git commit -m "feat(star-bank): requirement/story/fit table in the interview kit"
```

---

### Task 10 : Frontend — panneau « Toute ma banque »

**Files :**
- Create : `frontend/src/components/interview/StoryBankPanel.tsx`
- Modify : `frontend/src/components/interview/InterviewPrepTab.tsx` (ouverture du panneau à côté du kit)

**Interfaces :**
- Consumes : `starBankApi.list`, `starBankApi.updateFacts` (rattachement), `interviewPrepApi.updateSlot` (Task 9).
- Produces : `StoryBankPanel({ offerId, prep, open, onClose, onPrepUpdated })`.

Comportement attendu (maquette `banque-dans-le-kit`) :
- Panneau latéral à côté du kit sur grand écran, et en dessous sur mobile.
- Champ « Rechercher… » filtrant côté client sur le titre, le résultat, les tags et la situation.
- Groupes de `GET /star-stories` dans l'ordre reçu ; chaque histoire montre son titre, « Résultat : {result} » et « utilisée dans N kits ».
- Une histoire déjà dans les lignes du kit est marquée « ✓ dans ce kit ». Les autres proposent « Utiliser pour… », qui liste les exigences du tableau ; le choix appelle `updateSlot(offerId, slotId, { story_id })`.
- Dans « Sans expérience rattachée », un sélecteur des `experiences` du profil rattache l'histoire (`updateFacts(id, { experience })`).

- [ ] **Step 1 : implémenter.**
- [ ] **Step 2 : vérifier la compilation**

Run : `cd frontend && npm run lint && npm run build`
Expected : exit 0.

- [ ] **Step 3 : vérification manuelle** : le compteur du bouton égale le nombre d'histoires du panneau ; « Utiliser pour… » remplace l'histoire de la ligne choisie et la ligne affiche « choisie » ; rattacher une histoire la déplace dans le groupe de l'expérience.

- [ ] **Step 4 : commit (si autorisé)**

```bash
git add frontend/src/components/interview/StoryBankPanel.tsx frontend/src/components/interview/InterviewPrepTab.tsx
git commit -m "feat(star-bank): story bank side panel with use-for and attach"
```

---

### Task 11 : Frontend — doublons, versions écartées, suppression

**Files :**
- Create : `frontend/src/components/interview/DuplicateResolver.tsx`
- Modify : `frontend/src/components/interview/StorySlotsTable.tsx`, `frontend/src/components/interview/StarStoryCard.tsx`

**Interfaces :**
- Consumes : `prep.duplicates`, `starBankApi.merge`, `markDifferent`, `restore`, `usage`, `remove` (Task 9).
- Produces : `DuplicateResolver({ duplicate, current, onResolved })`.

Comportement attendu :
- Pour chaque entrée de `prep.duplicates`, un bandeau ambre au-dessus du détail : « « {titre} » est racontée avec « {other_story.result} » dans un autre kit et « {story.result} » ici. » et le lien « Choisir la bonne version » (formulation adaptée de la spec, qui citait des chiffres d'exemple).
- La vue côte à côte montre les faits des deux versions. Elle offre trois actions : « Garder celle-ci » (de chaque côté → `merge(keep, discard)`) et « Ce sont deux histoires différentes » (`markDifferent`). Le kit est rechargé ensuite (`interviewPrepApi.get`).
- `StarStoryCard` liste les `discarded_versions` repliées (« Versions écartées (N) »), chacune avec « Restaurer » (`restore`).
- « Supprimer de ma banque » appelle d'abord `usage`. La confirmation énumère les kits (« {entreprise} — {poste} ») et précise que ces lignes passeront en « manque ». `remove` n'est appelé qu'après confirmation.

- [ ] **Step 1 : implémenter.**
- [ ] **Step 2 : vérifier la compilation**

Run : `cd frontend && npm run lint && npm run build`
Expected : exit 0.

- [ ] **Step 3 : vérification manuelle** : deux kits locaux avec des versions différentes de la même expérience. Le bandeau s'affiche dans les deux kits. Garder une version redirige la ligne de l'autre kit et fait apparaître « Versions écartées (1) ». « Restaurer » remet les faits écartés. La suppression liste les kits, puis la ligne passe en « manque ».

- [ ] **Step 4 : commit (si autorisé)**

```bash
git add frontend/src/components/interview/DuplicateResolver.tsx frontend/src/components/interview/StorySlotsTable.tsx frontend/src/components/interview/StarStoryCard.tsx
git commit -m "feat(star-bank): duplicate resolution, discarded versions and guarded delete"
```

---

## Après le plan (hors exécution)

- Remplissage en production : sauvegarde, puis `migrate_star_stories_to_bank.py` en simulation, puis `--apply`. C'est à l'utilisateur de le lancer.
- Coût : comparer dans `api_usage` les tokens par kit (`sub_action` `story_match` et `stories`) à la moyenne d'avant (critère de la spec).
- Retrait de `interview_preps.stories` : projet séparé, après vérification en production.
