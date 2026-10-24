---
task: Rendre l'état « Évaluée » propre à chaque utilisateur et ne plus l'écrire dans job_offers
description: Fuite multi-tenant de pipeline_stage "evaluated" — routers/job_offers.py calcule pipeline_stage par utilisateur depuis offer_evaluations (liste GET /job-offers/ get_job_offers et détail GET /job-offers/{id} get_job_offer, "expired" partagé conservé) ; evaluate_offer_two_pass n'écrit plus evaluation_score ni pipeline_stage dans job_offers ; rattrapage evaluation_score vers "evaluated" retiré de clean_job_offers.normalize_existing_data ; frontend inchangé (spec matching hybride §4.7, étape 1a)
status: blocked
created: 2026-10-24
---

# État « Évaluée » par utilisateur

## Context
- Existing code checked: `evaluate_offer_two_pass` écrit `pipeline_stage: "evaluated"` et `evaluation_score` sur le document partagé `job_offers` (`backend/app/services/evaluation/evaluator.py:561-571` avant le plan `20261024-twopass-pure-evaluation-compute`). Le routeur retire déjà `evaluation_score` et réinjecte le score propre à l'utilisateur depuis `offer_evaluations` (`backend/app/routers/job_offers.py:491` et `:496` pour la liste, `:547` et `:562` pour le détail), mais il renvoie `pipeline_stage` brut. Côté frontend, ce champ alimente le badge « Évaluée » (`frontend/src/app/offers/page.tsx:271`) et un compteur (`frontend/src/app/applications/page.tsx:123`). Seuls deux endpoints renvoient `JobOfferResponse` : `get_job_offers` (`GET /job-offers/`, ligne 356) et `get_job_offer` (`GET /job-offers/{offer_id}`, ligne 529).
- Autres écrivains de `pipeline_stage` dans `job_offers`, inchangés : `"expired"` (`verify_job_offers.py:591`, `clean_job_offers.py:62`, `:345`, `:416`, `:858`) et `"discovered"` (`verify_job_offers.py:680`, `applications.py:789`, `job_offers_collectors.py:380`).
- `backend/app/tasks/clean_job_offers.py:119-126` : `normalize_existing_data` donne `"evaluated"` à une offre sans `pipeline_stage` qui porte un `evaluation_score`. Le test `test_normalize_existing_data_synchronizes_pipeline_stage` (`backend/tests/test_clean_and_verify_alignment.py:156-181`) fige ce comportement.
- Données existantes : les offres de prod qui portent déjà `pipeline_stage: "evaluated"` ou `evaluation_score` les gardent. Aucune migration, aucune écriture en base de prod : le routeur ignore la valeur stockée `"evaluated"` et retire déjà `evaluation_score`.
- Spec : `docs/superpowers/specs/2026-10-24-matching-hybrid-scoring-and-sectors-design.md`, §4.7, §5 (précondition) et §6.4, étape 1a du §7.
- Fresh info looked up: n/a. Logique métier interne.
- Git status checked: `backend/app/routers/job_offers.py` porte des modifications non commitées d'une autre session (+20/−6 : imports, `get_job_offer_evaluation_endpoint`, `soft_delete_job_offer`, `delete_job_offer`). Ce fichier reste en lecture seule jusqu'au commit de l'autre session, d'où `status: blocked`. Les autres fichiers du périmètre sont propres.

## Simpler Alternative Considered
1. Arrêter seulement l'écriture dans `evaluator.py`, sans toucher au routeur. Rejeté : les offres de prod déjà marquées `"evaluated"` continueraient de fuiter (pas de migration par Claude), et l'utilisateur qui évalue perdrait son badge « Évaluée ».
2. Corriger le frontend (masquer « Évaluée » quand `evaluation_score` est absent). Rejeté : l'API continuerait d'exposer l'état d'un autre utilisateur, deux pages seraient à changer, et la spec garde le frontend inchangé.

Le calcul dans le routeur couvre à la fois les données existantes et les nouvelles.

