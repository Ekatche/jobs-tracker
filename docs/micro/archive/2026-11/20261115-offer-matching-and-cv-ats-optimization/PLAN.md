---
title: Matching d'offres (faux-amis & compétences texte) + Somme exacte ATS & Optimisation génération CV
status: done
created: 2026-11-15
---

## User intent
1. Empêcher les faux positifs dans le matching d'offres (`offer_scoring`) sur le profil Lola Bart et tous les profils : notamment l'offre LinkedIn `4486393583` (`Chargé.e de projet en sciences sociales sur la rémission-guérison du VIH` @ INSERM), `Contrôleur de gestion sociale` et `Animateur prévention`, ainsi que l'absence de filtrage/pénalisation lorsque `competences_cles` est vide mais que la `description` est renseignée.
2. Rendre la somme du score ATS strictement transparente dans l'UI (`Somme : Adéquation offre (X/40) + Conformité ATS (Y/60) = Total/100`) et optimiser la génération de CV (`cv_tailor`, `ats_score`) : prise en compte de `website_url` en contact, détection des métriques/cadences métier (`~10 patients/semaine`), injection des mots-clés ATS de l'offre dans `tailor_prompt.md`, et protection des puces chiffrées dans `enforce_page_budget`.

## Surgical Scope
- `backend/app/services/offer_scoring/role_gate.py`
- `backend/app/services/offer_scoring/score.py`
- `backend/app/services/offer_scoring/assess.py`
- `backend/app/services/ats_score.py`
- `backend/app/services/cv_tailor.py`
- `backend/app/llm/prompts/cv/tailor_prompt.md`
- `frontend/src/components/resumes/ResumeAtsTab.tsx`
- `backend/tests/test_offer_scoring_role_gate.py`
- `backend/tests/test_offer_scoring_assess.py`
- `backend/tests/cv_guards/test_career_ops_guards.py`
- `backend/tests/cv_tailor/test_prompt.py`
- `backend/tests/cv_tailor/test_page_budget.py`

## Steps
- [x] 1. Corriger le filtrage métier (`role_gate.py`) et le score de compétences sur texte (`score.py`, `assess.py`) + tests unitaires.
- [x] 2. Somme exacte du score ATS (`ResumeAtsTab.tsx`, `ats_score.py`) et optimisation ATS de la génération de CV (`cv_tailor.py`, `tailor_prompt.md`) + tests unitaires.
- [x] 3. Vérification globale (`wc -l`, `flake8`, `pytest`, `npm run build`) et clôture du plan.

## Definition of Done
- [x] `cd backend && uv run flake8 --config ../.flake8 .` passe sans erreur.
- [x] `cd backend && uv run python -m pytest tests/test_offer_scoring_role_gate.py tests/test_hybrid_scoring.py tests/test_offer_scoring_assess.py tests/test_offer_profile_matcher.py tests/cv_guards/ tests/cv_tailor/ -q` passe intégralement.
- [x] `cd frontend && npm run build` passe sans erreur.
