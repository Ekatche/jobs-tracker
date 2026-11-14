---
task: Mettre à jour les modèles Gemini Flash obsolètes (2.5 / 3.7 → 3.8) et aligner les défauts LLM
description: Remplacer gemini-2.5-flash et gemini-3.7-flash par gemini-3.8-flash et gpt-5.6-terra dans pdf_job_offer.py, cv_parser.py, letter_bakeoff.py, test_resilience.py, test_letter_bakeoff.py, CAREER_OPS_INTEGRATION_PLAN.md et .env tout en conservant les modèles optimaux validés par benchmark (gpt-4o-mini, ministral-14b-2512)
status: done
created: 2026-11-14
---

# Mettre à jour les modèles Gemini Flash obsolètes (2.5 / 3.7 → 3.8) et aligner les défauts LLM

## Context
- Existing code checked: `backend/app/services/pdf_job_offer.py`, `backend/app/services/cv_parser.py`, `backend/scripts/letter_bakeoff.py`, `backend/tests/evaluation/test_resilience.py`, `backend/tests/test_letter_bakeoff.py`, `docs/CAREER_OPS_INTEGRATION_PLAN.md`, `.env` (lignes modèles uniquement).
- Fresh info looked up: Gemini 2.5 Flash et Gemini 3.7 Flash sont obsolètes/retirés au profit de `gemini-3.8-flash` (et `gemini-3.5-flash-lite` pour le palier léger). Les benchmarks existants du dépôt confirment que `openai/gpt-4o-mini` reste l'optimum qualité/coût pour `CRAWL_LLM_MODEL` (`docs/micro/archive/2026-09/20260916-crawl-llm-bakeoff/crawl-bakeoff-summary.md`, 75 % vs 69 %, 9x moins cher) et `DEFAULT_CV_PARSER_MODEL` avec `mistral/ministral-14b-2512` pour le VLM (`docs/cv-import.md`).
- Git status checked: clean (`main` à jour avec `origin/main`).

## Simpler Alternative Considered
none — request is already the minimal change (alignement des défauts et références obsolètes tout en conservant les modèles déjà validés par benchmark).

## Surgical Scope
- **Files touched**:
  - `backend/app/services/pdf_job_offer.py`
  - `backend/app/services/cv_parser.py`
  - `backend/scripts/letter_bakeoff.py`
  - `backend/tests/evaluation/test_resilience.py`
  - `backend/tests/test_letter_bakeoff.py`
  - `docs/CAREER_OPS_INTEGRATION_PLAN.md`
  - `.env`
- **Files NOT touched**:
  - `backend/app/services/usage_tracker.py` (conserve les tarifs historiques pour le calcul rétroactif des coûts)
  - `backend/job_crawler/crawler1.py`, `backend/app/services/role_normalizer.py` (conservent `openai/gpt-4o-mini` validé par benchmark)
  - `backend/scripts/crawl_bakeoff.py` (script historique de benchmark comparatif)
- **Symbols replaced** (→ to delete before done):
  - none
- **Symbols extended** (→ keep):
  - `_transcribe_scanned_pdf_with_vlm`
  - `_parse_cv_text`
  - `SIM_MODELS`
  - `SIM_CV_MODEL`
  - `FALLBACK_MODEL`

## Definition of Done
- [x] Build passes: `cd backend && .venv/bin/python -m py_compile app/services/pdf_job_offer.py app/services/cv_parser.py scripts/letter_bakeoff.py`
- [x] Tests pass: `cd backend && .venv/bin/pytest tests/test_pdf_offer_ingestion.py tests/evaluation/test_resilience.py tests/test_letter_bakeoff.py tests/test_cv_vlm_parser.py -q`
- [x] No dead code: `grep -rnE "gemini-2\.5-flash|gemini-3\.7-flash" backend/app/services/pdf_job_offer.py backend/app/services/cv_parser.py backend/scripts/letter_bakeoff.py backend/tests/evaluation/test_resilience.py backend/tests/test_letter_bakeoff.py ; test $? -eq 1`
- [x] Type check: n/a — Python backend module without mypy in CI
- [x] Manual check: `grep -E "^(EVALUATION_MODEL|INTERVIEW_PREP_MODEL|LETTER_MODEL_WRITER|LETTER_MODEL_REVISER)=" .env`

