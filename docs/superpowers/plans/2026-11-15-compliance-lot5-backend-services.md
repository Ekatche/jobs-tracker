# Lot 5 — Services IA & Garde-fous Backend Implementation Plan

> **For agentic workers:** Executed sequentially with immediate pytest + `ruff check` verification at each module boundary so backward compatibility (`app.services.*`, `app.services.evaluation.evaluator`, and `unittest.mock.patch` targets) remained intact.

**Goal:** Eliminate all 6 monolithic Lot 5 backend AI & guard service files (`letter_guards.py`, `cv_guards.py`, `profile/merge.py`, `cv_parser.py`, `evaluation/evaluator.py`, `interview_prep_service.py`) by modularizing each into cohesive submodules strictly `<= 300` lines while preserving 100% test and API compatibility.

**Architecture:**
- Apply strict 3-layer separation: declarative constants/models, pure deterministic scoring/matching/normalization helpers, and LLM/MongoDB/PDF I/O orchestrators.
- Deduplicate repetitive LLM invocation + token usage tracking in `interview_prep_service/llm_client.py` via `call_interview_llm(...)`.
- Preserve all `unittest.mock.patch(...)` targets (`acompletion`, `asyncio.sleep`, `record_api_usage`, `require_user_quota`, `compute_domain_relevance`, etc.) via dynamic `sys.modules[...]` lookups inside package submodules and full `__all__` re-exports in package facades (`__init__.py` / `evaluator.py`).

---

### Files Removed
- `backend/app/services/letter_guards.py` (537 lines, replaced by `backend/app/services/letter_guards/`)
- `backend/app/services/cv_guards.py` (943 lines, replaced by `backend/app/services/cv_guards/`)
- `backend/app/services/cv_parser.py` (784 lines, replaced by `backend/app/services/cv_parser/`)
- `backend/app/services/interview_prep_service.py` (961 lines, replaced by `backend/app/services/interview_prep_service/`)

### Files NOT Touched
- All existing test suites in `backend/tests/` and evaluation benchmark scripts in `backend/scripts/` (compatibility preserved through re-exports and dynamic `sys.modules` lookups)
- Lot 6 targets under `backend/app/services/normalization.py`, `backend/app/services/ats/router.py`, and `backend/app/tasks/` (5 remaining files > 500 lines)

### Modular Packages & Modules Created (all `<= 254` lines per file)
1. **`backend/app/services/letter_guards/`** (4 files, max 239 lines):
   `__init__.py` (25), `attribution.py` (232), `evaluate.py` (239), `rules.py` (93).
2. **`backend/app/services/cv_guards/`** (7 files, max 254 lines):
   `__init__.py` (45), `audit.py` (254), `constants.py` (172), `experience_audit.py` (140), `metrics.py` (248), `models.py` (39), `text_matching.py` (194).
3. **`backend/app/services/profile/` merge modules** (4 files, max 237 lines):
   `merge.py` (227), `merge_education.py` (237), `merge_experiences.py` (177), `merge_helpers.py` (103).
4. **`backend/app/services/cv_parser/`** (6 files, max 240 lines):
   `__init__.py` (83), `constants.py` (128), `llm_extract.py` (134), `normalization.py` (240), `orchestrator.py` (152), `pdf_io.py` (93).
5. **`backend/app/services/evaluation/`** modularization (6 files created/updated, max 244 lines):
   `bloc_h.py` (228), `block_builder.py` (181), `evaluator.py` (244), `llm_runner.py` (184), `prompts.py` (155), `scoring_rules.py` (205).
6. **`backend/app/services/interview_prep_service/`** (7 files, max 221 lines):
   `__init__.py` (93), `context.py` (78), `generators.py` (221), `llm_client.py` (95), `markdown_export.py` (154), `story_matching.py` (143), `story_writer.py` (204).

### Verification Commands
```bash
cd backend && uv run ruff check app/services/letter_guards app/services/cv_guards app/services/profile app/services/cv_parser app/services/evaluation app/services/interview_prep_service
cd backend && uv run python -m pytest tests/ -q
```
