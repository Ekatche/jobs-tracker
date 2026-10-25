# Secteurs et tailles d'entreprise — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** chaque offre porte `sector` et `company_size` (taxonomie du §3.1), et le candidat peut choisir ses secteurs et ses tailles d'entreprise dans « Ciblage & préférences ».

**Architecture :** un module unique `app/services/company_profiles.py` porte la taxonomie, le mapping natif depuis `raw_data`, la taille par l'API Recherche d'entreprises, le repli LLM et le cache `company_profiles`, derrière une classe `CompanyResolver`. `save_offers_to_database` l'appelle sur chaque offre insérée ou fusionnée, sans jamais bloquer la sauvegarde. Deux scripts (rattrapage du stock, migration de `preferred_industries`) réutilisent les mêmes fonctions. L'UI ajoute une section de chips.

**Tech Stack :** FastAPI, Motor (MongoDB), Pydantic v2, httpx (`AsyncClient`, `MockTransport` en test), LiteLLM (`acompletion`), pytest (`asyncio_mode = auto`), Next.js 15 / React / TypeScript, Tailwind.

**Spec :** `docs/superpowers/specs/2026-10-24-matching-hybrid-scoring-and-sectors-design.md`, étape 2 du Lot 1 (§7). Sections utiles : §3.1 (taxonomie), §3.2 (`company_profiles`, `CandidatePreferences`, migration), §4.1 (ordre de résolution), §5.1 (UI), §6.4 (tests attendus).

## Global Constraints

- Secteurs (clés exactes) : `tech_it`, `finance_insurance`, `healthcare_pharma`, `consulting_services`, `retail_ecommerce`, `industry_aerospace`, `energy_environment`, `media_communication`, `public_education`, `construction_realestate`, `logistics_transport`, `agri_food`, plus `other`. `other` est une valeur de sortie de l'enrichissement, jamais proposée ni acceptée comme préférence.
- Tailles (clés exactes) : `startup_tpe` (< 20 salariés), `pme` (20 - 249), `eti` (250 - 4 999), `grand_groupe` (5 000+).
- Règle ESN (§3.1, telle quelle dans le prompt) : « une ESN ou un cabinet de conseil IT relève de `consulting_services`, même si son code NAF est en 62.0x ; `tech_it` est réservé aux entreprises qui vendent leur propre produit ou plateforme ».
- Une valeur `sector` ou `company_size` connue n'est jamais écrasée par `None`, ni sur l'offre ni dans `company_profiles`.
- Sources : `sector_source` ∈ `native_source`, `llm_inferred`, `manual` ; `size_source` ∈ `native_source`, `api_entreprises`, `llm_inferred`, `manual`. `manual`, `native_source` et `api_entreprises` ne sont jamais remplacés par l'enrichissement automatique ; `llm_inferred` est remplacé par une valeur native.
- Le code NAF n'est pas utilisé pour le secteur (§4.1, point 3).
- API Recherche d'entreprises : `https://recherche-entreprises.api.gouv.fr/search`, limite documentée 7 requêtes/s par IP, 429 avec `Retry-After` au-delà ; `User-Agent` explicite.
- Repli LLM : modèle `os.getenv("SUMMARY_MODEL", "gpt-5-nano")`, même forme d'appel que `summarize_ats_offer_description` (`job_offers_collectors.py:124-180`). Pas de suivi `api_usage` : la dépense est globale, pas imputable à un utilisateur. Tout appel réel (rattrapage `--apply`) exige l'accord explicite de l'utilisateur sur la dépense.
- Rien de propre à un utilisateur n'est écrit dans `job_offers`.
- Production : aucune écriture par l'implémenteur. Les deux scripts se lancent en lecture d'abord ; `--apply` en prod revient à l'utilisateur.
- Tests : sans réseau ni Mongo. Commande : `cd backend && uv run pytest tests/<fichier> -v`. Frontend : `cd frontend && npm run lint && npm run build`.
- Coordination : prévenir la session `job-tracker-c5` avant de modifier `backend/app/models.py` et le frontend. Ne jamais toucher aux chemins STAR (`interview_prep_service.py`, `routers/interview_prep.py`, `star_*`, `frontend/src/components/interview/*`, `frontend/src/types/interview.ts`, `frontend/src/lib/api.ts`).
- Commits : seulement si l'utilisateur les a autorisés pour cette exécution, `git add` avec des chemins explicites.
- Écart assumé avec la spec : `response_format={"type": "json_object"}` + validation en code, au lieu d'un « JSON schema contraint ». Raison : c'est la forme déjà utilisée par le projet (`cv_parser`, `evaluator`, `role_normalizer`) et elle reste portable si `SUMMARY_MODEL` change de fournisseur.
- Écart assumé avec la spec §5.1 : la sauvegarde des secteurs et tailles ne déclenche pas `rematch_user` à cette étape. Le rattachement actuel n'utilise que `target_roles`, `locations` et `remote_policy` : un rematch sur ces champs ne changerait rien. Le déclenchement est ajouté à l'étape 4 (rematch par score), quand le secteur pèse.
- Pas de classe Pydantic `CompanyProfile` (elle n'aurait aucun utilisateur) : le schéma du §3.2 est décrit dans la docstring du module.

## Review Focus

1. **Premier passage d'ingestion après le déploiement** : les offres déjà en base qui réapparaissent passent par la branche fusion et déclenchent la résolution pour des centaines d'entreprises. La tâche Airflow a `execution_timeout=60 min` (`airflow/dags/collect_job_offers.py:49`). Le repli LLM est plafonné par lot (`DEFAULT_MAX_LLM_CALLS = 50`) ; le reste passe au rattrapage ou à l'ingestion suivante. Test : Task 3, `test_resolver_stops_calling_llm_after_budget`.
2. **Nom d'entreprise générique** (« Confidentiel », « Entreprise confidentielle », « Non spécifié », vide) : un profil partagé appliquerait le secteur d'une offre à toutes les autres. Aucune lecture ni écriture de cache, aucun appel API ou LLM ; seules les valeurs natives de l'offre sont appliquées. Test : Task 3, `test_resolver_skips_placeholder_company`.
3. **Échec de l'enrichissement pendant la sauvegarde** (Mongo sans `company_profiles`, API ou LLM en panne, base mockée par un `dict` dans les tests existants) : l'offre est quand même insérée ou mise à jour. Test : Task 4, `test_save_offers_survives_company_resolver_failure`.
4. **Réponse LLM inexploitable** (texte non JSON, valeur hors taxonomie comme `"fintech"`, clé manquante, exception) : `None` pour le champ concerné, aucune exception. Tests : Task 3, `test_infer_rejects_values_outside_taxonomy`, `test_infer_returns_none_on_invalid_json`.
5. **Offre fusionnée dont l'enregistrement natif a été remplacé** (JSON-LD HelloWork qui écrase l'enregistrement jobspy porteur de `company_industry`) : le `sector` déjà stocké sur l'offre est conservé. Test : Task 4, `test_save_offers_update_keeps_existing_sector`.

