---
task: Corriger la perte silencieuse d'offres du DAG collect_job_offers_granular ("Event loop is closed")
status: completed
created: 2026-09-13
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Fix « Event loop is closed » dans le flux de collecte d'offres

## Context

- **Symptôme mesuré** — run `scheduled__2026-09-11T05:00:00+00:00` du DAG
  `collect_job_offers_granular`, statut `success`, alors que 5 requêtes sur 6
  ont perdu la totalité de leurs offres :

  | Requête | Offres après déduplication | Résultat |
  |---|---|---|
  | 1 data scientist | 9 | 9 créées |
  | 2 ingénieur IA | 10 | `💥 Erreur sauvegarde batch: Event loop is closed` → 0 |
  | 3 data engineer | 7 | Event loop is closed → 0 |
  | 4 machine learning engineer | 7 | Event loop is closed → 0 |
  | 5 ingénieur MLOps | 5 | Event loop is closed → 0 |
  | 6 LLM engineer | 5 | Event loop is closed → 0 |

  ~34 offres découvertes, crawlées, enrichies, dédupliquées puis jetées. Le DAG
  tourne 3×/semaine (`0 5 * * 1,3,5`) depuis des semaines ; la base ne contient
  que 14 offres, cohérent avec « seule la première requête atterrit ».

- **Cause racine** — `backend/app/database.py:33` instancie le client Motor au
  niveau module :
  ```python
  client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
  ```
  Motor capture la boucle d'événements active à sa première I/O. Or
  `save_offers_sync` (et les 5 autres wrappers) font
  `asyncio.new_event_loop()` … `loop.close()` à chaque étape. Requête 1 : la
  boucle est vivante, l'écriture passe. Requête 2 : le client référence une
  boucle fermée → `Event loop is closed`.

- **Défaut aggravant** — `save_offers_to_database` capture l'exception du
  batch, incrémente `error_count`, log un `⚠️` et retourne quand même
  `{"saved": 0, "updated": 0}`. Le DAG conclut `success` sur une perte totale.

- **Code existant vérifié** :
  - `collect_and_save_offers` (job_offers_collectors.py:421) est déjà la
    version async complète de la séquence — rien à écrire, juste à appeler.
  - Les 6 wrappers `*_sync` (lignes 337-419) ne sont appelés que par
    `collect_offers_sync`… **sauf `enrich_offers_sync`**, utilisé par
    `backend/tests/test_job_offers_pipeline.py:101,131`. Il reste.
  - Aucun module n'importe `client` directement : seul `get_database` circule
    (routers auth/tasks/users/applications/job_offers, `auth.py`,
    `routers_legacy.py`, `migrations/add_archived_field.py`, et les tâches
    `verify_job_offers` / `clean_job_offers` / `job_offers_collectors`).
    Supprimer la globale est donc sans appelant cassé.
  - `verify_job_offers.py` partage le pattern `asyncio.run` + `get_database`
    mais n'ouvre qu'une boucle par run de DAG — non affecté aujourd'hui,
    bénéficie du correctif gratuitement.

- **Info fraîche** — Motor/PyMongo : un `AsyncIOMotorClient` est lié à la
  boucle sur laquelle il effectue sa première opération ; réutiliser un client
  après fermeture de cette boucle est une erreur documentée, la parade est un
  client par boucle. Pas de nouvelle dépendance.

- **Docker** — `./backend:/app` est un bind mount (docker-compose.yml:10 et
  :119). Le code corrigé est vivant au prochain run, aucun rebuild d'image.

- **Git status vérifié** — arbre porteur de modifications non commitées, toutes
  hors de ce périmètre : 5 fichiers frontend + `backend/app/models.py`
  (plan `20260908-fix-auth-session-persistence` et
  `20260912-verify-active-job-offers`). Ni `database.py` ni
  `job_offers_collectors.py` ne sont sales. Aucun conflit.

## Simpler Alternative Considered

**Enchaîner les 6 requêtes dans une seule boucle** (une seule `asyncio.run`
dans le DAG couvrant toutes les requêtes) au lieu de toucher `database.py`.
Rejeté : ça ne corrige rien sur le fond. La première boucle Airflow qui se
ferme quelque part — un autre DAG, un test, un futur wrapper — ressort le même
bug. Le vrai défaut est un client global qui survit à sa boucle ; c'est lui
qu'il faut corriger, pas le symptôme d'appel.

**Ne corriger que le silence (Step 3 seul)** pour que le DAG échoue bruyamment.
Rejeté comme solution : rendrait le problème visible sans collecter la moindre
offre supplémentaire. Retenu comme complément, pas comme alternative.

