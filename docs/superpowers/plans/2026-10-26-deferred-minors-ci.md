# Minors différés du score hybride + CI backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** corriger les 21 minors différés de la revue finale du score hybride (816202e) et remettre au vert la CI backend (tests + lint), puis commit et push sur `main`.

**Architecture:** correctifs locaux, un lot par zone (routeur offres, matcher, geo, embeddings/score, index/purge, scripts, front). Chaque correctif de comportement passe par un test RED puis GREEN. La CI passe en Python 3.12 + uv, comme la prod et `pyproject.toml` (`requires-python >=3.12`).

**Tech Stack:** FastAPI, Motor/Mongo, pytest-asyncio, uv, Airflow 3, Next.js.

**Spec:** rapport de revue finale des 21 minors (`/private/tmp/claude-501/-Users-elielkatche-job-tracker/60a8ccdf-f5f1-4f0c-beea-90e3b5c4f8a6/scratchpad/minors-21.md`) + plan d'origine `docs/superpowers/plans/2026-10-25-score-pertinence-hybride.md`.

## Global Constraints

- Suite backend : `cd backend && OPENAI_API_KEY=invalid GEMINI_API_KEY=invalid MISTRAL_API_KEY=invalid uv run pytest tests -q`. Jamais `pytest` nu (il collecte des scripts réels hors `tests/`). Jamais deux suites en parallèle (Mongo de test partagé sur 27018).
- Aucun appel réel LLM ou embedding : `embed=` injecté dans les tests. Aucune écriture en base de prod.
- **Fichiers interdits** (travail non commité d'un autre chantier dans `.worktrees/ft-removal-dedup-audit`, sinon le `merge --ff-only` échoue) : `.env.example`, `airflow/dags/collect_job_offers.py`, `backend/app/routers/applications.py`, `backend/app/services/company_profiles.py`, `backend/app/services/sources/__init__.py`, `backend/app/services/sources/france_travail.py`, `backend/app/services/sources/geo.py`, `backend/app/tasks/clean_job_offers.py`, `backend/app/tasks/job_offers_collectors.py`, `backend/job_trackers/src/job_trackers/tools/custom_tool.py`, `backend/retroactive_dedup_job_offers.py`, `backend/tests/test_clean_and_verify_alignment.py`, `backend/tests/test_crew_models_and_tools.py`, `backend/tests/test_job_offers_pipeline.py`, `backend/tests/test_normalization_and_dedup.py`, `backend/tests/test_offer_sources.py`, `backend/tests/test_application_offer_link.py`, `backend/app/services/offer_dedup.py`, `docker-compose.yml`, `docker-compose.prod.yml`, `docs/JOB_INGESTION_AND_NORMALIZATION.md`, tout `docs/micro/**`, `frontend/src/app/guide/page.tsx`.
- Ne pas toucher aux chemins STAR (`star_stories`, banque STAR).
- Lint CI : black + `isort --profile black --check` + `flake8 backend/` (config `backend/setup.cfg`) doivent passer en 3.12 sur l'arbre committé.
- Style : commentaires et docstrings en français, densité comparable au code voisin.

## Review Focus

1. Tri `recent` après déplacement du `$lookup` : `failed_conditions` doit toujours être rempli sur la page, et l'ordre ne doit pas changer.
2. `tag_new_offers` qui détache désormais : jamais une offre avec interaction réelle (garde), jamais une offre non évaluée faute de cosinus.
3. Verrou de rematch : une exception dans `rematch_user` ne doit jamais laisser l'utilisateur bloqué dans l'état « en cours ».
4. Purge des orphelins : ne supprime que les documents dont l'offre n'existe plus physiquement ; une offre `is_deleted` garde ses documents.
5. Régénération de `communes_departements.json` : une commune reste résolue comme avant ; seuls les noms de région ou de département priment sur les communes homonymes.

---

### Task 0: CI backend (tests + lint) — M1

**Files:** `.github/workflows/main.yml:25-66`, `.github/workflows/format-lint.yml:17-25`, `backend/app/routers/admin.py:7`.

- [ ] `main.yml` job `backend-test` : `python-version: '3.12'` ; install = `pip install uv` puis `cd backend && uv sync --frozen` ; le heredoc `.env` reçoit en plus `OPENAI_API_KEY=invalid`, `GEMINI_API_KEY=invalid`, `MISTRAL_API_KEY=invalid` ; run = `cd backend && uv run python -m pytest tests/ -v`.
- [ ] `format-lint.yml` : `python-version: '3.12'`.
- [ ] `admin.py:7` : retirer `status` de l'import `fastapi` (F401), seulement s'il n'est pas utilisé.
- [ ] Vérif : simulation lint 3.12 sur l'arbre committé (`git archive HEAD` dans le scratchpad `lintsim`, puis `uvx --python 3.12 black`, `isort --profile black --check`, `flake8 backend/`) → 0 erreur ; YAML parsé par `python -c 'import yaml,sys; yaml.safe_load(open(...))'`.
- Ruling M1 : `Literal[*SECTORS]` reste (valide dès 3.11, prod 3.12). C'est la CI qui s'aligne.

### Task 1: routeur des offres — M2, M3, M4, M21 (API)

**Files:** `backend/app/routers/job_offers.py` (`get_job_offers` ~397-560, `get_job_offer` ~605-643, `get_job_offers_count` ~1038-1130), tests dans le fichier de tests existant de la liste ou du tri par pertinence (pas un fichier interdit).

- [ ] M3 : extraire `_apply_search_filters(match_filter, *, keywords, location, company, contract_type, work_mode, sector, company_size, days_recent, current_user, only_saved, interaction_status) -> dict`, appelé par la liste ET le count. Il couvre tout le bloc, de keywords à days_recent, `restrict_to_profile_offers` compris. Comportement inchangé : la suite existante est le filet.
- [ ] M2 : en `sort="recent"`, `relevance_lookup_stages` se place APRÈS `$skip`/`$limit`. En `sort="relevance"`, il reste avant le `$sort`. Test : en `recent`, page 2 (`skip`) avec `failed_conditions` non vide sur une offre de la page, même ordre qu'avant. Test structurel : en `recent`, l'index du stage `$lookup` dans le pipeline est après `$limit`. Il passe par un spy sur `collection.aggregate` ou par une fonction pure `_build_list_pipeline(...)` si elle est extraite.
- [ ] M4 : `get_job_offer` lit `offer_relevance` (`user_id` = str(current_user.id), `offer_id` = offer_id) et remplit `failed_conditions` (`[]` par défaut). Test RED : un doc `offer_relevance` avec `failed_conditions=["geo"]` donne `failed_conditions == ["geo"]` sur `GET /job-offers/{id}`.
- [ ] M21 (API) :
  - départage par date à score égal en tri `relevance` ;
  - `sector` multi-valeurs (`$in`), deux secteurs donnent l'union ;
  - 422 sur `/job-offers/count/?sector=inconnu` et sur `company_size=inconnu` (liste + count) ;
  - preuve du `$unset` : le pipeline construit se termine par `$unset` de `_relevance`, `_oid_str` et `_score_sort`, assertion sur le pipeline et non sur la réponse ;
  - les fixtures qui seedent la base le font dans le `try`/`finally` qui nettoie.

### Task 2: matcher — M5, M6, M7

**Files:** `backend/app/services/offer_profile_matcher.py`, `backend/scripts/rematch_all_users.py` (renommage du champ), tests du matcher existants.

- [ ] M5/M6 : `RematchSummary` :
  - `kept_by_guard` ne compte que les offres DÉJÀ rattachées que la garde empêche de détacher ;
  - `applied_below_floor` est renommé `kept_below_floor`, et ne liste que les offres déjà rattachées, non filtrées dur et sous FLOOR ;
  - nouvelle liste `kept_hard_filtered`, pour les offres déjà rattachées, filtrées dur, gardées. Elle déclenche un `logger.warning` avec la raison du filtre.

  Une offre gardée mais pas rattachée n'incrémente rien.

  Mettre à jour les usages (`rematch_all_users.py`, tests).

  Tests RED :
  - garde sur une offre non rattachée sous FLOOR : `kept_by_guard == 0` ;
  - garde sur une offre rattachée filtrée dur : elle est dans `kept_hard_filtered` et un warning est émis.
- [ ] M7 : `tag_new_offers` applique la même décision que `rematch_user`. Il détache une offre déjà rattachée qui devient filtrée dur, sans score, ou sous FLOOR, sauf si elle est dans `interacted_offer_ids(user_id, db)`. Une offre non évaluée faute de cosinus n'est jamais détachée. Factoriser la décision dans un helper pur partagé, par exemple `_attachment_action(reason, result, already_attached, guarded) -> Literal["attach","detach","keep","none"]`. Mettre à jour la docstring, qui dit aujourd'hui « ne détache jamais ».

  Tests RED :
  - une offre rattachée qui devient filtrée dur est détachée ;
  - la même offre avec interaction `saved` reste rattachée ;
  - une offre rattachée sans cosinus (panne) reste rattachée.

### Task 3: verrou de rematch — M20

**Files:** `backend/app/routers/cover_letters.py` (`_safe_rematch_user`), test dédié.

- [ ] Coalescence par utilisateur, en mémoire du process : uvicorn tourne en un seul process. Si un rematch tourne déjà pour cet utilisateur, l'appel marque « à relancer » et rend la main. Le rematch en cours relance une seule fois à la fin s'il est marqué. `finally` libère toujours l'état, même si `rematch_user` lève une exception.

  Tests :
  - deux appels concurrents donnent 2 exécutions de `rematch_user`, pas 3 et jamais en parallèle ;
  - une exception au premier tour laisse l'utilisateur libre, et un appel suivant s'exécute.

### Task 4: geo — M9, M10, M11

**Files:** `backend/app/services/offer_scoring/geo.py`, `backend/scripts/build_communes_index.py`, `backend/app/services/offer_scoring/communes_departements.json` (régénéré), tests geo existants.

- [ ] M9 : code département entre parenthèses limité à 2 chiffres (`01`-`95`, `2A`/`2B`) ou à `971`-`976`. « Lyon (100) » se résout par le nom donc `{"69"}`.
- [ ] M10 : `_load_index` en `try/except (OSError, json.JSONDecodeError)`, `logger.error`, renvoie `{}` (fail-open, localisation inconnue).
- [ ] M11 : dans `build_index`, un nom de département ou de région REMPLACE l'entrée des communes homonymes (`index[key] = ...`, pas d'union). Les communes homonymes entre elles restent fusionnées : sens permissif, un faux « dans la zone » coûte moins qu'une offre perdue. Docstring mise à jour. Régénérer le JSON avec `cd backend && uv run python scripts/build_communes_index.py` (API publique gratuite geo.api.gouv.fr).

  Tests :
  - `departments_for_location("Bretagne") == {"22","29","35","56"}` ;
  - « Saint-Denis » contient toujours `93` et `974` ;
  - « Lyon » donne `{"69"}` ;
  - « Lyon (100) » donne `{"69"}` ;
  - « Fort-de-France (972) » donne `{"972"}`.

