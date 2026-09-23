---
task: Lettres de motivation — style imité depuis de vraies lettres (writing_samples) + premier paragraphe sobre
status: done
created: 2026-09-23
---

# Style par exemples + accroche sobre

## Context
- Premier paragraphe prétentieux. Causes : vocabulaire « thèse/conviction » (01_fond, 02_style),
  exemple ✅ qui ouvre sur une maxime, règles d'accroche contradictoires entre 02 (situation vécue),
  03 critique (élément de l'offre) et 04 révision (missions).
- `writing_style` = description libre seulement. Ajout `writing_samples` = texte de vraies lettres du candidat.
- Stockage Mongo via `PUT /profile/candidate` (sources.manual, dict générique) : pas de migration.

## Décision
Injection directe des exemples (tronqués à 6000 caractères) dans le bloc style du writer et du reviser,
consigne « imite forme, jamais contenu ». Écarté : fiche de style extraite une fois par LLM
(nouvel appel + stockage + invalidation — plus de code pour gain incertain).

## Surgical Scope
- backend/app/models.py — champ `writing_samples`
- backend/app/services/profile/merge.py — propagation
- backend/job_trackers/src/job_trackers/cover_letter_crew.py — `_build_voice_style_block(voice_style, writing_samples)`, writer/reviser/pipeline, PROMPT_VERSION v4
- backend/app/llm/prompts/cover_letter/01_fond.md, 02_style.md, 03_critique.md, 04_revision.md
- backend/tests/test_cover_letter_crew.py, test_profile_merge.py
- frontend/src/types/coverLetter.ts, frontend/src/components/profile/CandidateProfileSection.tsx (formulaire d'édition seulement)

## Definition of Done
- [x] `cd backend && uv run --no-sync pytest tests/test_cover_letter_crew.py tests/test_cover_letter_prompts.py tests/test_letter_llm.py tests/test_profile_merge.py -q` (baseline 57 passed)
- [x] `cd frontend && npx tsc --noEmit` sans nouvelle erreur

## Steps
- [x] 1 backend champ + merge + test merge
- [x] 2 crew : bloc style avec exemples + test
- [x] 3 prompts : accroche commune, exemple sobre, vocabulaire adouci
- [x] 4 frontend : textarea « Lettres d'exemple »
- [x] 5 vérification

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none (frontend tsc 0 error)
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-09-23 | claude | baseline | 57 passed
- 2026-09-23 | claude | steps 1-5 | done | 61 passed (4 nouveaux tests), tsc 0 erreur, 3 prompts format() OK
- 2026-09-23 | antigravity | audit & polish | 66 passed (unit & crew tests), fixed patch target in test_cover_letter_trigger.py, added English docstrings/comments, updated daily log & plan.
