---
task: Cumulative career seniority calculation and prompt injection for tailored CV
description: Calculer l'ancienneté cumulée non-chevauchante (_cumulative_career_years), injecter {career_seniority_phrase} dans tailor_prompt.md et valider par garde anti-surévaluation
status: done
created: 2026-10-26
---

# Cumulative Career Seniority Calculation and Prompt Injection

## Context
- Existing code checked:
  - `backend/app/services/cv_tailor.py:113-130`: `_career_years` fait `(max(ends) - min(starts)) / 12`, calculant un empan global avec trous plutôt que la durée de travail réelle.
  - `backend/app/llm/prompts/cv/tailor_prompt.md:39`: directive 3 figeait « avec une expérience dans », sans mentionner les années d'expérience même pour des profils confirmés/seniors. Cas utilisateur réel : 8 ans d'expérience d'éducatrice, résumé généré vague, sans mention des 8 ans.
  - `backend/app/services/cv_guards.py`: vérifie entreprises, compétences et diplômes, mais ne vérifiait pas les années d'expérience déclarées dans l'accroche.
- Fresh info looked up: n/a
- Git status checked: propre sur les fichiers ciblés.

## Simpler Alternative Considered
- Laisser le LLM déduire librement les années d'expérience depuis la liste des expériences : rejeté, les LLM hallucinent fréquemment les calculs de dates et d'ancienneté ou gonflent les années.
- Écrire en dur les années dans le résumé post-génération : rejeté, l'accroche doit s'intégrer de manière fluide dans les 3 phrases et la syntaxe générale.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/cv_templates.py` (helper `_cumulative_career_years`)
  - `backend/app/services/cv_tailor.py` (`format_career_seniority_phrase`, `load_tailor_prompt`, `compute_page_budget`)
  - `backend/app/llm/prompts/cv/tailor_prompt.md` (directive 3 `{career_seniority_phrase}`)
  - `backend/app/services/cv_guards.py` (garde anti-surévaluation des années dans `verify_cv_honesty`)
  - `backend/tests/test_cv_tailor.py`
  - `backend/tests/test_cv_guards.py`
- **Files NOT touched**:
  - `backend/app/routers/resumes.py`
  - `backend/app/services/cv_pdf_renderer.py`
- **Symbols replaced**: `_career_years` (cv_tailor.py) supprimé, remplacé par `_cumulative_career_years`
- **Symbols extended**:
  - `_cumulative_career_years` in `cv_templates.py`
  - `format_career_seniority_phrase` in `cv_tailor.py`
  - `load_tailor_prompt`, `compute_page_budget` in `cv_tailor.py`
  - `verify_cv_honesty` in `cv_guards.py` (`SENIORITY_CLAIM_RE`)

## Definition of Done
- [x] Build passes: `cd backend && uv run python -m py_compile app/services/cv_templates.py app/services/cv_tailor.py app/services/cv_guards.py`
- [x] Tests pass: `cd backend && uv run pytest tests/test_cv_tailor.py tests/test_cv_guards.py -v`
- [x] Full suite passes: `cd backend && uv run pytest tests` (1418 passed)
- [x] No dead code: `_career_years` supprimé, imports `date`, `_date_key`, `_end_key` retirés de `cv_tailor.py`
- [x] Deterministic check: `cd backend && uv run python -c "from app.services.cv_templates import _cumulative_career_years; from app.services.cv_tailor import format_career_seniority_phrase; yrs = _cumulative_career_years({'experiences': [{'start': '09/2018', 'end': '09/2026'}]}); assert yrs == 8.0, yrs; assert format_career_seniority_phrase(yrs) == \"avec 8 ans d'expérience dans\"; assert format_career_seniority_phrase(7.9) == \"avec 7 ans d'expérience dans\""`
- [x] Deployment: 495c09a sur `sentinel-vps`, `/docs` 200, ping MongoDB `ok` depuis le backend

## Steps
- [x] Step 1: Implémenter `_cumulative_career_years` dans `backend/app/services/cv_templates.py` et le brancher dans `compute_page_budget` (`backend/app/services/cv_tailor.py`).
- [x] Step 2: Mettre à jour `load_tailor_prompt` dans `cv_tailor.py` et `backend/app/llm/prompts/cv/tailor_prompt.md` avec `{career_seniority_phrase}`.
- [x] Step 3: Ajouter la garde anti-surévaluation des années dans `verify_cv_honesty` (`cv_guards.py`).
- [x] Step 4: Écrire les tests unitaires dans `backend/tests/test_cv_tailor.py` et `backend/tests/test_cv_guards.py`.
- [x] Step 5 (teardown): Exécuter la suite complète de tests backend.
- [x] Step 6: Déploiement sur le VPS.

## Code Review
- Dead code removed: yes (`_career_years`, 3 imports morts)
- Build status: passed
- Type errors: none
- Unintended side effects: `compute_page_budget` compte désormais les années réellement travaillées (chevauchements fusionnés, interruptions exclues) au lieu de l'empan premier poste – dernier poste. Un parcours avec de longues interruptions peut passer de 2 pages à 1 (`test_page_budget_ignores_career_gaps`).
- Security surface touched: no
- Verdict: ready

## Execution Log
- 2026-10-26T23:00Z | antigravity | step 1 | started
- 2026-10-26T23:01Z | antigravity | step 1 | done | `_cumulative_career_years` and `format_career_seniority_phrase` implemented in `cv_templates.py`, `_career_years` redirected in `cv_tailor.py`
- 2026-10-26T23:02Z | antigravity | step 2 | started
- 2026-10-26T23:02Z | antigravity | step 2 | done | `{career_seniority_phrase}` injected in `tailor_prompt.md` and passed from `load_tailor_prompt`
- 2026-10-26T23:02Z | antigravity | step 3 | started
- 2026-10-26T23:03Z | antigravity | step 3 | done | Seniority inflation check added in `verify_cv_honesty` (`cv_guards.py`)
- 2026-10-26T23:03Z | antigravity | step 4 | started
- 2026-10-26T23:05Z | antigravity | step 4 | done | Unit tests added in `test_cv_tailor.py` and `test_cv_guards.py` (35/35 passed)
- 2026-10-26T23:05Z | antigravity | step 5 | started
- 2026-10-26T23:05Z | antigravity | step 5 | done | Full CV subsystem test suite passed: 192 passed in 12.80s
- 2026-10-26T23:20Z | claude | review | done | arrondi par défaut (`round` gonflait 1,8 an en « 2 ans ») ; formulation déplacée dans `cv_tailor.py` ; garde stricte sur toutes les occurrences, « N+ ans » et « N years of experience » ; wrapper `_career_years` et imports morts retirés ; tests anonymisés ; `uv run pytest tests` = 1418 passed
- 2026-10-26T23:21Z | claude | step 6 | started | commit 495c09a poussé et tiré sur le VPS
- 2026-10-27T06:04Z | claude | step 6 | done | après l'incident réseau MongoDB (cf. plan 20261026-fix-parsed-cv-mobility-format), backend et base joignables, endpoints DB en 200

## Notes
- `_cumulative_career_years` fusionne les intervalles qui se chevauchent afin de ne pas double-compter les postes simultanés et de ne pas compter les périodes sans emploi comme de l'expérience.
- Arrondi par défaut partout : la phrase injectée dit « 7 ans » pour 7,9 ans, et la garde rejette toute valeur supérieure à `int(années cumulées)`. Une violation déclenche le second essai de génération, puis `CVHonestyError`.
- La garde lit les chiffres seulement : « huit ans d'expérience » écrit en toutes lettres n'est pas contrôlé.
