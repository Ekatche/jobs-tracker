# Plan — Lot 6 : Collecte, ATS & Tâches Airflow

Date : 2026-11-15  
Feuille de route : `docs/superpowers/specs/2026-11-15-code-size-compliance-roadmap.md`  
Périmètre : Refactoring modulaire des 5 derniers fichiers backend > 500 lignes sous `≤ 300` lignes par module, avec compatibilité descendante stricte des façades (`__init__.py` / `ats/router.py`) et cibles `unittest.mock.patch` / `monkeypatch`.

---

## Architecture cible & fichiers créés

### 1. `backend/app/services/normalization.py` (939 l.) → `backend/app/services/normalization/`
- `__init__.py` (81 l.) : façade + `__all__`
- `text.py` (169 l.) : nettoyage HTML/texte, normalisation chaînes/villes/entreprises/titres
- `urls.py` (211 l.) : canonisation URLs, détection ATS/plateformes, extraction domaine
- `fields.py` (213 l.) : normalisation salaires, contrats, dates, champs offre structurés
- `dedup.py` (204 l.) : clés d'identité et déduplication

### 2. `backend/app/services/ats/router.py` (927 l.) → `backend/app/services/ats/`
- `common.py` (97 l.) : utilitaires partagés de normalisation HTML/champs ATS
- `non_content.py` (89 l.) : détection pages d'erreur / marqueurs non-contenu
- `jsonld.py` (90 l.) : extraction structurée JSON-LD `JobPosting`
- `boards_api.py` (203 l.) : connecteurs API job boards
- `enterprise_ats.py` (174 l.) : extracteurs ATS entreprise
- `regional.py` (151 l.) : extracteurs plateformes régionales FR/EU
- `router.py` (174 l.) : table de routage + façade rétrocompatible

### 3. `backend/app/tasks/job_offers_collectors.py` (852 l.) → `backend/app/tasks/job_offers_collectors/`
- `__init__.py` (84 l.) : façade + constantes/patches compatibilité Airflow & tests
- `config.py` (54 l.) : configuration sources, budgets et paramètres collecte
- `queries.py` (155 l.) : génération et rotation des requêtes de recherche
- `crawl.py` (167 l.) : adaptateurs Crawl4AI / Tavily / JobSpy
- `enrich.py` (170 l.) : enrichissement descriptions et extraction structurée
- `persistence.py` (142 l.) : déduplication préventive et écriture MongoDB
- `pipeline.py` (145 l.) : orchestration collecte + point d'entrée synchrone Airflow

### 4. `backend/app/tasks/verify_job_offers.py` (846 l.) → `backend/app/tasks/verify_job_offers/`
- `__init__.py` (68 l.) : façade + `__all__` préservant imports DAG/crawler et cibles mock
- `html_checks.py` (178 l.) : parseur texte visible, JSON-LD `validThrough`, détection redirection/clôture
- `http_and_js.py` (231 l.) : check HTTP rapide niveau 1 et rendu JS headless Crawl4AI niveau 2
- `indeed_and_single.py` (156 l.) : lots API GraphQL Indeed + dispatch unitaire 2 niveaux
- `workflow.py` (255 l.) : priorité offres visibles, workers à budget temps, persistance et restauration faux-positifs

### 5. `backend/app/tasks/clean_job_offers.py` (644 l.) → `backend/app/tasks/clean_job_offers/`
- `__init__.py` (40 l.) : façade + `__all__`
- `protection.py` (105 l.) : garde candidatures liées (`applications`) et purge/soft-delete partagée
- `normalize_and_dedup.py` (212 l.) : normalisation champs en base, doublons exacts/similarité et filtre pré-insertion
- `purge_rules.py` (88 l.) : règles d'âge et d'offres malformées réutilisant `protection.py`
- `workflow.py` (147 l.) : orchestration nettoyage nocturne + point d'entrée synchrone Airflow

---

## Commandes de vérification

- Audit longueurs (`backend/app` : 0 fichier > 500 l., tous modules Lot 6 ≤ 255 l.)
- Lint Lot 6 : `cd backend && uv run ruff check app/services/normalization app/services/ats app/tasks/job_offers_collectors app/tasks/verify_job_offers app/tasks/clean_job_offers`
- Suite complète backend : `cd backend && uv run python -m pytest tests/ -q`