---

## Structure des fichiers

| Fichier | Rôle |
|---|---|
| `backend/app/services/company_profiles.py` (créé) | Taxonomie, mapping natif, API, repli LLM, `CompanyResolver` |
| `backend/app/database.py` (modifié) | `create_company_profiles_indexes` |
| `backend/main.py` (modifié) | Appel de l'index dans le lifespan |
| `backend/app/tasks/job_offers_collectors.py` (modifié) | Résolution dans `save_offers_to_database` |
| `backend/app/models.py` (modifié) | `CandidatePreferences.preferred_company_sizes` |
| `backend/scripts/backfill_company_attributes.py` (créé) | Rattrapage du stock |
| `backend/scripts/migrate_preferred_industries.py` (créé) | Migration de `preferred_industries` |
| `frontend/src/types/coverLetter.ts` (modifié) | Type `preferred_company_sizes` |
| `frontend/src/components/profile/TargetingPreferencesSection.tsx` (modifié) | Section « Secteurs d'activité & Taille d'entreprise » |
| `backend/tests/test_company_profiles.py` (créé), `test_backfill_company_attributes.py` (créé), `test_migrate_preferred_industries.py` (créé), `test_database_indexes.py`, `test_job_offers_pipeline.py`, `test_candidate_preferences.py` (modifiés) | Tests |

---

### Task 1 : Taxonomie et mapping natif

**Files:**
- Create: `backend/app/services/company_profiles.py`
- Test: `backend/tests/test_company_profiles.py`

**Interfaces:**
- Produces :
  - `SECTORS: tuple[str, ...]` (13 clés, `other` en dernier), `PREFERENCE_SECTORS` (les 12 sans `other`), `COMPANY_SIZES: tuple[str, ...]` (4 clés, ordre croissant).
  - `map_sector_label(label: Optional[str]) -> Optional[str]`
  - `map_indeed_size(label: Optional[str]) -> Optional[str]`
  - `extract_native_attributes(raw_data: Optional[dict]) -> dict` avec les clés `sector`, `company_size`, `sector_label` (libellé brut du site, transmis au LLM quand il ne se mappe pas).

- [ ] **Step 1 : écrire les tests qui échouent**

`test_map_sector_label` paramétré sur les libellés observés en prod (sondes HelloWork et Indeed du 2026-10-24) :

| Libellé | Attendu |
|---|---|
| `Services aux Entreprises` | `consulting_services` |
| `Secteur informatique, ESN` | `None` |
| `Santé, Social, Association` | `healthcare_pharma` |
| `Service public hospitalier` | `healthcare_pharma` |
| `Industrie Pharmaceutique, Biotechn., Chimie` | `healthcare_pharma` |
| `Immobilier` | `construction_realestate` |
| `Banque, Assurance, Finance` | `finance_insurance` |
| `Services aux Personnes, Particuliers` | `other` |
| `Tourisme, Hôtellerie, Loisirs` | `other` |
| `Enseignement, Formation` | `public_education` |
| `Service public d'état` | `public_education` |
| `Industrie high-tech, Telecom` | `tech_it` |
| `Retail` | `retail_ecommerce` |
| `Aerospace And Defense` | `industry_aerospace` |
| `Industrial Manufacturing` | `industry_aerospace` |
| `Real Estate` | `construction_realestate` |
| `Banks And Financial Services` | `finance_insurance` |
| `Insurance` | `finance_insurance` |
| `Agriculture And Extraction` | `agri_food` |
| `Consumer Goods And Services` | `None` |
| `Media News And Publishing` | `media_communication` |
| `Consulting And Business Services` | `consulting_services` |
| `Health Care` | `healthcare_pharma` |
| `Information Technology` | `None` |
| `Hospitality` | `other` |
| `Transformation digitale` | `None` |
| `Fintech` | `finance_insurance` |
| `None`, `""` | `None` |

