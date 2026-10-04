---
title: Fixer la couleur du titre d'intitulé de l'offre en noir dans les modèles de CV adapté
status: done
---

## User intent
Dans la génération de CV adapté, lors du changement de palette de couleur (accent swatches : marine, bleu-vert, ardoise, sauge, bordeaux, graphite), l'intitulé de poste cible (ex: "Data Scientist", "Lead Tech Full Stack") doit rester noir (`var(--color-slate-900)`) au lieu de prendre la couleur d'accent du thème, pour préserver la sobriété et la lisibilité du titre professionnel principal.

## Surgical Scope
- `backend/app/templates/cv/classique.html`: remplacer `color: var(--accent);` par `color: var(--color-slate-900);` sur `.cl-role`.
- `backend/app/templates/cv/creatif.html`: remplacer `color: var(--accent);` par `color: var(--color-slate-900);` sur `.cr-role`.
- `backend/app/templates/cv/executive_minimalist.html`: remplacer `color: var(--accent);` par `color: var(--color-slate-900);` sur `.exec-title`.
- `backend/app/templates/cv/sidebar_elegance.html`: remplacer `color: var(--accent);` par `color: var(--color-slate-900);` sur `.main-role-title`.

## Steps
- [x] 1. Mettre à jour `.cl-role` dans `classique.html`.
- [x] 2. Mettre à jour `.cr-role` dans `creatif.html`.
- [x] 3. Mettre à jour `.exec-title` dans `executive_minimalist.html`.
- [x] 4. Mettre à jour `.main-role-title` dans `sidebar_elegance.html`.
- [x] 5. Lancer la suite de tests des templates CV (`pytest backend/tests/test_cv_templates.py`, `test_resumes_api.py`, `test_cv_pdf_renderer.py`).

## Definition of Done
- [x] Les tests passent sans échec (81 tests templates + 65 tests API/PDF renderer passés).
- [x] Dans les 4 templates, le titre professionnel cible s'affiche avec la couleur sobre/noire `var(--color-slate-900)`.

## Code Review
- **Design & Typography:** Le titre de poste cible reste noir et contrasté quelle que soit la couleur choisie par l'utilisateur pour les accents/puces/bordures.
- **ATS Compliance:** N'altère aucune balise sémantique ni extraction textuelle.
- Verdict: ✅ DONE

## Execution Log
- 19:13 : Création du plan micro-dev et journal quotidien.
- 19:14 : Remplacement de `color: var(--accent)` par `color: var(--color-slate-900)` sur les 4 templates HTML.
- 19:15 : Exécution des tests de régression backend (81 + 65 tests validés avec succès).