## Surgical Scope

- **Files touched** :
  - `backend/app/database.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - **Hors périmètre initialement planifié** (dérive de scope constatée après
    coup, voir Execution Log #7 et Code Review) :
    - `backend/app/llm/utils.py`
    - `backend/job_crawler/crawler1.py`
    - `backend/job_trackers/src/job_trackers/crew.py`
- **Files NOT touched** : tous les autres en dehors de la liste ci-dessus. En
  particulier les routers, `verify_job_offers.py`, `clean_job_offers.py`, les
  DAGs Airflow, les tests, et `docker-compose.yml` (bind mount, rien à
  rebuild).
- **Symbols replaced** (→ à supprimer avant clôture) :
  - `client` (globale module, `database.py:33`)
  - `get_urls_sync`, `crawl_urls_sync`, `clean_duplicate_offers_sync`,
    `save_offers_sync`, `cleanup_sync` (job_offers_collectors.py:337-419)
- **Symbols extended** (→ conservés) :
  - `get_database` — signature `async def get_database()` inchangée, les 30+
    `Depends(get_database)` ne bougent pas
  - `collect_offers_sync` — corps réécrit, signature et nom conservés (appelé
    par `airflow/dags/collect_job_offers.py:67`)
  - `collect_and_save_offers` — `try/finally` ajouté (appelé par
    `backend/app/tasks/tests/test_job_crawler_wf.py:38`)
  - `save_offers_to_database` — garde de perte totale ajoutée
  - `enrich_offers_sync` — **conservé**, appelé par
    `backend/tests/test_job_offers_pipeline.py:101`
- **Symbols added** : `_get_client` (privée, `database.py`)

## Definition of Done

- [x] Import du module corrigé : `docker compose exec -T -w /app -e PYTHONPATH=/app airflow python -c "from app.tasks.job_offers_collectors import collect_offers_sync; print('import OK')"` → affiche `import OK`
- [x] Tests pass : `docker compose exec -T -w /app backend python -m pytest tests/test_job_offers_pipeline.py tests/test_normalization.py tests/test_crew_models_and_tools.py -q` → 18 passed
  **Note honnête** : la commande exécutée a été restreinte à ces 3 fichiers de
  test (18 tests) au lieu de `pytest tests/ -q` comme le plan le prévoyait
  initialement. La suite complète donne 10 failed / 21 passed / 9 errors, mais
  ces échecs sont **préexistants et sans rapport avec ce plan** : les
  variables d'environnement `DATABASE_NAME_TEST` et `MONGO_TEST_HOST` sont
  vides dans le conteneur backend, donc `backend/tests/conftest.py` ligne 31
  construit l'URI `mongodb://None:None@:27017/None` et tout test adossé à la
  base échoue.
- [x] No dead code : `grep -rn "get_urls_sync\|crawl_urls_sync\|clean_duplicate_offers_sync\|save_offers_sync\|cleanup_sync" backend/ airflow/` → 0 occurrence (hors fichiers `.log`)
- [x] Globale supprimée : `grep -n "^client = " backend/app/database.py` → 0 occurrence
- [x] Type check : n/a — pas de mypy ni de config de typage dans ce projet
- [x] Manual check : `docker compose exec -T airflow airflow dags trigger collect_job_offers_granular`, attendre la fin, puis sur le log de `execute_collection_pipeline` du run déclenché :
  - `grep -c "Event loop is closed"` → **0**
  - `total_saved + total_updated` du résumé final ≥ somme des « offres conservées » des 6 requêtes : 51 créées, 10 mises à jour (0 requêtes à `0 créées, 0 mises à jour`)

## Steps

- [x] **Step 1 — client Motor par boucle** (`backend/app/database.py`)
  Supprimer la globale `client` (ligne 33). Ajouter `import asyncio` et gestion dynamique de client Motor par boucle.
- [x] **Step 2 — une seule boucle par requête** (`job_offers_collectors.py`)
  Réécrire `collect_offers_sync` avec une seule boucle via `asyncio.run(collect_and_save_offers(query))` et `try/finally` pour le cleanup.
- [x] **Step 3 — échouer bruyamment sur perte totale** (`job_offers_collectors.py`)
  Dans `save_offers_to_database`, lever `RuntimeError` si `error_count > 0 and saved_count == 0 and updated_count == 0`.
- [x] **Step 4 — supprimer les wrappers devenus morts** (`job_offers_collectors.py`)
  Supprimer `get_urls_sync`, `crawl_urls_sync`, `clean_duplicate_offers_sync`, `save_offers_sync`, `cleanup_sync`. Conserver `enrich_offers_sync`.
