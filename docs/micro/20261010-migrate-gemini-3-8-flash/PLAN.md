---
task: Migrer toutes les occurrences de Gemini 3.7 Flash vers Gemini 3.8 Flash
description: Remplacer les références et valeurs par défaut gemini-3.7-flash par gemini-3.8-flash dans backend, tests, frontend et README — evaluator.py, interview_prep_service.py, test_offer_evaluation.py, ApplicationDetails.tsx, README.md
status: done
created: 2026-10-10
---

# Migrer toutes les occurrences de Gemini 3.7 Flash vers Gemini 3.8 Flash

## Context
- Existing code checked: `evaluator.py`, `interview_prep_service.py`, `test_offer_evaluation.py`, `ApplicationDetails.tsx`, `README.md`.
- Fresh info looked up: Google dépréciation de gemini-3.7-flash, alignement avec `gemini-3.8-flash` déjà standardisé dans `.env.example`, `docker-compose.yml`, `letter_llm.py`, `crew.py`, `cv_tailor.py`.
- Git status checked: clean (main branch up-to-date).

## Simpler Alternative Considered
none — request is already the minimal change (remplacement direct des constantes et mentions du modèle déprécié).

## Surgical Scope
- **Files touched**:
  - `backend/app/services/evaluation/evaluator.py`
  - `backend/app/services/interview_prep_service.py`
  - `backend/tests/test_offer_evaluation.py`
  - `frontend/src/components/applications/ApplicationDetails.tsx`
  - `README.md`
- **Files NOT touched**:
  - `backend/app/services/usage_tracker.py` (conserve le tarif historique de 3.7 pour les calculs rétroactifs des anciens tokens consommés, 3.8 est déjà présent)
  - `backend/app/services/cv_parser.py` (conserve la détection des anciens modèles gemini dans la liste des modèles à dérouter)
  - `backend/scripts/crawl_bakeoff.py` (conserve l'historique de benchmark comparatif de crawl)
  - archives sous `docs/`
- **Symbols replaced** (→ to delete before done):
  - `DEFAULT_EVALUATION_MODEL` fallback string `"gemini/gemini-3.7-flash"` → `"gemini/gemini-3.8-flash"`
  - `DEFAULT_INTERVIEW_MODEL` fallback string `"gemini/gemini-3.7-flash"` → `"gemini/gemini-3.8-flash"`
  - `PRIMARY_MODEL` string `"gemini/gemini-3.7-flash"` in `test_offer_evaluation.py` → `"gemini/gemini-3.8-flash"`
- **Symbols extended** (→ keep):
  - all others

## Definition of Done
- [x] Build passes: `cd frontend && npm run build`
- [x] Tests pass: `cd backend && uv run pytest tests/test_offer_evaluation.py -k test_scoring`
- [x] No dead code: `grep -rn "gemini-3.7-flash" backend/app/services/evaluation/ backend/app/services/interview_prep_service.py backend/tests/test_offer_evaluation.py frontend/src/components/applications/ApplicationDetails.tsx` returns 0 lines
- [x] Type check: `cd frontend && npx tsc --noEmit`
- [x] Manual check: `grep "Gemini 3.8 Flash" README.md frontend/src/components/applications/ApplicationDetails.tsx` returns matches in both files

## Steps
- [x] Step 1: Mettre à jour les modèles par défaut dans `backend/app/services/evaluation/evaluator.py` et `backend/app/services/interview_prep_service.py` vers `gemini/gemini-3.8-flash`.
- [x] Step 2: Mettre à jour `backend/tests/test_offer_evaluation.py` pour utiliser `gemini/gemini-3.8-flash` comme modèle principal et adapter `FALLBACK_MODEL` pour le test de bascule.
- [x] Step 3: Mettre à jour le badge de scoring IA dans `frontend/src/components/applications/ApplicationDetails.tsx` (`Gemini 3.8 Flash`).
- [x] Step 4: Mettre à jour la mention de Gemini 3.7 Flash dans `README.md` vers Gemini 3.8 Flash.
- [x] Step 5 (teardown): Vérifier qu'aucune référence active à `gemini-3.7-flash` ne persiste dans le code applicatif ciblé.

## Code Review
- Dead code removed: yes (0 occurrences of gemini-3.7-flash in surgical scope)
- Build status: pass (npm run build exit 0)
- Type errors: none (tsc --noEmit exit 0)
- Unintended side effects: none (diff reviewed line-by-line, perfectly surgical)
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-10-10T14:56Z | antigravity | step 1 | started
- 2026-10-10T14:57Z | antigravity | step 1 | done | `grep DEFAULT_EVALUATION_MODEL` and `DEFAULT_INTERVIEW_MODEL` show `gemini-3.8-flash`
- 2026-10-10T14:57Z | antigravity | step 2 | started
- 2026-10-10T14:58Z | antigravity | step 2 | done | `cd backend && uv run pytest tests/test_offer_evaluation.py -k test_scoring` 7 passed exit 0
- 2026-10-10T14:58Z | antigravity | step 3 | started
- 2026-10-10T14:58Z | antigravity | step 3 | done | `tsc --noEmit` exit 0, `grep` confirms `Gemini 3.8 Flash` in ApplicationDetails.tsx:439
- 2026-10-10T14:58Z | antigravity | step 4 | started
- 2026-10-10T14:59Z | antigravity | step 4 | done | `grep "Gemini 3.8 Flash" README.md` shows line 19 updated
- 2026-10-10T14:59Z | antigravity | step 5 | started
- 2026-10-10T15:00Z | antigravity | step 5 | done | `grep -rn "gemini-3.7-flash"` returned 0 occurrences exit 1
- 2026-10-10T15:00Z | antigravity | closeout | done | all DoD commands verified fresh, diff reviewed line-by-line

## Notes
- Preflight baseline (2026-10-10T14:55Z): `npm run build` exit 0, `tsc --noEmit` exit 0, `pytest -k test_scoring` 7 passed. Convention files read: AGENTS.md, GEMINI.md.