`test_map_indeed_size` paramétré : `"1 to 10"` → `startup_tpe` ; `"51 to 200"` → `pme` ; `"501 to 1,000"` et `"1,001 to 5,000"` → `eti` ; `"5,001 to 10,000"` et `"10,000+"` → `grand_groupe` ; `"11 to 50"`, `"201 to 500"`, `"Decline to state"`, `None` → `None`.

`test_extract_native_attributes` :
- `{"hellowork": {"company_industry": "Immobilier"}}` → `{"sector": "construction_realestate", "company_size": None, "sector_label": "Immobilier"}` ;
- `{"indeed": {"company_industry": "Insurance", "company_num_employees": "10,000+"}}` → `finance_insurance`, `grand_groupe` ;
- `{"hellowork": {"company_industry": "Secteur informatique, ESN"}}` → `sector` `None`, `sector_label` `"Secteur informatique, ESN"` ;
- `{"linkedin": {"job_level": "Senior"}}`, `{}`, `None` → les trois clés à `None`.

- [ ] **Step 2 : lancer les tests, constater l'échec**

Run : `cd backend && uv run pytest tests/test_company_profiles.py -v`
Attendu : FAIL, `ModuleNotFoundError: app.services.company_profiles`.

- [ ] **Step 3 : implémenter**

`map_sector_label` : libellé replié (minuscules, sans accents, comme `_fold_ascii` de `normalization.py`), puis règles ordonnées, la première qui trouve un mot-clé l'emporte. Un mot-clé correspond en début de mot (`re.search(r"\b" + re.escape(kw), label)`), ce qui évite « formation » dans « information » ou « transformation ». L'ordre est porteur de sens :

1. `healthcare_pharma` : `pharma`, `biotech`, `sante`, `health`, `hopital`, `hospitalier`, `medic`
2. `finance_insurance` : `banque`, `bank`, `assurance`, `insurance`, `financ`, `fintech`
3. `None` (règle ESN, le LLM tranche entre `tech_it` et `consulting_services`) : `informatique`, `information technology`
4. `tech_it` : `telecom`, `logiciel`, `software`, `internet`, `tech`, `saas`
5. `consulting_services` : `conseil`, `consulting`, `audit`, `services aux entreprises`, `business services`
6. `retail_ecommerce` : `retail`, `commerce`, `ecommerce`, `distribution`, `luxe`
7. `agri_food` : `agro`, `agricult`, `aliment`, `food`
8. `energy_environment` : `energ`, `environnement`, `environment`, `utilities`, `cleantech`
9. `industry_aerospace` : `aero`, `defense`, `defence`, `automobile`, `automotive`, `industri`
10. `media_communication` : `media`, `communication`, `publicite`, `advertising`, `edition`, `publishing`, `divertissement`, `entertainment`, `jeux video`, `video game`
11. `public_education` : `enseignement`, `education`, `formation`, `recherche`, `research`, `public`, `administration`, `government`
12. `construction_realestate` : `immobilier`, `real estate`, `construction`, `btp`, `batiment`, `urbanisme`
13. `logistics_transport` : `transport`, `logisti`, `supply chain`
14. `other` : `tourisme`, `hotel`, `hospitality`, `restaura`, `services aux personnes`

`map_indeed_size` : virgules retirées, puis table exacte des libellés du Step 1. Les tranches à cheval sur un seuil (`11 to 50`, `201 to 500`) renvoient `None`.

`extract_native_attributes` : parcourt toutes les valeurs dict de `raw_data` et prend le premier `company_industry` et le premier `company_num_employees` non vides. France Travail (`secteurActiviteLibelle`, `trancheEffectifEtab`) est volontairement absent : l'API est en panne depuis le 2026-10-04 et le format réel n'a jamais été observé.

