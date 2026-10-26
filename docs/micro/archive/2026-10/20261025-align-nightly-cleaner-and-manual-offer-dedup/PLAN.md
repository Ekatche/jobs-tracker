---
task: Aligner le nettoyeur nocturne et la création d'offre depuis une candidature sur la dédup d'insertion
description: cleanup_job_offers étape 3 remove_similarity_duplicates_global remplacée par merge_duplicate_offers (are_offers_duplicates, ville, report d'URL dans alternative_urls, survivant référencé, interactions rattachées) extraite de retroactive_dedup_job_offers.py vers app/services/offer_dedup.py ; find_offer_by_identity et find_company_variant_duplicate partagés entre save_offers_to_database et _ensure_offer_for_application (applications.py) ; fin des défauts « Entreprise »/« France », clean_job_title_syntax avant compute_unique_key, recherche alternative_urls, tests pytest AsyncMock MongoDB
status: done
created: 2026-10-25
---

# Aligner le nettoyeur nocturne et la création d'offre manuelle sur la dédup d'insertion

## Context
- Existing code checked:
  - Insertion `save_offers_to_database` (`backend/app/tasks/job_offers_collectors.py:444-576`) : `$or` sur `unique_key`, `url`, `alternative_urls`, `url $in alternative_urls`, puis variantes de nom d'entreprise (`distinct("entreprise")` paresseux + `company_match_strength` + `are_offers_duplicates`), puis `merge_multidiffusion_offers`. Bloque 12/12 doublons hérités rejoués en prod (audit du 25/10).
  - Nettoyeur `cleanup_workflow` étape 3 (`backend/app/tasks/clean_job_offers.py:462-469`) appelle `remove_similarity_duplicates_global` (l.622-917) : ignore la ville (critères 3-4), la plus récente gagne, perdant supprimé physiquement sans report d'URL, garde limitée à `applications`, branche tombstone sans garde. Résultat : va-et-vient quotidien (NEXTON 13-17/10, Talents Handicap 21-24/10), fusions Lyon/Suresnes, 1 interaction orpheline du 18/10.
  - `backend/retroactive_dedup_job_offers.py` porte déjà la règle d'insertion : `find_duplicate_pairs` (noms compatibles), `is_same_offer` (clé canonique ou `are_offers_duplicates`), `pick_survivor` (l'offre référencée survit, paire sautée si les deux le sont), `REFERENCING_COLLECTIONS`, `merge_multidiffusion_offers`, `delete_one` du perdant avant `update_one` du survivant (index uniques), `move_interactions`, recalcul des `unique_key` périmées. Simulation déjà passée en prod (12 paires) et en local (8 paires, 11 clés périmées).
  - `_ensure_offer_for_application` (`backend/app/routers/applications.py:726-821`) : recherche par `url` seulement (pas `alternative_urls`), clé calculée sans `clean_job_title_syntax` (`'Data Scientist (CDI)'` donne `capgemini|cdi data scientist|lyon` au lieu de `capgemini|data scientist|lyon`), défauts `"Entreprise"` et `"France"`, aucune recherche par variante d'entreprise, aucun test. Prod (lecture seule, 25/10) : 34 candidatures, 0 sans entreprise, 0 sans ville, 0 sans URL ; le correctif est préventif.
  - Index `job_offers` (`backend/app/database.py:64-80`) : `url` unique partiel, `unique_key` unique **sparse** (un document sans `unique_key` est accepté plusieurs fois).
  - `cleanup_invalid_offers` (l.363) classe invalides les offres d'entreprise `None`, `""`, `"Entreprise non spécifiée"`, `"Non spécifié"` (soft-delete si liées à une candidature).
  - Tests existants : `test_normalization_and_dedup.py:20` importe `find_duplicate_pairs, pick_survivor` du script ; `test_job_offers_pipeline.py:648+` couvre `save_offers_to_database` avec `MagicMock`/`AsyncMock` (`find_one` mocké, `distinct` non mocké, donc le `distinct` doit rester paresseux) ; `test_job_offers_pipeline.py:42` `test_tombstone_priority_sorting` est tautologique (redéfinit le `priority_sort_key` de la fonction remplacée et ne teste aucun code du projet).
  - Plans passés : `archive/2026-10/20261024-cross-board-company-variant-dedup` (variantes de nom, script rétroactif), `archive/2026-09/20260917-cross-source-job-offers-deduplication`.
