---
task: Cron verify_job_offers — vérifier toutes les offres par rotation, archiver au fil de l'eau, ne plus lancer le headless sur Indeed
description: verify_job_offers cron liveness coverage — rotation by last_verified_at ascending (never-verified first, then oldest check) instead of 200 most recent created_at, last_verified_at written on every checked offer (valid/closed/unknown), incremental per-offer MongoDB update_one soft-delete as each verification completes (no loss on Airflow execution_timeout 25 min), skip Crawl4AI headless for indeed hosts (Cloudflare 401 + networkidle 60 s timeout) returning unknown headless_skipped_antibot_domain; no age-based purge; pytest test_verify_job_offers; docs JOB_INGESTION_AND_NORMALIZATION SYSTEM_ARCHITECTURE
status: done
created: 2026-10-23
---

# Cron verify_job_offers : couverture complète par rotation, archivage incrémental, Indeed sans headless

## Context
- Existing code checked: `backend/app/tasks/verify_job_offers.py`.
  - `verify_job_offers_workflow` (l.505-628) sélectionne `is_deleted != True` trié `created_at` décroissant, `limit=200` (DAG `airflow/dags/verify_job_offers_dag.py`, `0 7 * * *`, `execution_timeout` 25 min, `retries: 1`). Aucun champ de date de vérification n'existe (`last_verified_at` absent du backend et du frontend). Conséquence : toute offre active hors du top 200 le plus récent n'est plus jamais vérifiée.
  - Les soft-deletes sont écrits seulement après `asyncio.gather` sur les 200 offres (l.586-610). Un run tué par `execution_timeout` n'archive rien.
  - `check_url_http_fast` : 401/403/429 ne sont pas traités à part et tombent dans `valid` + `requires_js_check: True`, donc headless. `verify_single_offer` (l.437-503) lance `check_url_headless_js` (Crawl4AI, `wait_until="networkidle"`) sous `Semaphore(5)`. Pour Indeed : 401 Cloudflare, puis timeout headless d'environ 60 s, puis `unknown` (mesuré dans le plan `archive/2026-10/20261023-linkedin-indeed-closed-offer-markers`).
  - Tests : `backend/tests/test_verify_job_offers.py` (40 tests, `tests_for` via code-review-graph). `test_verify_job_offers_workflow_dry_run_and_execution` (l.391-455) affirme `update_one.call_count == 1` et doit être adapté, car chaque offre vérifiée recevra une écriture `last_verified_at`.
  - Modèles : `JobOfferResponse` n'a pas `extra="forbid"` (seuls les modèles Task l'ont), donc un champ Mongo supplémentaire ne casse pas l'API.
  - Index : `database.py:64-97` indexe `created_at`, mais pas `last_verified_at`. Mongo `mongo:latest` (>= 6.0, `allowDiskUse` par défaut) : un tri sans index ne fait pas échouer la requête.
- Fresh info looked up: tri Mongo ascendant, un champ absent ou `null` est classé avant toute date, donc les offres jamais vérifiées passent en premier. Pas de nouvelle lib.
- Git status checked: `verify_job_offers.py` et `test_verify_job_offers.py` portent les changements non commités du plan `20261023-linkedin-indeed-closed-offer-markers` (même session, `done`). Ce plan s'empile dessus. `docs/JOB_INGESTION_AND_NORMALIZATION.md` et `docs/SYSTEM_ARCHITECTURE.md` sont modifiés par la même session. Hors périmètre (autres sessions) : `interview_prep.py`, `test_interview_prep_api.py`, fichiers frontend.

## Simpler Alternative Considered
1. Augmenter `limit` (par exemple 1000). Rejeté : allonge le run et aggrave le risque de timeout (environ 60 s par offre Indeed), sans garantir la couverture si le stock grossit.
2. Purge par âge (`cleanup_old_offers`). Rejeté par l'utilisateur le 2026-10-23 : le critère de date seul n'est pas assez robuste. L'archivage se fait uniquement sur un signal de clôture réel.

La rotation `last_verified_at` avec la même limite de 200 est le plus petit changement qui garantit que chaque offre finit par être contrôlée.

