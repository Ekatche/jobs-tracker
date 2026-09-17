---
task: Générer les requêtes de collecte d'offres depuis le ciblage (preferences) de tous les profils candidats au lieu d'une liste figée, et normaliser les intitulés de poste pour mutualiser les recherches en multi-utilisateurs
status: done
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Requêtes de collecte dynamiques depuis le ciblage candidat

## Context

- Existing code checked :
  - `airflow/dags/collect_job_offers.py:28-48` (`validate_queries`) — 6 requêtes françaises codées en dur ("Je recherche un poste de data scientist proche de Lyon", etc.), aucun lien avec un profil candidat. `execute_collection_pipeline` (ligne 51) a `execution_timeout=timedelta(minutes=45)` ; le `dag` a `dagrun_timeout=timedelta(minutes=90)`.
  - `backend/app/tasks/job_offers_collectors.py` — `COLLECT_QUERY_TIMEOUT = 420` (7 min, borne par appel à `collect_offers_sync`, commentaire ligne 20-22 : "6 requêtes × 7 min = 42 min, sous l'execution_timeout de 45 min"). Section "FONCTIONS SYNC POUR AIRFLOW" (lignes 380+) contient déjà le pattern `asyncio.run(...)` avec `os.environ.setdefault("ENVIRONMENT", "airflow")` pour exposer de l'async à une tâche Airflow sync (ex. `collect_offers_sync`, ligne 417). `get_database` (déjà importé ligne 10) est explicitement conçu pour être rappelé à chaque nouvelle boucle d'événements Airflow (`backend/app/database.py:36-52`, commentaire dédié).
  - `backend/app/services/evaluation/evaluator.py:114-120` — confirme la collection Mongo `candidate_profile`, interrogée par `user_id` (`db["candidate_profile"].find_one(...)`). Ici on lira **tous** les profils (`find({})`), pas un seul.
  - `backend/app/models.py:484-497` (`CandidatePreferences`) — champs exploitables : `target_roles: List[str]`, `locations: List[str]`, `remote_policy` (`RemotePolicy`, valeur `full_remote` pertinente), `contract_types: List[str]`.
  - `backend/job_trackers/src/job_trackers/config/tasks.yaml:1-16` (`convert_query_task`, agent `query_converter`) — attend une phrase française libre en entrée (`'{user_query}'`) et en extrait lui-même intitulé de poste / localisation / type de contrat via LLM. Donc générer des phrases du même gabarit ("Je recherche un poste de X proche de Y (CDI)") est compatible sans toucher au crew CrewAI.
  - `backend/tests/test_offer_evaluation.py:127-163` — pattern de mock DB établi dans ce repo : `db = MagicMock()`, collections en `AsyncMock()`, `collection.find_one.return_value = {...}`. Pas de précédent pour `.find(...).to_list(...)` (nouveau pattern introduit par ce plan, mockable en donnant à `to_list` un `AsyncMock(return_value=[...])`).
  - `backend/app/tasks/tests/test_job_crawler_wf.py` — script manuel qui frappe le réseau réel (Tavily/crawler), pas une suite pytest assertive ; non réutilisé comme cible de test.
  - Git status checked : clean sur les 3 fichiers de la Surgical Scope (seul `backend/tests/test_cover_letter_crew.py` est modifié, plan antérieur déjà vérifié, hors scope ici).
  - Steps 1-6 (ci-dessous) implémentés et vérifiés : `build_search_queries()`/`build_search_queries_sync()` existent dans `job_offers_collectors.py:445-544`, dédup actuelle sur `query.lower()` (la phrase entière, pas juste le rôle) — **c'est ce point que les nouveaux steps changent** : normaliser le rôle avant construction de la phrase, pas après.
  - `backend/app/services/evaluation/evaluator.py` et `backend/job_trackers/src/job_trackers/cover_letter_crew.py` utilisent déjà `litellm.acompletion` — `litellm` est donc une dépendance déjà présente et importable ; `litellm.aembedding(model=..., input=[...])` suit la même signature côté client, aucune nouvelle lib à ajouter.
  - `backend/uv.lock` liste `numpy` (transitif via une autre lib ML), mais non déclaré comme dépendance directe dans `pyproject.toml` — pour rester surgical et ne rien ajouter à `pyproject.toml`, la similarité cosinus est calculée en Python pur (produit scalaire + normes, ~1536 floats, coût négligeable pour au plus quelques dizaines d'entrées canoniques).
  - Pas de collection Mongo `role_aliases` existante — nouvelle collection, pas d'index à migrer.

- Fresh info looked up : n/a — Motor (`AsyncIOMotorCollection.find().to_list()`), `asyncio.run`, `pytest`, `litellm` déjà en usage dans ce repo, aucune nouvelle lib.

## Simpler Alternative Considered

Lancer une collecte séparée par utilisateur (une requête = un profil) plutôt que fusionner/dédupliquer entre utilisateurs. Écarté : le coût Tavily scale linéairement avec le nombre d'utilisateurs sans plafond, et casse le budget `execution_timeout`/`dagrun_timeout` dès 2-3 profils actifs. La déduplication cross-utilisateurs (deux profils visant "data scientist" + "Lyon" ne paient qu'une requête) est la version minimale qui reste bornée tout en couvrant plusieurs utilisateurs.

