# Plan: Education Deduplication and Conflicts Dismissal

## Context & Needs
1. **Divergences (Conflicts) Dismissal**:
   The user noted that while source conflicts provide transparency, they would like to be able to dismiss/hide them from view once reviewed, so they don't permanently clutter the profile view.
2. **Education Deduplication & Arbitration**:
   The current education merge algorithm uses strict `f"{school_slug}::{degree_slug}"` equality. Slight naming variations (e.g. "Université Claude Bernard Lyon 1" vs "Université Lyon 1", or "Master Informatique" vs "Master en Informatique / Data Science") result in duplicate entries instead of merging the information (school, degree, years, topics) and arbitrating properly based on source priority (`manual` > `cv` > `website` > `github`).

## Solution
1. **Frontend (`CandidateProfileSection.tsx`)**:
   Add a dismiss/hide button for the "Divergences détectées entre vos sources" alert box, with an optional toggle button to redisplay them on demand.
2. **Backend (`backend/app/services/profile/merge.py`)**:
   - Upgrade `_merge_education`:
     - Implement loose/fuzzy matching for school names and degree names across sources (using `_keys_loosely_match` and token containment).
     - Guard against merging two distinct diplomas from the same source.
     - Match and merge dates/years intelligently.
     - Preserve source priority order (`manual` > `cv` > `website` > `github`) when arbitrating school and degree names.
     - Combine and deduplicate topics (`_dedup_preserving_order`).
     - Record discrepancies in `conflicts` if distinct degrees or years are provided by different sources for the same education item.
     - Respect `excluded_education` properly.
3. **Tests (`backend/tests/test_profile_merge.py`)**:
   Add unit tests verifying education loose matching, deduplication, field arbitration, and conflict tracking.

## Steps
- [x] 1. Update `CandidateProfileSection.tsx` to add a dismiss/reopen control for the conflicts banner.
- [x] 2. Update `backend/app/services/profile/merge.py` with intelligent education matching and arbitration.
- [x] 3. Add tests in `backend/tests/test_profile_merge.py` covering loose education matching and arbitration.
- [x] 4. Run tests and type checks.
- [x] 5. Update `docs/micro/DAILY_LOG-2026-10-03.md` and `docs/micro/INDEX.md`.
