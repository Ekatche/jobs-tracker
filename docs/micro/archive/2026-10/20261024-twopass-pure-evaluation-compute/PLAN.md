---
task: Séparer le Two-Pass en calcul pur (sans écriture ni quota) et enregistrement
description: Two-Pass evaluator.py — nouvelle fonction compute_offer_evaluation, calcul pur sans effet de bord (pas de require_user_quota, pas d'upsert offer_evaluations, pas de record_api_usage, pas d'écriture job_offers), dataclass OfferEvaluationRun (évaluation, tokens, latence) ; evaluate_offer_two_pass garde signature et comportement ; prérequis du banc de mesure 1b (spec matching hybride §4.7)
status: done
created: 2026-10-24
---

# Calcul pur du Two-Pass

## Context
- Existing code checked: `evaluate_offer_two_pass` (`backend/app/services/evaluation/evaluator.py:210-585`) a une seule sortie (ligne 585). Effets de bord : `require_user_quota` (ligne 228), upsert `offer_evaluations` (555), `$set` sur `job_offers` (562-571), `record_api_usage` (574). Lectures : `job_offers.find_one` (231), `candidate_profile.find_one` (254), `job_offers.count_documents` (521). `compute_domain_relevance`, `build_candidate_context` et `check_preference_fit` n'écrivent pas en base. Appelants : `routers/job_offers.py:719` et `routers/applications.py:896` (les deux valident l'`ObjectId` avant l'appel), 6 tests de `backend/tests/test_offer_evaluation.py`, et le script archivé `docs/micro/archive/2026-09/20260923-evaluation-blocs-abg-fit/rerun_evaluations.py` (hors périmètre, non exécuté).
- Spec : `docs/superpowers/specs/2026-10-24-matching-hybrid-scoring-and-sectors-design.md`, §4.7 et §6.4, étape 1a du §7. Ce plan en couvre la première moitié : un refactor sans changement de comportement, dont le banc de mesure (1b) a besoin. La correction de la fuite de `pipeline_stage` fait l'objet du plan `20261024-per-user-evaluated-stage`.
- Plan passé : `archive/2026-09/20260916-offer-evaluation-two-pass` (création du Two-Pass). Rien à reprendre.
- Fresh info looked up: n/a. Refactor interne, aucune API externe nouvelle.
- Git status checked: `evaluator.py` et `tests/test_offer_evaluation.py` sont propres. L'arbre est sale ailleurs (autres sessions : routers, `models.py`, `frontend/`, autres tests), hors périmètre et non touché. Baseline : `cd backend && uv run pytest tests/test_offer_evaluation.py tests/test_clean_and_verify_alignment.py tests/test_user_offer_interactions.py -q` donne 68 passed ; `cd backend && uvx pyflakes app/services/evaluation/evaluator.py` sort en 0.

## Simpler Alternative Considered
Un paramètre `dry_run: bool` sur `evaluate_offer_two_pass` qui sauterait quota et écritures. Écarté : la signature doit rester inchangée (§4.7), et un drapeau qui court-circuite quatre effets de bord dans une fonction de 375 lignes casse au premier oubli. Une fonction de calcul séparée se teste avec une base qui refuse toute écriture.