- [ ] **Step 4 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_company_profiles.py -v`
Attendu : PASS.

- [ ] **Step 5 : commit** (si autorisé) — `feat(companies): add sector and size taxonomy with native mapping`

---

### Task 2 : Taille par l'API Recherche d'entreprises

**Files:**
- Modify: `backend/app/services/company_profiles.py`
- Test: `backend/tests/test_company_profiles.py`

**Interfaces:**
- Consumes : `company_match_strength` (`app/services/normalization.py:94`).
- Produces : `async def lookup_company_size(company: str, client: Optional[httpx.AsyncClient] = None) -> tuple[Optional[str], Optional[str]]`, qui renvoie `(company_size, siren)`, ou `(None, None)` si rien n'est retenu.

- [ ] **Step 1 : écrire les tests qui échouent**

Tous avec `httpx.AsyncClient(transport=httpx.MockTransport(handler))`, sans réseau. Réponse type : `{"results": [{"nom_complet": "SANOFI (SANOFI)", "sigle": None, "siren": "395030844", "categorie_entreprise": "GE", "tranche_effectif_salarie": "11"}]}`.

- `test_lookup_size_grand_groupe_from_category` : `"Sanofi"` → `("grand_groupe", "395030844")` (la tranche `11` du siège est ignorée pour une `GE`).
- `test_lookup_size_eti` : catégorie `ETI` → `eti`.
- `test_lookup_size_pme_split_by_tranche` : `PME` + `"11"` → `startup_tpe` ; `PME` + `"12"` → `pme` ; `PME` + `None` ou `"NN"` → `(None, None)`.
- `test_lookup_size_rejects_name_mismatch` (§6.4) : offre `"Orange"`, résultat `nom_complet` `"ORANGE BANK"` → `(None, None)`.
- `test_lookup_size_accepts_sigle_match` : offre `"BNP"`, `nom_complet` `"BNP PARIBAS (BNP)"`, `sigle` `"BNP"` → valeur retenue.
- `test_lookup_size_retries_once_after_429` : premier appel 429 avec `Retry-After: 0`, second 200 → valeur retenue, 2 requêtes.
- `test_lookup_size_gives_up_after_second_429` : deux 429 → `(None, None)`, 2 requêtes.
- `test_lookup_size_network_error_returns_none` : le handler lève `httpx.ConnectError` → `(None, None)`.
- `test_lookup_size_sends_query_params` : la requête porte `q=<nom>`, `per_page=1`, `minimal=true` et un `User-Agent` non vide.

- [ ] **Step 2 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_company_profiles.py -v -k lookup`
Attendu : FAIL, `ImportError: cannot import name 'lookup_company_size'`.

- [ ] **Step 3 : implémenter**

Constantes : `RECHERCHE_ENTREPRISES_URL = "https://recherche-entreprises.api.gouv.fr/search"`, `API_USER_AGENT = "job-tracker/1.0 (enrichissement taille entreprise)"`, `TPE_TRANCHES = {"00", "01", "02", "03", "11"}`, timeout 10 s.
- Garde : premier résultat seulement. Retenu si `company_match_strength(nom_complet sans le suffixe « (…) », company) == "strong"` ou `company_match_strength(sigle, company) == "strong"`.
- Correspondance : `GE` → `grand_groupe`, `ETI` → `eti`, `PME` → `startup_tpe` si tranche dans `TPE_TRANCHES`, `pme` si autre tranche numérique, `None` sinon ; catégorie absente → `None`.
- 429 : une seule nouvelle tentative après `min(Retry-After, 5)` secondes (`Retry-After` absent ou illisible : 1 s).
- Toute exception (`httpx.HTTPError`, JSON illisible) → `(None, None)` avec un `logger.warning`.
- Sans `client` fourni : `async with httpx.AsyncClient(timeout=10)` le temps de l'appel.