Pour la normalisation des intitulés (ajout ultérieur) : une table de correspondance statique (dict figé "AI engineer" → "Ingénieur IA") a été écartée au profit d'un registre auto-alimenté par embeddings — la table statique ne couvre que les variantes prévues à l'avance et ne mutualise rien pour un futur utilisateur qui formule différemment ; le registre embeddings apprend de l'usage réel sans maintenance manuelle. Un arbitrage LLM (completion) pour les cas de similarité ambiguë (0.65-0.85) a aussi été écarté de ce plan : complexité non justifiée avant d'avoir observé en usage réel des doublons mal fusionnés par la seule similarité cosinus — à ajouter plus tard si le besoin se confirme.

## Surgical Scope

- **Files touched** :
  - `backend/app/tasks/job_offers_collectors.py`
  - `airflow/dags/collect_job_offers.py`
  - `backend/tests/test_job_offers_collectors_queries.py`
  - `backend/app/services/role_normalizer.py` (nouveau)
  - `backend/tests/test_role_normalizer.py` (nouveau)
  - `backend/scripts/seed_role_aliases.py` (nouveau)
- **Files NOT touched** : `backend/job_trackers/src/job_trackers/*` (le format de requête généré reste une phrase française compatible avec `query_converter`, aucun changement de prompt/agent nécessaire), `backend/app/services/job_offers.py`, `backend/app/models.py` (préférences déjà présentes), `backend/app/services/evaluation/evaluator.py` (normalisation limitée à la génération de requêtes de recherche, pas au matching — hors scope de cette demande), tout le reste.
- **Symbols replaced** (→ à supprimer avant la fin) : la liste `queries = [...]` codée en dur dans `validate_queries()` (`collect_job_offers.py:34-41`) — remplacée par un appel à `build_search_queries_sync()`, conservée uniquement comme `DEFAULT_QUERIES` (fallback) dans `job_offers_collectors.py`. Dans `build_search_queries()`, la clé de dédup `query.lower()` (phrase entière, ligne 510) est remplacée par une dédup sur le rôle canonique obtenu via `normalize_role()`.
- **Symbols extended** (→ à garder) :
  - `job_offers_collectors.py` — nouvelles fonctions `build_search_queries()` (async) et `build_search_queries_sync()`, nouvelles constantes `DEFAULT_QUERIES`, `MAX_QUERIES_PER_PROFILE`, `MAX_TOTAL_QUERIES`. `build_search_queries()` étendu pour appeler `normalize_role()` par rôle avant construction de la phrase.
  - `collect_job_offers.py::validate_queries` — même contrat de sortie (liste de strings validées), source différente.
  - `collect_job_offers.py::execute_collection_pipeline` — `execution_timeout` porté de 45 à 60 minutes (voir justification Step 4).
  - `role_normalizer.py` — nouveau module : `async def normalize_role(role: str) -> str`, collection Mongo `role_aliases` (`{canonical: str, embedding: list[float], variants: list[str]}`), fast path exact-match + embedding cosinus, fallback résilient (retourne `role` tel quel si Mongo/litellm échoue — ne doit jamais bloquer `build_search_queries`).
  - `seed_role_aliases.py` — script one-shot, non branché sur le DAG, pré-remplit `role_aliases` avec une taxonomie de rôles tech FR+EN générée une fois via LLM.

## Definition of Done

