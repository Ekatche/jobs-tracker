---
task: Réduire la consommation de crédits Tavily (passes en doublon avec jobspy retirées, Tavily seulement au run de 07:00 UTC)
description: Budget crédits Tavily 2 300/mois — custom_tool.py TavilyJobBoardSearchTool retire le groupe hellowork.com et la Passe 3 LinkedIn (couverts par python-jobspy) ; collect_and_save_offers/collect_offers_sync gagnent use_web_search, is_web_search_run(now) + WEB_SEARCH_MAX_HOUR_UTC dans job_offers_collectors.py ; DAG Airflow collect_job_offers_granular (0 7,16) n'appelle Tavily/crew CrewAI qu'au run du matin, jobspy et France Travail aux deux runs
status: done
created: 2026-10-24
---

# Budget de crédits Tavily : retrait des doublons jobspy et recherche web une fois par jour

## Context
- Existing code checked:
  - `backend/job_trackers/src/job_trackers/tools/custom_tool.py` L113-208 : Passe 1 = 4 groupes (`welcometothejungle.com` 8, `apec.fr`+`cadremploi.fr` 6, `hellowork.com` 6, `free-work.com`+`lesjeudis.com` 6) + `francetravail.fr` si identifiants FT absents ; Passe 2 ATS ; Passe 3 `site:linkedin.com/jobs`. Tous en `search_depth="advanced"` (2 crédits).
  - `backend/app/tasks/job_offers_collectors.py` : `collect_and_save_offers(query)` L592 lance `get_urls_for_query` (crew CrewAI + Tavily) en parallèle de `collect_structured_offers` ; `collect_offers_sync(query)` L678.
  - `airflow/dags/collect_job_offers.py` : `execute_collection_pipeline` boucle sur `collect_offers_sync(query)`, schedule `0 7,16 * * 1-5`. Aucun `default_timezone` configuré, Airflow est donc en UTC.
  - Tests : `backend/tests/test_crew_models_and_tools.py` (`TestTavilyTool.test_funnel_three_passes_balanced_and_deduplicated` L67, `TestAirflowCollectionPipeline` L320, dont les mocks de `collect_offers_sync` n'acceptent que `query`), `backend/tests/test_job_offers_pipeline.py` (`_mock_collect_pipeline` L781). Airflow est importable dans le venv backend : les 2 tests du DAG s'exécutent, ils ne sont pas skippés.
  - Autre appelant de `collect_and_save_offers(query)` : `backend/app/tasks/tests/test_job_crawler_wf.py:51`, compatible grâce à la valeur par défaut `use_web_search=True`.
- Fresh info looked up: doc Tavily via Context7 (`/websites/tavily`) : `basic`/`fast` = 1 crédit, `advanced` = 2 crédits ; plan Free = 1 000 crédits/mois.
- Git status checked: `job_offers_collectors.py`, `test_job_offers_pipeline.py` et `docs/JOB_INGESTION_AND_NORMALIZATION.md` portent des modifications non commitées des plans de cette même session (`20261023-crawl-loss-metrics-and-recovery`, `20261023-jobspy-hellowork-source`), connues. `custom_tool.py`, `test_crew_models_and_tools.py` et le DAG sont propres.

## Simpler Alternative Considered
Passer toutes les recherches en `search_depth="basic"` (1 crédit) sans toucher au code de collecte : divise le coût par deux, mais Tavily continuerait à payer pour HelloWork et LinkedIn que jobspy ramène déjà gratuitement, et la qualité des résultats `basic` sur les job boards n'a pas été mesurée. Écarté pour ce plan ; à réévaluer avec le point « fusion des requêtes ».

Autre option : changer le schedule du DAG en `0 7 * * 1-5`. Écarté : jobspy et France Travail perdraient leur run de l'après-midi, alors qu'ils ne coûtent aucun crédit.

## Surgical Scope
- **Files touched**:
  - `backend/job_trackers/src/job_trackers/tools/custom_tool.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - `airflow/dags/collect_job_offers.py`
  - `backend/tests/test_crew_models_and_tools.py`
  - `backend/tests/test_job_offers_pipeline.py`
  - `docs/JOB_INGESTION_AND_NORMALIZATION.md`
- **Files NOT touched**: tous les autres, en particulier `backend/app/routers/*`, le frontend, `backend/app/services/sources/*`, `build_search_queries` (la fusion des requêtes fera l'objet d'un plan séparé).
- **Symbols replaced** (→ to delete before done): bloc Passe 3 de `TavilyJobBoardSearchTool._run` (variables locales `linkedin_query`, `response_linkedin`, `e_li`) ; entrée `(["hellowork.com"], 6)` de `job_board_groups` ; test `test_funnel_three_passes_balanced_and_deduplicated`, renommé `test_funnel_two_passes_balanced_and_deduplicated`.
- **Symbols extended** (→ keep): `collect_and_save_offers` (+ `use_web_search: bool = True`), `collect_offers_sync` (+ `use_web_search: bool = True`), `execute_collection_pipeline` ; nouveaux : `WEB_SEARCH_MAX_HOUR_UTC = 12`, `is_web_search_run(now: datetime) -> bool`.

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import app.tasks.job_offers_collectors; from job_trackers.src.job_trackers.tools.custom_tool import TavilyJobBoardSearchTool"` exit 0
- [x] Tests pass: `cd backend && uv run pytest tests/test_crew_models_and_tools.py tests/test_job_offers_pipeline.py tests/test_job_offers_collectors_queries.py -q` exit 0
- [x] HelloWork retiré de Tavily : `grep -c 'hellowork.com' backend/job_trackers/src/job_trackers/tools/custom_tool.py` = 0
- [x] Passe 3 LinkedIn retirée : `grep -c 'linkedin.com/jobs' backend/job_trackers/src/job_trackers/tools/custom_tool.py` = 0
- [x] Repli France Travail conservé : `grep -c 'francetravail.fr' backend/job_trackers/src/job_trackers/tools/custom_tool.py` >= 1
- [x] `use_web_search=False` n'appelle ni le crew ni Tavily : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q -k web_search` exit 0, au moins 1 test sélectionné
- [x] Règle horaire : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q -k is_web_search_run` exit 0, au moins 1 test sélectionné
- [x] Le DAG transmet le drapeau : `cd backend && uv run pytest tests/test_crew_models_and_tools.py -q -k Airflow` exit 0, au moins 3 tests sélectionnés
- [x] Doc à jour : `grep -c 'Passe 3' docs/JOB_INGESTION_AND_NORMALIZATION.md` = 0 et `grep -c '07:00 UTC' docs/JOB_INGESTION_AND_NORMALIZATION.md` >= 1
- [x] No dead code: `grep -cE 'linkedin_query|response_linkedin|e_li\b' backend/job_trackers/src/job_trackers/tools/custom_tool.py` = 0 et `grep -c 'test_funnel_three_passes' backend/tests/test_crew_models_and_tools.py` = 0
- [x] Type check: n/a — ni mypy ni ruff configurés dans `backend/pyproject.toml`
- [x] Manual check: n/a — le déploiement ne fait pas partie de ce plan (sur demande de l'utilisateur) ; vérification post-déploiement décrite dans Notes

## Steps
- [x] Step 1: Dans `custom_tool.py`, retirer `(["hellowork.com"], 6)` de `job_board_groups`, supprimer le bloc Passe 3 LinkedIn (L190-208) et mettre à jour le commentaire L113-115 (Indeed, LinkedIn et HelloWork collectés par python-jobspy). Dans `test_crew_models_and_tools.py`, renommer le test d'entonnoir en `test_funnel_two_passes_balanced_and_deduplicated`, retirer sa branche LinkedIn, ajouter `assert ["hellowork.com"] not in board_groups`, passer à `call_count == len(board_groups) + 1` et attendre 2 URLs (WTTJ, Greenhouse). Vérif : `cd backend && uv run pytest tests/test_crew_models_and_tools.py -q -k TestTavilyTool` + les trois `grep -c` sur `custom_tool.py` du DoD.
- [x] Step 2: Dans `job_offers_collectors.py`, ajouter `WEB_SEARCH_MAX_HOUR_UTC = 12` près des constantes et la fonction pure `is_web_search_run(now: datetime) -> bool` (`now.astimezone(timezone.utc).hour < WEB_SEARCH_MAX_HOUR_UTC`). Ajouter `use_web_search: bool = True` à `collect_and_save_offers` et à `collect_offers_sync`, qui le transmet. Quand il vaut `False`, ne pas appeler `get_urls_for_query` (ni crew, ni Tavily, ni crawl), loguer une ligne explicite, et laisser les sources structurées suivre le chemin actuel. Mettre à jour la docstring de `collect_and_save_offers`. Vérif : `cd backend && uv run python -c "import app.tasks.job_offers_collectors"` exit 0.
- [x] Step 3: Dans `test_job_offers_pipeline.py`, ajouter (a) `test_collect_skips_web_search_when_disabled` : avec `_mock_collect_pipeline`, `use_web_search=False`, `get_urls_for_query` et `crawl_urls_for_offers` jamais awaités, l'offre structurée arrive à `enrich_offers` ; (b) `test_is_web_search_run_only_for_morning_run` : 07:00 UTC vrai, 16:00 UTC faux, 18:00+02:00 (16:00 UTC) faux. Vérif : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q` exit 0.
- [x] Step 4: Dans `airflow/dags/collect_job_offers.py`, `execute_collection_pipeline` importe `is_web_search_run`, calcule une fois `use_web_search = is_web_search_run(datetime.now(timezone.utc))`, le logue et appelle `collect_offers_sync(query, use_web_search=use_web_search)`. Dans `TestAirflowCollectionPipeline`, faire accepter `use_web_search=True` aux deux mocks existants et ajouter un test : `is_web_search_run` patché à `False`, le mock capture `use_web_search is False` pour chaque requête. Vérif : `cd backend && uv run pytest tests/test_crew_models_and_tools.py -q -k Airflow` exit 0, 3 tests.
- [x] Step 5: Dans `docs/JOB_INGESTION_AND_NORMALIZATION.md`, section « 3. Tavily » : Passe 1 sans HelloWork, ligne Passe 3 supprimée, coût « 4 appels advanced par requête (5 avec le repli francetravail.fr), au seul run de 07:00 UTC ; jobspy et France Travail aux deux runs » ; L257 : retirer « Tavily LinkedIn (passe 3) complète ». Vérif : les deux `grep -c` doc du DoD.
- [x] Step 6 (teardown): Orphan scan borné aux symboles retirés (`linkedin_query`, `response_linkedin`, `e_li`, `test_funnel_three_passes`, entrée `hellowork.com`) ; confirmer 0 orphelin. Relancer tout le DoD.

## Code Review
- Dead code removed: yes — bloc Passe 3 (`linkedin_query`, `response_linkedin`, `e_li`) = 0 occurrence, `test_funnel_three_passes` = 0, `hellowork.com` absent de `custom_tool.py`
- Build status: pass — import du collecteur et de `TavilyJobBoardSearchTool` exit 0 ; 60 passed (crew + pipeline + queries), exit 0
- Type errors: none — pas de type checker configuré ; diagnostics IDE « Cannot find module » préexistants (imports via `sys.path`), non liés
- Unintended side effects: none dans le code. Comportement voulu mais à connaître : un run manuel après 12:00 UTC ne lance pas Tavily ; Tavily ne compense plus un blocage jobspy sur Indeed/LinkedIn/HelloWork (doc mise à jour). Les nouveaux tests sont entièrement mockés (aucun service externe)
- Security surface touched: no — aucun code d'auth, de secret ni de validation modifié (lecture de `TAVILY_API_KEY` inchangée)
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-24T10:00Z | claude-code | preflight | done | baseline DoD logged in Notes, build command corrected
- 2026-10-24T10:00Z | claude-code | step 1 | started
- 2026-10-24T10:01Z | claude-code | step 1 | done | `pytest -k TestTavilyTool` 5 passed exit 0; grep hellowork.com=0 linkedin.com/jobs=0 francetravail.fr=1
- 2026-10-24T10:01Z | claude-code | step 2 | started
- 2026-10-24T10:02Z | claude-code | step 2 | done | `uv run python -c import app.tasks.job_offers_collectors` exit 0 (is_web_search_run 07h=True 16h=False)
- 2026-10-24T10:02Z | claude-code | step 3 | started
- 2026-10-24T10:05Z | claude-code | step 3 | done | `pytest tests/test_job_offers_pipeline.py -q` 28 passed exit 0
- 2026-10-24T10:05Z | claude-code | step 4 | started
- 2026-10-24T10:09Z | claude-code | step 4 | done | `pytest tests/test_crew_models_and_tools.py -q -k Airflow` 3 passed exit 0 (aucun skip)
- 2026-10-24T10:09Z | claude-code | step 5 | started
- 2026-10-24T10:09Z | claude-code | step 5 | done | doc grep 'Passe 3'=0, '07:00 UTC'=1 ; aucune autre mention Tavily LinkedIn/HelloWork dans la doc ni SYSTEM_ARCHITECTURE.md
- 2026-10-24T10:10Z | claude-code | step 6 | started
- 2026-10-24T10:10Z | claude-code | step 6 | done | orphelins linkedin_query/response_linkedin/e_li=0, test_funnel_three_passes=0 (backend/app, job_trackers, tests, airflow)
- 2026-10-24T10:15Z | claude-code | close | done | DoD complet relancé : build exit 0, 60 passed exit 0, -k web_search 2 passed, -k is_web_search_run 1 passed, -k Airflow 3 passed, greps conformes ; diff relu

## Notes
- **Conventions lues (Phase 3)** : `CLAUDE.md` racine (identique à `AGENTS.md` et `GEMINI.md`) : directives tests (pertinence, `tests_for` avant refonte d'un test, `pytest` vert) ; `.cursorrules` (outils code-review-graph). Pas de fichier de convention imbriqué.
- **Correction du DoD avant exécution** : la commande de build importait `job_trackers.tools.custom_tool`, chemin inexistant (`ModuleNotFoundError: No module named 'job_trackers.tools'`). Remplacée par `from job_trackers.src.job_trackers.tools.custom_tool import TavilyJobBoardSearchTool`, le chemin réellement importable. L'intention (le module s'importe) est inchangée.
- **Baseline (2026-10-24, avant modification)** : build corrigé OK ; tests 57 passed (122 s) ; `hellowork.com` = 1, `linkedin.com/jobs` = 2, `francetravail.fr` = 1 ; `-k web_search` et `-k is_web_search_run` : 0 sélectionné ; `-k Airflow` : 2 passed ; doc `Passe 3` = 1, `07:00 UTC` = 0 ; orphelins `linkedin_query|response_linkedin|e_li` = 9, `test_funnel_three_passes` = 1.
- **Estimation après ce plan** : 4 appels advanced = 8 crédits par requête, 22 jours ouvrés, un seul run Tavily par jour. 5 requêtes : environ 880 crédits/mois ; 8 requêtes (`MAX_TOTAL_QUERIES`) : environ 1 400. Avec le repli `francetravail.fr` (10 crédits par requête) : 1 100 et 1 760. Tout reste sous 2 300. Hypothèse non mesurée : le crew appelle l'outil une seule fois par requête. `MAX_CREW_ATTEMPTS = 2` et l'agent `search_executor` peuvent le rappeler ; à mesurer (delta de `GET https://api.tavily.com/usage` avant/après un run) avant le plan de fusion des requêtes.
- **Déploiement couplé** : le retrait de `hellowork.com` côté Tavily ne doit partir en prod qu'avec la source HelloWork via jobspy (`20261023-jobspy-hellowork-source`, non commitée), sinon HelloWork disparaît de la collecte.
- **France Travail** : le repli `francetravail.fr` n'est ajouté que si `FRANCE_TRAVAIL_CLIENT_ID`/`SECRET` sont absents. Si la prod les définit alors que l'OAuth FT est en panne, France Travail n'est couvert par rien. Hors périmètre, à vérifier séparément.
- **Déclenchement manuel** : un run lancé à la main après 12:00 UTC n'appelle pas Tavily. C'est voulu (budget), à connaître avant de relancer une collecte pour tester Tavily.
- **Vérification post-déploiement** (observateur : Claude, sur demande de l'utilisateur) : dans les logs du run de 16:00 UTC de `collect_job_offers_granular`, `grep -c 'Passe 1'` = 0 et présence de la ligne « recherche web désactivée » ; au run de 07:00 UTC, aucune ligne `Passe 3` ni `hellowork.com` côté Tavily.
