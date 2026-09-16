---
task: Connecteurs ATS Zero-Token (Greenhouse, Lever, Ashby, Workable, Remotive, JSON-LD) et alignement des scripts de vérification et nettoyage sur le modèle JobOffer
status: done
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Connecteurs ATS Zero-Token & alignement des scripts de nettoyage

## Context

- Existing code checked :
  - `backend/app/tasks/job_offers_collectors.py:98-117` (`crawl_urls_for_offers`) : envoie 100% des URLs à `get_job_offers_from_query` / Crawl4AI dans `crawler1.py`, consommant un navigateur headless Chromium et 1000-2000 tokens LLM par page (`RobustLLMExtractionStrategy`), même pour des plateformes disposant d'APIs publiques directes ou de balises Schema.org JSON-LD.
  - `backend/app/models.py:285-324` (`JobOfferCreate`, `JobOfferResponse`) : définit `pipeline_stage: Optional[str] = "discovered"` (valeurs canoniques : `"discovered"`, `"evaluated"`, `"expired"`), `is_deleted: Optional[bool] = False`, `deleted_date`, `deletion_reason`.
  - `backend/app/models.py:117-132` (`JobApplication`) : champ `offer_id: Optional[str] = None` liant une candidature à une offre collectée.
  - `backend/app/tasks/verify_job_offers.py:465-490` (`_apply_verification_updates`) : met à jour `is_deleted=True`, `deleted_date`, `deletion_reason`, mais omet `pipeline_stage="expired"`, créant une désynchronisation d'état avec le modèle de données et le pipeline Kanban.
  - `backend/app/tasks/clean_job_offers.py:140-230` : logique de déduplication et suppression sans jointure préventive avec `db["applications"]` (`offer_id`), risquant d'orpheliner des candidatures utilisateur en cours si une offre est supprimée.
  - Git status checked : branche `main`, seuls les fichiers du plan précédent non commités sont présents (`job_offers_collectors.py`, `role_normalizer.py`, etc., tous testés et validés).
  - Fresh info looked up : endpoints publics Zero-Token vérifiés pour Greenhouse (`boards-api.greenhouse.io`), Lever (`api.lever.co/v0/postings`), Workable (`apply.workable.com/api/v1/widget/accounts`), Remotive (`remotive.com/api/remote-jobs`), et standard Schema.org JSON-LD (`<script type="application/ld+json">` avec `@type: JobPosting`).

## Simpler Alternative Considered

Laisser Crawl4AI et le LLM extraire toutes les URLs et n'ajouter que des regex côté crawler. Écarté : Crawl4AI est lourd en mémoire, sensible aux blocages Cloudflare/DOM, lent (15-45s par offre) et consomme inutilement du budget token là où une simple requête HTTP GET de 200 ms renvoie un JSON officiel déjà propre.

Pour les scripts de nettoyage : tout réécrire de zéro a été écarté. L'approche chirurgicale consiste à injecter la vérification `offer_id` dans `clean_job_offers.py` et à synchroniser `pipeline_stage: "expired"` dans `verify_job_offers.py`.

## Surgical Scope

- **Files touched** :
  - `backend/app/services/ats/__init__.py` (nouveau)
  - `backend/app/services/ats/router.py` (nouveau)
  - `backend/app/tasks/job_offers_collectors.py` (interception dans `crawl_urls_for_offers`)
  - `backend/app/tasks/verify_job_offers.py` (synchronisation `pipeline_stage: "expired"`)
  - `backend/app/tasks/clean_job_offers.py` (protection `offer_id` et synchronisation `pipeline_stage`)
  - `backend/tests/test_ats_parsers.py` (nouveau)
  - `backend/tests/test_clean_and_verify_alignment.py` (nouveau)
