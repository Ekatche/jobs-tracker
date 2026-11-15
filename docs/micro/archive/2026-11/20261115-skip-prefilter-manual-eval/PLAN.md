---
task: Bypass domain mismatch prefilter for manually added applications and compute max similarity across target roles
description: Skip domain relevance prefilter in evaluate_application_offer via skip_domain_prefilter parameter in evaluator.py and offer_linking.py and prevent multi-role embedding dilution in compute_domain_relevance in domain_relevance.py
status: done
created: 2026-11-15
---

# Bypass Domain Prefilter for Manual Applications & Fix Multi-Role Embedding Dilution

## Context
- Existing code checked:
  - `backend/app/routers/applications/offer_linking.py` (`L245-273`): `evaluate_application_offer` (`POST /applications/{application_id}/evaluate`) initializes a `job_offers` doc via `_ensure_offer_for_application` if needed and calls `pkg.evaluate_offer_two_pass(offer_id=offer_id, user_id=str(current_user.id), db=db)` without disabling the domain mismatch prefilter.
  - `backend/app/services/evaluation/evaluator.py` (`L112-212`): `compute_offer_evaluation` unconditionally computes `domain_similarity = await mod.compute_domain_relevance(candidate_identity, job_title)` and short-circuits LLM evaluation (`domain_mismatch_prefilter = True`) when `domain_similarity < 0.30`. Production log on `POST /applications/6af988e87defc68cd491745e/evaluate` (`Heva` / `Data Manager Snds`) logged `similarité=0.263 < seuil=0.3` even though `'Data Manager'` was present in `target_roles`.
  - `backend/app/services/evaluation/domain_relevance.py` (`L76-112`): `build_candidate_identity` concatenates `headline` and all `target_roles` into one long string, diluting single-role similarity in `compute_domain_relevance`.
  - `backend/app/routers/job_offers/actions.py` (`L24-56`): catalog offer evaluation (`POST /job-offers/{offer_id}/evaluate`) also calls `evaluate_offer_two_pass` and must keep the prefilter active by default.
  - `backend/tests/test_domain_relevance.py`, `backend/tests/evaluation/test_evaluation_service.py`, `backend/tests/test_pipeline_kanban.py`: existing tests mock `litellm.aembedding` with `input[1]` assertions or patch `app.routers.applications.evaluate_offer_two_pass`.
- Fresh info looked up: n/a — pure Python evaluation logic, FastAPI router wiring, and OpenAI-compatible `litellm.aembedding` batch input already used in `domain_relevance.py`.
- Git status checked: clean at `6fa7122` before archive sweep of `20261115-fix-flake8-f811-and-company-history` into `docs/micro/archive/2026-11/`. `docs/adrs/` does not exist.