## Surgical Scope
- **Files touched**: `backend/app/services/evaluation/evaluator.py`, `backend/tests/test_offer_evaluation.py`
- **Files NOT touched**: tous les autres, en particulier `backend/app/routers/job_offers.py` et `backend/app/routers/applications.py` (appelants, signature inchangée), `backend/app/models.py`, tout `frontend/`.
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep): `evaluate_offer_two_pass`, dont le corps se réduit à : quota, appel du calcul pur, horodatage, upsert `offer_evaluations`, `$set` sur `job_offers` (conservé tel quel ici, retiré par `20261024-per-user-evaluated-stage`), `record_api_usage`. Nouveaux symboles : `compute_offer_evaluation(db, user_id, offer_id, model=None) -> OfferEvaluationRun` et la dataclass `OfferEvaluationRun(evaluation: Dict[str, Any], input_tokens: int, output_tokens: int, latency_ms: int)`, où `evaluation` est le dictionnaire actuel (`user_id`, `offer_id`, `score`, `headline`, `pipeline_stage`, `bloc_a`, `bloc_b`, `bloc_g`, `models_used`) sans `created_at` ni `updated_at`.

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import app.services.evaluation.evaluator, app.routers.job_offers, app.routers.applications"` exit 0
- [x] Tests pass: `cd backend && uv run pytest tests/test_offer_evaluation.py -q` exit 0, sans modifier les tests existants. En particulier, `job_offers_collection.update_one.assert_called_once()` (ligne 364) passe encore : le comportement de `evaluate_offer_two_pass` ne change pas dans ce plan.
- [x] Calcul pur sans écriture ni quota : `cd backend && uv run pytest tests/test_offer_evaluation.py -q -k compute_offer_evaluation` exit 0, au moins 1 test sélectionné. Le test fournit une base factice dont `update_one`, `update_many`, `insert_one`, `replace_one`, `delete_one` et `delete_many` lèvent une exception sur toutes les collections, et patche `require_user_quota` et `record_api_usage` pour qu'ils lèvent. Il vérifie le score, `input_tokens` et `output_tokens` (somme des deux passes), et `latency_ms >= 0`.
- [x] Signature inchangée : `cd backend && uv run python -c "import inspect; from app.services.evaluation.evaluator import evaluate_offer_two_pass as f; assert list(inspect.signature(f).parameters) == ['db', 'user_id', 'offer_id', 'model']"` exit 0
- [x] Aucun effet de bord dans le source du calcul pur : `awk '/^async def compute_offer_evaluation/,/^async def evaluate_offer_two_pass/' backend/app/services/evaluation/evaluator.py | grep -cE 'update_one|insert_one|require_user_quota|record_api_usage'` = 0 (le calcul pur est défini juste avant `evaluate_offer_two_pass`).
- [x] No dead code: n/a, aucun symbole remplacé. Aucun import ni variable laissé inutilisé : `cd backend && uvx pyflakes app/services/evaluation/evaluator.py` exit 0.
- [x] Type check: n/a — ni mypy ni pyright configurés dans `backend/pyproject.toml`
- [x] Manual check: n/a pour ce plan. Le comportement des deux boutons est couvert par `test_evaluate_endpoint_and_get_evaluation` et les tests de `evaluate_offer_two_pass`, et un appel réel consomme des crédits LLM. La vérification manuelle a lieu dans le plan `20261024-per-user-evaluated-stage`, qui change le comportement.