### Task 5: embeddings, score, acronymes — M12, M15, M16, M17

**Files:** `backend/app/services/offer_scoring/embeddings.py`, `backend/app/services/evaluation/domain_relevance.py`, `backend/app/services/offer_scoring/score.py`, `backend/tests/test_domain_relevance.py` (ou le test existant de `domain_relevance`, pas `test_offer_sources.py`).

- [ ] M12 : test de `keep_relevant_titles` (`app.services.sources`, en import seul, sans modifier le fichier) avec un acronyme sensible à la casse. Il fige le comportement de collecte actuel.
- [ ] M15 : `zip(missing_ids, embedded_vectors, strict=True)` dans un `try` : une longueur différente se traite comme une erreur d'embedding (warning, fail-open, renvoi des seuls vecteurs en cache). Test RED : un `embed` qui renvoie un vecteur de moins ne met rien en cache et ne lève pas.
- [ ] M16 : un seul `_extract_embedding`, sans évaluation anticipée du défaut, partagé par `embeddings.py` et `domain_relevance.py`. `embeddings.py` l'importe depuis `domain_relevance`, ou les deux depuis un helper commun. Test : objet avec attribut `embedding` mais sans `__getitem__`.
- [ ] M17 : `score.py`, dans `skill_points.matches` : `frozenset({skill})` sort de la boucle sur les phrases. Branche morte : prouver qu'elle est inatteignable (aucun appelant ne peut produire la condition), puis la retirer. Sinon, la garder et ledger le ruling.