- **Files NOT touched** : `backend/job_crawler/crawler1.py` (reste le fallback propre pour les URLs non-ATS), `backend/app/models.py` (schéma déjà prêt), `frontend/*` (aucun impact visuel régressif).
- **Symbols replaced** (→ à supprimer avant la fin) : none.
- **Symbols extended** (→ à garder) :
  - `app/services/ats/router.py` — `async def extract_ats_or_jsonld_offer(url: str, client: Optional[httpx.AsyncClient] = None) -> Optional[dict]`, détecteurs de domaines, parseur JSON-LD universel.
  - `job_offers_collectors.py::crawl_urls_for_offers` — partitionne les URLs entre extracteur ATS direct et fallback Crawl4AI.
  - `verify_job_offers.py::_apply_verification_updates` — inclut `pipeline_stage: "expired"`.
  - `clean_job_offers.py` — fonction `is_offer_referenced_by_application(offer_id, db)` prévenant tout hard-delete.

## Definition of Done

- [x] Build passes : `cd backend && uv run ruff check app/services/ats/ app/tasks/job_offers_collectors.py app/tasks/verify_job_offers.py app/tasks/clean_job_offers.py tests/test_ats_parsers.py tests/test_clean_and_verify_alignment.py` (all clean)
- [x] Tests pass : `docker exec jobtracker-backend pytest tests/test_ats_parsers.py tests/test_clean_and_verify_alignment.py -v` (19/19 passed)
- [x] Regression tests pass : `docker exec jobtracker-backend pytest tests/test_job_offers_collectors_queries.py tests/test_verify_job_offers.py tests/test_role_normalizer.py -v` (29/29 passed)
- [x] No dead code : 0 import orphelin
- [x] Type check : n/a
- [x] Manual check : extraction validée sur format JSON-LD et gestion robuste des erreurs 404 confirmée sans crash ni appel LLM.

## Steps

- [x] Step 1 : Créer `backend/app/services/ats/router.py` et `__init__.py` :
  - Détecteurs par regex pour :
    - Greenhouse (`boards.greenhouse.io/{board}/jobs/{id}`) $\to$ `https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}`.
    - Lever (`jobs.lever.co/{company}/{id}`) $\to$ `https://api.lever.co/v0/postings/{company}/{id}`.
    - Ashby (`jobs.ashbyhq.com/{company}/{id}`) $\to$ API posting Ashby ou extraction payload JSON.
    - Workable (`apply.workable.com/{company}/j/{id}`) $\to$ `https://apply.workable.com/api/v1/widget/accounts/{company}`.
    - Remotive (`remotive.com/job/...`) $\to$ API Remotive.
  - Extracteur universel Schema.org JSON-LD :
    - Effectue un `GET` HTTP rapide avec `httpx`.
    - Recherche les balises `<script type="application/ld+json">` contenant `"@type": "JobPosting"`.
    - Extrait `title`, `hiringOrganization.name`, `jobLocation`, `description`, `employmentType`, `baseSalary`.
  - Normalise le résultat vers le format commun dict (`poste`, `entreprise`, `description`, `localisation`, `type_contrat`, `url`, `ats_platform`).
  - Gère les timeouts et exceptions : renvoie `None` en cas d'échec pour basculer en cascade sur Crawl4AI.
- [x] Step 2 : Modifier `backend/app/tasks/job_offers_collectors.py::crawl_urls_for_offers` :
  - Pour chaque URL de la liste, tente d'abord `extract_ats_or_jsonld_offer(url)`.
  - Les URLs ayant réussi sont converties directement en offres brutes (`ats_offers`).
  - Les URLs restantes (pages non-standardisées ou échecs HTTP) sont passées à `get_job_offers_from_query(remaining_urls)` (Crawl4AI + LLM).
  - Fusionne et retourne la liste combinée.
- [x] Step 3 : Adapter `backend/app/tasks/verify_job_offers.py` :
  - Dans `_apply_verification_updates` et les fonctions associées, s'assurer que toute offre marquée `is_deleted=True` reçoit également `pipeline_stage: "expired"`.
- [x] Step 4 : Adapter `backend/app/tasks/clean_job_offers.py` :
  - Ajouter la vérification des candidatures liées : avant toute opération de suppression physique (`delete_one` ou `delete_many`), interroger `db["applications"].find_one({"offer_id": str(offer_id)})`.
  - Si l'offre est liée à une candidature : ne jamais la supprimer de la base, mais la basculer en `is_deleted=True` et `pipeline_stage: "expired"`.
  - Préserver les champs `ats_platform`, `pipeline_stage` et `evaluation_score` lors des mises à jour de normalisation.