## Steps
- [x] Step 1: Mettre à jour `backend/app/services/pdf_job_offer.py` (`gemini/gemini-2.5-flash` → `gemini/gemini-3.8-flash`) et simplifier le déroutage Gemini dans `backend/app/services/cv_parser.py`.
- [x] Step 2: Mettre à jour `backend/scripts/letter_bakeoff.py`, `backend/tests/test_letter_bakeoff.py` (`SIM_CV_MODEL` → `gemini/gemini-3.8-flash`, `writer`/`reviser` → `openai/gpt-5.6-terra`) et `backend/tests/evaluation/test_resilience.py` (`FALLBACK_MODEL` → `gemini/gemini-3.5-flash-lite`).
- [x] Step 3: Aligner `.env` (`EVALUATION_MODEL`, `INTERVIEW_PREP_MODEL`, `LETTER_MODEL_WRITER`, `LETTER_MODEL_REVISER`) et mettre à jour `docs/CAREER_OPS_INTEGRATION_PLAN.md`.
- [x] Step 4 (teardown): Vérifier qu'aucune référence obsolète (`gemini-2.5-flash`, `gemini-3.7-flash`) ne subsiste dans le périmètre ciblé et valider tous les critères de la Definition of Done.

## Code Review
- Dead code removed: yes (0 occurrences of `gemini-2.5-flash` or `gemini-3.7-flash` in surgical scope, including `PRICES_USD_PER_M` in `letter_bakeoff.py:77`)
- Build status: pass (`py_compile` exit 0)
- Type errors: n/a (Python backend module without mypy in CI)
- Unintended side effects: none (`git diff` reviewed line by line; `usage_tracker.py` historical pricing and benchmark-validated `gpt-4o-mini` / `ministral-14b-2512` preserved)
- Security surface touched: no (only `.env` model selection keys modified, zero secrets exposed)
- Verdict: ✅ DONE

## Execution Log
- 2026-11-14T10:39Z | antigravity | step 1 | started
- 2026-11-14T10:40Z | antigravity | step 1 | done | `pytest tests/test_pdf_offer_ingestion.py tests/test_cv_vlm_parser.py -q` 15 passed exit 0
- 2026-11-14T10:40Z | antigravity | step 2 | started
- 2026-11-14T10:40Z | antigravity | step 2 | done | `pytest tests/test_letter_bakeoff.py tests/evaluation/test_resilience.py -q` 9 passed exit 0
- 2026-11-14T10:40Z | antigravity | step 3 | started
- 2026-11-14T10:41Z | antigravity | step 3 | done | `.env` model lines and `CAREER_OPS_INTEGRATION_PLAN.md` verified via grep
- 2026-11-14T10:41Z | antigravity | step 4 | started
- 2026-11-14T10:41Z | antigravity | step 4 | done | all DoD checks verified fresh (`py_compile` exit 0, 24 passed, 0 dead references)
- 2026-11-14T10:41Z | antigravity | closeout | done | diff reviewed line-by-line, `status: done`

## Notes
- Preflight baseline (2026-11-14T10:38Z): `py_compile` exit 0, `pytest tests/test_pdf_offer_ingestion.py tests/evaluation/test_resilience.py tests/test_letter_bakeoff.py tests/test_cv_vlm_parser.py -q` 24 passed in 2.84s; `.env` contenait les anciens défauts (`gemini-3.7-flash` / `gpt-6.1-sol`); `No dead code` détectait 6 occurrences pré-migration (dont `letter_bakeoff.py:77` retirée via Option A). Convention files read: `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `.cursorrules`.