- Fresh info looked up: n/a — logique métier interne, aucune API externe.
- Git status checked: worktree `ft-removal-dedup-audit` sur `main`, retrait France Travail non commité (même session). Deux fichiers du périmètre en portent déjà des modifications : `backend/app/tasks/job_offers_collectors.py` et `docs/JOB_INGESTION_AND_NORMALIZATION.md`. Les autres fichiers du périmètre sont propres.

## Simpler Alternative Considered
Désactiver l'étape 3 (`enable_global_similarity=False` dans le DAG) : écarté par l'utilisateur, qui garde un filet de sécurité nocturne (courses entre insertions parallèles, doublons hérités, chemin manuel).
Copier la recherche d'insertion dans `applications.py` au lieu de l'extraire : écarté. Deux copies de la règle finissent par diverger, et c'est précisément ce qui s'est passé avec le nettoyeur.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/offer_dedup.py` (nouveau)
  - `backend/retroactive_dedup_job_offers.py` (devient un simple lanceur)
  - `backend/app/tasks/clean_job_offers.py`
  - `backend/app/tasks/job_offers_collectors.py` (bloc de recherche de `save_offers_to_database` uniquement)
  - `backend/app/routers/applications.py` (`_ensure_offer_for_application` uniquement)
  - `backend/tests/test_normalization_and_dedup.py`
  - `backend/tests/test_clean_and_verify_alignment.py`
  - `backend/tests/test_job_offers_pipeline.py` (suppression de `test_tombstone_priority_sorting` uniquement)
  - `backend/tests/test_application_offer_link.py` (nouveau)
  - `docs/JOB_INGESTION_AND_NORMALIZATION.md`
- **Files NOT touched**:
  - `airflow/dags/clean_job_offers.py` : il appelle toujours `cleanup_workflow_sync(enable_global_similarity=True)` ;
  - `backend/app/services/normalization.py` : la règle `are_offers_duplicates` reste la référence ;
  - `is_offer_referenced_by_application`, `safe_delete_or_expire_offer`, `cleanup_invalid_offers`, `remove_similarity_duplicates` (mode standard, désactivé par défaut), `prevent_duplicate_insertion` (code mort préexistant, signalé et non supprimé) ;
  - frontend ;
  - tout le reste.
- **Symbols replaced** (à supprimer avant la fin) :
  - `remove_similarity_duplicates_global` (`clean_job_offers.py`) ;
  - `deduplicate_collection` (script, devient `merge_duplicate_offers` dans `offer_dedup.py`) ;
  - `test_tombstone_priority_sorting` (`test_job_offers_pipeline.py`) ;
  - le bloc de recherche inline de `save_offers_to_database` (l.480-505) ;
  - les clés de résumé `kept_active`, `kept_deleted` et `groups_processed` de `cleanup_workflow`.
- **Symbols extended** (à garder) : `cleanup_workflow`, `save_offers_to_database`, `_ensure_offer_for_application`. `REFERENCING_COLLECTIONS`, `id_variants`, `pick_survivor`, `is_same_offer`, `find_duplicate_pairs`, `load_referenced_offer_ids`, `move_interactions` et `describe` sont déplacés tels quels.

## Definition of Done
- [x] Build passes : `cd backend && uv run python -c "import main, retroactive_dedup_job_offers, app.tasks.clean_job_offers, app.services.offer_dedup"`, exit 0.
- [x] Tests ciblés : `cd backend && uv run pytest tests/test_normalization_and_dedup.py tests/test_clean_and_verify_alignment.py tests/test_job_offers_pipeline.py tests/test_application_offer_link.py -q`, 0 failed.
- [x] Suite complète : `cd backend && uv run pytest tests -q`, 0 failed, ou au plus les échecs déjà présents au baseline de la Phase 3, nommés dans Notes.
- [x] No dead code : `grep -rnE "remove_similarity_duplicates_global|deduplicate_collection|test_tombstone_priority_sorting|kept_active|groups_processed" backend airflow --include=*.py | wc -l` donne 0.
- [x] Le nettoyeur applique la règle d'insertion : `grep -c "merge_duplicate_offers" backend/app/tasks/clean_job_offers.py` ≥ 2 (import et appel), et `test_cleanup_workflow_global_step_uses_insertion_rule` passe.
- [x] Le nettoyeur garde la ville et l'URL du perdant : `test_merge_duplicate_offers_keeps_loser_url_and_city_split` passe.
- [x] Insertion et chemin manuel partagent la même recherche : `grep -c "find_offer_by_identity" backend/app/tasks/job_offers_collectors.py backend/app/routers/applications.py` ≥ 2 pour chacun des deux fichiers.
- [x] Plus de valeurs inventées : `grep -cE 'or "(Entreprise|France)"' backend/app/routers/applications.py` donne 0.
- [x] Intitulé nettoyé avant la clé : `grep -c "clean_job_title_syntax" backend/app/routers/applications.py` ≥ 2 (import et usage), et `test_manual_offer_key_uses_cleaned_title` passe.
- [x] Le chemin manuel est testé : `grep -cE "^(async )?def test_" backend/tests/test_application_offer_link.py` ≥ 5.
- [x] Lint : `cd backend && uv run --with pyflakes pyflakes app/services/offer_dedup.py retroactive_dedup_job_offers.py tests/test_application_offer_link.py` ne sort rien. `uv run --with pyflakes pyflakes app/tasks/clean_job_offers.py app/tasks/job_offers_collectors.py app/routers/applications.py` n'ajoute aucun avertissement par rapport au baseline.
- [x] Security : `semgrep scan --config p/python --error backend/app/routers/applications.py backend/app/services/offer_dedup.py`, 0 finding.
- [x] Type check : n/a — aucun vérificateur de types configuré dans `backend/pyproject.toml`.
- [x] Manual check : simulation du script (sans `--apply`) contre la base **locale**, avec le code du worktree. Elle doit annoncer 8 paires à fusionner et 11 `unique_key` à recalculer, comme avant le refactor (`scratchpad/retro_local.txt`). Commande machine dans Notes, observateur : l'agent exécutant.

## Steps
- [x] Step 1 : Créer `backend/app/services/offer_dedup.py`.
  - Y déplacer depuis le script, sans changer leur logique : `REFERENCING_COLLECTIONS`, `id_variants`, `pick_survivor`, `is_same_offer`, `find_duplicate_pairs`, `load_referenced_offer_ids`, `move_interactions`, `describe`.
  - Y déplacer `deduplicate_collection` sous la forme `async def merge_duplicate_offers(db, apply: bool = False) -> dict`. Les `print` deviennent `logger.info` / `logger.warning`. La fonction renvoie `{"merged": int, "skipped_referenced": int, "stale_keys": int}`. Elle reçoit `db` au lieu d'appeler `get_database`.
  - `retroactive_dedup_job_offers.py` ne garde que le docstring, `logging.basicConfig(level=logging.INFO, format="%(message)s")` et un `main` qui fait `await merge_duplicate_offers(await get_database(), apply="--apply" in sys.argv[1:])`.
  - Dans `test_normalization_and_dedup.py`, importer `find_duplicate_pairs, pick_survivor` depuis `app.services.offer_dedup`.
  - Ajouter `test_merge_duplicate_offers_keeps_loser_url_and_city_split`, avec un db en `dict` de `MagicMock`/`AsyncMock` :
    - offres A (Capgemini, « Data Scientist », Lyon, URL WTTJ), B (même poste, Lyon, URL LinkedIn), C (même poste, Paris, URL Indeed) ;
    - `applications.distinct` renvoie `[str(B_id)]`, les autres collections référentes `[]`, `user_offer_interactions.find().to_list` renvoie `[]` ;
    - asserts : `delete_one` attendu une seule fois, avec `{"_id": A_id}` ; le `$set` envoyé sur `{"_id": B_id}` contient les deux URL dans `{url} ∪ alternative_urls` ; aucun `delete_one` sur C ; le résultat vaut `merged == 1` et `skipped_referenced == 0`.
  - Verify : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q`, 0 failed. `uv run python -c "import retroactive_dedup_job_offers"`, exit 0.
