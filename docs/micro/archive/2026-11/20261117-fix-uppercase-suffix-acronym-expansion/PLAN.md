---
task: Prevent case-sensitive acronym expansion inside uppercase employer or city title segments
description: Fix expand_title_acronyms false-positive expansion of French DE to Data Engineer in uppercase suffixes in domain_relevance.py with regression tests in test_domain_relevance.py and test_offer_scoring_role_gate.py
status: done
created: 2026-11-17
---

# Prevent uppercase-segment acronym expansion (DE -> Data Engineer false positives)

## Context
- Existing code checked: `expand_title_acronyms` in `backend/app/services/evaluation/domain_relevance.py:63-73` disables `CASE_SENSITIVE_ACRONYMS` (`DE -> Data Engineer`, `DS -> Data Scientist`, `PM`, `PO`, `ML`, `QA`, `SRE`, `BI`) only when `title.isupper()`. Mixed-case offer titles containing an uppercase employer/location suffix (e.g. `"Chef de service administratif et financier - CONSEIL DEPARTEMENTAL DE L'ISERE"`) fail `title.isupper()`, expanding `DE` to `"Data Engineer"` and polluting both `role_gate._title_tokens` and `offer_scoring.embeddings.offer_embedding_text`. Verified in prod DB on `6afab01d475d8bd2cab8735d` and 4 other offers. Callers found via `ast-grep`: `role_gate.py`, `score.py`, `embeddings.py`, `domain_relevance.py`, `sources/__init__.py`. `code-review-graph` `tests_for` confirmed tests in `test_domain_relevance.py`.
- Fresh info looked up: n/a — pure Python string/regex logic.
- Git status checked: clean (`main` at `1cd691e`, only active new plan files created).

## Simpler Alternative Considered
Removing `"DE"` from `CASE_SENSITIVE_ACRONYMS` entirely — rejected because real mixed-case tech titles like `"DE Spark"` (covered by `test_domain_relevance.py:91`) legitimately use `DE` for `Data Engineer`, and other uppercase phrases like `"CHEF DE PROJET - Paris"` still contain uppercase French words that should not trigger case-sensitive expansion.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/evaluation/domain_relevance.py` (add segment & uppercase-neighbor guard around `CASE_SENSITIVE_ACRONYMS` substitution inside `expand_title_acronyms`)
  - `backend/tests/test_domain_relevance.py` (add parametrized uppercase-suffix cases to `test_expand_title_acronyms_extended`)
  - `backend/tests/test_offer_scoring_role_gate.py` (add parametrized non-regression test verifying `DATA_ROLES` reject `"Chef de service administratif et financier - CONSEIL DEPARTEMENTAL DE L'ISERE"` and `"Animateur petite enfance - SAINT LAURENT DE MURE"`)
- **Files NOT touched**: all others (`role_gate.py`, `score.py`, `embeddings.py`, `sources/__init__.py`, frontend)
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `expand_title_acronyms` in `backend/app/services/evaluation/domain_relevance.py`

## Definition of Done
- [x] Build/import check passes: `cd backend && uv run python -c "from app.services.evaluation.domain_relevance import expand_title_acronyms; from app.services.offer_scoring.role_gate import role_terms, title_matches_roles"`
- [x] Linter passes: `cd backend && uv run flake8 --config ../.flake8 .`
- [x] Tests pass: `cd backend && uv run python -m pytest tests/test_domain_relevance.py tests/test_offer_scoring_role_gate.py tests/test_hybrid_scoring.py tests/test_offer_scoring_assess.py tests/test_offer_profile_matcher.py -q`
- [x] No dead code: n/a — no symbols replaced (`0` symbols in `Symbols replaced`)
- [x] Line limits hold: `wc -l backend/app/services/evaluation/domain_relevance.py backend/tests/test_domain_relevance.py backend/tests/test_offer_scoring_role_gate.py` (source <= 300 lines, tests <= 400 lines)
- [x] Manual/regression check: `cd backend && uv run python -c "from app.services.evaluation.domain_relevance import expand_title_acronyms; from app.services.offer_scoring.role_gate import role_terms, title_matches_roles; assert expand_title_acronyms(\"Chef de service administratif et financier - CONSEIL DEPARTEMENTAL DE L'ISERE\") == \"Chef de service administratif et financier - CONSEIL DEPARTEMENTAL DE L'ISERE\"; assert not title_matches_roles(\"Chef de service administratif et financier - CONSEIL DEPARTEMENTAL DE L'ISERE\", role_terms(['Data Scientist', 'Ingénieur Data', 'Data Engineer']))"`

## Steps
- [x] Step 1: Add helper `_should_expand_case_sensitive(title: str, match: re.Match[str]) -> bool` in `backend/app/services/evaluation/domain_relevance.py` and use match-callback filtering inside `expand_title_acronyms` so uppercase French prose segments or uppercase word neighbors (`len >= 4`, skipping elided articles `L'`/`D'`) suppress case-sensitive expansion. Run import check + existing `test_domain_relevance.py`.
- [x] Step 2: Add parametrized regression tests in `backend/tests/test_domain_relevance.py` and `backend/tests/test_offer_scoring_role_gate.py`, keeping files under test hygiene rules (`@pytest.mark.parametrize`, <= 400 lines, offline). Run `pytest` on all scoring & domain relevance suites.
- [x] Step 3 (teardown): Verify `wc -l`, run full `flake8`, full DoD `pytest` suite, and manual assertion check; inspect `git diff` line by line and close out `PLAN.md`.

## Code Review
- Dead code removed: n/a — no symbols replaced (`0` orphans)
- Build status: pass (`import check`, `flake8` 0 errors, `190 passed in 0.59s`, `MANUAL CHECK OK`)
- Type errors: none (Python 3.12 annotations preserved)
- Unintended side effects: none — mixed-case acronyms (`DE Spark`, `DE / ML Engineer`, `PM Senior - PARIS`) keep expanding while uppercase employer/city prose (`CONSEIL DEPARTEMENTAL DE L'ISERE`, `MAIRIE DE BOURGOIN-JALLIEU`, `SAINT LAURENT DE MURE`, `PIERRE DE LUNE`, `VAL DE MARNE`) stay untouched
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-11-17T20:37Z | antigravity | step 1 | started
- 2026-11-17T20:38Z | antigravity | step 1 | done | import check exit 0; `pytest tests/test_domain_relevance.py -q` 26 passed
- 2026-11-17T20:38Z | antigravity | step 2 | started
- 2026-11-17T20:39Z | antigravity | step 2 | done | `pytest tests/test_domain_relevance.py tests/test_offer_scoring_role_gate.py tests/test_hybrid_scoring.py tests/test_offer_scoring_assess.py tests/test_offer_profile_matcher.py -q` 190 passed
- 2026-11-17T20:39Z | antigravity | step 3 | started
- 2026-11-17T20:39Z | antigravity | step 3 | done | `wc -l` 184/184/147, `flake8` exit 0, `MANUAL CHECK OK`, `190 passed in 0.59s`
- 2026-11-17T20:39Z | antigravity | plan | done | all 6 DoD items pass

## Notes
- Convention files read: `AGENTS.md`, `GEMINI.md`, `CLAUDE.md` (no `docs/adrs/` present in repository).
- Baseline (2026-11-17T20:37Z): `flake8 --config ../.flake8 .` exit 0; `pytest tests/test_domain_relevance.py tests/test_offer_scoring_role_gate.py tests/test_hybrid_scoring.py tests/test_offer_scoring_assess.py tests/test_offer_profile_matcher.py -q` -> 176 passed.
