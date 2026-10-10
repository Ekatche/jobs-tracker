---
task: Afficher les dates d'expérience des CV au format MM/AAAA au lieu de l'année seule
description: CV experience dates rendered as MM/YYYY instead of year only (temporal confusion); cv_templates.py _year_only/_with_years_only replaced by month-year formatter reusing _date_key; normalizes LLM formats 2023-02, 08/2025, sept. 2021; Jinja2 templates classique creatif executive_minimalist sidebar_elegance; pytest test_cv_templates
status: done
created: 2026-10-09
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Dates d'expérience des CV au format MM/AAAA

## Context
- Existing code checked: `backend/app/services/cv_templates.py:94-101` tronque chaque date à l'année (`_year_only`, `_with_years_only`), appliqué au rendu ligne 135. Introduit par 3d01fe0 (« dates affichées à l'année »), sans justification dans la spec 2026-10-02. Les 4 gabarits affichent `{{ exp.start_date }} – {{ exp.end_date or 'Présent' }}` tel quel. `_date_key` (même fichier, l.74) parse déjà (année, mois) depuis les formats LLM pour le tri. Le document stocké garde ses dates complètes (copie au rendu) : aucun CV à régénérer.
- Fresh info looked up: n/a — logique métier pure.
- Git status checked: sweep d'archive précédent non commité (2 plans déplacés + liens INDEX.md réécrits), hors périmètre ; seule une ligne est ajoutée à INDEX.md.

## Simpler Alternative Considered
Supprimer `_with_years_only` et afficher les dates brutes : un seul diff de suppression, mais formats hétérogènes sur un même CV (« 2023-02 », « 08/2025 », « sept. 2021 »). Rejeté : normaliser coûte 3 lignes en réutilisant `_date_key`. Format MM/AAAA choisi par l'utilisateur (tient mieux dans la colonne Executive de 24 mm).

## Surgical Scope
- **Files touched**: `backend/app/services/cv_templates.py`, `backend/tests/test_cv_templates.py`
- **Files NOT touched**: gabarits `backend/app/templates/cv/*.html`, `profile/periods.py`, frontend, tout le reste
- **Symbols replaced** (→ to delete before done): `_year_only`, `_with_years_only`, `test_experience_dates_show_years_only`
- **Symbols extended** (→ keep): `_date_key`, `render_cv_html`

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import app.services.cv_templates"`
- [x] Tests pass: `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -v`
- [x] Mois affiché sur les 4 modèles : le test paramétré vérifie `08/2025 – Présent`, `02/2023 – 06/2024`, `09/2019 – 03/2021` (formats `08/2025`, `2023-02`, `sept. 2019`/`mars 2021`)
- [x] Mois inconnu : année seule, `2019 – 2020` présent dans le test
- [x] Formats bruts absents du rendu : `2023-02` et `sept.` absents du HTML (assert dans le test)
- [x] No dead code: `grep -rn "_year_only\|_with_years_only\|show_years_only" backend/app backend/tests --include='*.py'` → 0 ligne
- [x] Type check: n/a — pas de type checker configuré pour le backend
- [x] Manual check: PDF rendu des 4 modèles en PNG (`generate_cv_pdf` + pymupdf), colonne de dates lisible sans chevauchement, en particulier Executive (24 mm)

## Steps
- [x] Step 1: Remplacer le test `test_experience_dates_show_years_only` par `test_experience_dates_show_month_and_year` (cas listés dans la DoD) ; le lancer seul, constater l'échec (RED).
- [x] Step 2: Dans `cv_templates.py`, remplacer `_year_only` par `_month_year` (s'appuie sur `_date_key` : mois connu → `MM/AAAA`, sinon `AAAA`, sans année → valeur inchangée) et `_with_years_only` par `_with_month_year` ; mettre à jour l'appel l.135.
- [x] Step 3: Lancer `test_cv_templates.py` et `test_cv_pdf_renderer.py` ; tout vert.
- [x] Step 4: Rendre les 4 modèles en PDF puis PNG dans le scratchpad, inspecter la colonne de dates (Executive en priorité).
- [x] Step 5 (teardown): Delete all dead code created by this plan. Run an orphan scan bounded to the replaced symbols. Confirm 0 orphans.

## Code Review
- Dead code removed: yes — `_year_only`, `_with_years_only`, `test_experience_dates_show_years_only` supprimés, 0 référence restante
- Build status: pass — `uv run python -c "import app.services.cv_templates"` exit 0
- Type errors: none (pas de type checker ; diagnostic IDE transitoire `_with_years_only` entre deux Edit, résolu par le second)
- Unintended side effects: none — tri inchangé (`_date_key` non modifié), document stocké intact (copie au rendu), `end_date` None reste « Présent » via le gabarit ; Executive affiche les dates sur 2 lignes (colonne 24 mm), lisible
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-09T15:55Z | claude-code | preflight | done | baseline: import exit 0 ; pytest test_cv_templates + test_cv_pdf_renderer 121 passed ; grep anciens symboles 5 lignes
- 2026-10-09T15:56Z | claude-code | step 1 | started
- 2026-10-09T15:56Z | claude-code | step 1 | done | RED attendu : `pytest -k month_and_year` FAIL sur `assert "08/2025 – Présent" in html`
- 2026-10-09T15:56Z | claude-code | step 2 | started
- 2026-10-09T15:57Z | claude-code | step 2 | done | import exit 0 ; `pytest -k month_and_year` 4 passed ; grep anciens symboles 0 ligne
- 2026-10-09T15:57Z | claude-code | step 3 | started
- 2026-10-09T15:58Z | claude-code | step 3 | done | `pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py` 121 passed
- 2026-10-09T15:58Z | claude-code | step 4 | started
- 2026-10-09T15:59Z | claude-code | step 4 | done | 4 PDF 1 page rendus (scratchpad/render_dates.py), PNG inspectés : 08/2025 – Présent, 02/2023 – 07/2025, 09/2021 – 01/2023, 2019 – 2021 lisibles ; Executive sur 2 lignes coupées après le tiret, sans chevauchement
- 2026-10-09T15:59Z | claude-code | step 5 | started
- 2026-10-09T15:59Z | claude-code | step 5 | done | grep anciens symboles (backend, frontend/src, docs/superpowers) 0 ligne ; callers_of(_with_years_only) not_found
- 2026-10-09T15:59Z | claude-code | close-out | done | DoD rejouée : import exit 0 ; 121 passed (Docker arrêté) ; orphans 0 ; diff lu (2 fichiers, +16 −12)

## Notes
- Limite connue, hors périmètre : `_MONTHS` de `cv_templates.py` ne connaît pas les mois anglais (« Aug 2025 ») ; une telle date s'affiche à l'année seule (même comportement que le tri actuel).
- Conventions lues : CLAUDE.md (= AGENTS.md = GEMINI.md, identiques), .cursorrules. Directive tests : `tests_for(render_cv_html)` → 14 tests, tous dans test_cv_templates.py ; le test remplacé garde sa couverture (même cas, nouvelles assertions).
- Baseline DoD : import OK, 121 passed, orphan grep = 5 lignes (attendu 0 après teardown).
