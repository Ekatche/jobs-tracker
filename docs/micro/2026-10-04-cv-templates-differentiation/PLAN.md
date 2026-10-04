---
title: Différencier Exécutif minimaliste et Créatif, compétences de Sidebar élégance
status: done
---

## User intent
- Exécutif minimaliste et Créatif se ressemblent (même structure une colonne, même pied en grille 3 colonnes). Formation/Langues/Intérêts paraissent alignés à droite (grille 3 colonnes). Les différencier ; Créatif doit différer par la FORME, pas seulement la couleur.
- Sidebar élégance : compétences en pastilles mal contourées, trop de place, espacement irrégulier (les « · » restent seuls en fin de ligne).

## Contraintes ATS (spec docs/superpowers/specs/2026-10-02-cv-modeles-visuels-design.md section 1)
- « · » visible entre compétences (test `test_ats_skills_separated_in_text` : « Python · FastAPI »), jamais de texte masqué.
- Nom en première ligne, titres de section standard (SECTION_TITLES), pas de texte pivoté, pas d'emoji, monogramme en canvas.
- Tests : backend/tests/test_cv_templates.py, backend/tests/test_cv_pdf_renderer.py (ORPHAN_TITLE_LAYOUTS calibré par modèle).

## Design proposé
- Exécutif : en-tête centré, titres majuscules + trait fin pleine largeur, colonne de dates à gauche (réutilisée pour la formation), compétences en texte (une ligne par catégorie), Formation/Langues/Intérêts en sections empilées à gauche.
- Créatif (forme) : bandeau d'en-tête pleine largeur à bord biseauté (clip-path) avec monogramme/photo à cheval ; titres de section dans une gouttière gauche (grille titre | contenu) ; expériences en frise verticale (trait + nœuds, dates en badge) ; compétences en cartes arrondies par catégorie avec pastilles teintées ; langues avec barre de niveau décorative (texte du niveau conservé) ; projets en cartes à bordure d'accent.
- Sidebar : compétences en texte continu, « · » en couleur d'accent, plus de pastilles.

## Rendu de revue
Maquette HTML (proposition, pas les vrais templates) : https://claude.ai/artifact/2iP8kh93oGkWgFfG9SSNAq, source scratchpad/cv-maquettes.html.
Script : scratchpad/render_cv.py (PNG via pymupdf), sortie scratchpad/cvshots/.

## Steps
- [x] 1. Validation design par l'utilisateur (2026-10-04, maquette approuvée)
- [x] 2. Sidebar compétences
- [x] 3. Exécutif (nom sans majuscules forcées : test ATS « Jean Dupont » en 1re ligne)
- [x] 4. Créatif (biais et frise en fonds dégradés : clip-path/position cassaient l'ordre d'extraction ; .cr-title break-after:auto car un h2 en grille repoussait toute la rangée en page 2)
- [x] 5. Tests ATS + rendus avant/après (121 tests CV verts ; spec et hint frontend à jour ; rendus scratchpad/cvshots/{before,after}/*_sheet.png)
- [x] 6. Suite backend : tests CV 121/121, offres 40/40 ; arrêt -x sur test_create_and_get_application_with_offer_id (fixture registered_user 403 à l'inscription, sans lien avec les CV). Push + déploiement VPS demandés par l'utilisateur le 2026-10-04.