### Task 6: index, purge, démarrage — M13, M14, M21 (index)

**Files:** `backend/app/database.py:111-123`, `backend/main.py:65-68`, `backend/app/services/offer_profile_matcher.py` (appel d'index dans `tag_new_offers`), nouveau `backend/app/services/offer_scoring/cleanup.py`, `airflow/dags/clean_job_offers.py`, tests.

- [ ] M13 : retirer la création de l'index `offer_relevance (user_id 1, score -1)` et le supprimer de façon idempotente : `drop_index("user_id_1_score_-1")`, avec `OperationFailure` « index not found » ignoré.
- [ ] M21 (index) : `create_offer_scoring_indexes(db)` est aussi appelé en tête de `tag_new_offers`, le chemin Airflow, de façon idempotente. `main.py` remplace le `print` du `except` par `logger.exception` (ou `logger.error`).
- [ ] M14 : `purge_orphan_scoring_docs(db) -> dict` supprime les docs `offer_relevance` et `offer_embeddings` dont `offer_id` ne correspond à aucun `job_offers._id` existant. Les offres `is_deleted` gardent leurs docs. Il renvoie les compteurs. Appelé par une nouvelle tâche du DAG `airflow/dags/clean_job_offers.py`, après la tâche existante.

  Test : seed d'une offre existante, d'une offre `is_deleted` et d'un `offer_id` absent. Seuls les docs de l'absent sont supprimés.

### Task 7: scripts — M8, M18

**Files:** `backend/scripts/rematch_all_users.py`, `backend/scripts/matching_bench.py:~905-910`.

- [ ] M8 : sans `--apply` ni `--confirm`, aucun appel d'embedding. Le script affiche une estimation puis sort 0 : profils, offres actives, offres sans vecteur en cache pour `EMBEDDING_MODEL`, appels estimés (× profils en dry-run), coût à ~0,03 $ / 1 000 textes. `--confirm` lance le dry-run réel ; `--apply` vaut accord.

  Test : `embed` espion jamais appelé sans flag.
- [ ] M18 : corriger le dénominateur du log de `report()` pour qu'il corresponde à l'ensemble réellement calculé.

### Task 8: frontend — M19

**Files:** `frontend/src/app/offers/page.tsx`, nouveau composant de filtres sous `frontend/src/components/` (ou à côté de la page selon la convention existante).

- [ ] Extraire les filtres secteur et taille dans un composant. Chaque contrôle a un label associé (`htmlFor`/`id`). Les `<select multiple>` natifs deviennent des cases à cocher groupées (`fieldset`/`legend`). Mêmes paramètres envoyés à l'API (`sector`, `company_size` répétés).
- [ ] Vérif : `cd frontend && npm run build` ; `npx eslint` sur les fichiers touchés.

### Clôture

- [ ] Suite backend complète verte, `npm run build`, simulation lint 3.12.
- [ ] Revue finale de toute la branche (modèle le plus capable), puis une passe de correctifs.
- [ ] Commit, ff-only dans le worktree `main` avec empreinte avant/après, `git push origin main`, `gh run list -R Ekatche/jobs-tracker` vert.
- [ ] Pas de déploiement sans accord de l'utilisateur. Mémoire `hybrid-relevance-score-deployed.md` mise à jour.