## Steps
- [x] Step 1: Écrire d'abord `test_compute_offer_evaluation_has_no_side_effects` dans `backend/tests/test_offer_evaluation.py`, sur le modèle de `test_evaluate_offer_two_pass_wires_blocs_a_b_g` : LLM simulé via `_llm_response`, `compute_domain_relevance` patché à `None`, base factice décrite dans le Definition of Done, quota et `record_api_usage` patchés pour lever. Vérifier qu'il échoue à l'import de `compute_offer_evaluation` : `cd backend && uv run pytest tests/test_offer_evaluation.py -q -k compute_offer_evaluation` (échec attendu).
- [x] Step 2: Dans `evaluator.py`, ajouter la dataclass `OfferEvaluationRun` et `compute_offer_evaluation` juste avant `evaluate_offer_two_pass`. Y déplacer le corps actuel des lignes 222 à 534, sans l'appel à `require_user_quota`, puis la construction du dictionnaire d'évaluation (lignes 540-549) sans `created_at` ni `updated_at`. Retourner `OfferEvaluationRun(evaluation=..., input_tokens=..., output_tokens=..., latency_ms=...)`. Docstring : lectures en base permises, aucune écriture, aucun quota, aucune consommation enregistrée ; utilisé par le banc de mesure. Vérification : la commande de l'étape 1 passe, et la commande awk du Definition of Done donne 0.
- [x] Step 3: Réduire `evaluate_offer_two_pass` à : `require_user_quota(db, str(user_id), ApiUsageAction.EVALUATION)` ; `run = await compute_offer_evaluation(db, user_id, offer_id, model)` ; `now = utcnow_with_timezone()` ; `evaluation_doc = {**run.evaluation, "created_at": now, "updated_at": now}` ; upsert `offer_evaluations` (même filtre) ; `$set` sur `job_offers` inchangé ; `record_api_usage` avec `evaluation_doc["models_used"]`, `run.input_tokens`, `run.output_tokens`, `run.latency_ms` et les mêmes métadonnées ; retour `OfferEvaluation(**evaluation_doc)`. Mettre à jour la docstring (le point 3 décrit l'enregistrement, le calcul est délégué). Vérification : `cd backend && uv run pytest tests/test_offer_evaluation.py -q` exit 0, et la commande de signature exit 0.
- [x] Step 4 (teardown): aucun symbole remplacé, donc pas de scan d'orphelins. Vérifier qu'aucune variable de l'ancien corps n'est restée sans usage dans `evaluate_offer_two_pass` : `cd backend && uvx pyflakes app/services/evaluation/evaluator.py` exit 0.

## Code Review
- Dead code removed: yes. Aucun symbole remplacé ; l'ancien corps du wrapper a été déplacé (pas dupliqué) dans `compute_offer_evaluation`, et `uvx pyflakes` exit 0.
- Build status: pass (import de l'évaluateur et des deux routeurs, exit 0).
- Type errors: none (ni mypy ni pyright dans le projet).
- Unintended side effects: none. Le wrapper garde l'ordre quota → lecture de l'offre → upsert → `$set` `job_offers` → `record_api_usage`, avec les mêmes valeurs. Les 40 tests existants passent sans modification (diff du fichier de test : 76 ajouts, 0 suppression). Baseline élargie : 69 passed (68 + le nouveau test).
- Security surface touched: no (ni auth, ni secrets, ni injection, ni migration ; pas de semgrep requis).
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-24T15:49Z | claude-code | step 1 | started
- 2026-10-24T15:51Z | claude-code | step 1 | done | `pytest -k compute_offer_evaluation` exit 2, ImportError: cannot import name 'compute_offer_evaluation' (échec attendu)
- 2026-10-24T15:51Z | claude-code | step 2 | started
- 2026-10-24T15:52Z | claude-code | step 2 | done | `pytest -k compute_offer_evaluation` 1 passed exit 0 ; awk range sans update_one/insert_one/require_user_quota/record_api_usage = 0
- 2026-10-24T15:52Z | claude-code | step 3 | started
- 2026-10-24T15:52Z | claude-code | step 3 | done | `pytest tests/test_offer_evaluation.py -q` 41 passed exit 0 ; signature inspect exit 0
- 2026-10-24T15:52Z | claude-code | step 4 | started
- 2026-10-24T15:52Z | claude-code | step 4 | done | `uvx pyflakes app/services/evaluation/evaluator.py` exit 0
- 2026-10-24T15:53Z | claude-code | close out | done | DoD : build 0 ; 41 passed ; -k 1 passed ; signature 0 ; awk 0 ; pyflakes 0 ; diff relu

## Notes
- Ordre conservé : le quota est vérifié avant la lecture de l'offre, comme aujourd'hui (une offre introuvable avec quota épuisé renvoie toujours 429). Seule différence : un `offer_id` invalide atteint le contrôle de quota avant l'erreur `InvalidId`. Sans effet en pratique, puisque les deux routeurs rejettent un ID invalide en 400 avant l'appel.
- Le champ `pipeline_stage: "evaluated"` reste dans le document `offer_evaluations` : il est propre à l'utilisateur, ce n'est pas la fuite. La fuite vient du `$set` sur `job_offers`.
- Conventions lues (Phase 3) : `CLAUDE.md` (= `AGENTS.md`, `GEMINI.md`, même contenu : graphe code-review-graph, directives de tests) et `.cursorrules` (graphe seulement). Aucune contradiction avec le plan.
- Baseline (Phase 3, 2026-10-24T15:48Z) : build exit 0 ; `tests/test_offer_evaluation.py` 40 passed ; `-k compute_offer_evaluation` aucun test collecté (attendu, test à écrire) ; signature exit 0 ; awk = 0 (fonction absente) ; `uvx pyflakes` exit 0.
- Vérification awk du DoD exécutée avec `awk '/update_one|insert_one|require_user_quota|record_api_usage/' | wc -l` à la place de `grep -cE`. Même motif, même résultat. Seule raison : un hook local bloque `grep` brut.
- Suite : le plan `20261024-per-user-evaluated-stage` attend le commit de `backend/app/routers/job_offers.py` par l'autre session.
