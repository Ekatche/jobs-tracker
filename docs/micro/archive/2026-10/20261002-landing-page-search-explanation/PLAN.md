---
task: Documenter et vulgariser le fonctionnement de la recherche d'offres sur la landing page
description: "Documenter et vulgariser le fonctionnement de la recherche d'offres sur la landing page — app/page.tsx"
status: done
created: 2026-10-02
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Documenter et vulgariser le fonctionnement de la recherche d'offres sur la landing page

## Context
- Existing code checked: `frontend/src/app/page.tsx` contains the landing page with Hero, Tools, GDPR, FAQ, and Footer. The search is briefly mentioned as "Le Radar d'opportunités sans bruit", but the actual pipeline (sources directes ATS/jobboards, nettoyage syntaxique, déduplication cross-plateformes, matching transparent sans boîte noire, veille automatique Airflow sans effort manuel) n'était pas vulgarisé ni explicité.
- Fresh info looked up: n/a (React, Next.js App Router, Tailwind CSS, react-icons already installed and configured).
- Git status checked: clean on tracked files (`main...origin/main`).

## Simpler Alternative Considered
- Only add a bullet point in the existing "Radar d'opportunités" card: rejected because it does not make the search process sufficiently transparent, accessible, and reassuring for users of the personal circle.

## Surgical Scope
- **Files touched**:
  - `frontend/src/app/page.tsx`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**: `Home` in `frontend/src/app/page.tsx`

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build` (Exit code 0)
- [x] Tests pass: n/a — no unit tests for landing page UI
- [x] No dead code: n/a — none replaced
- [x] Type check: `npm --prefix frontend run build` (Next.js includes typecheck and linting in build)
- [x] Manual check: Landing page displays the pedagogical search pipeline section and updated FAQ entries cleanly.

## Steps
- [x] Step 1: Write and validate the plan file `docs/micro/plans/20261002-landing-page-search-explanation.md`.
- [x] Step 2: Update `frontend/src/app/page.tsx` to add:
  - Une section dédiée et visuelle "Comment fonctionne notre recherche & veille d'offres ?" avec 4 étapes progressives (1. Veille directe multi-sources, 2. Nettoyage & déduplication instantanée, 3. Décryptage d'adéquation, 4. Pilotage 100 % automatique).
  - Deux questions supplémentaires dans la FAQ pour répondre aux interrogations concrètes sur la provenance des offres et le fonctionnement 100% automatisé.
- [x] Step 3: Run `npm --prefix frontend run build` to confirm zero build/type/lint errors.
- [x] Step 4: Append entry to `docs/micro/DAILY_LOG-2026-10-02.md`.

## Code Review
- Dead code removed: yes
- Build status: pass (`npm --prefix frontend run build` exited with code 0)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-10-02 10:45: Plan authored and verified against codebase.
- 2026-10-02 10:46: Updated `frontend/src/app/page.tsx` with dedicated 4-step search pipeline section, visual indicators, and enhanced FAQ questions.
- 2026-10-02 10:46: Verified with `npm --prefix frontend run build` (exited 0, all 18 static/dynamic routes generated cleanly).
- 2026-10-02 10:47: Daily log updated in `docs/micro/DAILY_LOG-2026-10-02.md`.

## Notes
- None.
