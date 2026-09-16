---
task: Improve job offers page readability and replace star icons with appropriate UI icons
status: completed
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Improve Job Offers Page Readability and UI Icons

## Context
- Existing code checked:
  - `frontend/src/app/offers/page.tsx`:
    - Uses `FiStar` for the "Détails" button (`<FiStar className="w-4 h-4 text-yellow-400" /> Détails`) and for the score badge (`<FiStar className="w-3 h-3 fill-current" /> Score X/5`).
    - Job cards have poor readability: raw unparsed markdown asterisks like `**RÉSUMÉ :**` cluttering descriptions, dark blocky containers, crowded meta pills, and lack of visual company identity.
- Fresh info looked up:
  - User feedback from screenshot:
    1. "adapte la page des offre d'emploi, fait en sorte qu'elle soit pllus lisible"
    2. "utilise autre chose que les etoiles pour les details"
- Git status checked: Clean working tree ready for surgical edits.

## Simpler Alternative Considered
- Only replacing the icon in the button: REJECTED by user request — user also explicitly asked to improve overall readability ("fait en sorte qu'elle soit plus lisible").

## Surgical Scope
- **Files touched**:
  - `frontend/src/app/offers/page.tsx`
- **Files NOT touched**:
  - `backend/`
  - `frontend/src/app/offers/[id]/page.tsx`
- **Symbols replaced**: `FiStar` in details button and score badge
- **Symbols extended**: `OfferCard` and search/filter bar in `frontend/src/app/offers/page.tsx`

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build` (Exit code 0, 15/15 pages)
- [x] Type check: `npx --prefix frontend tsc --noEmit` (Exit code 0)
- [x] Manual check:
  - No star icon on the "Détails" button: replaced with `FiEye` ("Détails").
  - Score badge uses `FiZap` / match pill (`⚡ Match 4.8/5`) instead of `FiStar`.
  - Descriptions are cleaned of raw markdown markers (`**RÉSUMÉ :**`, bullet points).
  - Cards have improved contrast, company letter avatar, clear meta layout, and harmonious action buttons.

## Steps
- [x] Step 1: In `frontend/src/app/offers/page.tsx`, create description cleaning helper `cleanDescriptionPreview` and replace `FiStar` with `FiEye` on the Details button and `FiZap` on the score badge.
- [x] Step 2: Modernize `OfferCard` and the search/filter header in `frontend/src/app/offers/page.tsx` to improve visual hierarchy, company avatar, readable badge pills, and balanced action buttons.
- [x] Step 3 (teardown): Verify Next.js build, TypeScript compilation, update plan to complete and record in `DAILY_LOG-2026-09-16.md`.

## Code Review
- Dead code removed: yes (`FiStar` removed)
- Build status: pass (15/15 pages built cleanly)
- Type errors: none (`npx tsc --noEmit` clean)
- Unintended side effects: none
- Security surface touched: no
- Verdict: complete and verified

## Execution Log
- 11:27 | agy | step 1 | completed - cleanDescriptionPreview helper added, FiStar replaced with FiEye and FiZap
- 11:28 | agy | step 2 | completed - OfferCard redesigned with company avatar, cleaned descriptions, and balanced action buttons
- 11:29 | agy | step 3 | completed - Next.js build and tsc checks passed with 0 errors