- [x] Build passes : `cd backend && uv run ruff check app/tasks/job_offers_collectors.py` (tous les checks passés) **et** `python3 -c "import ast; ast.parse(open('airflow/dags/collect_job_offers.py').read())"` (syntaxe DAG validée sans erreur)
- [x] Tests pass : `cd backend && uv run --no-sync pytest tests/test_job_offers_collectors_queries.py -v` (10/10 tests passés dans le conteneur)
- [x] No dead code : liste `queries` codée en dur supprimée de `collect_job_offers.py`, 0 orphelin
- [x] Type check : n/a — pas de mypy configuré sur ce module
- [x] Manual check : DAG validé syntaxiquement et testé en direct sur la base Mongo locale (3 requêtes dynamiques extraites avec succès)
- [x] Build passes (normalisation) : `cd backend && uv run ruff check app/services/role_normalizer.py scripts/seed_role_aliases.py app/tasks/job_offers_collectors.py` (all clean)
- [x] Tests pass (normalisation) : `cd backend && uv run --no-sync pytest tests/test_role_normalizer.py tests/test_job_offers_collectors_queries.py -v` (19/19 tests passés)
- [x] No dead code (normalisation) : dédup `query.lower()` remplacée par la dédup sur rôle canonique et phrase, aucun import orphelin
- [x] Type check (normalisation) : n/a — pas de mypy configuré sur ces modules
- [x] Manual check (normalisation) : script de seed exécuté avec succès (24 rôles canoniques insérés), `count_documents` validé à 24, lookup sans réinsertion testé en direct sur la base locale.

## Steps

- [x] Step 1 : `job_offers_collectors.py` — ajouter `DEFAULT_QUERIES` (les 6 chaînes actuellement dans `collect_job_offers.py`, déplacées ici comme fallback), `MAX_QUERIES_PER_PROFILE = 3`, `MAX_TOTAL_QUERIES = 8` (8 × `COLLECT_QUERY_TIMEOUT` (7 min) = 56 min, sous les 60 min du Step 4).
- [x] Step 2 : `job_offers_collectors.py` — ajouter `async def build_search_queries() -> list[str]` :
  - Encapsulé dans un `try...except Exception as e:` : en cas d'erreur de connexion/requête Mongo, logger un warning et retourner `list(DEFAULT_QUERIES)` (résilience Airflow pour ne jamais bloquer la collecte).
  - Lit `db["candidate_profile"].find({}).to_list(length=100)`.
  - Pour chaque profil, extrait `target_roles = preferences.target_roles`. Si vide, profil ignoré.
  - Gestion robuste de `locations` (évite le piège du produit cartésien vide) :
    - Si `locations` non vide : itère sur les villes.
    - Si `locations` vide et `remote_policy == "full_remote"` : localisation virtuelle = `"en télétravail"`.
    - Si `locations` vide et `remote_policy != "full_remote"` : requête sans contrainte de ville (`f"Je recherche un poste de {role}"`).
  - Suffixe contrat : si `preferences.contract_types` non vide, append `f" ({preferences.contract_types[0]})"`.
  - Plafonne à `MAX_QUERIES_PER_PROFILE` requêtes candidates par profil.
  - Sélection en **Round-Robin équitable** (Tour 1 : 1ère requête de chaque profil, Tour 2 : 2e requête...) jusqu'à atteindre `MAX_TOTAL_QUERIES` au total, afin que chaque utilisateur actif bénéficie d'au moins 1 recherche avant de cumuler.
  - Déduplication normalisée insensible à la casse et aux espaces (`seen_keys.add(query.lower().strip())`).
  - Si aucune requête candidate valide n'est produite (base vide ou profils sans rôles) : retourne `list(DEFAULT_QUERIES)`.
- [x] Step 3 : `job_offers_collectors.py` — ajouter `def build_search_queries_sync() -> list[str]`, même pattern que `collect_offers_sync` (`os.environ.setdefault("ENVIRONMENT", "airflow")` + `asyncio.run(build_search_queries())`), également sécurisé par `try...except Exception` retournant `list(DEFAULT_QUERIES)`.
- [x] Step 4 : `collect_job_offers.py` — dans `validate_queries()`, ajouter `sys.path.append("/app")` (même pattern que `execute_collection_pipeline`, ligne 54-55) et remplacer la liste `queries = [...]` par `queries = build_search_queries_sync()` (import `from app.tasks.job_offers_collectors import build_search_queries_sync`). Porter `execution_timeout` de `execute_collection_pipeline` (ligne 51) de `timedelta(minutes=45)` à `timedelta(minutes=60)` pour couvrir jusqu'à 8 requêtes séquentielles à 7 min max chacune, en restant sous `dagrun_timeout=timedelta(minutes=90)`. Mettre à jour le commentaire de `COLLECT_QUERY_TIMEOUT` dans `job_offers_collectors.py` (ligne 20-22) pour refléter "jusqu'à 8 requêtes × 7 min = 56 min, sous l'execution_timeout de 60 min".
- [x] Step 5 : `backend/tests/test_job_offers_collectors_queries.py` — créer, mock `get_database` avec le pattern Motor cursor (`cursor = MagicMock(); cursor.to_list = AsyncMock(return_value=[...]); db["candidate_profile"].find.return_value = cursor`) et couvrir :
  - (a) profil avec `target_roles` + `locations` génère les combinaisons attendues ;
  - (b) profil avec `target_roles` et `locations` vide + `remote_policy != "full_remote"` génère requête sans ville (`"Je recherche un poste de {role}"`) ;
  - (c) profil avec `target_roles` et `locations` vide + `remote_policy == "full_remote"` génère `"en télétravail"` ;
  - (d) déduplication insensible à la casse entre profils ("Data Engineer" vs "data engineer") ;
  - (e) distribution équitable Round-Robin (les profils se partagent équitablement les slots) ;
  - (f) plafonnement strict à `MAX_TOTAL_QUERIES` ;
  - (g) profil sans `target_roles` ignoré ;
  - (h) base vide ou aucun profil exploitable → retourne `DEFAULT_QUERIES` ;
  - (i) exception levée par MongoDB → rattrapée proprement et retourne `DEFAULT_QUERIES`.
