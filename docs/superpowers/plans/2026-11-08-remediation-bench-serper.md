# Plan de remédiation : banc de comparaison Serper / Tavily

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Statut** : terminé — exécuté et validé (audit Argon approuvé à 100 %)  
**Branche cible** : `feature/exploration-serper` (`.worktrees/exploration-serper`)  
**Design de référence** : [exploration Serper](../specs/2026-11-08-exploration-serper-design.md)  
**Plan initial** : [2026-11-08-exploration-serper.md](./2026-11-08-exploration-serper.md)

**Goal:** Corriger les 6 anomalies identifiées lors de la revue de code et du premier run réel Serper (isolation stricte de `router.py`, bruit sur les sous-requêtes ATS Serper, faux positifs de `compute_pre_annotation`, coût Scénario A à 0 appel, modularisation du monolithe de 2 875 lignes et mise en conformité stricte des fichiers de test sous les 350 lignes).

**Architecture:** Découpage du script monolithique `backend/scripts/bench_serper_tavily.py` en un package modulaire `backend/scripts/bench/` (`models.py`, `queries.py`, `adapters.py`, `qualification.py`, `reporting.py`, `orchestrator.py`) avec `bench_serper_tavily.py` conservé comme façade CLI rétrocompatible (< 250 lignes). Scission des fichiers de test dans `backend/tests/bench/` pour qu'aucun fichier ne dépasse 350 lignes.

**Tech Stack:** Python 3.12, Pydantic v2, httpx, pytest.

## Global Constraints

- **Zéro modification du code applicatif de production** : `backend/app/services/ats/router.py` doit revenir exactement à son état `main` (`871c87a`).
- **Zéro écriture en base de données** : aucune invocation de `collect_and_save_offers`.
- **Hygiène stricte des fichiers de test (`AGENTS.md` §4)** : aucun fichier dans `backend/tests/bench/` ne doit dépasser **350 lignes** ; utiliser `@pytest.mark.parametrize` et externaliser les fixtures dans `conftest.py`.
- **Tests 100 % hors réseau et déterministes**.

---

### Task 1: Restaurer l'isolation de `router.py` et modulariser `bench_serper_tavily.py`