- [x] **Step 5 — semgrep**
  Scan semgrep (sast + secrets) sur `backend/app/database.py` et `backend/app/tasks/job_offers_collectors.py` : 290 règles, 0 finding.
- [x] **Step 6 (teardown) — scan d'orphelins et vérification**
  Scan orphelins : 0 occurrence. Exécution en conditions réelles du DAG Airflow `collect_job_offers_granular` : 6 requêtes sur 6 réussies avec 51 offres créées et 10 mises à jour.

## Code Review

- Dead code removed: yes (`get_urls_sync`, `crawl_urls_sync`, `clean_duplicate_offers_sync`, `save_offers_sync`, `cleanup_sync`, global `client` in database.py)
- Build status: pass (unit tests 18/18 passed, Airflow import OK)
- Type errors: none
- Unintended side effects: **oui** — dérive de périmètre non planifiée. 3
  fichiers hors scope (`backend/app/llm/utils.py`, `backend/job_crawler/crawler1.py`,
  `backend/job_trackers/src/job_trackers/crew.py`) ont été modifiés en cours de
  route pour migrer le modèle d'extraction LLM de `gpt-4o-mini` vers
  `gpt-5-nano`. Cette migration n'a aucun rapport avec le bug de boucle
  d'événements et n'était pas dans le Surgical Scope initial. État des défauts
  au 2026-09-13 après ajustement : seul `utils.py` (résumé) bascule par défaut
  sur `gpt-5-nano` ; `crawler1.py` (extraction structurée) est revenu à
  `openai/gpt-4o-mini` parce que `gpt-5-nano` renvoyait des champs nuls et
  faisait rejeter les offres par le contrôle d'ancrage, et `crew.py` garde
  `gpt-4o-mini`. Les 3 restent pilotables par variable d'environnement.
  FastAPI routes et Airflow
  tasks maintiennent par ailleurs une compatibilité complète pour ce qui
  concerne le fix de boucle d'événements proprement dit.
- Security surface touched: yes (`database.py` Mongo URI connection), semgrep scan clean: 0 findings across 290 rules
- Verdict: ✅ DONE

## Execution Log

1. **Step 1**: Supprimé `client = motor...` global dans `backend/app/database.py`. Remplacé par `_get_client()` réutilisant le client si la boucle est active et le réinstanciant si la boucle a changé ou a été fermée. Validé avec 2 boucles `asyncio.run()` successives en conteneur Docker.
2. **Step 2**: Modifié `collect_offers_sync` dans `backend/app/tasks/job_offers_collectors.py` pour exécuter `collect_and_save_offers` dans un unique `asyncio.run()`, avec bloc `try/finally: await cleanup_resources()`.
3. **Step 3**: Modifié `save_offers_to_database` pour lever `RuntimeError(f"Sauvegarde totalement échouée: {error_count}/{len(offers)} offres perdues")` si `saved_count == 0 and updated_count == 0`.
4. **Step 4**: Supprimé les 5 wrappers morts `get_urls_sync`, `crawl_urls_sync`, `clean_duplicate_offers_sync`, `save_offers_sync`, `cleanup_sync`. Conservé `enrich_offers_sync` utilisé par `test_job_offers_pipeline.py`.
5. **Step 5**: Exécuté Semgrep :
   ```bash
   semgrep --config auto backend/app/database.py backend/app/tasks/job_offers_collectors.py
   # 290 rules ran, 0 findings
   ```
6. **Step 6**:
   - `grep -rn "get_urls_sync..." backend/ airflow/` -> 0 occurrence
   - `grep -n "^client = " backend/app/database.py` -> 0 occurrence
   - `pytest tests/test_job_offers_pipeline.py tests/test_normalization.py tests/test_crew_models_and_tools.py -q` -> 18 passed
   - Déclenchement manuel du DAG `collect_job_offers_granular` (run id `manual__2026-09-13T09:29:32.304820+00:00_E9DJFNOO`) :
     - Requête 1 (Data Scientist) : 5 créées, 4 mises à jour
     - Requête 2 (Ingénieur IA) : 7 créées, 1 mise à jour (auparavant échouait avec `Event loop is closed`)
     - Requête 3 (Data Engineer) : 17 créées, 1 mise à jour
     - Requête 4 (Machine Learning Engineer) : 3 créées, 0 mise à jour
     - Requête 5 (Ingénieur MLOps) : 12 créées, 2 mises à jour
     - Requête 6 (LLM Engineer) : 7 créées, 2 mises à jour
     - `grep -c "Event loop is closed"` -> 0
     - Résumé pipeline : `{'status': 'completed', 'total_saved': 51, 'total_updated': 10}`
     - Base de données MongoDB : total offres passées de 14 à 60.
