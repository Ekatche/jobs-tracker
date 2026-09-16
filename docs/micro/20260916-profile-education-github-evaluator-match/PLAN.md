---
task: Consolidate candidate education & github projects into profile and exploit full profile context in offer evaluator
status: completed
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Renseigner le profil complet (Formations, Projets GitHub) et optimiser l'évaluateur de matching

## Context
- Existing code checked:
  - `backend/app/services/profile/merge.py`: Uses `_merge_simple_list("education", sources, order, "school")`. In CV parser sources, education uses keys `institution`, `dates`, `degree`, `details`. Because `school` is missing, `item.get("school")` returns `None` and all 4 degrees (CNAM AI spec, Nexa Master Data Science, IAE Lyon Master & Licence) were discarded during merge, resulting in `education: []`.
  - `backend/app/services/profile/collectors/github.py`: Ready to collect public repos for a user handle (`Ekatche` present in CV `personal_info`), but GitHub source was never collected into `candidate_profile.sources`.
  - `backend/app/services/evaluation/evaluator.py`: In Pass 2 (`evaluate_offer_two_pass`), `candidate_context` only provided `headline`, `summary`, `preferences`, `skills`, and `experiences`. It completely omitted `education`, `projects`, `certifications`, and `languages`. The matching LLM had zero visibility on degrees (leading to false negatives like "missing Bac+5").
  - `frontend/src/components/profile/CandidateProfileSection.tsx`: Has no visual section for rendering candidate `education` or `certifications`.
- Fresh info looked up: None.
- Git status checked: Working branch `fix/profile-multi-sources`.

## Simpler Alternative Considered
None — education must be normalized properly in merge, collected into DB, fed into evaluator prompt, and displayed in UI.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/services/profile/merge.py`
  - `backend/app/services/profile/collectors/github.py`
  - `backend/tests/test_profile_merge.py`
  - `backend/app/services/evaluation/evaluator.py`
  - `backend/tests/test_offer_evaluation.py`
  - `frontend/src/components/profile/CandidateProfileSection.tsx`
- **Files NOT touched**:
  - All other routers, workers, and pages.
- **Symbols replaced**: None.
- **Symbols extended**:
  - `_merge_education`, `_merge_certifications`, `_extract_languages` in `backend/app/services/profile/merge.py`.
  - `candidate_context` and Pass 2 prompt in `backend/app/services/evaluation/evaluator.py`.
  - `CandidateProject` in `backend/app/models.py` (added `repo` and `highlights`).
  - Profile view in `frontend/src/components/profile/CandidateProfileSection.tsx` to render education & certifications.

## Definition of Done
- [x] Backend merge & evaluator tests pass: `docker exec jobtracker-backend pytest tests/test_profile_merge.py tests/test_profile_periods.py tests/test_profile_collectors.py tests/test_offer_evaluation.py -v` (95/95 passed)
- [x] Full profile update in DB: User profile in MongoDB contains normalized `education` (4 degrees with school, degree, years, topics), imported GitHub projects from `Ekatche` (15 total projects), and complete skills/experiences/languages.
- [x] Evaluator prompt verification: Pass 2 LLM payload receives `education`, `projects`, `languages`, `certifications`, and matches degrees for academic requirements (e.g. Bac+5).
- [x] Frontend type check passes: `npx tsc --noEmit` & `npm run build` (0 errors).
- [x] Frontend UI verification: Formations & Diplômes displayed cleanly in `CandidateProfileSection.tsx` with modern responsive layout.

## Steps
- [x] Step 1: In `backend/app/services/profile/merge.py`, implement `_merge_education` supporting both `institution`/`school`, `dates`/`years`, and `details`/`topics`. Add unit test in `backend/tests/test_profile_merge.py`.
- [x] Step 2: In `backend/app/services/evaluation/evaluator.py`, enrich `candidate_context` with `education`, `projects`, `certifications`, and `languages`. Update Pass 2 prompt instructions to evaluate degrees and technical projects against job criteria.
- [x] Step 3: Run GitHub collector for user (`Ekatche`) and re-merge candidate profile in MongoDB to populate `education` and `projects`.
- [x] Step 4: In `frontend/src/components/profile/CandidateProfileSection.tsx`, add a modern « Formations & Diplômes » card section (with institution, degree, dates, topics) and certifications.
- [x] Step 5 (teardown): Run `tsc --noEmit`, backend pytest, verify live matching on an offer, and record daily log.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- Step 1: Replaced `_merge_simple_list` with dedicated `_merge_education`, `_merge_certifications`, and `_extract_languages` in `merge.py`. Handled keys `institution`, `dates`, `details`, and nested `personal_info.languages`. Added 3 unit tests in `tests/test_profile_merge.py`. Evidence: 24/24 tests passed in 0.09s.
- Step 2: Enriched `candidate_context` in `evaluator.py` (Pass 2) with `education`, `projects`, `certifications`, and `languages`. Updated prompt matching instructions for academic degree requirements and verifiable project evidence. Added test in `test_offer_evaluation.py`. Evidence: 12/12 tests passed in 0.18s.
- Step 3: Collected public repositories from GitHub for `https://github.com/Ekatche` and added `repo`/`highlights` support to `CandidateProject`. Synchronized and persisted candidate profile into MongoDB: 4 degrees (CNAM, Nexa, IAE), 15 projects with stack and GitHub links, languages and headline. Evidence: MongoDB replace_one completed with 0 errors.
- Step 4: Added « Formations & Diplômes » and « Certifications » responsive card sections in `CandidateProfileSection.tsx` with degree badges, calendar dates, topics tags and modern slate borders. Evidence: `tsc --noEmit` and `npm run build` completed with code 0.
- Step 5: Ran full regression suite across all 4 test modules (95/95 passed). Validated type checking and Next.js production build.

## Notes
- `CandidateProject` model in `models.py` required `repo` and `highlights` attributes to prevent Pydantic serialization loss during MongoDB document updates.




## Notes
