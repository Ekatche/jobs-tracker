---
task: Fix candidate profile lookup in offer evaluator to match ObjectId and string user_id
status: completed
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Fix Candidate Profile Lookup in Offer Evaluator

## Context
- Existing code checked:
  - `backend/app/services/evaluation/evaluator.py:115`: Queries `candidate_profile` using `{"user_id": user_str_id}` (only string).
  - `backend/app/routers/cover_letters.py`: Stores and queries `candidate_profile` with `"user_id": ObjectId(user_id)`.
  - Symptom: Because `find_one({"user_id": user_str_id})` does not match BSON `ObjectId`, `profile_doc` defaults to empty `{}`. Gemini 3.7 Flash then correctly reports: *"Profil du candidat totalement vide (aucune expérience, compétence ou préférence renseignée)."* with a degraded score of 1.1/5.0.
- Fresh info looked up:
  - The live candidate profile in the MongoDB database actually has 4 experiences (Nile, Léon Bérard, Nodya, Bimedoc), rich technical skills (Python, FastAPI, RAG, etc.), and targeting preferences.
- Git status checked: Clean working tree ready for surgical fix.

## Simpler Alternative Considered
- Migrating all existing MongoDB `candidate_profile` documents to store `user_id` as string: REJECTED because `cover_letters.py` and other services expect `ObjectId(user_id)`. Querying with `{"$or": [{"user_id": ObjectId(user_id)}, {"user_id": str(user_id)}]}` is non-breaking and handles both.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/evaluation/evaluator.py`: Query `candidate_profile` with `$or` for `ObjectId` and `str`.
  - `backend/tests/test_offer_evaluation.py`: Add unit test validating that evaluator correctly queries and uses candidate profile when `user_id` is an `ObjectId`.
- **Files NOT touched**:
  - `backend/app/routers/cover_letters.py`
  - `backend/app/routers/applications.py`
  - `frontend/`
- **Symbols replaced**: none
- **Symbols extended**: `evaluate_offer_two_pass` in `backend/app/services/evaluation/evaluator.py`

## Definition of Done
- [x] Tests pass: `.venv/bin/pytest tests/test_offer_evaluation.py -v` (11/11 tests pass)
- [x] End-to-end evaluation with live user profile loads 4 experiences and non-empty context (Score raised from 1.1 to 4.8/5.0).
- [x] No dead code: 0 orphans
- [x] Type check: `python3 -m py_compile backend/app/services/evaluation/evaluator.py` (Exit code 0)

## Steps
- [x] Step 1: In `backend/app/services/evaluation/evaluator.py`, update the `candidate_profile` retrieval to support both `ObjectId` and string representations of `user_id`.
- [x] Step 2: In `backend/tests/test_offer_evaluation.py`, add a test verifying that `evaluate_offer_two_pass` queries `candidate_profile` with `$or` query matching `ObjectId`.
- [x] Step 3 (teardown): Run pytest test suite, verify compilation, update plan to complete and record in `DAILY_LOG-2026-09-16.md`.

## Code Review
- Dead code removed: yes
- Build status: pass (11/11 tests pass)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: complete and verified

## Execution Log
- 11:15 | agy | step 1 | completed - support both ObjectId and string user_id when querying candidate_profile
- 11:15 | agy | step 2 | completed - unit test added and passed (11/11 tests in test_offer_evaluation.py)
- 11:16 | agy | step 3 | completed - re-evaluation executed against live database with user profile, score updated to 4.8/5.0