- [x] Step 2 : Dans `offer_dedup.py`, ajouter deux fonctions extraites à l'identique du bloc l.480-505 de `save_offers_to_database` :
  - `async def find_offer_by_identity(collection, offer: dict) -> Optional[dict]`. Elle cherche avec un `$or` sur : `unique_key` (si elle est renseignée) ; `url` et `alternative_urls` égaux à l'URL nettoyée (si elle existe) ; `url $in offer["alternative_urls"]` (si la liste est présente). Elle renvoie `None` sans requête si aucune condition n'existe.
  - `async def find_company_variant_duplicate(collection, offer: dict, known_companies: list) -> Optional[dict]`. Elle filtre les noms avec `company_match_strength`, lit les candidats avec `find({"entreprise": {"$in": noms}})`, et renvoie le premier pour lequel `are_offers_duplicates(candidate, offer)` est vrai.
  - Remplacer le bloc inline de `save_offers_to_database` par ces deux appels, en gardant le cache paresseux `known_companies` : le `distinct` n'est lu qu'au premier besoin.
  - Verify : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q`, 0 failed (dont `test_save_offers_to_database_*`).
- [x] Step 3 : Nettoyeur.
  - Dans `cleanup_workflow`, l'étape 3 (`enable_global_similarity`) appelle `await merge_duplicate_offers(await get_database(), apply=True)`.
  - Le résumé lit `merged` comme `similarity_deleted` et ajoute `"skipped_referenced"`. Supprimer `kept_active`, `kept_deleted` et `groups_processed` (variables, logs, clés du résumé).
  - Supprimer `remove_similarity_duplicates_global` et les imports qu'elle seule utilisait. Supprimer `test_tombstone_priority_sorting`.
  - Ajouter `test_cleanup_workflow_global_step_uses_insertion_rule` dans `test_clean_and_verify_alignment.py` :
    - `normalize_existing_data`, `remove_exact_duplicates` et `cleanup_invalid_offers` sont patchés en `AsyncMock` qui renvoient des dict vides ;
    - `get_database` est patché pour renvoyer un objet sentinelle ;
    - `merge_duplicate_offers` est patché pour renvoyer `{"merged": 2, "skipped_referenced": 1, "stale_keys": 0}` ;
    - asserts : appel `(sentinelle, apply=True)`, `summary["similarity_duplicates_deleted"] == 2`, `summary["skipped_referenced"] == 1`, `summary["success"] is True`.
  - Verify : `cd backend && uv run pytest tests/test_clean_and_verify_alignment.py tests/test_job_offers_pipeline.py -q`, 0 failed.
- [x] Step 4 : `_ensure_offer_for_application`.
  - `poste = clean_job_title_syntax(position)` si `position`, sinon `"Poste non spécifié"` (repli inchangé). `localisation = location or None`.
  - Entreprise connue : `unique_key = compute_unique_key(company, poste, localisation)`.
  - Entreprise absente :
    - stocker `"Non spécifié"` (convention de `normalize_offer_fields`) ;
    - **ne pas** poser de `unique_key` (l'index est sparse) ;
    - ne pas faire de recherche par clé ni par variante ;
    - une candidature sans entreprise ne doit jamais fusionner avec une autre.
  - Les étapes 2 et 3 (par URL, puis par clé) deviennent `find_offer_by_identity(db["job_offers"], probe)`, puis `find_company_variant_duplicate(..., await db["job_offers"].distinct("entreprise"))` si l'entreprise est connue. `probe` contient `entreprise`, `poste`, `localisation`, `url`, `description` et `unique_key` (si elle existe).
  - Le repli sur `DuplicateKeyError` utilise `find_offer_by_identity(db["job_offers"], new_offer_doc)`.
  - Le reste ne change pas : description complétée, lien de la candidature, `_migrate_user_offer_data`.
  - Créer `backend/tests/test_application_offer_link.py`. Le db est un `dict` de `MagicMock`, avec `applications.update_one` en `AsyncMock` et `application_id = str(ObjectId())`. Tests :
    - `test_manual_offer_found_by_alternative_url` : `find_one` renvoie l'offre existante seulement si `{"alternative_urls": U}` figure dans le `$or`. Le résultat vaut son id, `insert_one` n'est pas attendu.
    - `test_manual_offer_key_uses_cleaned_title` : position `"Data Scientist (CDI)"`, entreprise Capgemini, Lyon. `find_one` ne renvoie l'offre que si `{"unique_key": "capgemini|data scientist|lyon"}` figure dans le `$or`. L'offre est liée.
    - `test_manual_offer_matches_company_variant` : entreprise `"BackMarket"`. `find_one` renvoie `None`, `distinct` renvoie `["Back Market", "Autre"]`, `find().to_list` renvoie un candidat « Back Market », même poste, même ville. L'offre est liée au candidat, sans insertion.
    - `test_manual_offer_without_location_is_not_france` : `location=None`, rien en base. Le document inséré a `localisation is None` et `unique_key == "capgemini|data scientist|non-specifie"`.
    - `test_manual_offer_without_company_is_never_keyed` : `company=""`. Le document inséré n'a pas de clé `unique_key` et vaut `entreprise == "Non spécifié"`. Aucun `$or` passé à `find_one` ne contient de condition `unique_key`, et `distinct` n'est pas attendu.
  - Verify : `cd backend && uv run pytest tests/test_application_offer_link.py -q`, 5 passed.
- [x] Step 5 : Dans `docs/JOB_INGESTION_AND_NORMALIZATION.md`, près de la ligne « Doublons déjà en base », ajouter une ligne : le nettoyage nocturne `cleanup_job_offers` (étape 3) applique chaque nuit la même fusion que le script (`merge_duplicate_offers`) avec écriture, et l'offre créée depuis une candidature passe par la même recherche que l'insertion. Verify : `grep -c "merge_duplicate_offers" docs/JOB_INGESTION_AND_NORMALIZATION.md` ≥ 1.
- [x] Step 6 (teardown) :
  - Orphan scan borné aux symboles remplacés (`remove_similarity_duplicates_global`, `deduplicate_collection`, `test_tombstone_priority_sorting`, `kept_active`, `groups_processed`) : 0 référence. Supprimer aussi les imports devenus inutiles dans `clean_job_offers.py`, `job_offers_collectors.py` et `applications.py` (pyflakes).
  - Lancer la simulation locale (Manual check), puis la suite complète.
  - Verify : les commandes « No dead code », « Lint » et « Suite complète » de la Definition of Done.

## Code Review
- Dead code removed: yes. Les recherches bornées aux symboles remplacés (`remove_similarity_duplicates_global`, `deduplicate_collection`, `test_tombstone_priority_sorting`, `kept_active`, `groups_processed`) dans `backend` et `airflow` donnent 0. pyflakes est muet sur les 6 fichiers de code touchés. Les 6 imports inutilisés de `tests/test_job_offers_pipeline.py` existaient déjà à HEAD (sortie pyflakes identique) : laissés en place.
- Build status: pass. Imports `main`, `retroactive_dedup_job_offers`, `app.tasks.clean_job_offers` et `app.services.offer_dedup` : exit 0. Tests ciblés : 93 passed. Suite complète : 3 failed (les 3 échecs du baseline) et 1158 passed, contre 1152 au baseline (+7 ajoutés, −1 supprimé).
- Type errors: n/a, aucun vérificateur de types configuré.
- Unintended side effects: aucun non documenté. Trois changements voulus figurent dans Notes : l'exception de l'étape 3 remonte désormais, les seuils du DAG ne s'appliquent plus au mode global, et l'entreprise est passée par `.strip()`. Simulation locale identique à l'octet près à celle d'avant le refactor.
- Security surface touched: yes. Dans `applications.py`, le code modifié construit des requêtes Mongo à partir de champs saisis par l'utilisateur, uniquement en égalité ou `$in`, sans `$where` ni regex. semgrep run : pass (`p/python`, 151 règles, 0 finding, exit 0 sur `applications.py` et `offer_dedup.py`).
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-25T19:10Z | claude-code | preflight | done | baseline: imports exit 0 ; tests ciblés 87 passed ; suite complète 3 failed / 1152 passed ; pyflakes des 4 fichiers existants sans sortie ; semgrep applications.py sans finding
- 2026-10-25T19:10Z | claude-code | step 1 | started
- 2026-10-25T19:13Z | claude-code | step 1 | done | `uv run pytest tests/test_normalization_and_dedup.py -q` 44 passed exit 0 ; `uv run python -c "import retroactive_dedup_job_offers"` exit 0
- 2026-10-25T19:13Z | claude-code | step 2 | started
- 2026-10-25T19:14Z | claude-code | step 2 | done | `uv run pytest tests/test_job_offers_pipeline.py -q` 35 passed exit 0 ; pyflakes job_offers_collectors.py + offer_dedup.py exit 0
- 2026-10-25T19:14Z | claude-code | step 3 | started
- 2026-10-25T19:17Z | claude-code | step 3 | done | `uv run pytest tests/test_clean_and_verify_alignment.py tests/test_job_offers_pipeline.py -q` 44 passed exit 0 ; pyflakes clean_job_offers.py exit 0
- 2026-10-25T19:17Z | claude-code | step 4 | started
- 2026-10-25T19:19Z | claude-code | step 4 | done | `uv run pytest tests/test_application_offer_link.py -q` 5 passed exit 0 ; pyflakes applications.py + test exit 0
- 2026-10-25T19:19Z | claude-code | step 5 | started
- 2026-10-25T19:19Z | claude-code | step 5 | done | `grep -c "merge_duplicate_offers" docs/JOB_INGESTION_AND_NORMALIZATION.md` = 1
- 2026-10-25T19:19Z | claude-code | step 6 | started
- 2026-10-25T19:23Z | claude-code | step 6 | done | orphan grep = 0 ; pyflakes des 6 fichiers sans sortie, exit 0 ; simulation locale « Paires à fusionner : 8 », « unique_key à recalculer avec --apply : 11 », sortie identique à `retro_local.txt` ; `uv run pytest tests -q` 3 failed (baseline) / 1158 passed
- 2026-10-25T19:27Z | claude-code | close out | done | DoD relancée en une passe : build exit 0 ; ciblés 93 passed ; 3 tests nommés passed ; dead code 0 ; `merge_duplicate_offers` ×2 dans clean_job_offers.py ; `find_offer_by_identity` 2 et 3 ; `or "(Entreprise|France)"` 0 ; `clean_job_title_syntax` 2 ; 5 tests manuels ; pyflakes muet ; semgrep 0 finding exit 0 ; les 7 tests ajoutés passent avec `MONGO_HOST=127.0.0.1:1` ; diff relu en entier

## Notes
- Fichiers de convention lus en Phase 3 : `CLAUDE.md`, `AGENTS.md` et `GEMINI.md` (identiques : code-review-graph, directives de suppression des tests) et `.cursorrules` (code-review-graph). Aucun fichier de convention sous `backend/`.
- Baseline (Phase 3, 2026-10-25) :
  - `uv run pytest tests -q` donne 3 failed / 1152 passed. Échecs préexistants, hors périmètre : `test_admin.py::test_admin_endpoints_forbidden_for_normal_user`, `test_admin.py::test_admin_toggle_status_cannot_disable_self` et `test_offer_evaluation.py::test_evaluate_invalid_ids` (TypeError).
  - Tests ciblés : 87 passed.
  - pyflakes de `clean_job_offers.py`, `job_offers_collectors.py`, `applications.py` et `retroactive_dedup_job_offers.py` : aucune sortie.
  - semgrep `p/python` sur `applications.py` : 0 finding.
- `git status` en Phase 3 : seuls les changements du retrait France Travail (même session) touchent le périmètre, dans `job_offers_collectors.py` et la doc ; aucun conflit.
- **Conséquence du déploiement** : une fois déployé, le nettoyage de 06:00 UTC applique en écriture les fusions que le script annonce en simulation, soit 12 paires en prod et 8 en local. Déployer revient donc à lancer `--apply`. À dire à l'utilisateur avant tout déploiement, avec un `mongodump` préalable.
- Les offres `is_deleted` sont exclues de la fusion (comme dans le script) : le nettoyeur ne propage plus les tombstones. C'est un choix : une offre fermée sur un site peut rester ouverte ailleurs, et `verify_job_offers` se charge de la clôture.
- Hors périmètre, signalé :
  - `is_offer_referenced_by_application` et `cleanup_invalid_offers` ne protègent que `applications` (pas les évaluations ni les kits) ;
  - `prevent_duplicate_insertion` n'est jamais appelée ;
  - une offre manuelle sans entreprise (`"Non spécifié"`) serait passée en soft-delete par `cleanup_invalid_offers`. Ce cas est impossible via l'API (`company: str` requis) et absent en prod.
- Commande du Manual check, propre à cette machine : elle monte le code du worktree dans l'image backend locale, sur le réseau du conteneur, en lecture seule et sans `--apply`. `cd <worktree> && docker run --rm --network "$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' jobtracker-backend)" -v "$PWD/backend:/app" -w /app -e PYTHONPATH=/app --env-file /Users/elielkatche/job-tracker/.env "$(docker inspect -f '{{.Config.Image}}' jobtracker-backend)" python retroactive_dedup_job_offers.py`. Attendu : « Paires à fusionner : 8 » et « unique_key à recalculer avec --apply : 11 ».
- Écarts et changements de comportement relevés à l'exécution :
  - **Propagation d'exception** : `remove_similarity_duplicates_global` interceptait ses propres exceptions. Si `merge_duplicate_offers` lève une exception, `cleanup_workflow` passe par son `except` global et renvoie `success: False`, sans faire les étapes 4 et 5. Le comportement est plus honnête (un échec de fusion n'est plus masqué), mais c'est un changement.
  - **Seuils du DAG** : `airflow/dags/clean_job_offers.py` passe `company_similarity_threshold=0.80` et `position_similarity_threshold=0.75`. Ils ne servent plus qu'au mode standard (`remove_similarity_duplicates`, désactivé dans le DAG). Le mode global applique la règle de l'insertion avec ses propres seuils (intitulé ≥ 0.82, Jaccard ≥ 0.5 si l'entreprise ne correspond que faiblement). C'est le but de l'alignement. Le DAG est hors périmètre et reste inchangé.
  - **`.strip()` sur l'entreprise** dans `_ensure_offer_for_application` : non prévu par le plan. Une entreprise faite d'espaces est donc traitée comme absente (pas de clé), au lieu de produire une clé vide.
  - L'étape « clés périmées » réécrit chaque nuit quelques `unique_key` (« Non spécifié » stocké contre `non-specifie` calculé). Ce sont des écritures inoffensives, déjà présentes dans le script.
  - Test de fusion : la variable de compréhension `c` est renommée `call`, parce qu'elle masquait visuellement l'offre C. Pas de changement de logique ; 44 passed après le renommage.
  - Correction à l'exécution : monter le worktree sur `/app` masque le venv de l'image (`/app/.venv`), d'où `ModuleNotFoundError: No module named 'motor'`. La commande qui marche monte le code sur `/src`, en lecture seule : `docker run --rm --network job-tracker_app-network -v <worktree>/backend:/src:ro -w /src -e PYTHONPATH=/src --env-file /Users/elielkatche/job-tracker/.env job-tracker-backend /app/.venv/bin/python retroactive_dedup_job_offers.py`.
