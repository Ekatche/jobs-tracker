# Lot 4 — Schémas & Routeurs Backend Implementation Plan

> **For agentic workers:** Executed sequentially with immediate pytest verification at each boundary so backward compatibility (`app.models`, `app.routers.*`, and `unittest.mock.patch` targets) remained intact.

**Goal:** Eliminate all monolithic Lot 4 backend files (`routers_legacy.py`, `models.py`, `interview_prep.py`, `cover_letters.py`, `applications.py`, `job_offers.py`) by modularizing each into cohesive packages strictly `<= 300` lines per file while keeping 100% test/API compatibility.

**Architecture:**
- Remove dead legacy router `backend/app/routers_legacy.py` (0 imports verified).
- Split `backend/app/models.py` (1066 lines) into 10 domain modules inside `backend/app/models/` with a flat `__init__.py` re-export surface (`__all__`).
- Split each monolithic router (`interview_prep.py`, `cover_letters.py`, `applications.py`, `job_offers.py`) into focused sub-router packages under `backend/app/routers/<name>/`, preserving FastAPI static-before-dynamic route registration ordering and resolving patched service dependencies/constants dynamically through `sys.modules[__package__]` (`_pkg()`).

---

### Files Removed
- `backend/app/routers_legacy.py` (754 lines, unused)
- `backend/app/models.py` (replaced by `backend/app/models/`)
- `backend/app/routers/interview_prep.py` (replaced by `backend/app/routers/interview_prep/`)
- `backend/app/routers/cover_letters.py` (replaced by `backend/app/routers/cover_letters/`)
- `backend/app/routers/applications.py` (replaced by `backend/app/routers/applications/`)
- `backend/app/routers/job_offers.py` (replaced by `backend/app/routers/job_offers/`)

### Files NOT Touched
- All existing test suites in `backend/tests/` (compatibility preserved through package `__init__.py` re-exports and `_pkg()` lookups)
- `backend/main.py` and `backend/app/routers/__init__.py`
- Lots 5 & 6 targets under `backend/app/services/` and `backend/app/tasks/` (11 remaining files > 500 lines)

### Modular Packages Created (all `<= 300` lines per file)
1. **`backend/app/models/`** (10 files, max 199 lines):
   `__init__.py` (180), `applications.py` (199), `common.py` (43), `evaluation.py` (124), `interview.py` (169), `offers.py` (94), `profile.py` (140), `resumes.py` (136), `usage.py` (109), `users.py` (83).
2. **`backend/app/routers/interview_prep/`** (5 files, max 259 lines):
   `__init__.py` (97), `core.py` (144), `generation.py` (259), `helpers.py` (170), `slots.py` (207).
3. **`backend/app/routers/cover_letters/`** (4 files, max 294 lines):
   `__init__.py` (138), `letters.py` (269), `profile_sources.py` (294), `roles.py` (164).
4. **`backend/app/routers/applications/`** (5 files, max 296 lines):
   `__init__.py` (87), `background.py` (265), `crud.py` (225), `offer_linking.py` (296), `pipeline.py` (119).
5. **`backend/app/routers/job_offers/`** (7 files, max 259 lines):
   `__init__.py` (111), `actions.py` (139), `analytics.py` (137), `catalog.py` (237), `filters.py` (259), `interactions.py` (136), `pipeline.py` (238).

### Verification Command
```bash
cd backend && uv run python -m pytest tests/ -q
```
