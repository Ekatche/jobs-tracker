---
task: Prevent cover letter agents from listing resume experiences and enforce single anchor proof
status: completed
created: 2026-09-19
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Prevent Cover Letter Agents From Listing Resume Experiences

## Context
- Existing code checked:
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`: `_call_analyst` passed `selected_exps[:3]` blindly to `_call_writer`.
  - `backend/app/llm/prompts/cover_letter/01_fond.md`: Rules defined 1 single developed experience, but needed firmer boundary on auxiliary mentions.
  - `backend/app/llm/prompts/cover_letter/02_style.md`: Mixed signals remained ("raconter son parcours", "J'ai conçu... J'ai développé..."), lacked explicit narrative arc and contrastive few-shot example.
  - `backend/app/llm/prompts/cover_letter/03_critique.md`: Needed strict instruction that any multi-employer enumeration forces a "revise" verdict.
  - `backend/app/llm/prompts/cover_letter/04_revision.md`: "Principe de révision minimale" prevented structural rewrite when a CV catalogue was detected.
  - `backend/app/services/letter_guards.py`: Missing deterministic code guard against paragraph openings starting with employer prepositions (`À...`, `Chez...`, `Au...`) and limiting distinct candidate employers mentioned to at most 2.
- Fresh info looked up: Prompt engineering best practices on coverage bias, information bottleneck, and multi-agent task handoff.
- Git status checked: Pre-existing uncommitted changes in `applications.py` and `docker-compose.yml` noted and untouched.

## Simpler Alternative Considered
- Only tweak `02_style.md` prompt: Tested previously and failed because feeding 3 full experiences into the context triggers the model's coverage bias regardless of negative constraints.

## Surgical Scope
- **Files touched**:
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `backend/app/llm/prompts/cover_letter/01_fond.md`
  - `backend/app/llm/prompts/cover_letter/02_style.md`
  - `backend/app/llm/prompts/cover_letter/03_critique.md`
  - `backend/app/llm/prompts/cover_letter/04_revision.md`
  - `backend/app/services/letter_guards.py`
  - `backend/tests/test_letter_guards.py`
- **Files NOT touched**:
  - `backend/app/routers/applications.py`
  - `docker-compose.yml`
  - all other files
- **Symbols replaced**: none
- **Symbols extended**:
  - `evaluate_letter_guards` in `backend/app/services/letter_guards.py`
  - `_call_analyst` & `_call_writer` in `backend/job_trackers/src/job_trackers/cover_letter_crew.py`

## Definition of Done
- [x] Build passes: `n/a — Python interpreted project`
- [x] Tests pass: `./.venv/bin/pytest tests/test_letter_guards.py tests/test_cover_letter_crew.py tests/test_cover_letter_prompts.py` (40 passed in 6.04s)
- [x] No dead code: `confirmed removed / no orphans`
- [x] Type check: `pass`
- [x] Manual check: Counter-example letter evaluated in `test_guards_user_counter_example_is_blocked` and triggers all blocking violations.

## Steps
- [x] Step 1: Add deterministic guardrails in `backend/app/services/letter_guards.py` and unit tests in `backend/tests/test_letter_guards.py` to block letters with employer-opening paragraphs (`r"^(?:À|Au|Chez|Au sein de|Mon expérience à|Lors de mon passage chez)\s+[A-Z]"`) or more than 2 distinct candidate companies mentioned in the letter body.
- [x] Step 2: Update `_call_analyst` in `backend/job_trackers/src/job_trackers/cover_letter_crew.py` to act as a strategist: identify the primary challenge of the offer, select exactly ONE primary anchor experience (`primary_experience`) from the candidate profile, and at most ONE optional secondary context (`secondary_context`).
- [x] Step 3: Update `_call_writer` in `backend/job_trackers/src/job_trackers/cover_letter_crew.py` and prompts (`01_fond.md`, `02_style.md`) to feed ONLY the primary anchor experience and enforce the Pitch Arc (1. Problem conviction, 2. Target company bridge, 3. In-depth anchor proof, 4. Forward-looking collaboration) with contrastive few-shot examples.
- [x] Step 4: Update `03_critique.md` and `04_revision.md` to ensure any structural resume-catalogue defect overrides minimal revision and commands full paragraph re-anchoring.
- [x] Step 5 (teardown): Run `./.venv/bin/pytest tests/test_letter_guards.py tests/test_cover_letter_crew.py tests/test_cover_letter_prompts.py` and verify all tests pass with zero regressions.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none (verified by 40 unit tests passing)
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 10:47 - Step 1: Added `_FORBIDDEN_EMPLOYER_OPENING`, temporal connectors in `BANNED_LEXICON`, and employer count verification in `letter_guards.py`. Added 3 unit tests in `test_letter_guards.py`. Result: 23 passed.
- 10:49 - Step 2: Refactored `_call_analyst` to formulate `target_challenge`, `guiding_thesis`, and pick single `anchor_company` using `_find_anchor_exp`.
- 10:50 - Step 3: Updated `_call_writer` with `_SafePromptDict` fallback. Refactored `01_fond.md` and `02_style.md` to remove resume-echo phrases and inject contrastive few-shot example using anonymized companies.
- 10:50 - Step 4: Strengthened criterion 0 in `03_critique.md` (mandatory `revise` on catalogue) and added structural override exception in `04_revision.md`.
- 10:50 - Step 5: Full test suite ran: 40 tests passed across `test_letter_guards.py`, `test_cover_letter_crew.py`, and `test_cover_letter_prompts.py`.

## Notes
- Anonymized company names ("Initech", "DataCorp", "PartnerTech") were used in few-shot prompt examples to adhere to project test rules forbidding hardcoding candidate identities.