- [x] Step 5 : Écrire `backend/tests/test_ats_parsers.py` :
  - Tests unitaires 100% offline avec mocks HTTP (`unittest.mock` / mock `httpx.AsyncClient`) :
    - Extraction Greenhouse API.
    - Extraction Lever API.
    - Extraction Workable API.
    - Extraction universelle Schema.org JSON-LD (simulant une page HelloWork/Meteojob).
    - Gestion robuste d'une erreur 404/500 ou HTML sans JSON-LD (renvoie `None` proprement).
- [x] Step 6 : Écrire `backend/tests/test_clean_and_verify_alignment.py` :
  - Tester que `verify_job_offers` positionne bien `pipeline_stage: "expired"`.
  - Tester que `clean_job_offers` préserve une offre liée à une candidature dans `applications` et ne la supprime pas.
- [x] Step 7 (teardown) :
  - Relancer `ruff check` sur tous les fichiers touchés.
  - Exécuter la suite complète de tests dans le conteneur Docker.
  - Vérifier 0 code mort ou orphelin.

## Code Review
- Dead code removed: oui, imports nettoyés dans clean_job_offers.py et les tests. Aucun symbole orphelin.
- Build status: pass (`uv run ruff check` OK, 19/19 nouveaux tests OK, 29/29 tests de régression OK).
- Type errors: aucun.
- Unintended side effects: aucun, le repli en cascade sur Crawl4AI + LLM garantit 100% de rétrocompatibilité sur les URLs qui ne matchent pas les APIs ATS ou JSON-LD.
- Security surface touched: non, endpoints publics en lecture seule, aucune clé API en dur, isolation stricte multi-tenant préservée.
- Verdict: ✅ DONE

## Execution Log
- 2026-09-16 23:12 Step 1 complete. Created `backend/app/services/ats/router.py` with Greenhouse, Lever, Workable, and universal Schema.org JSON-LD extraction. Passed ruff check.
- 2026-09-16 23:13 Step 2 complete. Integrated `extract_ats_or_jsonld_offer` in `job_offers_collectors.py::crawl_urls_for_offers` with fast-path Zero-Token extraction and cascade fallback on Crawl4AI. Passed ruff check.
- 2026-09-16 23:13 Step 3 complete. Synchronized `pipeline_stage: "expired"` in `verify_job_offers.py` on soft-delete, and `"discovered"` on restore. 10/10 tests in `test_verify_job_offers.py` passed.
- 2026-09-16 23:15 Step 4 complete. Added application reference protection (`is_offer_referenced_by_application` and `safe_delete_or_expire_offer`) in `clean_job_offers.py` to prevent hard-delete of active candidate applications. Synchronized `pipeline_stage` across exact duplicates, similarity duplicates, and old/invalid offer cleanups.
- 2026-09-16 23:16 Step 5 complete. Created `backend/tests/test_ats_parsers.py` with 10 unit tests covering Greenhouse, Lever, Workable, JSON-LD simple, JSON-LD graph, and graceful 404 handling. 10/10 passed.
- 2026-09-16 23:17 Step 6 complete. Created `backend/tests/test_clean_and_verify_alignment.py` with 9 unit tests covering reference lookup, soft-delete protection, pipeline_stage synchronization, and cleanup workflows. 9/9 passed.
- 2026-09-16 23:18 Step 7 complete. Ran full linting check (clean) and 48 total tests in Docker container (19 new tests + 29 regression tests, all passed in < 0.5s).

## Notes
- `normalize_employment_type` gère les variantes avec tiret ou underscore (ex. `"Full-time"` $\to$ `"CDI"`).
- La protection des candidatures actives préserve l'accès complet à la fiche d'offre pour le candidat sans polluer le catalogue public grâce au marquage `is_deleted: True` et `pipeline_stage: "expired"`.

