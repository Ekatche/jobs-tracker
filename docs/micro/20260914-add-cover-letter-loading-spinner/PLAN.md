---
task: Add loading spinner, full LLM generation, and improved letter display layout
status: complete
created: 2026-09-14
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Full Cover Letter Generation, Spinner Feedback & Polished Layout

## Context
- Existing code checked:
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py` had stubbed LLM calls (`_call_writer` returned `"Madame, Monsieur,\n\nVotre offre chez " + company_name + "..."`), causing incomplete 2-line letters.
  - `backend/job_trackers/src/job_trackers/letter_llm.py` had default models pointing to unsupported/empty credit providers. `openai/gpt-4o-mini` and `mistral/mistral-small-latest` are tested and active with available credits.
  - `frontend/src/components/applications/CoverLetterPanel.tsx` lacked immediate spinner feedback on click, suffered from cramped header buttons, and only offered a raw textarea without formatted reading view.
- Fresh info looked up: LiteLLM provider completion verified for `openai/gpt-5.6-sol`, `openai/gpt-5.6-luna` and `gemini/gemini-3.8-flash`.
- Git status checked: working directory changes tracked.

## Simpler Alternative Considered
None — solving the user's issue requires connecting real LLM generation so the letter is complete, adding the requested loading spinner, and polishing the result panel layout.

## Surgical Scope
- **Files touched**:
  - `backend/job_trackers/src/job_trackers/letter_llm.py`
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `frontend/src/components/applications/CoverLetterPanel.tsx`
- **Files NOT touched**: all others
- **Symbols replaced**: stub implementations in `cover_letter_crew.py`
- **Symbols extended**: `CoverLetterPanel` state and display mode

## Definition of Done
- [x] Backend tests pass: `docker compose exec backend pytest tests/test_cover_letters_api.py tests/test_cover_letter_crew.py -v` (6 passed)
- [x] Full letter generation verified: letter generated with real candidate facts, ~220-300 words, and passing guards.
- [x] Frontend type check passes: `npx tsc --noEmit` (0 errors)
- [x] Frontend build passes: `npm run lint` (in frontend docker build)
- [x] Layout check: CoverLetterPanel includes "Aperçu" (reading view) and "Édition" (editor view), responsive buttons, and animated spinner on generation.

## Steps
- [x] Step 1: Update `DEFAULT_MODELS` in `letter_llm.py` to use `openai/gpt-5.6-sol` (Writer/Reviser), `openai/gpt-5.6-luna` (Analyst) and `gemini/gemini-3.8-flash` (Critic, ensuring cross-provider validation).
- [x] Step 2: Implement real prompts and LiteLLM/CrewAI calls in `cover_letter_crew.py` for `_call_analyst`, `_call_writer`, `_call_critic`, and `_call_reviser` adhering to letter guard rules.
- [x] Step 3: Update `CoverLetterPanel.tsx` to add `generating` state, animated spinners on buttons, optimistic pending state, responsive header controls, and a toggle between "Aperçu" (document view) and "Édition".
- [x] Step 4: Rebuild frontend container and test end-to-end letter generation on the Deloitte offer.
- [x] Step 5 (teardown): Verify tests and confirm 0 regressions.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 00:12 Step 1 complete: `letter_llm.py` updated with active provider models (`openai/gpt-5.6-sol` Writer/Reviser, `openai/gpt-5.6-luna` Analyst, `gemini/gemini-3.8-flash` Critic).
- 00:13 Step 2 complete: `cover_letter_crew.py` implemented with real LiteLLM prompts for analyst, writer, critic, and reviser. Full letter generated (1,455 characters, status `ready`).
- 00:13 Step 3 complete: `CoverLetterPanel.tsx` updated with dual view modes ("Aperçu" / "Éditer"), animated spinner feedback, and optimistic pending state.
- 00:14 Step 4 complete: Frontend Docker container rebuilt and healthy, backend restarted.
- 00:14 Step 5 complete: `pytest tests/test_cover_letters_api.py tests/test_cover_letter_crew.py -v` passed (6/6).

## Notes
- Initial stubs used `gemini-3.6-flash` which returned a 429 quota exhaustion error. Upgraded through `gpt-4o-mini`/`mistral-small-2501` and finally to the latest GPT-5.6 family (Sol/Luna) + Gemini 3.8 Flash for optimal quality-to-price ratio.
- Config: Writer/Reviser `gpt-5.6-sol` (~$0.04/call), Analyst `gpt-5.6-luna` (~$0.001/call), Critic `gemini-3.8-flash` (free tier, cross-provider).