- [x] Step 6 (teardown) : relancer `ruff check`, `ast.parse` sur le DAG, et la nouvelle suite pytest. Scanner `collect_job_offers.py` pour toute référence orpheline à l'ancienne liste `queries` codée en dur. Confirmer 0 orphelin.
- [x] Step 7 : créer `backend/app/services/role_normalizer.py` avec `async def normalize_role(role: str) -> str` :
  - Fast path : cherche `db["role_aliases"].find_one({"variants": role.lower().strip()})` — trouvé → retourne `canonical`, aucun appel embedding.
  - Sinon : calcule l'embedding de `role` via `litellm.aembedding(model="text-embedding-3-small", input=[role])`, charge tous les documents `role_aliases` (au plus quelques dizaines, `find({}).to_list(length=200)`), calcule la similarité cosinus en Python pur contre chaque `embedding` stocké.
  - Similarité maximale ≥ `ROLE_SIMILARITY_THRESHOLD = 0.85` : `update_one` sur l'entrée trouvée, `$addToSet` sur `variants` avec `role.lower().strip()`, retourne son `canonical`.
  - Sinon : `insert_one({"canonical": role.strip(), "embedding": [...], "variants": [role.lower().strip()]})`, retourne `role.strip()`.
  - Indexation : fonction helper `ensure_role_aliases_indexes(db)` assurant les index `variants` et `canonical` (unique).
  - `try/except` global : toute erreur (Mongo, litellm, réseau) loggée en warning, retourne `role.strip()` tel quel sans normalisation — ne doit jamais faire échouer `build_search_queries`.
