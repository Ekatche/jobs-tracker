---
task: Implement 4-layer job offer normalization pipeline and multi-criteria deduplication
status: done
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Implement 4-layer job offer normalization pipeline and multi-criteria deduplication

## Context
- Existing code checked:
  - `docs/JOB_INGESTION_AND_NORMALIZATION.md`: defines the 4 layers (Deterministic syntax cleanup, Seniority & Canonical title, Multi-criteria fuzzy/Jaccard dedup, and Multi-source fusion).
  - `backend/app/services/normalization.py`: contains initial city/company/position normalization and URL cleaners, but lacks contract/emoji/bracket cleaning, seniority level extraction, description Jaccard matching, and multi-source consolidation.
  - `backend/app/services/job_offers.py`: `clean_job_offer_duplicates_optimized` currently drops duplicate offers without consolidating alternative URLs or preserving richer metadata (salary, description).
  - `backend/app/tasks/clean_job_offers.py`: `remove_similarity_duplicates` deletes duplicates without updating the survivor with merged attributes.
  - `backend/app/models.py`: lacks typed `canonical_title`, `seniority_level`, and `alternative_urls` on `JobOfferCreate` and `JobOfferResponse`.
- Fresh info looked up: Jaccard word-shingle tokenization & Levenshtein / SequenceMatcher thresholds.
- Git status checked: clean on `main` (with recent uncommitted micro-dev changes present and verified).

## Simpler Alternative Considered
Simple exact hash match on company and title. Rejected because multidiffusion (e.g. Indeed vs LinkedIn vs direct ATS) uses different titling formats ("Data Scientist (H/F) - CDI [Paris]" vs "Senior Data Scientist"), leading to duplicate offers polluting the candidate's dashboard and missing salary/source data.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/normalization.py`
  - `backend/app/services/job_offers.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - `backend/app/tasks/clean_job_offers.py`
  - `backend/app/models.py`
  - `backend/tests/test_normalization_and_dedup.py`
- **Files NOT touched**:
  - All frontend files, database connection setup, auth endpoints.
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `backend/app/services/normalization.py`: add `clean_job_title_syntax`, `extract_seniority`, `jaccard_description_similarity`, `are_offers_duplicates`, `merge_multidiffusion_offers`, and `deduplicate_and_merge_offers`.
  - `backend/app/services/job_offers.py`: wire `clean_job_offer_duplicates_optimized` to `deduplicate_and_merge_offers`.
  - `backend/app/tasks/job_offers_collectors.py`: enrich offers with `canonical_title` and `seniority_level`, and use `deduplicate_and_merge_offers`.
  - `backend/app/tasks/clean_job_offers.py`: update `remove_similarity_duplicates` to update the survivor document with merged attributes before deleting/expiring duplicates.
  - `backend/app/models.py`: add `canonical_title`, `seniority_level`, `alternative_urls` to `JobOfferCreate` and `JobOfferResponse`.

## Definition of Done
- [x] Build passes: `docker exec jobtracker-backend python -c "from app.services.normalization import deduplicate_and_merge_offers; print('NORMALIZATION OK')"`
- [x] Tests pass: `docker exec jobtracker-backend pytest tests/test_normalization_and_dedup.py`
- [x] Full regression suite passes: `docker exec jobtracker-backend pytest tests/test_crew_models_and_tools.py tests/test_user_offer_interactions.py tests/test_ats_parsers.py tests/test_clean_and_verify_alignment.py tests/test_verify_job_offers.py tests/test_job_offers_collectors_queries.py tests/test_normalization_and_dedup.py`
- [x] No dead code: confirmed all replaced helper branches cleaned.
- [x] Type check: `ruff check backend/app/services/normalization.py backend/app/tasks/clean_job_offers.py backend/tests/test_normalization_and_dedup.py`
- [x] Manual check: verify multidiffusion example (ATS + Indeed + LinkedIn) merges into a single offer with primary ATS url, preserved salary, and combined alternative URLs.

## Steps
- [x] Step 1: Implement Couche 1 (`clean_job_title_syntax`), Couche 2 (`extract_seniority`), Couche 3 (`jaccard_description_similarity`, `are_offers_duplicates`), and Couche 4 (`merge_multidiffusion_offers`, `deduplicate_and_merge_offers`) in `backend/app/services/normalization.py`.
- [x] Step 2: Extend `JobOfferCreate` and `JobOfferResponse` in `backend/app/models.py` with `canonical_title`, `seniority_level`, and `alternative_urls`.
- [x] Step 3: Wire `deduplicate_and_merge_offers` into `backend/app/services/job_offers.py` (`clean_job_offer_duplicates_optimized`) and enrich offers in `backend/app/tasks/job_offers_collectors.py`.
- [x] Step 4: Update `backend/app/tasks/clean_job_offers.py` (`remove_similarity_duplicates`) to merge data into the survivor document in MongoDB before deleting/expiring duplicates.
- [x] Step 5: Add comprehensive unit tests in `backend/tests/test_normalization_and_dedup.py` verifying all 4 layers, multidiffusion merging, ATS URL priority, and salary/field preservation.
- [x] Step 6 (teardown): Confirm 0 dead code, run full test suite and linters.

## Code Review
- Dead code removed: yes (removed unused imports in job_offers.py and job_offers_collectors.py)
- Build status: pass (exit 0 across all 76 regression tests)
- Type errors: none (ruff check 100% clean)
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 23:56 Step 1: Implemented 4-layer functions (clean_job_title_syntax, extract_seniority, jaccard_description_similarity, are_offers_duplicates, get_source_priority, merge_multidiffusion_offers, deduplicate_and_merge_offers) in normalization.py. Smoke test passed: exit 0 (SMOKE TESTS PASSED).
- 23:57 Step 2: Added canonical_title, seniority_level, alternative_urls to JobOfferCreate and JobOfferResponse models in models.py. Verified import in Docker: exit 0 (MODELS OK).
- 23:58 Step 3: Wired clean_job_offer_duplicates_optimized to deduplicate_and_merge_offers in job_offers.py and enriched offers with Couche 1/2 in job_offers_collectors.py. Verified in Docker: exit 0 (COLLECTORS OK).
- 23:59 Step 4: Updated remove_similarity_duplicates in clean_job_offers.py to merge data into survivor MongoDB document before deleting/expiring duplicates. Verified in Docker: exit 0 (CLEAN_JOB_OFFERS OK).
- 00:00 Step 5: Created test_normalization_and_dedup.py with 15 unit tests covering all 4 layers. All 15 tests passed in 0.07s.
- 00:00 Step 6: Full regression test suite (76 tests) passed in 0.31s. ruff clean on all 6 touched files. Manual multidiffusion check verified with ATS priority.

## Notes
(deviations from plan, errors hit, corrections made)
- Candidate preference roles sanitized with clean_job_title_syntax in build_search_queries to guarantee zero prompt pollution from user profiles.