## Simpler Alternative Considered
Simply lowering `DOMAIN_RELEVANCE_THRESHOLD` globally — rejected because it would weaken noise filtering on scraped catalog offers (`POST /job-offers/{id}/evaluate`) while still failing when a user manually adds an offer outside their usual profile (explicit user requirement: manually added offers must always be evaluable). Keeping `skip_domain_prefilter: bool = False` scoped to `POST /applications/{application_id}/evaluate` plus max-per-role similarity fixes both issues cleanly.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/evaluation/domain_relevance.py` (add optional `candidate_roles: Optional[List[str]] = None` to `compute_domain_relevance`, deduplicate candidates, compute `max` cosine similarity in one batch `aembedding` call)
  - `backend/app/services/evaluation/evaluator.py` (add `skip_domain_prefilter: bool = False` to `compute_offer_evaluation` and `evaluate_offer_two_pass`; skip prefilter when `True`, pass `candidate_roles` when `False`)
  - `backend/app/routers/applications/offer_linking.py` (pass `skip_domain_prefilter=True` in `evaluate_application_offer`)
  - `backend/tests/test_domain_relevance.py` (add tests for multi-role `max` similarity, candidate deduplication, and empty/only-roles fallback)
  - `backend/tests/evaluation/test_evaluation_service.py` (add tests verifying `skip_domain_prefilter=True` bypasses `compute_domain_relevance` and runs LLM passes, and `skip_domain_prefilter=False` passes `candidate_roles`)
  - `backend/tests/test_pipeline_kanban.py` (assert `skip_domain_prefilter=True` is forwarded in `test_evaluate_application_offer_endpoint`)
- **Files NOT touched**: all others (including `backend/app/routers/job_offers/actions.py`, `backend/app/services/evaluation/block_builder.py`, `backend/app/services/evaluation/llm_runner.py`, and frontend files)
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `compute_domain_relevance` in `backend/app/services/evaluation/domain_relevance.py`
  - `compute_offer_evaluation` and `evaluate_offer_two_pass` in `backend/app/services/evaluation/evaluator.py`
  - `evaluate_application_offer` in `backend/app/routers/applications/offer_linking.py`

## Definition of Done
- [x] Lint passes: `cd backend && uv run flake8 --config ../.flake8 .`
- [x] Tests pass: `cd backend && uv run python -m pytest tests/test_domain_relevance.py tests/evaluation/ tests/test_pipeline_kanban.py tests/test_provider_errors_api.py -q`
- [x] No dead code: n/a — no symbols replaced
- [x] Type check: `cd backend && uv run python -c "from app.services.evaluation.domain_relevance import compute_domain_relevance; from app.services.evaluation.evaluator import evaluate_offer_two_pass, compute_offer_evaluation; from app.routers.applications.offer_linking import evaluate_application_offer"`
- [x] Manual-eval bypass & catalog prefilter defaults verified: `cd backend && uv run python -c "import inspect; from app.services.evaluation.evaluator import evaluate_offer_two_pass, compute_offer_evaluation; assert inspect.signature(evaluate_offer_two_pass).parameters['skip_domain_prefilter'].default is False; assert inspect.signature(compute_offer_evaluation).parameters['skip_domain_prefilter'].default is False"`

## Steps
- [x] Step 1: Extend `compute_domain_relevance` in `backend/app/services/evaluation/domain_relevance.py` with `candidate_roles: Optional[List[str]] = None` to embed deduplicated `[candidate_identity, *candidate_roles]` plus `expand_title_acronyms(offer_title)` in one batch `aembedding` call and return `max` cosine similarity (preserving 2-arg call index `input[1]`). Verify with `cd backend && uv run python -m pytest tests/test_domain_relevance.py -q`.
- [x] Step 2: Extend `compute_offer_evaluation` and `evaluate_offer_two_pass` in `backend/app/services/evaluation/evaluator.py` with `skip_domain_prefilter: bool = False`; bypass `compute_domain_relevance` when `skip_domain_prefilter=True`, otherwise pass `candidate_roles=[candidate_headline, *(candidate_target_roles or [])]`. Verify with `cd backend && uv run python -m pytest tests/evaluation/ -q`.
- [x] Step 3: Pass `skip_domain_prefilter=True` in `evaluate_application_offer` (`backend/app/routers/applications/offer_linking.py`). Verify with `cd backend && uv run python -m pytest tests/test_pipeline_kanban.py tests/test_provider_errors_api.py -q`.
- [x] Step 4: Add unit tests in `backend/tests/test_domain_relevance.py`, `backend/tests/evaluation/test_evaluation_service.py`, and assertion in `backend/tests/test_pipeline_kanban.py` (keeping all test files under 400 lines, offline and parametrized). Verify with `cd backend && uv run python -m pytest tests/test_domain_relevance.py tests/evaluation/ tests/test_pipeline_kanban.py -q`.
- [x] Step 5 (teardown): Confirm 0 dead code / unused imports, run `git diff` review, and re-run all Definition of Done commands (`flake8`, full targeted `pytest`, imports, and signature defaults check).

## Code Review
- Dead code removed: n/a — no symbols replaced; zero unused imports (`flake8` exit 0)
- Build status: pass (`flake8 --config ../.flake8 .` exit 0, targeted `pytest` 97 passed, Python imports & signature checks exit 0)
- Type errors: none (optional typed parameters `candidate_roles: Optional[List[str]] = None` and `skip_domain_prefilter: bool = False`)
- Unintended side effects: none — catalog endpoint `/job-offers/{id}/evaluate` and default callers keep `skip_domain_prefilter=False`; 2-arg `compute_domain_relevance(identity, title)` calls preserve `input[1]` indexing
- Security surface touched: no (evaluation scoring prefilter & Kanban evaluation endpoint wiring)
- Verdict: ✅ DONE

## Execution Log
- 2026-11-15T14:21Z | antigravity | step 1 | started
- 2026-11-15T14:22Z | antigravity | step 1 | done | `pytest tests/test_domain_relevance.py -q` 24 passed
- 2026-11-15T14:22Z | antigravity | step 2 | started
- 2026-11-15T14:22Z | antigravity | step 2 | done | `pytest tests/evaluation/ -q` 53 passed
- 2026-11-15T14:22Z | antigravity | step 3 | started
- 2026-11-15T14:22Z | antigravity | step 3 | done | `pytest tests/test_pipeline_kanban.py tests/test_provider_errors_api.py -q` 16 passed
- 2026-11-15T14:22Z | antigravity | step 4 | started
- 2026-11-15T14:23Z | antigravity | step 4 | done | `pytest tests/test_domain_relevance.py tests/evaluation/ tests/test_pipeline_kanban.py -q` 90 passed
- 2026-11-15T14:23Z | antigravity | step 5 | started
- 2026-11-15T14:23Z | antigravity | step 5 | done | `flake8` exit 0; `pytest` 97 passed; imports & defaults verified
- 2026-11-15T14:23Z | antigravity | plan | done | all 5 DoD items pass

## Notes
- Convention files read in Phase 3: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`.
- Preflight baseline (`2026-11-15T14:21Z`): `flake8 --config ../.flake8 .` exit 0; `pytest tests/test_domain_relevance.py tests/evaluation/ tests/test_pipeline_kanban.py tests/test_provider_errors_api.py -q` -> `93 passed`; import check exit 0; `skip_domain_prefilter` signature check failed with `KeyError` (expected before Step 2).
- Archive sweep (`2026-11-15`): archived `20261115-fix-flake8-f811-and-company-history` into `docs/micro/archive/2026-11/` and updated its link in `docs/micro/INDEX.md`.
