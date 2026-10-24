---
task: Stocker dans job_offers.raw_data l'enregistrement d'origine de chaque source au lieu d'une copie des champs pré-normalisés
description: raw_data des job_offers = copie inutile des champs mappés ; source_record ajouté par map_jobboard_row (ligne jobspy BSON-safe, date_posted en ISO, cellules vides retirées), map_france_travail_offer (item API), extracteurs ATS greenhouse/lever/workable/smartrecruiters/indeed GraphQL et parse_jsonld_job_posting (payload JSON-LD) ; enrich_offers range raw_data par source {ats_platform: record}, repli llm_crawl ; merge_multidiffusion_offers fusionne les enregistrements par source (le plus récent l'emporte, ancien format à plat remplacé) pour les doublons multi-job boards et la re-collecte ; ré-extraction future (job_level, company_industry, salaire numérique, is_remote) sans recollecter
status: done
created: 2026-10-24
---

# Garder les données d'origine des sources dans `raw_data`

## Context
- Existing code checked :
  - unique écrivain : `backend/app/tasks/job_offers_collectors.py:384` (`"raw_data": offer`, le dict déjà mappé) ; aucun lecteur dans `backend/app`, `frontend/src` ni les tests. Les occurrences dans `routers/applications.py` sont une variable locale homonyme, sans rapport ;
  - mappers : `map_jobboard_row` (`sources/jobboards.py:44`, appelé `:84` sur `jobs.to_dict("records")`), `map_france_travail_offer` (`sources/france_travail.py:51`) ;
  - extracteurs zéro token (`services/ats/router.py`) : greenhouse `:71` (payload `data`), lever `:119` (`data`), workable `:167` (`j`), smartrecruiters `:206` (`data`), indeed GraphQL `:283` (`job`), `parse_jsonld_job_posting` `:338` (`item`). Le repli JSON-LD du crawler (`job_crawler/crawler1.py:874`) appelle `parse_jsonld_job_posting` et ajoute le dict tel quel (`:604`), donc il hérite du changement sans modification ;
  - `summarize_offers` (`job_offers_collectors.py:183`) réécrit `description` sur place : l'enregistrement d'origine garde la description brute ;
  - fusion : `merge_multidiffusion_offers` (`services/normalization.py:797`) part d'une copie du primaire. Aujourd'hui, le `raw_data` du secondaire est perdu, que la fusion se fasse dans le lot (`deduplicate_and_merge_offers:920`) ou à la sauvegarde (`save_offers_to_database:501`, où le primaire est le document en base). Conséquence : une offre déjà en base ne reçoit jamais de nouveau `raw_data` à la re-collecte. Autre appelant : `retroactive_dedup_job_offers.py:145`.
- Fresh info looked up :
  - probe dans le conteneur `jobtracker-backend` (pandas 2.3.3, pymongo 4.13.0) : `DataFrame.to_dict("records")` convertit déjà les scalaires numpy en types Python natifs. Seul `datetime.date` (`date_posted`) fait échouer `bson.encode` (`InvalidDocument`). Les NaN s'encodent mais n'apportent rien ;
  - colonnes jobspy disponibles : `job_level`, `job_function`, `company_industry`, `min_amount`/`max_amount`/`interval`/`currency`, `is_remote`, `work_from_home_type`, `skills`, `experience_range`, `company_num_employees`, etc. ;
  - MongoDB `mongo:latest` accepte les clés imbriquées avec `@` (JSON-LD `@type`, `@context`).
- Git status checked : dans le périmètre, `jobboards.py`, `normalization.py`, `job_offers_collectors.py`, `test_offer_sources.py`, `test_normalization_and_dedup.py`, `test_job_offers_pipeline.py` et `docs/JOB_INGESTION_AND_NORMALIZATION.md` portent des modifications non commitées. Elles viennent toutes des plans précédents de cette même session (HelloWork, dédup multi-job boards, type de contrat), aucune d'une autre session. `france_travail.py`, `ats/router.py` et `test_ats_parsers.py` sont propres.

## Simpler Alternative Considered
Un seul enregistrement par offre (celui de la collecte en cours, qui remplace le précédent). C'est plus simple, mais une offre publiée sur LinkedIn et Indeed ne garderait qu'une des deux sources. Or LinkedIn est la seule à donner `job_level`/`job_function`, et Indeed la seule à donner le salaire chiffré et `company_industry`. Le rangement par source ne coûte qu'une fusion de dictionnaires dans `merge_multidiffusion_offers`, et cette fonction doit être modifiée de toute façon pour que la re-collecte rafraîchisse `raw_data`. Retenu : rangement par source.

## Surgical Scope
- **Files touched** :
  - `backend/app/services/sources/jobboards.py` : nouveau `_source_record(row)`, clé `source_record` dans `map_jobboard_row` ;
  - `backend/app/services/sources/france_travail.py` : clé `source_record` (l'item API) dans `map_france_travail_offer` ;
  - `backend/app/services/ats/router.py` : clé `source_record` dans les dicts renvoyés par les 5 extracteurs API et par `parse_jsonld_job_posting` ; import `headers as api_headers` dans `extract_indeed_job` (élargissement approuvé, voir Notes) ;
  - `backend/app/tasks/job_offers_collectors.py` : `raw_data` = `{ats_platform or "llm_crawl": source_record or offer}` dans `enrich_offers` ;
  - `backend/app/services/normalization.py` : étape 13 de `merge_multidiffusion_offers` (union des enregistrements par source) et petit helper `_source_records` ;
  - `backend/tests/test_offer_sources.py`, `backend/tests/test_ats_parsers.py`, `backend/tests/test_normalization_and_dedup.py`, `backend/tests/test_job_offers_pipeline.py` ;
  - `docs/JOB_INGESTION_AND_NORMALIZATION.md` : sous-section « Données d'origine (`raw_data`) ».
- **Files NOT touched** : tous les autres. En particulier `backend/job_crawler/crawler1.py`, `backend/retroactive_dedup_job_offers.py`, `backend/app/routers/*` et tout `frontend/` (fichiers d'une autre session). Pas de modèle Pydantic à changer : `raw_data` n'est exposé nulle part.
- **Symbols replaced** (→ to delete before done) : aucun symbole. La valeur `"raw_data": offer` (`job_offers_collectors.py:384`) est remplacée sur place.
- **Symbols extended** (→ keep) : `map_jobboard_row`, `map_france_travail_offer`, `extract_greenhouse_job`, `extract_lever_job`, `extract_workable_job`, `extract_smartrecruiters_job`, `extract_indeed_job`, `parse_jsonld_job_posting`, `enrich_offers`, `merge_multidiffusion_offers`.

## Definition of Done
- [x] Build passes : `cd backend && uv run python -c "import app.tasks.job_offers_collectors, app.services.normalization, app.services.sources.jobboards, app.services.sources.france_travail, app.services.ats.router"` exit 0
- [x] Tests pass : `cd backend && uv run pytest tests/test_offer_sources.py tests/test_ats_parsers.py tests/test_normalization_and_dedup.py tests/test_job_offers_pipeline.py -q` exit 0
- [x] Ligne jobspy conservée et encodable : `date_posted` en ISO, NaN retirés, `job_level` gardé, `bson.encode` sans erreur. L'item France Travail est conservé tel quel. Commande : `cd backend && uv run pytest tests/test_offer_sources.py -q -k source_record` exit 0, au moins 2 tests sélectionnés
- [x] Payload conservé par chaque extracteur ATS (greenhouse, lever, workable, smartrecruiters, indeed) et par JSON-LD : `cd backend && uv run pytest tests/test_ats_parsers.py -q` exit 0 et `grep -c 'source_record' backend/tests/test_ats_parsers.py` >= 6
- [x] Fusion : un enregistrement par source, l'entrant l'emporte sur la même source, l'ancien format à plat est remplacé quand un vrai enregistrement arrive et conservé sinon. Commande : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k raw_data` exit 0, au moins 2 tests sélectionnés
- [x] Collecte : `enrich_offers` range `raw_data` par source (`{"linkedin": <ligne>}`, repli `llm_crawl`), sans clé `source_record` au premier niveau du document. La re-collecte d'une offre existante réécrit son `raw_data` dans le `$set`. Commande : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q -k raw_data` exit 0, au moins 2 tests sélectionnés
- [x] Données réelles (amendé, voir Notes) : `cd backend && uv run python -c "import bson; from app.services.sources.jobboards import _scrape_site; offers = [o for s in ('linkedin', 'indeed', 'hellowork') for o in _scrape_site(s, 'data scientist', 'Lyon')]; [bson.encode(o['source_record']) for o in offers]; print(len(offers), 'encodées')"` exit 0, au moins 1 offre encodée. Le probe lit le réseau mais n'écrit pas en base.
- [x] Doc à jour : `grep -c 'source_record' docs/JOB_INGESTION_AND_NORMALIZATION.md` >= 1
- [x] No dead code : `cd backend && uv run python -m pyflakes app/services/sources/jobboards.py app/services/sources/france_travail.py app/services/ats/router.py app/tasks/job_offers_collectors.py app/services/normalization.py` sans nouvel avertissement par rapport au baseline de la Phase 3
- [x] Type check : n/a — ni mypy ni ruff configurés dans `backend/pyproject.toml`
- [x] Manual check : n/a pour ce plan. Aucun rattrapage n'est possible pour les offres existantes (l'origine n'a jamais été stockée). Leur `raw_data` se remplit à la prochaine collecte qui les retrouve, en local puis en prod après le déploiement lancé par l'utilisateur.

## Steps
- [x] Step 1 : jobspy et France Travail.
  - `jobboards.py` : `_source_record(row)` garde les cellules non vides (via `_value`) et met les `date`/`datetime` en ISO ; `map_jobboard_row` ajoute `"source_record": _source_record(row)`.
  - `france_travail.py` : `"source_record": item`.
  - Tests `test_map_jobboard_row_keeps_source_record` (avec `bson.encode`) et `test_map_france_travail_offer_keeps_source_record`.
  - Vérification : `pytest tests/test_offer_sources.py -q`.
- [x] Step 2 : ATS et JSON-LD.
  - `"source_record"` dans les 6 dicts renvoyés : greenhouse `data`, lever `data`, workable `j`, smartrecruiters `data`, indeed `job`, JSON-LD `item`.
  - Une assertion `source_record` dans chacun des 5 tests de succès existants, plus `test_parse_jsonld_job_posting_keeps_source_record`.
  - `extract_indeed_job` : `from jobspy.indeed.constant import headers as api_headers` (élargissement approuvé, voir Notes).
  - Vérification : `pytest tests/test_ats_parsers.py -q`.
- [x] Step 3 : fusion.
  - `normalization.py` : `_source_records(offer)` renvoie `raw_data` seulement s'il est rangé par source (toutes les valeurs sont des dicts), `{}` sinon.
  - Étape 13 de `merge_multidiffusion_offers` : `{**primaire, **secondaire}`, appliqué seulement si le résultat est non vide, pour ne pas effacer un ancien `raw_data` sans le remplacer.
  - Tests `test_merge_raw_data_keeps_one_record_per_source` et `test_merge_raw_data_replaces_legacy_flat_copy`.
  - Vérification : `pytest tests/test_normalization_and_dedup.py -q -k raw_data`.
- [x] Step 4 : collecte.
  - `enrich_offers` : `"raw_data": {ats_platform or "llm_crawl": offer.get("source_record") or offer}`.
  - Tests `test_enrich_raw_data_keyed_by_source` (avec `normalize_role` mocké) et `test_save_offers_to_database_update_refreshes_raw_data` (document en base au format à plat, offre entrante `{"linkedin": …}`, `$set.raw_data` attendu).
  - Vérification : `pytest tests/test_job_offers_pipeline.py -q -k raw_data`.
- [x] Step 5 : documentation et données réelles.
  - Sous-section « Données d'origine (`raw_data`) » dans `docs/JOB_INGESTION_AND_NORMALIZATION.md` : format, clé par source, règle de fusion, absence de rattrapage.
  - Lancer le probe jobspy réel du DoD.
  - Vérification : le `grep -c` de la doc et le probe.
- [x] Step 6 (teardown) : aucun symbole remplacé. Scan des orphelins limité à `raw_data` : `"raw_data": offer` a disparu de `job_offers_collectors.py`, et `source_record` n'apparaît au premier niveau d'aucun document construit par `enrich_offers`. pyflakes sur les 5 fichiers de code. 0 orphelin attendu.

## Code Review
- Dead code removed : yes. Aucun symbole remplacé ; `"raw_data": offer` remplacé sur place (0 occurrence restante) ; pyflakes 0 ligne sur les 5 fichiers.
- Build status : pass (import des 5 modules, exit 0).
- Type errors : none (n/a, pas de type checker configuré).
- Unintended side effects : aucun dans le périmètre. Diff relu hunk par hunk : chaque ligne du plan trace à une étape. Les autres hunks de ces fichiers viennent de plans antérieurs (HelloWork, type de contrat, `use_web_search`). Effets voulus mais à connaître : `retroactive_dedup_job_offers.py` et le repli JSON-LD du crawler héritent de la fusion par source ; les clés `indeed` et `hellowork` sont partagées entre deux chemins (le plus récent l'emporte) ; France Travail API (`france_travail`) et JSON-LD (`francetravail`) restent deux clés distinctes, toutes deux conservées. Le correctif Indeed (`headers as api_headers`) n'existe qu'en jobspy 1.4.1 : le conteneur en 1.1.82 le casse jusqu'au rebuild. Hors périmètre : `tests/test_normalization.py::test_normalize_offer_fields` échoue à cause du plan type de contrat (voir Notes).
- Security surface touched : no. Aucun code d'auth, de validation d'entrée ou de requête construite par concaténation. On stocke des payloads tiers en base comme avant (seule la forme change) ; `raw_data` n'est exposé par aucune API.
- Verdict : ✅ DONE

## Execution Log
- 2026-10-24T13:26Z | claude-code | phase 3 | baseline | build 0, tests 126 passed 3 failed (Indeed `api_headers`, préexistant), sélections 0, pyflakes 0
- 2026-10-24T13:26Z | claude-code | step 1 | started
- 2026-10-24T13:27Z | claude-code | step 1 | done | `pytest tests/test_offer_sources.py -q` exit 0, 41 passed ; `-k source_record` 2 passed
- 2026-10-24T13:27Z | claude-code | step 2 | started
- 2026-10-24T13:28Z | claude-code | step 2 | done | `pytest tests/test_ats_parsers.py -q` exit 0, 20 passed (les 3 échecs Indeed de la baseline compris) ; `grep -c source_record` = 7
- 2026-10-24T13:28Z | claude-code | step 3 | started
- 2026-10-24T13:30Z | claude-code | step 3 | done | `pytest tests/test_normalization_and_dedup.py -q -k raw_data` exit 0, 2 passed
- 2026-10-24T13:30Z | claude-code | step 4 | started
- 2026-10-24T13:33Z | claude-code | step 4 | done | `pytest tests/test_job_offers_pipeline.py -q -k raw_data` exit 0, 2 passed
- 2026-10-24T13:33Z | claude-code | step 5 | started
- 2026-10-24T13:36Z | claude-code | step 5 | done | probe réel exit 0 (1er passage 75 encodées, 25 par site) ; `grep -c source_record` doc = 3
- 2026-10-24T13:36Z | claude-code | step 6 | started
- 2026-10-24T13:36Z | claude-code | step 6 | done | pyflakes 5 fichiers exit 0, 0 ligne ; `"raw_data": offer` 0 occurrence ; `source_record` absent du premier niveau (assertion de `test_enrich_raw_data_keyed_by_source`) ; 0 orphelin
- 2026-10-24T13:40Z | claude-code | close | done | DoD complet frais : build 0 ; tests 4 fichiers 136 passed ; source_record 2 ; ATS 20 passed, grep 7 ; fusion 2 ; collecte 2 ; doc 3 ; pyflakes 0 ligne ; probe réel exit 0, 50 encodées

## Notes
- Conventions lues : `CLAUDE.md` (identique à `AGENTS.md` et `GEMINI.md`, vérifié par `diff -q`).
- Baseline (Phase 3, avant toute modification) :
  - build exit 0 ; pyflakes exit 0, 0 ligne ;
  - tests : 126 passed, 3 failed, tous dans `test_ats_parsers.py` (`test_extract_indeed_job_success`, `test_extract_indeed_job_without_key_or_result`, `test_extract_ats_or_jsonld_offer_routes_indeed`). Erreur : `ImportError: cannot import name 'api_headers' from 'jobspy.indeed.constant'` ;
  - sélections `-k source_record` / `-k raw_data` : 0 test (exit 5) ; doc 0 ; `grep source_record` des tests ATS : 0.
- Élargissement approuvé par l'utilisateur (2026-10-24) : le plan HelloWork de cette session a passé jobspy de 1.1.82 à 1.4.1 dans le venv (pas encore déployé, le conteneur tourne en 1.1.82). Or jobspy 1.4.1 a renommé `api_headers` en `headers` : même clé d'API, même endpoint GraphQL, sans `Host` ni `indeed-locale` (l'extracteur pose déjà `indeed-co`). Correctif d'une ligne ajouté à l'étape 2.
- Amendement du DoD « Données réelles » : le probe tourne dans le venv local (jobspy 1.4.1, la version qui sera déployée) et non dans le conteneur (1.1.82), et il couvre aussi HelloWork. `bson.encode` ne touche pas la base.
- Taille : une ligne jobspy contient la description complète en markdown, qui est aussi stockée dans `description`. Ce doublon existe déjà aujourd'hui (`raw_data` copie l'offre). Avec deux ou trois sources par offre, compter quelques dizaines de Ko par document : bien en dessous de la limite BSON de 16 Mo.
- Les payloads ATS, l'item France Travail et l'objet JSON-LD sont déjà du JSON : encodables en BSON sans conversion.
- Clé `indeed` partagée par jobspy et l'extracteur GraphQL, clé `hellowork` partagée par jobspy et le JSON-LD HelloWork : le plus récent l'emporte, et les deux contiennent des données d'origine d'Indeed (ou de HelloWork).
- `retroactive_dedup_job_offers.py` profite de la même règle de fusion sans modification.
- Hors périmètre, découvert à l'étape 3 : `tests/test_normalization.py::test_normalize_offer_fields` échoue (`assert 'CDI' == 'CDI & Plein temps'`). Cause : le plan type de contrat (archivé) a remplacé le bloc `type_contrat` de `normalize_offer_fields` par `detect_contract_type`, qui ramène la valeur à `CDI`. Ce fichier ne figurait ni dans son DoD ni dans celui-ci, et `raw_data` n'y est pour rien. Non corrigé ici : à signaler à l'utilisateur.
- Probe réel (étape 5), venv local jobspy 1.4.1 : 1er passage 75 offres encodées (25 LinkedIn, 25 Indeed, 25 HelloWork). Au passage suivant, LinkedIn a répondu 429 (limite de débit) : `_scrape_site` l'a absorbé, et les autres sites suffisent au DoD. Champs conservés hors `description` : Indeed `min_amount` 10/25, `company_industry` 4/25 ; HelloWork `job_function` 25/25, `company_industry` 25/25, `experience_range`, `skills`, `min_amount` 9/25.
- Teardown : le premier contrôle `"raw_data": offer` utilisait un motif ast-grep invalide (erreur de parse, compte vide lu comme 0). Contrôle refait aussitôt avec `grep -c '"raw_data": offer,'` : 0, et la seule occurrence de `raw_data` (`job_offers_collectors.py:384`) est la nouvelle forme.
- Tests ajoutés sans service externe : DB et `normalize_role` mockés, aucun accès réseau. Les conteneurs n'ont pas été arrêtés, pour ne pas gêner les autres sessions. Le probe réel n'est pas dans la suite.