## Surgical Scope
- **Files touched**: `backend/app/tasks/verify_job_offers.py`, `backend/tests/test_verify_job_offers.py`, `docs/JOB_INGESTION_AND_NORMALIZATION.md`, `docs/SYSTEM_ARCHITECTURE.md`
- **Files NOT touched**: tous les autres, notamment `airflow/dags/*` (limite, horaire et timeout inchangés), `backend/app/tasks/clean_job_offers.py` (purge par âge reste désactivée), `backend/app/models.py`, `backend/app/database.py` (pas d'index, voir Notes)
- **Symbols replaced** (→ to delete before done): la boucle de soft-delete post-`gather` de `verify_job_offers_workflow` (l.586-610, y compris `from bson import ObjectId` local). Elle est remplacée par la persistance par offre.
- **Symbols extended** (→ keep): `verify_job_offers_workflow` (tri, persistance incrémentale, `last_verified_at`), `verify_single_offer` (court-circuit headless Indeed), `test_verify_job_offers_workflow_dry_run_and_execution` (assertions adaptées)

## Definition of Done
- [x] Build passes: `cd backend && uv run python -m py_compile app/tasks/verify_job_offers.py`
- [x] Tests pass: `cd backend && uv run pytest tests/test_verify_job_offers.py -q` (43 passed : 40 existants dont 1 adapté, plus 3 nouveaux)
- [x] Rotation : `cd backend && uv run pytest tests/test_verify_job_offers.py -q -k rotates_by_last_verified_at`. Exit 0 : le tri vaut `[("last_verified_at", 1), ("created_at", -1)]` et chaque offre vérifiée (valid, closed, unknown) reçoit `last_verified_at`.
- [x] Soft-delete seulement sur clôture confirmée : `cd backend && uv run pytest tests/test_verify_job_offers.py -q -k dry_run_and_execution`. Exit 0 : `is_deleted` n'est posé que pour l'offre close, et `dry_run=True` ne fait aucune écriture.
- [x] Archivage incrémental : `cd backend && uv run pytest tests/test_verify_job_offers.py -q -k persists_closed_before_batch_ends`. Exit 0 : une offre close est écrite en base alors qu'une autre vérification est encore bloquée (run interrompu par `asyncio.wait_for`).
- [x] Indeed sans headless : `cd backend && uv run pytest tests/test_verify_job_offers.py -q -k indeed_skips_headless`. Exit 0 : `check_url_headless_js` n'est pas appelé et le statut vaut `unknown`.
- [x] Aucun critère d'âge introduit : `git diff -- backend/app/tasks/verify_job_offers.py | grep -cE '^\+.*(timedelta|\$lt)'` → `0`
- [x] DAGs et nettoyage intacts : `git diff --quiet -- airflow/dags/ backend/app/tasks/clean_job_offers.py` exit 0
- [x] Doc à jour : `grep -c "last_verified_at" docs/JOB_INGESTION_AND_NORMALIZATION.md` ≥ 1 et `grep -c "200 offres les plus récentes" docs/JOB_INGESTION_AND_NORMALIZATION.md` → `0`
- [x] No dead code: plus aucun `from bson import ObjectId` local ni boucle `for closed in closed_offers` dans `verify_job_offers.py` (`grep -c "for closed in closed_offers" backend/app/tasks/verify_job_offers.py` → `0`)
- [x] Type check: n/a — pas de type checker configuré pour backend
- [x] Manual check: sonde réelle Indeed, `cd backend && uv run python -c "import asyncio,time; from app.tasks.verify_job_offers import verify_single_offer as v; t=time.time(); r=asyncio.run(v({'_id':'x','url':'https://fr.indeed.com/viewjob?jk=4f1c2d3e5a6b7c8d'}, asyncio.Semaphore(1))); print(r['status'], r['reason'], round(time.time()-t,1)); assert r['status']=='unknown' and time.time()-t < 15"` exit 0 (contre environ 70 s avant)

## Steps
- [x] Step 1: Tests d'abord, dans `backend/tests/test_verify_job_offers.py` :
  (a) adapter `test_verify_job_offers_workflow_dry_run_and_execution`. En exécution réelle, `update_one` est appelé pour les 3 offres, chaque `$set` contient `last_verified_at`, et seul l'appel `{"_id": closed_id}` porte `is_deleted: True` et `deletion_reason: "http_status_404"`. `updated_db_count == 1`. Le dry run garde `update_one.assert_not_called()`.
  (b) `test_verify_job_offers_workflow_rotates_by_last_verified_at` : vérifie l'argument de `cursor.sort`.
  (c) `test_verify_job_offers_workflow_persists_closed_before_batch_ends` : une offre close immédiate et une offre dont la vérification attend indéfiniment. `asyncio.wait_for(..., 0.5)` lève `TimeoutError`, et `update_one` a déjà été appelé avec `{"_id": closed_id}` et `is_deleted: True`.
  (d) `test_verify_single_offer_indeed_skips_headless` : `check_url_http_fast` mocké renvoie `valid` / `status_code` 401 / `requires_js_check` True sur `https://fr.indeed.com/viewjob?jk=abc`. `check_url_headless_js` (AsyncMock) n'est pas attendu, `status == "unknown"`, `is_valid is None`.
  Lancer pytest : (a), (b), (c) et (d) doivent échouer (rouge).
- [x] Step 2: Dans `verify_single_offer`, avant le niveau 2 : si `"indeed" in (urlparse(url).hostname or "").split(".")`, retourner `status: "unknown"`, `is_valid: None`, `reason: "headless_skipped_antibot_domain"`. Les clôtures déjà détectées au niveau 1 (404, JSON-LD, redirection, texte) restent archivées. Vérifier : pytest `-k indeed_skips_headless` vert.
- [x] Step 3: Dans `verify_job_offers_workflow` : tri `[("last_verified_at", 1), ("created_at", -1)]`. Remplacer la boucle de soft-delete post-`gather` par une coroutine interne par offre qui attend `verify_single_offer`, puis, si `not dry_run`, fait un `update_one({"_id": offer["_id"]}, {"$set": {...}})` avec `last_verified_at` toujours, et les champs de soft-delete actuels (`is_deleted`, `pipeline_stage: "expired"`, `deleted_date`, `deletion_reason`, `updated_at`) seulement si `is_valid is False`. Une erreur d'écriture est loguée sans interrompre le lot. `updated_db_count` compte les soft-deletes réellement modifiés. Supprimer dans cette étape l'ancienne boucle et l'import local `ObjectId`. Vérifier : pytest complet vert, et DoD « No dead code ».
- [x] Step 4: Docs. `docs/JOB_INGESTION_AND_NORMALIZATION.md` : section liveness (200 offres par run, d'abord les jamais ou moins récemment vérifiées via `last_verified_at` ; archivage écrit au fil de l'eau) et puce « Liveness Indeed » (headless sauté ; seules les clôtures visibles en HTTP sont archivées ; purge par âge désactivée par choix). `docs/SYSTEM_ARCHITECTURE.md:135` : mentionner la rotation. Vérifier : commandes DoD « Doc à jour ».
- [x] Step 5: Lancer toutes les commandes du DoD, y compris la sonde Indeed réelle.
- [x] Step 6 (teardown): orphan scan borné à la boucle remplacée (`for closed in closed_offers`, import local `ObjectId`). Résultat attendu : 0. `git diff --stat` limité aux 4 fichiers du Surgical Scope (en plus du diff du plan précédent déjà présent).

## Code Review
- Dead code removed: yes — boucle post-`gather` `for closed in closed_offers`, import local `from bson import ObjectId`, normalisation `raw_results` (déplacée dans `verify_and_persist`) ; 0 occurrence pour chacun.
- Build status: pass — `py_compile` exit 0.
- Type errors: n/a — pas de type checker configuré.
- Unintended side effects: none attendu. Changements de comportement voulus : chaque offre vérifiée reçoit `last_verified_at` (1 écriture Mongo par offre au lieu d'une par offre close) ; l'écriture utilise `offer["_id"]` natif au lieu de `ObjectId(offer_id)` (plus juste si un `_id` n'est pas un ObjectId) ; les offres Indeed sans clôture HTTP passent de `unknown` après ~60 s headless à `unknown` immédiat. Fichiers suivis modifiés identiques à l'état de début de session (aucun hors scope).
- Security surface touched: no — pas d'auth, d'entrée utilisateur ni de migration ; `update_one` filtré sur l'`_id` lu en base.
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-23T19:10Z | claude-code | preflight | done | baseline DoD logged in Notes
- 2026-10-23T19:10Z | claude-code | step 1 | started
- 2026-10-23T19:11Z | claude-code | step 1 | done | `pytest tests/test_verify_job_offers.py -q` 39 passed, 4 failed (rouge attendu : dry_run_and_execution 1 == 3, rotates sort non appelé, persists 0 == 1, indeed headless awaited 1)
- 2026-10-23T19:11Z | claude-code | step 2 | started
- 2026-10-23T19:12Z | claude-code | step 2 | done | `pytest -k indeed_skips_headless` exit 0 (1 passed)
- 2026-10-23T19:12Z | claude-code | step 3 | started
- 2026-10-23T19:13Z | claude-code | step 3 | done | py_compile exit 0 ; pytest 43 passed exit 0 ; ast-grep + grep `for closed in closed_offers` 0, `ObjectId` 0
- 2026-10-23T19:13Z | claude-code | step 4 | started
- 2026-10-23T19:14Z | claude-code | step 4 | done | grep last_verified_at JOB_INGESTION 1 ; « 200 offres les plus récentes » 0 ; SYSTEM_ARCHITECTURE rotation 1
- 2026-10-23T19:14Z | claude-code | step 5 | started
- 2026-10-23T19:14Z | claude-code | step 5 | done | build 0 ; pytest 43 passed ; 4 `-k` exit 0 ; âge 0 ; DAGs exit 0 ; doc 1/0 ; boucle morte 0 ; sonde Indeed réelle exit 0 `unknown headless_skipped_antibot_domain 0.3` s (68,1 s avant)
- 2026-10-23T19:14Z | claude-code | step 6 | started
- 2026-10-23T19:15Z | claude-code | step 6 | done | ast-grep `ObjectId($$$)` 0 ; grep `for closed in closed_offers` 0, `bson` 0, `raw_results` 0 ; diff --stat limité aux 4 fichiers du scope
- 2026-10-23T19:24Z | claude-code | close-out | done | DoD complet relancé : build 0 ; 43 passed ; 4 `-k` exit 0 ; sonde Indeed exit 0 (0,2 s) ; âge 0 ; DAGs 0 ; doc 1/0 ; boucle morte 0 ; diff relu

## Notes
- Conventions lues (preflight) : `CLAUDE.md` (= `AGENTS.md` = `GEMINI.md`, `cmp` identique ; règles de pertinence des tests), `.cursorrules` (graphe code-review-graph). Python 3.12 (`backend/.python-version`), `asyncio.wait_for` lève le `TimeoutError` builtin.
- Baseline DoD (2026-10-23T19:10Z, avant toute modification) : build exit 0 ; pytest 40 passed ; `-k rotates_by_last_verified_at` / `persists_closed_before_batch_ends` / `indeed_skips_headless` exit 5 (aucun test) ; `-k dry_run_and_execution` exit 0 (ancienne assertion) ; critère d'âge 0 ; DAGs intacts exit 0 ; doc `last_verified_at` 0 et « 200 offres les plus récentes » 1 ; boucle morte 1 ; sonde Indeed réelle `unknown` en 68,1 s (assert < 15 s en échec).
- Décision utilisateur 2026-10-23 : pas de purge par âge. Ce plan n'ajoute aucun critère de date à la décision d'archiver (DoD dédié).
- Couverture attendue : avec N offres actives et 200 par jour, chaque offre est revérifiée tous les N/200 jours environ. Les offres `unknown` reçoivent aussi `last_verified_at`, sinon Indeed resterait toujours en tête de file et bloquerait la rotation.
- Pas d'index `last_verified_at` : Mongo >= 6.0 trie sans index (spill disque). Si le run logue un tri lent sur un gros stock, ajouter `create_index("last_verified_at")` dans `database.py` (plan séparé).
- Le timeout réel du run en prod n'a pas été confirmé (logs Airflow prod non lus). Le plan supprime la perte de résultats quoi qu'il en soit.
- Après déploiement : premier run sur le VPS, vérifier dans le log Airflow le résumé `Vérification terminée` et la présence de `last_verified_at` sur 200 offres.
- Clôture 2026-10-23T19:24Z : tests ajoutés entièrement mockés (`get_database`, `verify_single_offer`, `check_url_*`), aucun service externe requis. `test_..._persists_closed_before_batch_ends` dure ~0,5 s (`wait_for`).
- Prochaine action : déployer le backend et Airflow sur le VPS, puis lire le log du premier run (`Vérification terminée`, `last_verified_at` posé sur 200 offres). Index `last_verified_at` seulement si le tri se révèle lent.