- [ ] **Step 4 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_company_profiles.py -v`
Attendu : PASS.

- [ ] **Step 5 : commit** (si autorisé) — `feat(companies): resolve company size from recherche-entreprises API`

---

### Task 3 : Repli LLM, `CompanyResolver` et index `company_profiles`

**Files:**
- Modify: `backend/app/services/company_profiles.py`, `backend/app/database.py:99-103` (ajout après `create_star_stories_indexes`), `backend/main.py:13`, `backend/main.py:48-54`
- Test: `backend/tests/test_company_profiles.py`, `backend/tests/test_database_indexes.py`

**Interfaces:**
- Consumes : Task 1 (`extract_native_attributes`, `SECTORS`, `COMPANY_SIZES`), Task 2 (`lookup_company_size`), `normalize_company` (`normalization.py:60`).
- Produces :
  - `async def infer_company_attributes(company: str, poste: str = "", description: str = "", sector_label: Optional[str] = None) -> Optional[dict]` : `{"sector": Optional[str], "company_size": Optional[str]}`, ou `None` si l'appel échoue (exception, JSON illisible).
  - `DEFAULT_MAX_LLM_CALLS = 50`
  - `class CompanyResolver` : `__init__(self, db, http_client: Optional[httpx.AsyncClient] = None, max_llm_calls: Optional[int] = DEFAULT_MAX_LLM_CALLS)` (ne touche pas à `db`), attribut `llm_calls: int`, méthode `async def resolve(self, offer: dict) -> None` qui complète `offer["sector"]` et `offer["company_size"]` sur place. `max_llm_calls=None` : pas de plafond.
  - `def is_placeholder_company(company: Optional[str]) -> bool`
  - `async def create_company_profiles_indexes(db) -> None` dans `app/database.py`.

- [ ] **Step 1 : écrire les tests du repli LLM**

`acompletion` est importé au niveau du module (`from litellm import acompletion`) et patché par `patch("app.services.company_profiles.acompletion", new_callable=AsyncMock)`. Réponse simulée : objet dont `.choices[0].message.content` vaut la chaîne JSON.

- `test_infer_returns_taxonomy_values` : contenu `{"sector": "consulting_services", "company_size": "eti"}` → même dict ; l'appel reçoit `response_format={"type": "json_object"}` et `drop_params=True`, et le prompt contient la phrase de la règle ESN et le `sector_label` passé (`"Secteur informatique, ESN"`).
- `test_infer_rejects_values_outside_taxonomy` : `{"sector": "fintech", "company_size": "huge"}` → `{"sector": None, "company_size": None}`.
- `test_infer_accepts_other_and_null` : `{"sector": "other", "company_size": null}` → `{"sector": "other", "company_size": None}`.
- `test_infer_returns_none_on_invalid_json` : contenu `"je ne sais pas"` → `None`.
- `test_infer_returns_none_on_exception` : `acompletion` lève `Exception("boom")` → `None`.
- `test_infer_omits_temperature_for_gpt5` : `SUMMARY_MODEL=gpt-5-nano` → pas de clé `temperature` dans l'appel.

- [ ] **Step 2 : écrire les tests du résolveur**

Faux `company_profiles` en mémoire dans le fichier de test (`find_one` sur `company_name_normalized`, `update_one` qui applique `$set` et `$setOnInsert` avec `upsert=True`), base factice `{"company_profiles": fake}`. `lookup_company_size` et `infer_company_attributes` sont patchés dans `app.services.company_profiles` par des `AsyncMock`.

- `test_resolver_uses_native_values_without_external_calls` : offre `{"entreprise": "Foncia", "raw_data": {"indeed": {"company_industry": "Real Estate", "company_num_employees": "10,000+"}}}` → `sector` `construction_realestate`, `company_size` `grand_groupe` ; ni API ni LLM appelés ; profil `FONCIA` avec `sector_source == size_source == "native_source"`.
- `test_resolver_cache_hit_makes_no_external_call` (§6.4) : profil existant complet (`sector` `tech_it`/`native_source`, `company_size` `pme`/`api_entreprises`) ; offre sans `raw_data` → valeurs du profil, ni API ni LLM.
- `test_resolver_api_size_then_llm_for_sector_only` : API `("eti", "123456789")`, LLM `{"sector": "agri_food", "company_size": "pme"}` → offre `agri_food` + `eti` (la taille de l'API n'est pas remplacée par celle du LLM) ; profil `size_source "api_entreprises"`, `siren "123456789"`, `sector_source "llm_inferred"`.
- `test_resolver_marks_llm_attempt_even_when_null` : API `(None, None)`, LLM `{"sector": None, "company_size": None}` ; deuxième offre de la même entreprise → l'API et le LLM ne sont appelés qu'une fois chacun au total.
- `test_resolver_never_overwrites_known_value_with_none` (§6.4) : offre avec `sector` `finance_insurance` déjà posé, sans taille, API `(None, None)`, LLM `{"sector": None, "company_size": "pme"}` → offre `finance_insurance` + `pme` ; profil `sector` `tech_it`/`native_source` + offre sans `raw_data` → `sector` du profil inchangé.
- `test_resolver_native_value_replaces_llm_inferred_in_profile` : profil `sector` `other`/`llm_inferred`, offre native `Insurance` → profil `finance_insurance`/`native_source`.
- `test_resolver_never_replaces_manual` : profil `sector` `media_communication`/`manual`, offre native `Retail` → offre `retail_ecommerce` (sa propre valeur native), profil inchangé.
- `test_resolver_skips_placeholder_company` (Review Focus 2) : `entreprise` dans `["Confidentiel", "Entreprise confidentielle", "Non spécifié", "", None]`, offre avec `raw_data` HelloWork `Immobilier` → `sector` `construction_realestate`, aucun `find_one`, `update_one`, API ni LLM.
- `test_resolver_stops_calling_llm_after_budget` (Review Focus 1) : `max_llm_calls=1`, deux entreprises inconnues → un seul appel LLM ; la deuxième garde `*_source` absent dans son profil, pour qu'une exécution suivante réessaie.
- `test_resolver_llm_failure_leaves_source_unmarked` : `infer_company_attributes` renvoie `None` → profil sans `sector_source`.

- [ ] **Step 3 : écrire le test d'index**

Dans `test_database_indexes.py` : `test_create_company_profiles_indexes_unique_name` : `create_index` appelé avec `"company_name_normalized"` et `unique=True` sur `db["company_profiles"]`.

- [ ] **Step 4 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_company_profiles.py tests/test_database_indexes.py -v`
Attendu : FAIL sur les nouveaux tests (`ImportError`).

- [ ] **Step 5 : implémenter**