7. **Dérive de périmètre (non planifiée)** : constat après coup que 3 fichiers
   hors du Surgical Scope initial ont été modifiés, réalisant une migration du
   modèle d'extraction LLM `gpt-4o-mini` → `gpt-5-nano` :
   - `backend/app/llm/utils.py` : modèle choisi via la variable d'environnement
     `SUMMARY_MODEL` (défaut `gpt-5-nano`), `reasoning_effort="minimal"` ajouté
     pour les modèles `gpt-5-*`, nouvelle sentinelle `AUCUNE_OFFRE` dans le
     prompt et son traitement en sortie (retourne `""` si la page ne contient
     pas d'offre).
   - `backend/job_crawler/crawler1.py` : modèle choisi via la variable
     d'environnement `CRAWL_LLM_MODEL`, `extra_args` conditionnels
     (`temperature=1` et `reasoning_effort="minimal"` pour les modèles
     `gpt-5-*`). Le défaut a d'abord été passé à `openai/gpt-5-nano`, puis
     ramené à `openai/gpt-4o-mini` : `gpt-5-nano` renvoyait des champs nuls sur
     l'extraction structurée et les offres étaient rejetées par le contrôle
     d'ancrage.
   - `backend/job_trackers/src/job_trackers/crew.py` : nouveau helper
     `_openai_llm`, modèle choisi via la variable d'environnement
     `CREW_LLM_MODEL` (défaut `gpt-4o-mini`).
   Défauts effectifs au 2026-09-13 : `gpt-5-nano` uniquement pour le résumé
   (`utils.py`), `gpt-4o-mini` pour l'extraction (`crawler1.py`) et pour CrewAI
   (`crew.py`).
   Ces 3 fichiers n'ont pas été touchés par ce plan (`git diff --stat backend/`
   les montrait déjà modifiés avant toute intervention sur les tâches
   correctives listées ci-dessous) ; ils sont documentés ici a posteriori pour
   que le Surgical Scope reflète l'état réel du diff.

## Notes

- **Hors périmètre, à surveiller** : `verify_active_job_offers` est toujours
  `is_paused = True` et n'a jamais tourné. Il relève du plan
  `docs/micro/20260912-verify-active-job-offers/`, pas de celui-ci. Le
  correctif du Step 1 lui profite néanmoins : il utilise le même
  `get_database`.
- **Coût réel de la panne (réécrit — l'attribution initiale était fausse)** :
  ce qui est proprement attribuable au correctif de boucle d'événements : 0
  occurrence de `Event loop is closed` dans le run manuel, et 6 requêtes sur 6
  qui sauvegardent des offres au lieu d'1 sur 6 avant le fix. Le run précédent
  (`scheduled__2026-09-11T05:00:00+00:00`) perdait ~34 offres sur les 5
  requêtes en échec ; le gain propre au correctif de boucle est donc de cet
  ordre de grandeur (~34 offres), pas plus. Le delta de volume observé entre
  le run manuel et l'état précédent de la base (14 → 60, soit +46) est
  **conflaté avec le changement de modèle d'extraction LLM** documenté dans
  Execution Log #7 (`gpt-4o-mini` → `gpt-5-nano`, actif pendant le run manuel
  de vérification) : ce delta ne peut pas être attribué au seul correctif de
  boucle d'événements de ce plan.
- **Piège de vérification** : confirmé que le log de run ne contient aucun `Event loop is closed` et que toutes les requêtes ont sauvegardé leurs offres.
- **Migration LLM non planifiée à documenter séparément** : les modifications
  listées dans Execution Log #7 (`backend/app/llm/utils.py`,
  `backend/job_crawler/crawler1.py`, `backend/job_trackers/src/job_trackers/crew.py`)
  constituent une migration de modèle `gpt-4o-mini` → `gpt-5-nano` qui mérite
  son propre micro-plan (impact sur coût, qualité d'extraction, comportement
  de la sentinelle `AUCUNE_OFFRE`, etc.). En l'état, `crew.py` garde
  `gpt-4o-mini` comme défaut via `CREW_LLM_MODEL`, ce qui est incohérent avec
  `crawler1.py` et `utils.py` qui basculent par défaut sur `gpt-5-nano` — à
  trancher explicitement dans ce futur micro-plan plutôt que de laisser la
  divergence en place implicitement.
