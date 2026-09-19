---
task: regenerate-edit-tailored-cv
status: done
created: 2026-09-19
completed: 2026-09-19
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Ajouter la régénération et l'édition de CV adaptés + Alignement du titre de poste

## Context
- Existing code checked:
  - `backend/app/llm/prompts/cv/tailor_prompt.md`: instructions de prompt pour l'adaptation de CV.
  - `backend/app/routers/resumes.py`: API `PUT /resumes/{id}` (`update_resume`) supporte déjà `content`, `template`, `with_photo`.
  - `frontend/src/lib/api.ts`: `resumeApi.update` et `resumeApi.generate` sont déjà implémentés.
  - `frontend/src/components/resumes/ResumePreviewModal.tsx`: aperçu PDF du CV avec switch de template.
  - `frontend/src/components/resumes/ResumeCard.tsx`: carte affichant les métadonnées du CV avec bouton de téléchargement et suppression.
  - `frontend/src/app/resumes/page.tsx`: page de gestion des CVs.
- Fresh info looked up: n/a
- Git status checked: branches et fichiers audités.

## Simpler Alternative Considered
- Intégrer directement un mode / onglet d'édition interactif dans `ResumePreviewModal` pour modifier le titre, le résumé, les puces d'expérience et les compétences avec bouton "Sauvegarder", et un bouton "Régénérer" sur `ResumeCard` et dans le header de `ResumePreviewModal`.

## Surgical Scope
- **Files touched**:
  - `backend/app/llm/prompts/cv/tailor_prompt.md`
  - `frontend/src/components/resumes/ResumeCard.tsx`
  - `frontend/src/components/resumes/ResumePreviewModal.tsx`
  - `frontend/src/app/resumes/page.tsx`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**: `ResumePreviewModal`, `ResumeCard`, `ResumesContent`

## Definition of Done
- [x] Build passes: `cd frontend && npm run build`
- [x] Prompt updated: `backend/app/llm/prompts/cv/tailor_prompt.md` enjoint formellement le LLM d'utiliser l'intitulé exact de l'offre (dégenré si besoin, ex: "Ingénieur IA") sans ajouts de sous-titres fantaisistes
- [x] Bouton Régénérer: disponible sur `ResumeCard` et dans `ResumePreviewModal`, permettant de lancer une nouvelle génération à partir de la même offre
- [x] Éditeur interactif: présent dans `ResumePreviewModal` pour modifier le titre visé, le résumé, les compétences et les puces d'expérience, avec sauvegarde persistée via `resumeApi.update`
- [x] Type check: vérifié avec succès par Next.js build
- [x] Manual check: flux de régénération et d'édition prêts

## Steps
- [x] Step 1: Mettre à jour `backend/app/llm/prompts/cv/tailor_prompt.md` pour contraindre `target_role_title` à l'intitulé strict de l'offre
- [x] Step 2: Ajouter l'action de régénération dans `frontend/src/components/resumes/ResumeCard.tsx` et `frontend/src/app/resumes/page.tsx`
- [x] Step 3: Enrichir `frontend/src/components/resumes/ResumePreviewModal.tsx` avec un mode édition (champs éditables pour le titre, le résumé, les puces d'expérience, compétences) et sauvegarde via `resumeApi.update`
- [x] Step 4: Vérifier la compilation frontend (`npm run build`)
- [x] Step 5 (teardown): Valider l'absence de code orphelin ou régressions

## Code Review
- Dead code removed: yes
- Build status: pass (Next.js 15.2.4 compiled 18/18 pages)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- Step 1: Directive stricte ajoutée dans `backend/app/llm/prompts/cv/tailor_prompt.md` interdisant l'anglicisation et les ajouts de spécialités dans `target_role_title`.
- Step 2: Ajout des props `onRegenerate` et `onEdit` avec boutons interactifs dans `ResumeCard.tsx`.
- Step 3: Implémentation du double onglet "Aperçu PDF / Éditer le contenu" dans `ResumePreviewModal.tsx` avec édition réactive du titre, résumé, puces d'expériences et compétences.
- Step 4: Connexion des handlers `handleRegenerateResume` et `handleUpdateResumeContent` dans `page.tsx`.
- Step 5: `npm run build` exécuté et validé sans erreur. `pytest tests/test_cv_tailor.py tests/test_cv_guards.py` validé (5 tests passés).

## Notes
- Aucune régression détectée.
