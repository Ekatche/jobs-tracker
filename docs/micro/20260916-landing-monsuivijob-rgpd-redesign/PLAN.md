---
task: Redesign landing page with MonSuiviJob branding, GDPR transparency, and vulgarized tool showcase without aggressive CTAs
status: complete
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Moderniser la landing page et adopter la marque MonSuiviJob (clarté, vulgarisation, RGPD, zéro pression)

## Context
- Existing code checked:
  - `frontend/src/app/page.tsx`: Basic, outdated landing page with generic cards and no comprehensive product preview or privacy commitments.
  - `frontend/src/components/layout/Header.tsx`: Displays "Job Tracker" brand in navbar.
  - `frontend/src/app/onboarding/page.tsx`: Mentions legacy "Career-Ops Job Tracker" in hero and completion button.
- Fresh info looked up: Modern web guidance (`css-layout` responsive container patterns, visual cards, modern subtle gradients, clear readability).
- Git status checked: Active branch `fix/profile-multi-sources`, previous daily micro-tasks successfully logged.

## Simpler Alternative Considered
- Just changing the text "Job Tracker" into "MonSuiviJob" without changing the landing page structure: Rejected because the user specifically requested a modernized landing, clearer pedagogical messaging, accessible vulgarization of features, RGPD commitments, and removing pushy marketing / CTAs.

## Surgical Scope
- **Files touched**:
  - `frontend/src/components/layout/Header.tsx` (Update brand title to "MonSuiviJob", add a refined subtitle / badge if applicable)
  - `frontend/src/app/page.tsx` (Complete modernization: informative hero with realistic dashboard snapshot, vulgarized tool modules, dedicated RGPD & privacy section, clean calm footer)
  - `frontend/src/app/onboarding/page.tsx` (Replace legacy "Job Tracker" mentions with "MonSuiviJob")
- **Files NOT touched**:
  - `frontend/src/lib/api.ts`
  - `frontend/src/app/offers/*`
  - All backend routers and models
- **Symbols replaced** (→ to delete before done):
  - Legacy `Home` component implementation in `frontend/src/app/page.tsx`
- **Symbols extended** (→ keep):
  - `Header` component in `frontend/src/components/layout/Header.tsx`

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build` (Exit code 0, static generation 14/14 complete)
- [x] Tests pass: `n/a — UI presentation layer verified via build and lint`
- [x] No dead code: Replaced symbols confirmed removed
- [x] Type check: `npx --prefix frontend tsc --noEmit` (Exit code 0)
- [x] Manual check: Verify Header shows "MonSuiviJob", Landing page hero contains all essential information calmly, tools are explained with everyday language, RGPD guarantees are prominently visible, and CTA spam is avoided

## Steps
- [x] Step 1: Update branding in `frontend/src/components/layout/Header.tsx` and `frontend/src/app/onboarding/page.tsx` to "MonSuiviJob".
- [x] Step 2: Redesign `frontend/src/app/page.tsx` with:
  - Modern, serene aesthetics (deep blue / indigo tones, accessible typography, high contrast, clean badges).
  - Informative Hero section containing immediate answers: what the app does, who it is for, and a visual preview card illustrating the calm tracking workflow (status pills, dates, relances) without pushing aggressive sign-up.
  - "Nos outils expliqués simplement" (Vulgarized tools section):
    * 1. Le Carnet de bord : Centraliser toutes ses candidatures au même endroit en toute simplicité.
    * 2. L'Assistant de candidature : Préparer des lettres pertinentes adaptées aux offres sans jargon technique.
    * 3. Le Radar d'opportunités : Découvrir des opportunités adaptées sans être submergé.
    * 4. Le Suivi des relances : Savoir quand et comment relancer courtoisement sans stress.
  - Section "Respect strict de votre vie privée & RGPD" :
    * Données protégées et non revendues.
    * Droit à l'oubli et suppression en un clic.
    * Hébergement sécurisé conforme aux normes européennes.
    * Transparence algorithmique (vous gardez le contrôle total).
  - Footer sobre et clair avec mentions éthiques et légales.
- [x] Step 3: Run typecheck (`npx --prefix frontend tsc --noEmit`) and frontend build (`npm --prefix frontend run build`).
- [x] Step 4 (teardown): Remove any unused imports/styles and confirm 0 dead code.

## Code Review
- Dead code removed: yes (old landing component replaced completely, 0 orphan imports)
- Build status: pass (`next build` succeeded with exit code 0)
- Type errors: none (`npx tsc --noEmit` clean exit)
- Unintended side effects: none (strictly scoped to UI presentation & branding)
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 10:08: Step 1 completed — Updated Header.tsx with new MonSuiviJob logo/branding and updated onboarding welcome/completion texts.
- 10:09: Step 2 completed — Replaced page.tsx with modern, calm, informative landing page with dashboard preview, vulgarized feature cards, dedicated RGPD commitments section, FAQ, and ethical footer.
- 10:10: Step 3 completed — Verified TypeScript typecheck (`npx tsc --noEmit` -> code 0) and Next.js production build (`npm run build` -> code 0).
- 10:11: Step 4 completed — Confirmed 0 dead code and completed execution log.

## Notes
- None.
