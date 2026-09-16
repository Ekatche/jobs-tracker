---
task: Enrichir le prompt de cover letter et ses garde-fous avec les meilleures pratiques de career-ops
status: completed
created: 2026-09-15
completed: 2026-09-15
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Amélioration du prompt de cover letter (inspirations career-ops)

## Context
- Existing code checked:
  - Prompt: `backend/app/llm/prompts/cover_letter/02_style.md`
  - Guards & Rules: `backend/app/services/letter_guards.py` (`BANNED_LEXICON`, `LETTER_RULES`)
  - Tests: `backend/tests/test_cover_letter_prompts.py`, `backend/tests/test_letter_guards.py`
- Fresh info looked up:
  - Analyse du mode `modes/cover.md` de `career-ops-hq/career-ops` : règles de voix active stricte, "concrete over abstract", "opening move" opérationnel, auto-test d'anti-généricité, extension du lexique interdit.
- Git status checked: clean (branche `fix/profile-multi-sources`, commit `1cc0db9`)

## Simpler Alternative Considered
- Modifier uniquement `02_style.md` sans aligner `BANNED_LEXICON` dans `letter_guards.py` : rejeté car `LETTER_RULES` et `letter_guards.py` sont la source de vérité pour le code et l'évaluation du réviseur ; les garde-fous doivent rester en stricte synchronisation avec le prompt du rédacteur.

## Surgical Scope
- **Files touched**:
  - `backend/app/llm/prompts/cover_letter/02_style.md`
  - `backend/app/services/letter_guards.py`
  - `backend/tests/test_letter_guards.py`
- **Files NOT touched**:
  - All other files (`cover_letter_crew.py`, `letter_llm.py`, `applications.py`, etc.)
- **Symbols replaced**: none
- **Symbols extended**:
  - `BANNED_LEXICON` dans `backend/app/services/letter_guards.py` (enrichi de nouveaux clichés interdits)

## Definition of Done
- [x] Build passes: `uv run python -m py_compile app/services/letter_guards.py`
- [x] Tests pass: `uv run pytest tests/test_cover_letter_prompts.py tests/test_letter_guards.py tests/test_cover_letter_crew.py`
- [x] No dead code: confirm all newly banned terms are covered by test assertions
- [x] Type check: n/a
- [x] Manual check: `uv run python -c "from app.services.letter_guards import LETTER_RULES; print(len(LETTER_RULES['banned_lexicon']))"`

## Steps
- [x] Step 1: Enrichir `BANNED_LEXICON` dans `backend/app/services/letter_guards.py` avec les clichés identifiés ("synergie", "actionable insights", "valeur ajoutée", "alignement stratégique", "opportunité unique", "profil idéal", "mettre à profit").
- [x] Step 2: Mettre à jour `backend/app/llm/prompts/cover_letter/02_style.md` en intégrant la voix active stricte, la règle "concrete over abstract", l'opening move et l'auto-évaluation.
- [x] Step 3: Ajouter des tests de non-régression dans `backend/tests/test_letter_guards.py`.
- [x] Step 4: Exécuter la suite de tests complète de validation.
- [x] Step 5 (teardown): Confirmer 0 orphelins et mettre à jour le journal quotidien `docs/micro/DAILY_LOG-2026-09-15.md`.

## Code Review
- Dead code removed: yes
- Build status: pass (py_compile 0 errors, 23/23 tests passés)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 11:21 Step 1: BANNED_LEXICON étendu avec 7 termes dans `letter_guards.py`.
- 11:22 Step 2: `02_style.md` mis à jour avec voix active, concrete over abstract, opening move, anti-généricité.
- 11:23 Step 3: Test `test_guards_new_career_ops_banned_lexicon_fails` ajouté dans `test_letter_guards.py`.
- 11:25 Step 4: Tests unitaires 23/23 passés en 3.34s. Interpolation validée.
- 11:27 Step 5: Teardown effectué, `DAILY_LOG-2026-09-15.md` renseigné.

## Notes
- Alignement strict entre le prompt de rédaction et le validateur de garde-fous en Python.
