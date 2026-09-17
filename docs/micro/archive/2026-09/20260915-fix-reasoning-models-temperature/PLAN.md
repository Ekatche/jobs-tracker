---
task: Fixer l'incompatibilité de temperature et max_tokens pour les modèles reasoning dans cover_letter_crew
status: completed
created: 2026-09-15
completed: 2026-09-15
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Fixer l'incompatibilité de temperature pour les modèles reasoning OpenAI

## Context
- Existing code checked:
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py` (`_call_analyst`, `_call_writer`, `_call_reviser`)
  - `backend/job_trackers/src/job_trackers/letter_llm.py` (`DEFAULT_MODELS`, `ROLE_TEMPERATURES`)
  - `backend/scripts/letter_bakeoff.py` (qui a déjà résolu ce problème avec `_build_completion_kwargs`)
  - `backend/tests/test_cover_letter_crew.py`
- Fresh info looked up:
  - Erreur rapportée en prod : `litellm.BadRequestError: OpenAIException - Unsupported value: 'temperature' does not support 0.7 with this model. Only the default (1) value is supported.`
  - Les modèles OpenAI `gpt-5.*`, `o1`, `o3` ne supportent pas de paramètre `temperature` personnalisé (seul le défaut 1 est accepté) et consomment des tokens de raisonnement sur le quota de completion.
- Git status checked: clean/understood

## Simpler Alternative Considered
- Passer `temperature=1` : rejeté car `gpt-5.*` rejette tout passage explicite de temperature s'il est envoyé selon les versions de l'API OpenAI, le plus sûr est d'omettre le kwarg `temperature` pour les préfixes de raisonnement (`gpt-5`, `o1`, `o3`, `gpt-o`), exactement comme testé et validé lors du bake-off.

## Surgical Scope
- **Files touched**:
  - `backend/job_trackers/src/job_trackers/letter_llm.py` (définir `build_completion_kwargs` et helper pour les modèles reasoning)
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py` (utiliser `build_completion_kwargs` pour analyst, writer, critic, reviser et augmenter `max_completion_tokens` pour writer/reviser)
  - `backend/tests/test_cover_letter_crew.py` (adapter le test de temperature pour les modèles standard vs reasoning)
  - `backend/tests/test_letter_llm.py` (test unitaire de `build_completion_kwargs`)
- **Files NOT touched**:
  - All other files (`applications.py`, `letter_guards.py`, etc.)
- **Symbols replaced**: none
- **Symbols extended**:
  - `build_completion_kwargs` dans `letter_llm.py`

## Definition of Done
- [x] Build passes: `uv run python -m py_compile job_trackers/src/job_trackers/cover_letter_crew.py job_trackers/src/job_trackers/letter_llm.py`
- [x] Tests pass: `uv run pytest tests/test_cover_letter_crew.py tests/test_letter_llm.py`
- [x] No dead code: 0 orphelins
- [x] Type check: n/a
- [x] Manual check: simulation d'un appel `_call_writer` en dry-run confirmant l'absence de `temperature` pour `gpt-5.6-terra` et sa présence pour un modèle standard (ex. `mistral`).
- [x] Live check: appel réel à `_call_writer` avec `gpt-5.6-terra` validé (1954 caractères générés, 0 erreur 400).

## Steps
- [x] Step 1: Ajouter la fonction `build_completion_kwargs(model: str, temperature: float, extra: dict | None = None) -> dict` dans `backend/job_trackers/src/job_trackers/letter_llm.py`.
- [x] Step 2: Utiliser `build_completion_kwargs` dans `backend/job_trackers/src/job_trackers/cover_letter_crew.py` pour `_call_analyst`, `_call_writer`, `_call_critic`, `_call_reviser`, et ajuster `max_completion_tokens=2500` pour writer/reviser pour absorber les tokens de raisonnement.
- [x] Step 3: Mettre à jour `backend/tests/test_cover_letter_crew.py` pour vérifier le comportement de `build_completion_kwargs` (omission pour reasoning, transmission pour modèles standard) et `backend/tests/test_letter_llm.py`.
- [x] Step 4: Exécuter tous les tests unitaires pour valider la non-régression (32/32 passés).
- [x] Step 5 (teardown): Mettre à jour `docs/micro/DAILY_LOG-2026-09-15.md` et marquer le plan comme `completed`.

## Code Review
- Dead code removed: yes
- Build status: pass (py_compile OK, 32/32 tests passés, live run OK)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 13:40 Step 1: `build_completion_kwargs` ajouté dans `letter_llm.py`.
- 13:45 Step 2: `cover_letter_crew.py` mis à jour (`_call_analyst`, `_call_writer`, `_call_critic`, `_call_reviser`), `max_completion_tokens` rehaussé à 2500 pour writer et reviser.
- 13:47 Step 3: Tests unitaires mis à jour dans `test_cover_letter_crew.py` et `test_letter_llm.py`.
- 13:48 Step 4: 32/32 tests unitaires passés en 2.97s.
- 13:51 Live verification: appel `_call_writer` avec `gpt-5.6-terra` exécuté avec succès (lettre de 1954 caractères générée sans erreur 400).
- 13:52 Step 5: `DAILY_LOG-2026-09-15.md` mis à jour et plan clôturé.

## Notes
- Alignement du code de production avec le correctif déjà éprouvé dans le bake-off.