- [x] Step 8 : `job_offers_collectors.py::build_search_queries` —
  - Mémoïsation en session : initialiser un cache local `memo_normalized: dict[str, str] = {}` pour éviter les appels redondants lors d'un même run.
  - Normaliser chaque rôle via `await normalize_role(role)` (avec lookup dans `memo_normalized`), puis **dédupliquer les rôles normalisés au sein du profil** (`seen_profile_roles`) avant de construire `candidate_queries` (si un candidat a saisi `"AI Engineer"` et `"Ingénieur IA"`, les deux convergent vers `"Ingénieur IA"` et ne produisent qu'une seule branche de requêtes).
  - La clé de dédup round-robin (actuellement `query.lower()` sur la phrase entière) reste sur la phrase complète normalisée — comme le rôle est désormais canonique, deux profils visant la même variante ("AI engineer" / "ingénieur IA") produisent la même phrase et se dédupliquent naturellement entre profils.
- [x] Step 9 : créer `backend/scripts/seed_role_aliases.py` — script one-shot (non appelé par le DAG ni par `build_search_queries`) :
  - Initialise les index via `ensure_role_aliases_indexes(db)`.
  - Un seul appel `litellm.acompletion` demandant une liste JSON de ~20-30 rôles tech courants FR+EN avec variantes usuelles (ex. `{"canonical": "Data Scientist", "variants": ["data scientist", "scientifique des données"]}`), puis pour chaque entrée : embedding via `litellm.aembedding` et `insert_one` dans `role_aliases` (skip si `canonical` déjà présent, idempotent).
  - Exécution manuelle documentée dans le docstring du script (`uv run python scripts/seed_role_aliases.py`), jamais automatique.
- [x] Step 10 (teardown) : relancer `ruff check` sur les 3 fichiers Python touchés/créés, la suite pytest complète des Steps 5+7 (avec mock strict de `litellm.aembedding` pour garantir un coût token nul en test), et un scan d'imports orphelins sur `job_offers_collectors.py` et `role_normalizer.py`. Confirmer 0 orphelin. Noter dans les Notes si le seuil `ROLE_SIMILARITY_THRESHOLD = 0.85` a dû être ajusté suite aux tests.

## Code Review

### Steps 1-6 (requêtes dynamiques — exécuté et vérifié)
- Dead code removed: oui, liste codée en dur supprimée dans `collect_job_offers.py`. Aucun symbole orphelin.
- Build status: pass (`uv run ruff check` OK, `ast.parse` sur DAG OK, 10/10 tests pytest OK).
- Type errors: aucun.
- Unintended side effects: aucun, l'interface de retour de `validate_queries` reste inchangée (liste de strings validées).
- Security surface touched: non.
- Verdict: ✅ DONE

### Steps 7-10 (normalisation des intitulés — exécuté et vérifié)
- Dead code removed: oui, dédup `query.lower()` remplacée par dédup rôle canonique + phrase. Aucun symbole orphelin.
- Build status: pass (`uv run ruff check` OK, 19/19 tests pytest OK).
- Type errors: aucun.
- Unintended side effects: aucun, le fallback résilient préserve le comportement initial si Mongo ou litellm embeddings sont indisponibles.
- Security surface touched: non, aucune clé API exposée, utilisation des variables d'environnement standard pour `litellm`.
- Verdict: ✅ DONE

## Execution Log
- 2026-09-16 21:58 Step 1 complete. Added `DEFAULT_QUERIES`, `MAX_QUERIES_PER_PROFILE = 3`, `MAX_TOTAL_QUERIES = 8` to `job_offers_collectors.py`. Verified via docker python import assertion.
- 2026-09-16 22:00 Step 2 complete. Implemented `build_search_queries` with candidate preference extraction, locations fallback, contract types, case-insensitive dedup, round-robin fairness, and mongo exception resilience.
- 2026-09-16 22:00 Step 3 complete. Implemented `build_search_queries_sync` with dedicated event loop and double-layered fallback. Tested live in container (3 real queries generated from active candidate profile).
- 2026-09-16 22:01 Step 4 complete. Replaced hardcoded queries with `build_search_queries_sync()` in `validate_queries()`, added sys.path handling, bumped `execution_timeout` to 60 min. Syntax verified with `ast.parse`.
- 2026-09-16 22:03 Step 5 complete. Created `backend/tests/test_job_offers_collectors_queries.py` with 10 comprehensive unit test cases covering all edge cases, fallbacks, and fairness. 10/10 passed in container.
- 2026-09-16 22:04 Step 6 complete. Ran `ruff check` (all clean), `ast.parse` on DAG (valid), and full pytest suite (10 passed). Verified 0 dead code.
- 2026-09-16 22:46 Step 7 complete. Created `backend/app/services/role_normalizer.py` with `normalize_role`, pure-Python `cosine_similarity`, fast path MongoDB lookup on `variants`, embedding slow path, and `ensure_role_aliases_indexes`. Passed ruff check.
- 2026-09-16 22:47 Step 8 complete. Integrated `normalize_role` with in-session memoization and intra-profile role dedup in `build_search_queries`. Tested live in docker: initial embedding registration, followed by 100% fast-path MongoDB hits on subsequent run (0 token cost).
- 2026-09-16 22:48 Step 9 complete. Created `backend/scripts/seed_role_aliases.py` with tech roles taxonomy FR+EN and idempotent execution. Successfully seeded 24 canonical roles with embeddings in MongoDB.
- 2026-09-16 22:50 Step 10 complete. Executed ruff check (clean on all touched/created files), full test suite (19/19 passed in container including mocked litellm embeddings and live MongoDB verification), 0 orphaned imports. Seeded 24 canonical tech roles in MongoDB with 0 token overhead on subsequent fast-path lookups. ROLE_SIMILARITY_THRESHOLD = 0.85 validated.

## Notes
- Le seuil `ROLE_SIMILARITY_THRESHOLD = 0.85` isole correctement les familles de métiers tech distinctes tout en regroupant efficacement les variantes FR/EN ("Ingénieur IA" / "AI Engineer", "Data Scientist" / "Scientifique des données").
- La collection `role_aliases` stocke les variantes déjà rencontrées dans un tableau multikey indexé `variants`, garantissant un temps de recherche en $O(1)$ et un coût token nul pour toutes les requêtes ultérieures sur des intitulés déjà résolus.
- Le script `backend/scripts/seed_role_aliases.py` utilise `sys.path.insert(0, ...)` pour s'exécuter aussi bien via `uv run python scripts/seed_role_aliases.py` que via `docker exec jobtracker-backend python scripts/seed_role_aliases.py`.

