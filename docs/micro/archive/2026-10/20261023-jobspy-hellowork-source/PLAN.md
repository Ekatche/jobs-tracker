---
task: Ajouter HelloWork comme source structurée via python-jobspy 1.4.1
description: HelloWork source structurée — bump python-jobspy 1.1.82 vers 1.4.1 (pyproject.toml, uv.lock, requirements.txt via uv pip compile, curl-cffi remplace tls-client, cffi 2, markdownify 1.2, numpy 2.5 sans pin), JOBBOARD_SITES + "hellowork" dans jobboards.py, scrape_jobs fetch_description remplace linkedin_fetch_description déprécié, échecs scraper lus dans jobs_df.attrs["errors"] (plus d'exception 429 LinkedIn), job_type multiple "internship, fulltime" mappé en Stage (filtre anti-stage map_jobboard_row), pytest test_offer_sources, docs JOB_INGESTION_AND_NORMALIZATION
status: done
created: 2026-10-23
---

# Ajouter HelloWork comme source structurée via python-jobspy 1.4.1

## Context
- Existing code checked:
  - `backend/app/services/sources/jobboards.py` : `JOBBOARD_SITES = ("indeed", "linkedin")` (L16) ; `_scrape_site` (L62-77) appelle `scrape_jobs(..., linkedin_fetch_description=True, ...)` ; `map_jobboard_row` (L43-59) mappe `job_type` par égalité stricte sur `JOB_TYPE_LABELS` ; `fetch_jobboard_offers` (L80-96) isole les sites par `gather(return_exceptions=True)` et filtre `type_contrat == "Stage"` hors contrat stage ou alternance.
  - Appel unique : `backend/app/services/sources/__init__.py:129`. Le passage Tavily LinkedIn (passe 3) ne dépend pas d'une exception jobspy.
  - Tests : `backend/tests/test_offer_sources.py` L197-244 (`tests_for` sur jobboards.py : 3 tests directs + `test_clean_city_label`).
  - Dépendances : `backend/pyproject.toml:34` `python-jobspy>=1.1.82`, `:77` override `numpy>=2.1` ; `backend/requirements.txt` généré par `uv pip compile pyproject.toml -o requirements.txt` (L418 `numpy==1.26.3`, L667 `python-jobspy==1.1.82`, L822 `tls-client==1.0.1`) ; `Dockerfile` et `Dockerfile.airflow` installent `requirements.txt` avec `--override numpy>=2.1`.
  - Conteneurs locaux : backend et airflow en numpy 2.5.3, Python 3.12.15, jobspy 1.1.82, cffi 1.17.1. L'override Docker prend déjà la dernière numpy.
  - Plan passé : `archive/2026-09/20260925-collect-sources-and-geo-filter` (pin numpy de jobspy 1.1.82, override).
- Fresh info looked up: wheel python-jobspy 1.4.1 décompressé dans le scratchpad et lu.
  - `Site.HELLOWORK = "hellowork"`.
  - `scrape_jobs(fetch_description=...)` : `linkedin_fetch_description` émet un DeprecationWarning.
  - `Scraper.fail()` ne lève plus d'exception. L'erreur est rangée dans `jobs_df.attrs["errors"][site]`.
  - `JobPost._row` joint une liste `job_type` par `", "` et aplatit `location` en `"Lyon 6e, 69, France"`.
  - Une carte HelloWork « Stage » plein temps donne `job_type = "internship, fulltime"` : vérifié par instanciation de `JobPost`.
  - `Alternance` est mappée en `INTERNSHIP`.
  - Sonde réelle 1.4.1, « data engineer » / « Lyon, France » :
    - HelloWork : 5 offres en 1,4 s, descriptions de 830 à 5 304 caractères, `errors={}` ;
    - Indeed : 5 offres en 0,5 s ;
    - LinkedIn : 0 offre, `errors={'linkedin': 'response status code 429 (blocked: use a proxy)'}`, sans exception.
  - Dry-run :
    - `uv lock --upgrade-package python-jobspy --dry-run` : jobspy 1.4.1, ajoute curl-cffi 0.16.3, cffi 1.17.1 vers 2.1.1, markdownify 0.13.1 vers 1.2.3, retire tls-client ;
    - `uv pip compile --upgrade-package python-jobspy` vers un fichier du scratchpad : mêmes changements, plus numpy 1.26.3 vers 2.5.4 (jobspy ne pinne plus numpy) ;
    - cffi n'est utilisé que par cryptography 45.0.2, markdownify que par jobspy.
- Git status checked: arbre sale hors périmètre (`applications.py`, `job_offers.py`, `interview_prep.py`, `verify_job_offers.py`, `test_verify_job_offers.py`, `test_interview_prep_api.py`, frontend, docs). Ces fichiers viennent d'autres sessions, aucun n'est dans le périmètre. Seul `docs/JOB_INGESTION_AND_NORMALIZATION.md` porte déjà des modifications non commitées du plan verify (section liveness et limites). Les éditions de ce plan portent sur d'autres lignes et ne touchent pas ces modifications.

## Simpler Alternative Considered
- Ajouter seulement `"hellowork"` à `JOBBOARD_SITES` sans bump : impossible, `Site.HELLOWORK` n'existe pas en 1.1.82.
- Bumper sans traiter `attrs["errors"]` : un 429 LinkedIn ou un blocage HelloWork deviendrait silencieux. Le log n'afficherait que « 0 offres », sans cause.
- Bumper sans corriger `job_type` multiple : les stages HelloWork passeraient le filtre anti-stage d'une recherche en CDI.
- Retirer HelloWork de la passe 1 Tavily (6 résultats, un appel « advanced » par requête) : écarté de ce plan. On mesure d'abord le recouvrement, voir Notes.

## Surgical Scope
- **Files touched**:
  - `backend/pyproject.toml` (plancher `python-jobspy>=1.4.1`)
  - `backend/uv.lock` (régénéré)
  - `backend/requirements.txt` (régénéré)
  - `backend/app/services/sources/jobboards.py`
  - `backend/tests/test_offer_sources.py`
  - `docs/JOB_INGESTION_AND_NORMALIZATION.md` (section 2 jobspy, passe 3 Tavily, section numpy override, puce jobspy des limites)
- **Files NOT touched**:
  - `backend/Dockerfile`, `backend/Dockerfile.airflow` : l'override `numpy>=2.1` reste inoffensif, numpy 2.5.4 le satisfait ;
  - `backend/app/services/sources/__init__.py`, `geo.py` ;
  - passes Tavily (crew, `job_offers_collectors.py`) ;
  - tous les fichiers déjà modifiés par d'autres sessions.
- **Symbols replaced** (→ to delete before done): argument `linkedin_fetch_description=True` de `scrape_jobs` dans `_scrape_site`, remplacé par `fetch_description=True`
- **Symbols extended** (→ keep): `JOBBOARD_SITES`, `_scrape_site`, `map_jobboard_row`, `JOB_TYPE_LABELS` (inchangé), docstring du module `jobboards.py`

## Definition of Done
- [x] Build passes (lock cohérent) : `cd backend && uv lock --locked` → exit 0
- [x] jobspy 1.4.1 dans le lock : `grep -A1 'name = "python-jobspy"' backend/uv.lock | grep -c 'version = "1.4.1"'` → 1
- [x] jobspy 1.4.1 dans requirements : `grep -c '^python-jobspy==1.4.1$' backend/requirements.txt` → 1
- [x] tls-client retiré : `grep -c '^tls-client==' backend/requirements.txt` → 0
- [x] Dépendances transitives importables : `cd backend && uv run python -c "from cryptography.fernet import Fernet; Fernet(Fernet.generate_key()).encrypt(b'x'); import jose, curl_cffi, jobspy, numpy; from jobspy.model import Site; assert Site.HELLOWORK.value == 'hellowork'; print('ok', numpy.__version__)"` → `ok 2.x`
- [x] Tests pass : `cd backend && uv run pytest tests/test_offer_sources.py -q` → 0 failed, dont les 2 nouveaux tests
- [x] HelloWork activé : `grep -c '"hellowork"' backend/app/services/sources/jobboards.py` → ≥ 1
- [x] No dead code : `grep -rc 'linkedin_fetch_description' backend/app` → 0 partout
- [x] Type check: n/a — pas de mypy/pyright configuré pour le backend
- [x] Manual check (sonde réseau, hors suite par défaut) : `cd backend && uv run python -c "from app.services.sources.jobboards import _scrape_site; r = _scrape_site('hellowork', 'Data Engineer', 'Lyon'); print(len(r), sum(bool(o['description']) for o in r), {o['localisation'] for o in r})"` → au moins 1 offre, au moins 1 description non vide, localisations lyonnaises

## Steps
- [x] Step 1: Dépendances. Dans `backend/pyproject.toml`, passer `python-jobspy>=1.1.82` à `python-jobspy>=1.4.1`. Puis `cd backend && uv lock --upgrade-package python-jobspy` et `uv pip compile pyproject.toml -o requirements.txt --upgrade-package python-jobspy`. Vérifier avec `git diff --stat backend/requirements.txt backend/uv.lock` : seuls python-jobspy, curl-cffi, cffi, markdownify, numpy et tls-client changent, plus les commentaires `# via`. Vérifier aussi les 5 premières lignes de DoD.
- [x] Step 2: `_scrape_site` dans `jobboards.py`.
  - Remplacer `linkedin_fetch_description=True` par `fetch_description=True`.
  - Après l'appel, si `jobs.attrs.get("errors", {}).get(site)`, émettre `logger.warning` avec le site, le rôle et l'erreur, puis renvoyer quand même les lignes reçues (résultats partiels conservés).
  - Ajouter `"hellowork"` à `JOBBOARD_SITES`.
  - Mettre à jour la docstring du module : Indeed, LinkedIn, HelloWork ; un échec jobspy arrive dans `attrs["errors"]`, pas en exception.
  - Ajouter `test_scrape_site_passes_fetch_description_and_logs_site_errors` : monkeypatch de `jobspy.scrape_jobs` par une fonction qui renvoie un `pandas.DataFrame` d'une ligne avec `attrs["errors"] = {"linkedin": "429"}`. Vérifier que le kwarg `fetch_description=True` est passé sans `linkedin_fetch_description`, que la ligne est mappée et qu'un warning contenant « 429 » est émis (`caplog`).
  - Vérification : `cd backend && uv run pytest tests/test_offer_sources.py -q`.
- [x] Step 3: `map_jobboard_row`.
  - Calculer `type_contrat` sur la valeur `job_type` découpée par `","`, chaque élément nettoyé par `strip()`. Prendre le premier élément connu de `JOB_TYPE_LABELS`, sinon `""`.
  - Ajouter `test_map_jobboard_row_multi_job_type_keeps_internship` : `"internship, fulltime"` donne `"Stage"`, `"fulltime, parttime"` donne `"Temps partiel"`, `"fulltime"` donne `""`.
  - Vérification : `cd backend && uv run pytest tests/test_offer_sources.py -q`.
- [x] Step 4: Sonde réelle. Lancer la commande « Manual check » du DoD et consigner le résultat dans Notes : nombre d'offres, descriptions, localisations. Si HelloWork renvoie 0 offre avec une erreur dans le warning, mettre `status: blocked` et noter l'erreur.
- [x] Step 5: Doc `docs/JOB_INGESTION_AND_NORMALIZATION.md`.
  - Section 2 : titre « jobspy (Indeed + LinkedIn + HelloWork) », ligne HelloWork, dépendance `python-jobspy>=1.4.1`, risque : erreurs par site lues dans `attrs["errors"]`.
  - Passe 3 : retirer « (si jobspy 429) », la passe tourne toujours.
  - Section numpy override : jobspy 1.4.1 ne pinne plus numpy ; l'override Docker `numpy>=2.1` est conservé, inoffensif.
  - Puce jobspy des « Limites connues » : ajouter HelloWork.
  - Ne pas toucher aux lignes liveness déjà modifiées.
  - Vérification : `grep -c 'HelloWork' docs/JOB_INGESTION_AND_NORMALIZATION.md` ≥ 4 et `grep -c 'si jobspy 429' docs/JOB_INGESTION_AND_NORMALIZATION.md` → 0.
- [x] Step 6 (teardown): scan d'orphelins borné aux symboles remplacés.
  - `grep -rc 'linkedin_fetch_description' backend/app` → 0 partout.
  - `grep -rn 'tls_client' backend/app` → aucune ligne : tls-client n'était importé que par jobspy 1.1.82.
  - Confirmer 0 orphelin, puis relancer tout le DoD.

## Code Review
- Dead code removed: yes. `linkedin_fetch_description` n'apparaît plus dans `backend/app`. `tls-client` est sorti de `requirements.txt` et de `uv.lock`, et aucun import `tls_client` ne reste dans `backend/app`.
- Build status: pass. `uv lock --locked` exit 0, imports transitifs OK (cryptography avec cffi 2.1.1, jose, curl_cffi, jobspy, numpy 2.2.6 dans le venv local).
- Type errors: none. Pas de type checker configuré. Les diagnostics IDE « Cannot find module jobspy » viennent de l'interpréteur conda de l'IDE, pas du venv uv, et existaient déjà avant ce plan.
- Unintended side effects:
  - `test_fetch_jobboard_offers_isolates_site_failure_and_drops_internships` a été adapté au troisième site : une URL par site, voir Notes.
  - Chaque collecte interroge désormais aussi HelloWork : ~12 s de plus par requête, en parallèle d'Indeed et LinkedIn via `asyncio.gather`.
  - `requirements.txt` passe numpy de 1.26.3 à 2.5.4. Effet nul en Docker : l'override `numpy>=2.1` installait déjà la dernière 2.x.
- Security surface touched: yes, chaîne de dépendances réseau (curl-cffi remplace tls-client). `get_semgrep_supply_chain_findings` ne fait que relire les anciens scans de la plateforme et n'analyse pas les nouvelles versions. À la place, `uvx pip-audit --no-deps --disable-pip` sur python-jobspy 1.4.1, curl-cffi 0.16.3, cffi 2.1.1, markdownify 1.2.3 et numpy 2.5.4 renvoie « No known vulnerabilities found ». Aucun code d'auth, de secret ou d'entrée utilisateur n'est touché.
- Verdict: ✅ DONE

## Execution Log
- 2026-10-23T20:08Z | claude-code | preflight | done | baseline DoD loggée dans Notes
- 2026-10-23T20:08Z | claude-code | step 1 | started
- 2026-10-23T20:08Z | claude-code | step 1 | done | `uv lock --locked` exit 0 ; lock 1.4.1 → 1 ; requirements 1.4.1 → 1 ; tls-client → 0 ; imports `ok 2.2.6` ; diff : cffi, curl-cffi, markdownify, numpy (requirements seul), python-jobspy, tls-client
- 2026-10-23T20:08Z | claude-code | step 2 | started
- 2026-10-23T20:10Z | claude-code | step 2 | done | `pytest tests/test_offer_sources.py -q` exit 0, 38 passed (nouveau test inclus) ; `linkedin_fetch_description` → 0 dans app
- 2026-10-23T20:10Z | claude-code | step 3 | started
- 2026-10-23T20:11Z | claude-code | step 3 | done | `pytest tests/test_offer_sources.py -q` exit 0, 39 passed ; `-k multi_job_type` inclus
- 2026-10-23T20:11Z | claude-code | step 4 | started
- 2026-10-23T20:11Z | claude-code | step 4 | done | sonde `_scrape_site('hellowork', 'Data Engineer', 'Lyon')` : 25 offres, 25 descriptions, 12 s
- 2026-10-23T20:11Z | claude-code | step 5 | started
- 2026-10-23T20:12Z | claude-code | step 5 | done | `grep -c 'HelloWork'` → 5 ; `grep -c 'si jobspy 429'` → 0
- 2026-10-23T20:12Z | claude-code | step 6 | started
- 2026-10-23T20:13Z | claude-code | step 6 | done | `linkedin_fetch_description` 0 dans backend/app ; `tls_client` 0 ligne ; DoD complet relancé vert
- 2026-10-23T20:13Z | claude-code | close-out | done | DoD : lock exit 0, 1.4.1 lock+requirements, tls-client 0, imports ok 2.2.6, 39 passed, hellowork 1, dead 0, sonde 25/25 ; pip-audit 5 paquets : aucune vulnérabilité

## Notes
- Conventions lues : `CLAUDE.md` (identique à `AGENTS.md` et `GEMINI.md`), `.cursorrules` (bloc code-review-graph). Pas de fichier de convention sous `backend/`.
- Baseline DoD (2026-10-23T20:08Z, avant tout changement) : `uv lock --locked` exit 0 ; lock 1.4.1 → 0 ; requirements 1.4.1 → 0 ; tls-client → 1 ; imports → exit 1 `ModuleNotFoundError: No module named 'curl_cffi'` ; `pytest tests/test_offer_sources.py` → 37 passed ; `"hellowork"` → 0 ; `linkedin_fetch_description` → 1 (jobboards.py). Rouge attendu partout sauf lock et tests.
- Déploiement (hors plan) : le prod ne prend jobspy 1.4.1 qu'après reconstruction des images backend **et** airflow, qui installent `requirements.txt`. À la première collecte, vérifier dans les logs Airflow les lignes `📥 hellowork: N offres` et l'absence de warning HelloWork.
- Recouvrement Tavily : la passe 1 Tavily interroge encore HelloWork (6 résultats, un appel « advanced » par requête). `drop_known_urls` écarte déjà les URL HelloWork couvertes par jobspy avant le crawl, ce qui évite de payer le crawl et le LLM sur ces doublons. Le retrait de HelloWork de la passe 1 Tavily, qui économiserait un appel « advanced » par requête, se décidera après une semaine de mesure : part des URL Tavily HelloWork déjà couvertes par jobspy.
- Localisation : HelloWork donne `"Lyon 6e, 69, France"`. `clean_city_label` donne « Lyon 6e », puis `normalize_city` le ramène à « Lyon ». Le filtre géo est en fail-open si la commune n'est pas résolue, donc pas de perte. Aucun changement prévu.
- Délai : HelloWork attend 2 à 5 s entre pages. Pour 25 résultats, une page suffit en principe, plus une requête de détail par offre (`fetch_description`).
- LinkedIn depuis l'IP locale : 429 à la sonde du 2026-10-23. Avec 1.4.1, ce blocage n'est plus une exception : il devient un warning grâce au step 2.
- Step 2, échec puis correction (tentative 1) : `test_fetch_jobboard_offers_isolates_site_failure_and_drops_internships` échouait (`['u1', 'u1'] == ['u1']`). Son faux `_scrape_site` renvoyait la même URL pour chaque site hors LinkedIn, donc le troisième site la dupliquait. Correction : une URL par site dans le faux (`f"{site}-cdi"`), assertion explicite `["indeed-cdi", "hellowork-cdi"]`. Fichier dans le périmètre.
- Sonde step 4 (2026-10-23, IP locale) : 25 offres en 12 s. Les 25 ont une description, de 830 à 7 740 caractères. Localisations : Lyon, Lyon 2e, 3e, 6e, 7e, 9e et Rillieux-la-Pape (à ~10 km, dans le rayon). `type_contrat` vaut `''` ou `'Stage'`. Les stages seront écartés d'une recherche en CDI par le filtre de `fetch_jobboard_offers`.