- `is_placeholder_company` : vrai si le nom est vide, si `normalize_company` renvoie `"Non spécifié"`, ou si le nom replié contient `confidenti` ou `anonym`.
- Prompt de `infer_company_attributes` (en français) : la liste des secteurs avec leurs libellés du §3.1, la règle ESN mot pour mot, les 4 tailles avec leurs seuils, la consigne « `other` si aucun secteur ne convient, `null` si tu ne sais pas », puis le nom de l'entreprise, le poste, le `sector_label` s'il existe et les 1 500 premiers caractères de la description. Sortie attendue : `{"sector": ..., "company_size": ...}`. Appel : `acompletion(model, messages, response_format={"type": "json_object"}, drop_params=True, timeout=30)`, température 0.2 sauf pour les préfixes `o1`, `o3`, `gpt-5`, `gpt-o` (même règle que `summarize_ats_offer_description`). Valeur hors `SECTORS` ou `COMPANY_SIZES` → `None`.
- `CompanyResolver.resolve(offer)`, dans cet ordre (§4.1) :
  1. valeurs natives (`extract_native_attributes(offer.get("raw_data"))`) posées sur l'offre si le champ y est vide ;
  2. les deux champs remplis, ou entreprise générique : fin ;
  3. lecture du profil `company_profiles` par `normalize_company(entreprise)` ; une valeur native remplace celle du profil si sa source est absente ou `llm_inferred` (source passée à `native_source`) ;
  4. champs vides de l'offre complétés depuis le profil ;
  5. taille toujours vide et `size_source` absent : `lookup_company_size` ; un résultat non nul donne `size_source = "api_entreprises"` et `siren` ;
  6. au moins un champ encore vide dont la source est absente, et budget LLM restant : un appel `infer_company_attributes`, `llm_calls += 1`. Résultat non `None` : chaque champ encore vide dont la source est absente reçoit la valeur du LLM (même `None`) avec la source `llm_inferred` ; c'est la marque « déjà tenté » qui évite de repayer à chaque ingestion. Les autres champs ne bougent pas ;
  7. upsert du profil : `$set` des champs modifiés et de `updated_at`, `$setOnInsert` de `company_name_raw`.
- `create_company_profiles_indexes` : `create_index("company_name_normalized", unique=True)`. Lifespan de `main.py` : dans le bloc `if db is not None:`, un `try/except` à part, après celui des index STAR, qui affiche `Erreur de création des index company_profiles: {e}`.

- [ ] **Step 6 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_company_profiles.py tests/test_database_indexes.py -v`
Attendu : PASS.

- [ ] **Step 7 : commit** (si autorisé) — `feat(companies): cache company profiles with LLM fallback`

---

### Task 4 : Enrichissement à l'ingestion

**Files:**
- Modify: `backend/app/tasks/job_offers_collectors.py:435-564` (`save_offers_to_database`)
- Test: `backend/tests/test_job_offers_pipeline.py` (à la suite des tests de sauvegarde, après la ligne 870)

**Interfaces:**
- Consumes : `CompanyResolver(db)` et `resolve(offer)` (Task 3).
- Produces : les documents `job_offers` insérés ou mis à jour portent `sector` et `company_size` quand ils sont résolus.

- [ ] **Step 1 : écrire les tests qui échouent**

Même montage que `test_save_offers_to_database_cross_source_dedup` (l. 645) : base `{"job_offers": mock_collection}`, `get_database` patché. `CompanyResolver` est remplacé par `monkeypatch.setattr("app.tasks.job_offers_collectors.CompanyResolver", Fake)`.

- `test_save_offers_insert_carries_resolved_sector` : `find_one` renvoie `None`, `distinct` renvoie `[]` ; le faux résolveur pose `sector="finance_insurance"`, `company_size="eti"` → le document passé à `insert_one` porte ces deux valeurs.
- `test_save_offers_update_keeps_existing_sector` (Review Focus 5) : document existant avec `sector="finance_insurance"` et `company_size="eti"` et `raw_data` sans `company_industry`, offre entrante HelloWork dont le `raw_data` ne porte pas non plus `company_industry` ; résolveur réel, `lookup_company_size` et `infer_company_attributes` patchés par des `AsyncMock` → le `$set` porte `sector == "finance_insurance"` et `company_size == "eti"`, et aucun des deux mocks n'est appelé.
- `test_save_offers_survives_company_resolver_failure` (Review Focus 3) : `resolve` lève `RuntimeError` → `res["saved"] == 1` et `insert_one` appelé.

- [ ] **Step 2 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -v -k "save_offers"`
Attendu : FAIL sur les 3 nouveaux tests (`AttributeError` sur `CompanyResolver` absent du module).

- [ ] **Step 3 : implémenter**

Import de `CompanyResolver` en tête de module. Un résolveur par appel, créé après `db = await get_database()`. Appel sur `merged` juste après `merge_multidiffusion_offers` (avant le calcul de `update_fields`), et sur `new_doc` avant `insert_one`, chaque fois dans un `try/except Exception` qui journalise un `logger.warning` et continue. `merge_multidiffusion_offers` n'est pas modifié : il part du document existant, qui garde son secteur.

- [ ] **Step 4 : lancer toute la suite du pipeline**

