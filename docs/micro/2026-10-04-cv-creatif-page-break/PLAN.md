---
title: Correction du saut de page après l'intro sur le modèle de CV créatif
status: done
---

## User intent
Sur le modèle de CV créatif (`creatif`), un saut de page indésirable poussait la section Expérience professionnelle sur la page 2, laissant la page 1 quasi-vide après le paragraphe d'introduction. L'objectif était de supprimer ce saut de page pour que les premières expériences s'enchaînent naturellement sous le résumé sur la page 1.

## Root Cause Analysis
1. Dans `backend/app/templates/cv/creatif.html`, `.cr-sec` est défini avec `display: grid; grid-template-columns: 31mm 1fr;`.
2. Pour la section Expériences (`section.cr-sec`), le conteneur grid ne contenait que deux enfants directs :
   - Le titre `h2.cr-title` (colonne 1).
   - Le conteneur complet `div.cr-timeline` (colonne 2), qui regroupe la totalité des expériences du candidat.
3. Le moteur de rendu Chromium (utilisé via Playwright) traite les éléments de grille (`grid items`) comme des blocs monolithiques difficiles à fragmenter sur une seule rangée lorsque le contenu global (`div.cr-timeline`) dépasse l'espace restant sur la page 1.
4. Chromium constatait que la rangée contenant `div.cr-timeline` ne rentrait pas sur la page 1 (déjà occupée par le bandeau d'en-tête et le résumé) et repoussait l'intégralité de la section sur la page 2.

## Surgical Scope
1. `backend/app/templates/cv/creatif.html`:
   - Appliquer `display: contents` sur `.cr-timeline` pour décomposer la liste d'expériences en cellules de grille directes (`.cr-job` sur `grid-column: 2`).
   - Assigner explicitement `grid-column: 1; grid-row: 1;` sur le titre de la section expérience (`.cr-sec:has(.cr-timeline) .cr-title`).
   - Déplacer la bordure de frise verticale sur chaque `.cr-job` (`border-left: 2px solid var(--accent-line)` avec puce centrée).
   - Ajuster `line-height: 1.2` sur `.cr-title` pour préserver l'intégrité de l'extraction textuelle ATS (`test_ats_standard_section_titles_extracted`).
2. `backend/tests/test_cv_pdf_renderer.py`:
   - Ajouter `test_creatif_experiences_start_on_page_one_after_summary` pour garantir la non-régression.
   - Nettoyer les imports en tête de fichier pour satisfaire Flake8.
3. `docs/micro/2026-10-04-cv-creatif-page-break/PLAN.md`: Documentation complète de l'intervention.
4. `docs/micro/DAILY_LOG-2026-10-04.md`: Journalisation de la tâche.

## Steps
- [x] 1. Analyser et reproduire le saut de page avec Playwright et pdfplumber (page 1 isolant le résumé, expériences repoussées en page 2).
- [x] 2. Adapter le CSS de `backend/app/templates/cv/creatif.html` (`display: contents` sur `.cr-timeline`, placement de grille par poste).
- [x] 3. Valider avec la suite de tests de rendu (`test_cv_templates.py`, `test_cv_pdf_renderer.py`).
- [x] 4. Ajouter le test de non-régression `test_creatif_experiences_start_on_page_one_after_summary`.
- [x] 5. Mettre à jour `DAILY_LOG-2026-10-04.md` et passer le plan en `done`.

## Definition of Done
- [x] La page 1 accueille le bandeau, le paragraphe d'introduction et les premières expériences sans saut de page prématuré.
- [x] Tous les tests de rendu PDF et d'extraction ATS passent au vert (`pytest tests/test_cv_pdf_renderer.py` - 121 passés).
- [x] Flake8 0 erreur sur les fichiers impactés.

## Code Review
- **Fragmentation paged-media Chromium :** L'usage de `display: contents` sur `.cr-timeline` résout élégamment le blocage de fragmentation de Blink en évitant d'encapsuler toutes les expériences dans un unique grid-item monolithique.
- **Préservation ATS :** L'ajustement du `line-height` du titre évite tout entrelacement horizontal lors du balayage de coordonnées par `pdfplumber`.

## Execution Log
- 22:53 : Validation du lancement micro-dev avec l'utilisateur.
- 22:54 : Reproduction exacte du saut de page (pages: 3, P1 quasi-vide après l'intro, P2 débutant sur les expériences).
- 22:56 : Diagnostic du blocage de fragmentation de grille CSS dans Chromium Blink.
- 22:58 : Implémentation de `display: contents` sur `.cr-timeline`, placement direct des `.cr-job` et ajustement du line-height des titres.
- 23:00 : Validation locale complète (121 tests passés au vert, flake8 0 warning).