## Surgical Scope
- **Files touched**: `backend/app/routers/job_offers.py`, `backend/app/services/evaluation/evaluator.py`, `backend/app/tasks/clean_job_offers.py`, `backend/tests/test_user_offer_interactions.py`, `backend/tests/test_offer_evaluation.py`, `backend/tests/test_clean_and_verify_alignment.py`
- **Files NOT touched**: tous les autres, en particulier tout `frontend/` (dont `offers/page.tsx` et `applications/page.tsx`), `backend/app/models.py` et `backend/app/routers/applications.py`.
- **Symbols replaced** (→ to delete before done): dans `evaluate_offer_two_pass`, le bloc `db["job_offers"].update_one(...)` et son commentaire ; dans `normalize_existing_data`, la branche `elif offer.get("evaluation_score") is not None`.
- **Symbols extended** (→ keep): `get_job_offers` et `get_job_offer`, qui renvoient `pipeline_stage` calculé pour l'utilisateur courant. Nouveau : `_user_pipeline_stage(stored_stage: Optional[str], has_own_evaluation: bool) -> str` dans `routers/job_offers.py`, qui renvoie `"expired"` si l'offre est expirée (état partagé), sinon `"evaluated"` si l'utilisateur a son propre document `offer_evaluations`, sinon `"discovered"`.

## Definition of Done
- [ ] Précondition, autre session commitée : `git diff --quiet HEAD -- backend/app/routers/job_offers.py` exit 0
- [ ] Précondition, calcul pur livré : `grep -c 'async def compute_offer_evaluation' backend/app/services/evaluation/evaluator.py` = 1
- [ ] Build passes: `cd backend && uv run python -c "import app.routers.job_offers, app.services.evaluation.evaluator, app.tasks.clean_job_offers"` exit 0
- [ ] Tests pass: `cd backend && uv run pytest tests/test_user_offer_interactions.py tests/test_offer_evaluation.py tests/test_clean_and_verify_alignment.py -q` exit 0
- [ ] B ne voit pas « Évaluée » une offre que seul A a évaluée : `cd backend && uv run pytest tests/test_user_offer_interactions.py -q -k evaluated_stage` exit 0, au moins 3 tests sélectionnés. Liste : une offre stockée `"evaluated"` avec un `offer_evaluations` pour A seulement est rendue `"evaluated"` à A et `"discovered"` à B. Détail : même chose sur `GET /job-offers/{id}`. Une offre stockée `"expired"` reste `"expired"` pour A comme pour B.
- [ ] `evaluate_offer_two_pass` n'écrit plus dans `job_offers` : `grep -c 'db\["job_offers"\].update_one' backend/app/services/evaluation/evaluator.py` = 0, et `cd backend && uv run pytest tests/test_offer_evaluation.py -q -k two_pass_success` exit 0, avec `job_offers_collection.update_one.assert_not_called()` à la place de `assert_called_once()` (ligne 364).
- [ ] Rattrapage retiré : `grep -c 'evaluation_score' backend/app/tasks/clean_job_offers.py` = 0, et `cd backend && uv run pytest tests/test_clean_and_verify_alignment.py -q -k synchronizes_pipeline_stage` exit 0, le test attendant `"discovered"` pour une offre qui porte un `evaluation_score` sans `pipeline_stage`.
- [ ] Frontend inchangé par ce plan : `git diff -- frontend | shasum` donne la même valeur qu'en Phase 3. `frontend/` porte des modifications d'autres sessions : si la valeur change, identifier l'auteur du changement avant de conclure.
- [ ] No dead code: les deux `grep -c` ci-dessus donnent 0, et `cd backend && uvx pyflakes app/routers/job_offers.py app/services/evaluation/evaluator.py app/tasks/clean_job_offers.py` ne signale aucun avertissement de plus que la baseline de Phase 3.
- [ ] Type check: n/a — ni mypy ni pyright configurés dans `backend/pyproject.toml`
- [ ] Manual check: étape 6, observée par l'utilisateur.

