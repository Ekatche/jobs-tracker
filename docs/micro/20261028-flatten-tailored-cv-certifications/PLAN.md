---
task: Aplatir les certifications en chaînes dans TailoredCVSchema lors de la génération de CV
description: Erreur de validation Pydantic TailoredCVSchema certifications Input should be a valid string input_type=dict — ajout d'un field_validator(mode="before") sur TailoredCVSchema.certifications dans backend/app/models.py pour convertir les objets CandidateCertification (name, issuer, year, topics) en chaînes formatées sans doublon d'organisme/année, et précision du format de chaîne dans backend/app/llm/prompts/cv/tailor_prompt.md
status: done
created: 2026-10-28
---

# Aplatir les certifications en chaînes dans TailoredCVSchema

## Context
- Existing code checked:
  - `backend/app/models.py:554-559` : `CandidateCertification` stocke chaque certification du profil sous forme de dict `{"name": str, "issuer": str, "year": Optional[str], "topics": List[str]}`.
  - `backend/app/models.py:750-758` : `TailoredCVSchema.certifications` attend `List[str]` sans validateur de pré-normalisation.
  - `backend/app/services/cv_tailor.py:79-93` : `load_tailor_prompt` sérialise le profil candidat brut dans `{candidate_profile}` (où `certifications` est une liste de dicts). Le LLM recopie parfois ces dicts tels quels dans `certifications` de sa réponse JSON, provoquant un `ValidationError` (`4 validation errors for TailoredCVSchema certifications.N Input should be a valid string ... input_type=dict`) et une HTTP 422 dans `backend/app/routers/resumes.py:170`.
  - `backend/app/templates/cv/*.html` : les 4 templates HTML itèrent sur `cv.certifications` et affichent directement `{{ cert }}` comme chaîne.
- Fresh info looked up: n/a — Pydantic v2 `@field_validator("certifications", mode="before")` déjà utilisé dans `backend/app/models.py` (`CandidateProject.clean_context`).
- Git status checked: clean (`main` à jour avec `origin/main`, aucun élément à archiver lors du sweep).

## Simpler Alternative Considered
- Modifier uniquement la consigne dans `tailor_prompt.md` : insuffisant, un LLM en mode `json_object` peut toujours recopier la structure d'entrée `{name, issuer, year, topics}` présente dans `{candidate_profile}`. Le validateur Pydantic `mode="before"` garantit de façon déterministe qu'aucun dict de certification ne fait échouer la validation.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/llm/prompts/cv/tailor_prompt.md`
  - `backend/tests/test_cv_tailor.py`
- **Files NOT touched**:
  - `backend/app/services/cv_tailor.py`
  - `backend/app/services/cv_guards.py`
  - `backend/app/services/cv_templates.py`
  - `backend/app/routers/resumes.py`
  - `backend/app/templates/cv/*.html`
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `TailoredCVSchema` in `backend/app/models.py` (ajout du validateur `normalize_certifications` et du helper `_format_certification_item`)

## Definition of Done
- [x] Build passes: `cd backend && uv run python -m py_compile app/models.py tests/test_cv_tailor.py`
- [x] Tests pass: `cd backend && uv run pytest tests/test_cv_tailor.py -v`
- [x] Deterministic dict-coercion check: `cd backend && uv run python -c "from app.models import TailoredCVSchema; cv = TailoredCVSchema(target_role_title='Data Scientist', professional_summary='Résumé', certifications=[{'name': 'Microsoft Certified: Azure Data Scientist', 'issuer': 'Microsoft', 'year': None, 'topics': []}, {'name': 'MLOps — Machine Learning Operations', 'issuer': 'Coursera', 'year': '2024', 'topics': []}, {'name': 'Expertise Big Data — 2021', 'issuer': '', 'year': '2021', 'topics': []}]); assert cv.certifications == ['Microsoft Certified: Azure Data Scientist', 'MLOps — Machine Learning Operations — Coursera (2024)', 'Expertise Big Data — 2021'], cv.certifications"`
- [x] No dead code: n/a — aucun symbole remplacé
- [x] Type check: n/a — pas de mypy configuré dans le projet
- [x] Manual check: n/a — couvert par les tests unitaires et la vérification déterministe

## Steps
- [x] Step 1: Ajouter `_format_certification_item` et `@field_validator("certifications", mode="before")` sur `TailoredCVSchema` dans `backend/app/models.py` pour convertir tout dict (`name`/`title`, `issuer`/`organization`, `year`/`date`) en chaîne propre sans dupliquer l'organisme ni l'année s'ils figurent déjà dans `name`, et filtrer les entrées vides.
- [x] Step 2: Préciser dans `backend/app/llm/prompts/cv/tailor_prompt.md` (directive 8 et schéma JSON) que chaque élément de `certifications` doit être une chaîne de caractères unique (et non un objet JSON).
- [x] Step 3: Ajouter un test unitaire dans `backend/tests/test_cv_tailor.py` vérifiant que `TailoredCVSchema` et `generate_tailored_cv_content` acceptent et aplatissent les certifications renvoyées sous forme de dicts par le LLM.
- [x] Step 4 (teardown): Vérifier qu'aucun code mort n'a été introduit et exécuter la suite de tests `tests/test_cv_tailor.py` et `tests/test_resumes_api.py`.

## Code Review
- Dead code removed: n/a — no symbols replaced
- Build status: pass
- Type errors: none
- Unintended side effects: none — existing string certifications pass through trimmed, dict items are cleanly formatted
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-10-28T08:14Z | antigravity | step 1 | started
- 2026-10-28T08:14Z | antigravity | step 1 | done | `py_compile app/models.py` exit 0, deterministic dict-coercion check OK
- 2026-10-28T08:14Z | antigravity | step 2 | started
- 2026-10-28T08:15Z | antigravity | step 2 | done | `pytest tests/test_cv_tailor.py -q` 28 passed
- 2026-10-28T08:15Z | antigravity | step 3 | started
- 2026-10-28T08:16Z | antigravity | step 3 | done | `pytest tests/test_cv_tailor.py -v` 29 passed
- 2026-10-28T08:16Z | antigravity | step 4 | started
- 2026-10-28T08:16Z | antigravity | step 4 | done | `pytest tests/test_cv_tailor.py tests/test_resumes_api.py -v` 57 passed, 0 dead code
- 2026-10-28T08:16Z | antigravity | plan | done | all DoD items pass

## Notes
- Conventions read: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`.
- Preflight baseline: `py_compile` exit 0, `pytest tests/test_cv_tailor.py -q` 28 passed, deterministic dict-coercion check fails as expected with `ValidationError: 1 validation error for TailoredCVSchema certifications.0 Input should be a valid string`.