Run : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -v`
Attendu : PASS, tests existants compris (leur base mockée n'a pas `company_profiles` : le `try/except` absorbe le `KeyError`).

- [ ] **Step 5 : commit** (si autorisé) — `feat(offers): enrich sector and company size at ingestion`

---

### Task 5 : Script de rattrapage du stock

**Files:**
- Create: `backend/scripts/backfill_company_attributes.py`
- Test: `backend/tests/test_backfill_company_attributes.py`

**Interfaces:**
- Consumes : `extract_native_attributes`, `is_placeholder_company`, `CompanyResolver` (Tasks 1 et 3), `normalize_company`, `get_database`.
- Produces :
  - `LLM_COST_PER_COMPANY_USD = 0.0006`
  - `def estimate_backfill(offers: list[dict], profiles_by_name: dict[str, dict]) -> dict` : clés `offers`, `companies`, `resolved_natively`, `resolved_from_cache`, `max_llm_calls`, `estimated_cost_usd`.
  - `async def backfill(apply: bool, limit: Optional[int]) -> dict`, CLI `--apply`, `--limit N`.

- [ ] **Step 1 : écrire les tests qui échouent**

Définitions des compteurs : `offers` = offres ciblées ; `companies` = noms normalisés distincts hors noms génériques ; `resolved_natively` = offres dont tous les champs manquants viennent de leur propre `raw_data` ; `resolved_from_cache` = offres non résolues nativement dont les champs restants sont couverts par le profil en cache ; `max_llm_calls` = entreprises pour lesquelles, après mise en commun des valeurs natives de toutes leurs offres et du profil en cache, un champ reste vide avec une source absente (borne haute : l'API peut encore fournir la taille) ; `estimated_cost_usd = round(max_llm_calls * LLM_COST_PER_COMPANY_USD, 4)`.

`test_estimate_backfill_counts` : 4 offres sans secteur ni taille — « Foncia » A (`raw_data` HelloWork `Immobilier`), « Foncia » B (sans `raw_data`), « Sanofi » (sans `raw_data`, profil complet en cache), « Confidentiel » (`raw_data` Indeed `Insurance` + `10,000+`) — et `profiles_by_name = {"SANOFI": {...complet}}` → `offers == 4`, `companies == 2`, `resolved_natively == 1` (Confidentiel), `resolved_from_cache == 1` (Sanofi), `max_llm_calls == 1` (Foncia : taille inconnue), `estimated_cost_usd == 0.0006`.

`test_estimate_backfill_profile_already_tried_by_llm` : profil `{"sector_source": "llm_inferred", "size_source": "llm_inferred"}` avec valeurs `None` → l'entreprise ne compte pas dans `max_llm_calls`.

- [ ] **Step 2 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_backfill_company_attributes.py -v`
Attendu : FAIL, `ModuleNotFoundError`.

- [ ] **Step 3 : implémenter**

Même squelette que `scripts/backfill_canonical_titles.py` (argparse, `asyncio.run`, `get_database`). Cible : offres non supprimées dont `sector` ou `company_size` vaut `None` ou manque, projection `entreprise`, `poste`, `description`, `raw_data`, `sector`, `company_size`. Sans `--apply` : lecture de `company_profiles`, `estimate_backfill`, impression des chiffres ; aucun appel externe, aucune écriture. Avec `--apply` : `CompanyResolver(db, max_llm_calls=None)` sur chaque offre, puis `update_one` avec `$set` des seuls champs passés de vide à rempli ; impression du nombre d'offres mises à jour et de `resolver.llm_calls`. Exécution : `docker exec jobtracker-backend python scripts/backfill_company_attributes.py`.

- [ ] **Step 4 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_backfill_company_attributes.py -v`
Attendu : PASS.

- [ ] **Step 5 : vérifier le dry-run en local**

Run : `docker exec jobtracker-backend python scripts/backfill_company_attributes.py`
Attendu : exit 0, les six compteurs imprimés. Relire le diff : aucun `update_one` ni appel à `CompanyResolver` hors de la branche `apply`.

- [ ] **Step 6 : commit** (si autorisé) — `feat(scripts): backfill sector and company size on stored offers`

---

### Task 6 : `preferred_company_sizes` et migration de `preferred_industries`

Prévenir `job-tracker-c5` avant de modifier `models.py`.

**Files:**
- Modify: `backend/app/models.py:584` (ajout après `preferred_industries`)
- Create: `backend/scripts/migrate_preferred_industries.py`
- Test: `backend/tests/test_candidate_preferences.py`, `backend/tests/test_migrate_preferred_industries.py`

**Interfaces:**
- Consumes : `map_sector_label`, `PREFERENCE_SECTORS` (Task 1).
- Produces :
  - `CandidatePreferences.preferred_company_sizes: List[str] = Field(default_factory=list)`
  - `def migrate_industry_values(values: list[str]) -> tuple[list[str], list[str]]` : `(nouvelles valeurs, valeurs sans correspondance)`.
  - `async def migrate(apply: bool) -> dict`, CLI `--apply`.

- [ ] **Step 1 : écrire les tests qui échouent**

- `test_put_preferences_round_trips_sectors_and_sizes` (même montage que `test_put_preferences_endpoint`, l. 76) : PUT avec `preferred_industries=["finance_insurance", "tech_it"]` et `preferred_company_sizes=["eti", "grand_groupe"]` → la réponse et le GET `/profile/candidate` renvoient ces deux listes.
- `test_candidate_preferences_defaults` étendu : `preferred_company_sizes == []`.
- `test_migrate_industry_values` : `["Finance", "Tech", "finance_insurance", "Aéronautique", "Tourisme", "Cuisine moléculaire"]` → `(["finance_insurance", "tech_it", "industry_aerospace", "Tourisme", "Cuisine moléculaire"], ["Tourisme", "Cuisine moléculaire"])` : doublon retiré, ordre conservé, `other` jamais produit (« Tourisme » reste tel quel).

- [ ] **Step 2 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_candidate_preferences.py tests/test_migrate_preferred_industries.py -v`
Attendu : FAIL sur les nouveaux tests.