## Steps
- [ ] Step 1: Écrire ou adapter les tests d'abord, puis constater qu'ils échouent. Dans `backend/tests/test_user_offer_interactions.py`, ajouter `test_evaluated_stage_is_per_user_in_list` (paramétré sur la valeur stockée `"evaluated"` et `"expired"`) et `test_evaluated_stage_is_per_user_in_detail`, sur le modèle de `test_multi_tenant_isolation_user_a_hiding_offer_does_not_hide_from_user_b` : `offer_evaluations.find` et `find_one` ne renvoient un document que pour `USER_A_ID`. Dans `backend/tests/test_offer_evaluation.py:364`, remplacer `assert_called_once()` par `assert_not_called()`. Dans `backend/tests/test_clean_and_verify_alignment.py:178-179`, attendre `"discovered"` et corriger le commentaire. Vérification : `cd backend && uv run pytest tests/test_user_offer_interactions.py tests/test_offer_evaluation.py tests/test_clean_and_verify_alignment.py -q` échoue sur ces tests, et seulement sur eux.
- [ ] Step 2: Dans `backend/app/routers/job_offers.py`, ajouter `_user_pipeline_stage`. Dans la boucle de `get_job_offers`, en dehors du `if current_user`, poser `offer["pipeline_stage"] = _user_pipeline_stage(offer.get("pipeline_stage"), oid_str in eval_score_map)` ; dans `get_job_offer`, faire de même avec `evaluation is not None` (`False` sans utilisateur connecté). Mettre à jour les deux commentaires sur `evaluation_score` (lignes 487-490 et 545-546) : le champ n'est plus écrit, mais les documents anciens le portent encore, tout comme `pipeline_stage: "evaluated"`. Vérification : `cd backend && uv run pytest tests/test_user_offer_interactions.py -q` exit 0.
- [ ] Step 3: Dans `evaluate_offer_two_pass`, supprimer le bloc `db["job_offers"].update_one(...)` et son commentaire. Mettre à jour la docstring si elle mentionne `job_offers`. Vérification : `cd backend && uv run pytest tests/test_offer_evaluation.py -q` exit 0, et le `grep -c` correspondant du Definition of Done donne 0.
- [ ] Step 4: Dans `normalize_existing_data` (`backend/app/tasks/clean_job_offers.py:123-124`), supprimer la branche `elif offer.get("evaluation_score") is not None`. Vérification : `cd backend && uv run pytest tests/test_clean_and_verify_alignment.py -q` exit 0, et `grep -c 'evaluation_score' backend/app/tasks/clean_job_offers.py` = 0.
- [ ] Step 5 (teardown): scan d'orphelins borné aux symboles retirés. `grep -rn 'evaluation_score' backend/app/tasks/clean_job_offers.py` et `grep -c 'db\["job_offers"\].update_one' backend/app/services/evaluation/evaluator.py` donnent 0 ; `uvx pyflakes` sans nouvel avertissement. Confirmer zéro orphelin.
- [ ] Step 6 (vérification manuelle, observée par l'utilisateur) : backend local redémarré, l'utilisateur évalue une offre avec le compte A (environ 0,02 $ de crédits LLM). Le badge « Évaluée » reste visible pour A sur `/offers` ; avec un compte B, la même offre s'affiche sans ce badge. Résultat noté dans `## Notes`.

## Code Review
- Dead code removed:
- Build status:
- Type errors:
- Unintended side effects:
- Security surface touched:
- Verdict:

## Execution Log
(append-only, filled by executing-micro-plans)

## Notes
- **Blocage (2026-10-24)** : `backend/app/routers/job_offers.py` porte des modifications non commitées d'une autre session. Règle de l'utilisateur : lecture seule jusqu'à leur commit. Débloquer quand `git diff --quiet HEAD -- backend/app/routers/job_offers.py` sort en 0 et que le plan `20261024-twopass-pure-evaluation-compute` est `done`, puis repasser `status: planned`.
- Les étapes 2 à 4 vont ensemble : retirer l'écriture dans `evaluator.py` (étape 3) sans le calcul du routeur (étape 2) ferait perdre le badge « Évaluée » à l'utilisateur qui vient d'évaluer. Ne pas commiter l'étape 3 seule.
- Sécurité : la correction resserre la ségrégation des données entre utilisateurs, mais aucun fichier ne relève de la surface sensible (auth, secrets, injection, migration). Pas de semgrep requis.