**Files:**
- Modify: `backend/app/services/ats/router.py` (retirer l'alias `route_and_extract` ajouté en fin de fichier)
- Create: `backend/scripts/bench/__init__.py`
- Create: `backend/scripts/bench/models.py`
- Create: `backend/scripts/bench/queries.py`
- Create: `backend/scripts/bench/adapters.py`
- Create: `backend/scripts/bench/qualification.py`
- Create: `backend/scripts/bench/reporting.py`
- Create: `backend/scripts/bench/orchestrator.py`
- Modify: `backend/scripts/bench_serper_tavily.py` (façade CLI + ré-exports rétrocompatibles, < 250 lignes)

**Interfaces:**
- Produces: tous les symboles existants restent importables depuis `scripts.bench_serper_tavily` ET depuis `scripts.bench.*`.
- Consumes: `from app.services.ats.router import ExpiredOfferError, extract_ats_or_jsonld_offer as route_and_extract`.

- [x] **Step 1: Retirer la modification dans `backend/app/services/ats/router.py`**
  Supprimer les 4 lignes ajoutées à la fin de `backend/app/services/ats/router.py` et vérifier avec `git diff main -- backend/app/` qu'aucun fichier de `backend/app/` n'est modifié.

- [x] **Step 2: Extraire les sous-modules dans `backend/scripts/bench/`**
  - `queries.py` : constantes de domaines (`SPAM_AGGREGATORS`, `COVERED_ELSEWHERE`, `PREFERRED_JOB_BOARDS`, `COMPANY_ATS_DOMAINS`, `EXCLUDED_PATHS`), `SYNTHETIC_PROFILES`, `SYNTHETIC_QUERIES`.
  - `models.py` : modèles Pydantic (`CandidateProfile`, `BenchmarkQuery`, `SearchPassConfig`, `CostProjection`, `NormalizedHit`, `SearchAttempt`, `RunLimits`, `RunManifest`, `BudgetCapReachedError`, `BenchmarkQueryResult`, `ExtractedOfferInfo`, `EvaluationRecord`, `ProviderComparisonMetrics`, `QueryComparisonMetrics`, `BenchmarkComparisonReport`).
  - `adapters.py` : `extract_domain`, `check_job_url`, `is_valid_job_url`, `split_ats_domains_for_serper`, `build_serper_ats_subqueries`, `aggregate_hits`, `BaseBenchmarkAdapter`, `TavilyBenchmarkAdapter`, `SerperBenchmarkAdapter`. Factoriser la logique commune de `execute_query` dans `BaseBenchmarkAdapter` pour éliminer la duplication entre Tavily et Serper.
  - `qualification.py` : `compute_pre_annotation`, `extract_unique_urls`, `generate_evaluation_table`, `export_evaluation_csv`, `export_evaluation_jsonl`.
  - `reporting.py` : `build_comparison_report`, `format_manifest_summary`, `get_code_version`, `get_search_passes`, `build_manifest`.
  - `orchestrator.py` : `run_benchmark`, `check_no_secrets_in_args`, `parse_cli_args`, `main`.
  - `bench_serper_tavily.py` : point d'entrée CLI et ré-export des symboles publics.

- [x] **Step 3: Vérifier la non-régression des imports et des tests**
  Run: `cd backend && uv run pytest tests/bench/ -v`
  Expected: 52 passed, `git diff 871c87a -- backend/app/` vide.

- [x] **Step 4: Commit**
  `refactor(bench): revert router.py change and split monolith into scripts/bench package`

---

### Task 2: Figer les requêtes optimisées (`query_converter`) et filtrer le bruit ATS Serper

**Files:**
- Modify: `backend/scripts/bench/queries.py`
- Modify: `backend/scripts/bench/models.py`
- Modify: `backend/scripts/bench/adapters.py`
- Test: `backend/tests/bench/test_adapters.py`

**Interfaces:**
- `BenchmarkQuery` conserve `query_text: str` (requête optimisée envoyée aux moteurs, ex: `"offres emploi Data Engineer Lyon CDI"`) et ajoute `user_query: Optional[str] = None` (phrase initiale du candidat, ex: `"Je recherche un poste de Data Engineer proche de Lyon (CDI)"`).
- `check_job_url(url, exclude_domains=None, exclude_paths=None) -> tuple[bool, Optional[str]]` rejette les sous-domaines support/vitrine des éditeurs ATS et les URLs de listing/aide.

- [x] **Step 1: Écrire les tests unitaires sur le filtrage du bruit ATS et les requêtes optimisées**
  Ajouter un test paramétré dans `test_adapters.py` vérifiant que `check_job_url` rejette :
  - `https://support.teamtailor.com/fr/articles/2564412-fiches-de-poste` (`excluded_ats_subdomain` / `excluded_path`)
  - `https://support.recruitee.com/en/articles/9728908-apec-contract`
  - `https://recruitee.com/fr/temoignages-clients` (domaine racine vitrine sans sous-domaine entreprise ni `/o/`)
  - `https://eulen.taleo.net/careersection/eul_career_site/jobsearch.ftl?lang=es` (`excluded_path:jobsearch.ftl`)
  - `https://chicago.taleo.net/careersection/careersection/103/joblist.ftl?lang=en` (`excluded_path:joblist.ftl`)
  Tout en acceptant les vraies offres ATS :
  - `https://francophoniecarrieres.recruitee.com/o/data-engineer`
  - `https://jobs.ashbyhq.com/elevenlabs/3b807ff1-a6b0-4f1c-b4f4-6ab265ac6d2f/application`
  - `https://boards.greenhouse.io/datadog/jobs/123456`

- [x] **Step 2: Mettre à jour `SYNTHETIC_QUERIES` et `check_job_url`**
  1. Dans `SYNTHETIC_QUERIES`, remplacer les phrases conversationnelles `"Je recherche un poste de..."` dans `query_text` par les requêtes optimisées figées conformes à `query_converter` (`tasks.yaml` : ex. `"offres emploi Data Engineer Lyon CDI"`), et stocker la phrase d'origine dans `user_query`.
  2. Dans `EXCLUDED_PATHS`, ajouter : `"/articles/"`, `"/temoignages"`, `"/help/"`, `"/support/"`, `"/pricing"`, `"/tarifs"`, `"jobsearch.ftl"`, `"joblist.ftl"`, `"/jobs/search"`.
  3. Dans `check_job_url`, bloquer les sous-domaines techniques/support (`support.*`, `help.*`, `docs.*`, `blog.*`, `status.*`, `community.*`) ainsi que les pages vitrines des éditeurs ATS (`recruitee.com` ou ` www.recruitee.com` sans `/o/`, `teamtailor.com` ou `www.teamtailor.com` sans `/jobs/`).

- [x] **Step 3: Lancer les tests pour vérifier le passage au vert**
  Run: `cd backend && uv run pytest tests/bench/test_adapters.py -v`
  Expected: PASS.

- [x] **Step 4: Commit**
  `fix(bench): use optimized search queries and filter ATS support/listing noise`

---

### Task 3: Corriger l'heuristique `compute_pre_annotation` et le coût Scénario A à 0 appel

**Files:**
- Modify: `backend/scripts/bench/qualification.py`
- Modify: `backend/scripts/bench/reporting.py`
- Test: `backend/tests/bench/test_qualification.py`

**Interfaces:**
- `compute_pre_annotation(profile=None, query=None, title=None, location=None, extraction_status="extracted", relevance_score=None) -> Literal["pertinent", "non_pertinent", "incertain"]`
- `build_comparison_report(...)` : `cost_scenario_a_usd = 0.0` lorsque `serper_calls == 0 and serper_credits == 0`.

- [x] **Step 1: Écrire les tests reproduisant les faux positifs de pré-annotation et le bug `cost_scenario_a_usd`**
  1. Tester que pour une requête `target_role="Data Engineer"`, `location="Lyon"` :
     - Un poste `"Analytics Engineer"` ou `"Software Engineer"` (qui ne partage que le mot générique `"engineer"`) est annoté `"incertain"` ou `"non_pertinent"`, et NON `"pertinent"`.
     - Un poste `"Data Engineer"` dont la localisation extraite est `"London, UK"` ou `"Capital Federal"` (alors que la requête cible `"Lyon"` sans full-remote) est annoté `"non_pertinent"`.
     - Un poste `"Senior Data Engineer (H/F)"` à `"Lyon"` est annoté `"pertinent"`.
  2. Tester que `build_comparison_report(..., serper_calls=0, serper_credits=0)` produit `report.serper.cost_scenario_a_usd == 0.0`.

- [x] **Step 2: Implémenter le correctif dans `compute_pre_annotation` et `build_comparison_report`**
  1. Dans `compute_pre_annotation` :
     - Ignorer les termes génériques non discriminants (`{"engineer", "ingenieur", "ingénieur", "developer", "developpeur", "développeur", "manager", "lead", "senior", "junior", "consultant", "specialist", "h/f", "f/h"}`) lors du calcul de correspondance partielle : exiger que les termes de spécialité (`"data"`, `"devops"`, `"mlops"`, `"llm"`, `"fullstack"`, `"product"`, `"cloud"`, `"sre"`, `"analytics"`, etc.) soient présents dans le titre.
     - Si `location` (extrait de l'offre) est renseigné et que la requête cible une ville précise (`query.location` et `not query.is_remote`), vérifier qu'il n'y a pas de contradiction géographique manifeste (villes/pays étrangers connus ou autre métropole française incompatible).
  2. Passer `location=info.location` lors de l'appel à `compute_pre_annotation` dans `generate_evaluation_table`.
  3. Dans `build_comparison_report`, poser `serp_cost_a = 0.0 if (serper_calls == 0 and serper_credits == 0) else round(cp.serper_starter_pack_usd / cp.serper_pack_validity_months, 2)`.

- [x] **Step 3: Vérifier les tests de qualification**
  Run: `cd backend && uv run pytest tests/bench/test_qualification.py -v`
  Expected: PASS.

- [x] **Step 4: Commit**
  `fix(bench): tighten pre-annotation role/location matching and fix zero-call scenario A cost`

---

### Task 4: Mettre tous les fichiers de test sous la barre stricte des 350 lignes et valider

**Files:**
- Modify/Split: `backend/tests/bench/conftest.py`
- Modify/Split: `backend/tests/bench/test_manifest.py` (580 l. → scinder en `test_models.py` + `test_manifest.py`, chacun < 320 l.)
- Modify/Split: `backend/tests/bench/test_adapters.py` (633 l. → scinder en `test_url_filters.py` + `test_adapters.py`, chacun < 350 l.)
- Modify/Split: `backend/tests/bench/test_qualification.py` (564 l. → scinder en `test_qualification.py` + `test_reporting.py`, chacun < 320 l.)
- Keep: `backend/tests/bench/test_orchestrator.py` (~251 l.)

- [x] **Step 1: Scinder et paramétrer les fichiers de test dans `backend/tests/bench/`**
  - `test_models.py` : validation des modèles Pydantic, projections de coûts Scénarios A/B et break-even.
  - `test_manifest.py` : génération du manifeste, CLI `--dry-run`, sécurité des arguments CLI.
  - `test_url_filters.py` : `extract_domain`, `check_job_url`, `is_valid_job_url`, `split_ats_domains_for_serper`, `build_serper_ats_subqueries`, `aggregate_hits` (avec `@pytest.mark.parametrize`).
  - `test_adapters.py` : `TavilyBenchmarkAdapter`, `SerperBenchmarkAdapter`, gestion des erreurs et plafonds `RunLimits`.
  - `test_qualification.py` : `extract_unique_urls`, `compute_pre_annotation`, `generate_evaluation_table`, exports CSV/JSONL.
  - `test_reporting.py` : `build_comparison_report`, métriques par requête, distribution des domaines, formatage Markdown.
  - `test_orchestrator.py` : `run_benchmark` et exécution de bout en bout avec mocks.

- [x] **Step 2: Vérifier la longueur de chaque fichier et exécuter toute la suite**
  Run: `wc -l backend/tests/bench/*.py backend/scripts/bench/*.py backend/scripts/bench_serper_tavily.py`
  Expected: Aucun fichier dans `backend/tests/bench/*.py` ne dépasse **350 lignes**.
  Run: `cd backend && uv run pytest tests/bench/ tests/test_ats_parsers.py -v`
  Expected: 100 % PASS.

- [x] **Step 3: Exécuter un run réel de contrôle Serper (1 requête, max 3 appels)**
  Run: `cd backend && uv run python scripts/bench_serper_tavily.py --live --provider serper --limit-queries 1 --max-calls 3 --max-credits 5`
  Expected: 0 URL de support (`support.teamtailor.com`, `support.recruitee.com`), 0 page `jobsearch.ftl`/`joblist.ftl`, pré-annotation cohérente avec le poste et la localisation.

- [x] **Step 4: Commit**
  `refactor(tests): split bench test suite into <350-line thematic modules`