- [ ] **Step 3 : implémenter**

Champ ajouté au modèle, sans validation de valeurs (les valeurs historiques sans correspondance doivent rester enregistrables, §3.2). Script : parcourt `candidate_profile`, traite `preferences.preferred_industries` et chaque `sources.<clé>.preferences.preferred_industries`. Valeur déjà dans `PREFERENCE_SECTORS` : gardée ; correspondance hors `other` : remplacée ; sinon : gardée et listée. Sans `--apply` : imprime, par profil, avant → après et les valeurs sans correspondance, sans écrire. Avec `--apply` : `$set` des seuls chemins modifiés.

- [ ] **Step 4 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_candidate_preferences.py tests/test_migrate_preferred_industries.py -v`
Attendu : PASS.

- [ ] **Step 5 : commit** (si autorisé) — `feat(preferences): add preferred company sizes and migrate industries`

---

### Task 7 : Section « Secteurs d'activité & Taille d'entreprise »

Prévenir `job-tracker-c5` avant de modifier le frontend. Vérifier que `git status --porcelain` est vide sur les deux fichiers (précondition du §5).

**Files:**
- Modify: `frontend/src/types/coverLetter.ts:43-58`, `frontend/src/components/profile/TargetingPreferencesSection.tsx` (état l. 60-84, `openSections` l. 87-93, `applyPreferences` l. 98-117, payload l. 202-216, nouvelle section après la section contrat, l. 695-782)

**Interfaces:**
- Consumes : `preferred_industries`, `preferred_company_sizes` de `PUT /profile/candidate/preferences` (Task 6).

- [ ] **Step 1 : type**

`preferred_company_sizes?: string[]` dans l'interface `CandidatePreferences`.

- [ ] **Step 2 : section**

Accordéon de clé `"sectors"`, titre « Secteurs d'activité & Taille d'entreprise », construit sur le modèle de la section contrat (chips `CONTRACT_OPTIONS`). Deux constantes ; libellés courts choisis par le plan, la description du §3.1 en `title` de chaque chip :

| Valeur | Libellé |
|---|---|
| `tech_it` | Tech & Logiciel |
| `finance_insurance` | Banque, Finance & Assurance |
| `healthcare_pharma` | Santé & Pharma |
| `consulting_services` | Conseil, Audit & ESN |
| `retail_ecommerce` | Retail & E-commerce |
| `industry_aerospace` | Industrie & Aéronautique |
| `energy_environment` | Énergie & Environnement |
| `media_communication` | Médias & Communication |
| `public_education` | Secteur public & Éducation |
| `construction_realestate` | Immobilier & BTP |
| `logistics_transport` | Transport & Logistique |
| `agri_food` | Agroalimentaire & Agriculture |

Tailles (libellés du §3.1) : `startup_tpe` « Startup / TPE (< 20 salariés) », `pme` « PME (20 - 249 salariés) », `eti` « ETI (250 - 4 999 salariés) », `grand_groupe` « Grand Groupe (5 000+ salariés) ».

Une valeur de `preferred_industries` hors taxonomie (non migrée) s'affiche en chip grisée supprimable, avec le `title` « Ancienne valeur, non utilisée pour le tri ». Aucune saisie libre. `applyPreferences` lit les deux champs ; le payload de `handleSubmit` les envoie (aujourd'hui `preferred_industries` n'est pas envoyé et la sauvegarde l'écrase avec `[]`).

- [ ] **Step 3 : vérifier**

Run : `cd frontend && npm run lint && npm run build`
Attendu : exit 0, aucune nouvelle alerte.

- [ ] **Step 4 : contrôle manuel (observateur : l'utilisateur)**

Sur l'app locale : cocher deux secteurs et une taille, enregistrer, recharger la page : les chips restent cochées ; modifier un autre champ (ville), enregistrer : les secteurs ne sont pas effacés.

- [ ] **Step 5 : commit** (si autorisé) — `feat(preferences-ui): select sectors and company sizes`

---

## Après le plan (hors exécution)

- Déployer le backend, puis l'utilisateur lance en prod `migrate_preferred_industries.py` et `backfill_company_attributes.py` en lecture, relit les chiffres, puis `--apply` après accord sur la dépense LLM affichée.
- Le secteur et la taille ne pèsent dans le classement qu'à l'étape 3 (score) ; le rematch sur ces champs arrive à l'étape 4.
