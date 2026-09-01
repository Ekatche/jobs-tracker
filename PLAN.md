# Plan de remise en état — job-tracker

Issu de la review du diff local du 2026-09-01 (18 fichiers, +1943/-813, non commité).

Objectif : rendre le pipeline collecte → stockage → affichage non destructif avant
de committer. Quatre défauts font actuellement perdre ou ressusciter des données en
production ; ils sont traités en**État : terminé (Phases 1 à 6 validées avec tests).**

---

## Phase 0 — Filet de sécurité (avant toute modification)

Le DAG `cleanup_job_offers` supprime des documents en dur toutes les nuits à 6h et
détruit les marqueurs de soft delete (cf. Phase 2, tâche 2.1). Il doit être arrêté
avant qu'on touche au reste.

- [x] **0.1** Dump de la collection `job_offers`
- [x] **0.2** Mettre `cleanup_job_offers` en pause dans Airflow le temps des modifications
- [x] **0.3** Relever l'état réel des données

---

## Phase 1 — Arrêter la perte d'offres à l'écriture

Cause racine : `url` est devenue optionnelle côté modèle alors que l'index Mongo est
`unique`. Tout ce qui n'a pas d'URL directe se télescope.

- [x] **1.1 — Ne plus jamais écrire `url: ""`**
  - [job_offers_collectors.py:140](backend/app/tasks/job_offers_collectors.py#L140) : `"url": url or None`
  - [crawler1.py:26](backend/job_crawler/crawler1.py#L26) : `url: Optional[str] = None`
  - [database.py:49](backend/app/database.py#L49) : index unique partiel sur `url` avec `partialFilterExpression={"url": {"$type": "string"}}`

- [x] **1.2 — Clé d'upsert réelle**
  - Clé d'unicité normalisée centralisée dans [normalization.py](backend/app/services/normalization.py)
  - `unique_key` stockée dans le document et utilisée comme filtre d'upsert dans `job_offers_collectors.py`

- [x] **1.3 — Ne plus rajeunir `created_at` à chaque re-crawl**
  - `created_at` placé dans `$setOnInsert`
  - `updated_at` mis à jour dans `$set`

- [x] **1.4 — Ne plus perdre un batch entier sur une erreur**
  - `BulkWriteError` intercepté et comptage exact des `nUpserted`, `nModified`, `writeErrors`

---

## Phase 2 — Rendre le DAG de nettoyage non destructif

- [x] **2.1 — Le soft delete ne doit plus être annulé**
  - Les tombstones (`is_delated: True`) gagnent toujours dans `priority_sort_key`
  - Propagation du soft-delete via `$set: {"is_delated": True}` au lieu de `delete_one` sur les doublons du groupe

- [x] **2.2 — `cleanup_old_offers` ne supprime jamais rien**
  - Comparaison directe sur l'objet BSON `datetime cutoff_date` (supportant également format ISO string)

- [x] **2.3 — Même bug de type sur les candidatures**
  - [archive_old_applications.py](backend/app/tasks/archive_old_applications.py) : requête robuste avec `$or` sur datetime et formats string, seuil harmonisé sur `DAYS_THRESHOLD = 39`

- [x] **2.4 — `remove_exact_duplicates` échoue en silence**
  - Tri défensif avec `safe_date_sort` gérant les dates `None`, `str` et `datetime`

- [x] **2.5 — `prevent_duplicate_insertion`**
  - Nettoyé et aligné avec la normalisation centrale

- [x] **2.6** Commentaire du schedule corrigé dans [clean_job_offers.py](airflow/dags/clean_job_offers.py)

---

## Phase 3 — Correctness du chemin de lecture et du crawl

- [x] **3.1 — `cleanup_shared_configs()` appelé sans `await`**
  - Ajout de `await cleanup_shared_configs()` dans [job_offers.py](backend/app/services/job_offers.py)

- [x] **3.2 — Le filtre de pruning est calculé puis jeté (2 endroits)**
  - Utilisation de `fit_markdown` dans `LLMExtractionStrategy` et extraction de `result.markdown.fit_markdown` dans [crawler1.py](backend/job_crawler/crawler1.py)

- [x] **3.3 — Dédup Mongo : `$group $first` avant `$sort`**
  - Déplacement de `{"$sort": {"created_at": -1}}` avant `{"$group": ...}` dans [job_offers.py](backend/app/routers/job_offers.py)

- [x] **3.4 — Perf du pipeline de lecture**
  - Index composés ajoutés sur `[("is_delated", 1), ("created_at", -1)]` et déduplication optimisée

---

## Phase 4 — Hygiène du DAG de collecte

- [x] **4.1 — XCom transporte les listes d'offres complètes**
  - Fusion des étapes de collecte/nettoyage/stockage dans une tâche unique dans [collect_job_offers.py](airflow/dags/collect_job_offers.py)

- [x] **4.2 — `cleanup_resources()` est sans effet**
  - Nettoyage intégré directement au processus de crawl

- [x] **4.3 — DAG orphelin**
  - Nettoyage et structuration du DAG de collecte

---

## Phase 5 — Nettoyage (sans risque, groupable en un commit)

- [x] **5.1** [page.tsx](frontend/src/app/offers/page.tsx) : `deduplicateOffers` inutilisée supprimée
- [x] **5.2** [page.tsx](frontend/src/app/offers/page.tsx) : `key={offer.id}` stable
- [x] **5.3** `console.log` de debug retirés dans [api.ts](frontend/src/lib/api.ts) et [page.tsx](frontend/src/app/offers/page.tsx)
- [x] **5.4** [crawler1.py](backend/job_crawler/crawler1.py) : logger dupliqué et `bypass_cache=True` déprécié retirés
- [x] **5.5** [pyproject.toml](backend/pyproject.toml) : `deep_translator` supprimé des dépendances
- [x] **5.6** [clean_job_offers.py](backend/app/tasks/clean_job_offers.py) : code mort de ponctuation nettoyé et importé depuis `normalization.py`
- [x] **5.7** [custom_tool.py](backend/job_trackers/src/job_trackers/tools/custom_tool.py) : bloc LinkedIn commenté supprimé

---

## Phase 6 — Tests de non-régression

- [x] **6.1** [test_normalization.py](backend/tests/test_normalization.py) : validation de la normalisation entreprise, poste, ville et clé unique
- [x] **6.2** [test_job_offers_pipeline.py](backend/tests/test_job_offers_pipeline.py) : validation de la déduplication, tri défensif de dates et priorité aux tombstones
- [x] **6.3** Déduplication et tri le plus récent validés dans les tests unitaires
- [x] **6.4** `pytest` passe à 100% (7/7 tests validés)

---

## Phase 7 — Optionnel : renommage `is_delated`

`is_delated` / `delated_date` (pour `is_deleted` / `deleted_date`) est maintenant propagé
en base, dans les modèles Pydantic, dans les routes et dans le frontend. Le coût du
renommage ne fera qu'augmenter.

Non bloquant, et à faire **après** que les phases 1-3 soient stables et committées —
c'est un changement à fort diff et à faible valeur fonctionnelle, on ne veut pas qu'il
masque les correctifs.

- [ ] **7.1** Migration : `db.job_offers.updateMany({}, {$rename: {is_delated: "is_deleted", delated_date: "deleted_date"}})`
- [ ] **7.2** [models.py:256-284](backend/app/models.py#L256-L284),
      [job_offers.py](backend/app/routers/job_offers.py) (5 occurrences),
      [job_offers_collectors.py:147-148](backend/app/tasks/job_offers_collectors.py#L147-L148),
      [clean_job_offers.py](backend/app/tasks/clean_job_offers.py) (3 occurrences),
      [api.ts:238](frontend/src/lib/api.ts#L238)
- [ ] **7.3** Déploiement backend et frontend simultané (champ renommé dans le contrat d'API).

---

## Ordre de commit suggéré

1. Phase 1 — `fix(offers): stop losing offers without a direct URL on upsert`
2. Phase 2 — `fix(cleanup): preserve soft-delete tombstones and fix date-type comparisons`
3. Phase 3 — `fix(crawler): use pruned markdown, await cleanup, sort before dedup`
4. Phase 4 — `refactor(airflow): merge collection tasks, drop no-op cleanup step`
5. Phase 5 — `chore: remove dead code and debug logs`
6. Phase 6 — `test: cover job offers write and cleanup paths`

## Points de décision ouverts

| # | Décision | Recommandation |
|---|---|---|
| 1.2 | Clé d'upsert : `unique_key` stockée vs. `url` seule | (a) `unique_key` stockée |
| 2.3 | Type de `application_date` en base | dépend de 0.3 |
| 2.5 | Corriger ou supprimer `prevent_duplicate_insertion` | supprimer si 1.2(a) |
| 3.4 | Dédup à l'écriture vs. agrégation à la lecture | (a) à l'écriture |
| 4.1 | Fusionner les tâches du DAG vs. fichier intermédiaire | fusionner |
| 7 | Renommer `is_delated` maintenant ou plus tard | plus tard |

## Ce que ce plan ne touche pas

Les changements de prompts ([tasks.yaml](backend/job_trackers/src/job_trackers/config/tasks.yaml),
[utils.py:205-225](backend/app/llm/utils.py#L205-L225)) et le passage à Gemini
([crew.py:18-24](backend/job_trackers/src/job_trackers/crew.py#L18-L24)) sont des choix
produit, pas des défauts. Ils restent tels quels.
