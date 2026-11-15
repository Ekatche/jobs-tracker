---
task: Fix offer description extraction failing when English cookie consent banners (CookieYes) precede job content
description: Fix summarize_chunks returning AUCUNE_OFFRE on diagnoly.com and similar sites due to English CookieYes consent banner not dismissed by COOKIE_DISMISS_JS in crawler1.py and not stripped by cookie_patterns in backend/app/llm/utils.py
status: done
created: 2026-11-15
---

# Fix Offer Description Extraction Blocked by Cookie Consent Banners

## Context
- Existing code checked: `backend/job_crawler/crawler1.py` (`COOKIE_DISMISS_JS` lines 33-47, `get_filtered_markdown` lines 309-479), `backend/app/llm/utils.py` (`fetch_documents` lines 33-229, `summarize_chunks` lines 275-405), `backend/app/routers/applications/offer_linking.py` (`regenerate_application_description`).
- Fresh info looked up: reproduced live on `https://www.diagnoly.com/tr/job/data-scientist/?utm_source=chatgpt.com` — `fetch_documents` returned 3676 chars (551 words) with ~1600 chars of English CookieYes banner at the top followed by the full Data Scientist job offer; `summarize_chunks` (`gpt-5-nano`) returned `AUCUNE_OFFRE` because `cookie_patterns` only matched French cookie banners and the prompt did not clarify to ignore leading cookie/modal notices when an offer follows.
- Git status checked: clean working tree after archiving `20261114-update-outdated-llm-models`.

## Simpler Alternative Considered
Only editing the LLM prompt was considered, but stripping English cookie banners deterministically (zero tokens) and dismissing CookieYes in `COOKIE_DISMISS_JS` prevents wasting tokens and avoids `gpt-5-nano` (`reasoning_effort="minimal"`) misclassifying the whole page.

## Surgical Scope
- **Files touched**:
  - `backend/job_crawler/crawler1.py`
  - `backend/app/llm/utils.py`
  - `backend/tests/test_summarize_offer_cookie_guard.py`
  - `docs/micro/20261115-fix-cookie-banner-offer-extraction/PLAN.md`
  - `docs/micro/INDEX.md`
- **Files NOT touched**: all others
- **Symbols replaced** (→ must delete before done): none
- **Symbols extended** (→ keep, add or modify only):
  - `COOKIE_DISMISS_JS` in `backend/job_crawler/crawler1.py`
  - `summarize_chunks` in `backend/app/llm/utils.py`

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import app.llm.utils, job_crawler.crawler1"`
- [x] Tests pass: `cd backend && uv run pytest tests/test_summarize_offer_cookie_guard.py tests/pipeline/test_crawler_guards.py -q`
- [x] No dead code: n/a — no symbols replaced
- [x] Type check: `cd backend && uv run python -m py_compile app/llm/utils.py job_crawler/crawler1.py tests/test_summarize_offer_cookie_guard.py`
- [x] Manual check: `cd backend && uv run python -c` live extraction on `https://www.diagnoly.com/tr/job/data-scientist/?utm_source=chatgpt.com` returns a non-empty structured summary mentioning `Diagnoly` and `Data Scientist`

## Steps
- [x] Step 1: Extend `COOKIE_DISMISS_JS` in `backend/job_crawler/crawler1.py` to dismiss CookieYes banners (`button[data-cky-tag="accept-button"]`, `.cky-btn-accept`)
- [x] Step 2: Extend `cookie_patterns` in `backend/app/llm/utils.py` (`summarize_chunks`) to strip English cookie consent / CookieYes blocks, and clarify the prompt `RÈGLE PRIORITAIRE` so leading cookie/warning banners do not trigger `AUCUNE_OFFRE` when job offer content is present
- [x] Step 3: Add deterministic offline unit tests in `backend/tests/test_summarize_offer_cookie_guard.py` using `@pytest.mark.parametrize` (no network, no inline >10-line payloads) verifying cookie banner stripping and `summarize_chunks` behavior
- [x] Step 4 (teardown): Run all Definition of Done commands including live verification on the Diagnoly URL, inspect full `git diff`, fill `## Code Review`, and close out plan

## Code Review
- Dead code removed: n/a (no symbols replaced)
- Build status: pass (`import app.llm.utils, job_crawler.crawler1` and `py_compile` exit 0)
- Type errors: none
- Unintended side effects: none (full `git diff` inspected; pure helper `clean_cookie_banners` only strips cookie consent notices)
- Security surface touched: no (SSRF guards untouched; prompt-injection guard preserved)
- Verdict: ✅ DONE

## Execution Log
- 2026-11-15T10:51Z | antigravity | step 1 | started
- 2026-11-15T10:51Z | antigravity | step 1 | done | `py_compile` and `tests/pipeline/test_crawler_guards.py` (7 passed) exit 0
- 2026-11-15T10:51Z | antigravity | step 2 | started
- 2026-11-15T10:52Z | antigravity | step 2 | done | `py_compile app/llm/utils.py` and `clean_cookie_banners` check exit 0
- 2026-11-15T10:52Z | antigravity | step 3 | started
- 2026-11-15T10:52Z | antigravity | step 3 | done | `pytest tests/test_summarize_offer_cookie_guard.py -q` (7 passed)
- 2026-11-15T10:52Z | antigravity | step 4 | started
- 2026-11-15T10:52Z | antigravity | step 4 | done | All DoD checks exit 0 (14 passed pytest + live Diagnoly extraction 2313 chars)

## Notes
- Convention files checked: `AGENTS.md`, `GEMINI.md` (no `docs/adrs/` in repo).
- Baseline DoD before edits: `import app.llm.utils, job_crawler.crawler1` exit 0; `py_compile` exit 0; `tests/pipeline/test_crawler_guards.py` 7 passed. Live `summarize_chunks` on Diagnoly URL returned `""` (`AUCUNE_OFFRE`).
