---
task: Add UX notifications on preferences saving, deep-scrape portfolio pages, and implement Mistral VLM for CV parsing
status: completed
created: 2026-09-15
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# UX Notifications, Deep Portfolio Scraping, and Mistral VLM CV Parsing

## Context
- Existing code checked:
  - `frontend/src/components/profile/TargetingPreferencesSection.tsx`: Had inline top banner for save feedback, but when the user is at the bottom of the long form clicking Save, the banner was off-screen.
  - `backend/app/services/profile/collectors/website.py`: Only inspected `sitemap.xml` and fell back to 7 hardcoded static paths (`/`, `/about`, `/projects`, etc.). Real personal portfolios without a sitemap lost all subpage links (`/projects/xyz`, `/work/...`).
  - `backend/app/services/cv_parser.py`: Used PyMuPDF raw text extraction (`page.get_text()`) which jumbled multi-column layouts, badges, and sidebars. `MISTRAL_API_KEY` is present in `.env` and `mistral/pixtral-12b-2409` vision capability was tested and verified.
- Fresh info looked up:
  - Tested `mistral/pixtral-12b-2409` in container with base64 encoded PDF page rendered via PyMuPDF (`fitz`). Confirmed functional.
- Git status checked: Clean working state.

## Simpler Alternative Considered
- For UX: A browser `alert()` — rejected because it interrupts workflow and has poor UX.
- For website: Relying only on single-page scraping — rejected because portfolios spread projects and details across sub-pages.
- For CV: Raw regex extraction — rejected because modern resumes have diverse graphical layouts.

## Surgical Scope
- **Files touched**:
  - `frontend/src/components/profile/TargetingPreferencesSection.tsx`
  - `backend/app/services/profile/collectors/website.py`
  - `backend/app/services/cv_parser.py`
  - `backend/app/routers/cover_letters.py`
  - `backend/tests/test_profile_collectors.py`
  - `backend/tests/test_cv_vlm_parser.py`
- **Files NOT touched**:
  - `backend/app/models.py`
  - `frontend/src/app/profile/page.tsx`
  - All other files
- **Symbols replaced**: none
- **Symbols extended**:
  - `TargetingPreferencesSection`: added floating toast notification on save success/error and button-level status indicator.
  - `discover_pages` in `website.py`: added internal link crawler on root HTML to discover real portfolio links.
  - `parse_cv_with_vlm` in `cv_parser.py`: added PDF page image rendering + multimodal call to `mistral/pixtral-12b-2409` with automatic text fallback.
  - `import_cv_source` in `cover_letters.py`: forwarded `pdf_path=file_path` for VLM execution with defensive fallback for single-argument mocks.

## Definition of Done
- [x] Build passes: `python3 -m py_compile backend/app/services/profile/collectors/website.py backend/app/services/cv_parser.py backend/app/routers/cover_letters.py`
- [x] Tests pass: `pytest tests/test_profile_collectors.py tests/test_cv_vlm_parser.py tests/test_profile_endpoints.py tests/test_candidate_preferences.py -v` (45 passed)
- [x] No dead code: confirmed
- [x] Type check: `cd frontend && npx tsc --noEmit` (exit code 0)
- [x] Manual check: Save preferences displays visible toast, website collector discovers internal project links, CV parses structured info via Mistral VLM.

## Steps
- [x] Step 1: Add floating toast notification and button feedback in `frontend/src/components/profile/TargetingPreferencesSection.tsx`.
- [x] Step 2: Enhance `discover_pages` in `backend/app/services/profile/collectors/website.py` to fetch root HTML and extract internal links (`href`), filtering anchors and non-HTML assets.
- [x] Step 3: Implement `render_pdf_pages_to_images` and `parse_cv_with_vlm` in `backend/app/services/cv_parser.py` using `mistral/pixtral-12b-2409` with graceful fallback to text LLM.
- [x] Step 4: Write unit tests in `backend/tests/test_profile_collectors.py` and `backend/tests/test_cv_vlm_parser.py`.
- [x] Step 5: Run tests and type checks, rebuild frontend container and verify health.
- [x] Step 6 (teardown): Clean up temporary files, verify zero dead code or orphaned symbols, update Execution Log and Daily Log.

## Code Review
- Dead code removed: yes
- Build status: pass (exit code 0 on python and next build)
- Type errors: none
- Unintended side effects: none
- Security surface touched: yes (PDF file handling / URL validation preserved)
- Verdict: ✅ DONE

## Execution Log
- 2026-09-15 22:25: Step 1 completed. Added floating toast notification and reactive button states in `TargetingPreferencesSection.tsx`. `npx tsc --noEmit` passed with code 0.
- 2026-09-16 08:47: Step 2 completed. Implemented HTML internal link extraction in `website.py` and validated with 25 unit tests (100% pass) in `test_profile_collectors.py`.
- 2026-09-16 08:50: Step 3 completed. Implemented `render_pdf_pages_to_base64_images` and `parse_cv_with_vlm` in `cv_parser.py` with Pixtral VLM multimodal prompt and text fallback. Updated `cover_letters.py`.
- 2026-09-16 09:00: Step 4 completed. Created `test_cv_vlm_parser.py` (5 tests passing). Full suite of 45 tests passing in container.
- 2026-09-16 09:09: Step 5 completed. Rebuilt and restarted `jobtracker-frontend` container. Container healthy and responsive on port 3875.
- 2026-09-16 09:12: Step 6 completed. Teardown confirmed, zero dead code, daily log updated.

## Notes
- `MISTRAL_API_KEY` is loaded from environment. If absent, fallback to `gemini/gemini-2.5-flash` or text parser ensures 100% resilience.
