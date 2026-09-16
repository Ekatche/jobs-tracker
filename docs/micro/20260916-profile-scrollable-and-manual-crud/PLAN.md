---
task: Add scrollable viewport containers for dense profile sections and enable manual CRUD for experiences and projects
status: completed
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Profil Candidat : Conteneurs scrollables et gestion manuelle (CRUD) des expériences et projets

## Context
- Existing code checked:
  - `frontend/src/components/profile/CandidateProfileSection.tsx`:
    - View mode: Displays all 15 projects in an unrestricted grid, causing excessive vertical page length and poor scannability. Experiences also grow without bound.
    - Edit mode: Form only exposes `headline`, `summary`, `website`, `github`, `linkedin`, `email`, `phone`, and `skillsText`. `experiences` and `projects` state arrays are populated by `populateForm`, but have no UI inputs, preventing the candidate from adding, modifying, or removing experiences and projects manually.
  - `backend/app/routers/cover_letters.py`: `update_candidate_profile` already accepts `experiences` and `projects` in `PUT /profile/candidate` and persists them to the top-priority `manual` source.
- Fresh info looked up: None needed.
- Git status checked: Working branch `fix/profile-multi-sources`.

## Simpler Alternative Considered
None — users need both a readable, non-bloated reading view (scroll containers) and the ability to adjust their experiences/projects directly.

## Surgical Scope
- **Files touched**:
  - `frontend/src/components/profile/CandidateProfileSection.tsx`
- **Files NOT touched**:
  - Backend files and other frontend components.
- **Symbols replaced**: None.
- **Symbols extended**:
  - `CandidateProfileSection.tsx`:
    - View mode: scrollable wrapper with custom scrollbar styling on projects, experiences, and education grids (`max-h-[520px] overflow-y-auto`).
    - Edit mode: interactive experience editor (role, company, location, start, end, stack, add/delete) and project editor (name, description, stack, url, repo, add/delete).

## Definition of Done
- [x] Frontend type check passes: `cd frontend && npx tsc --noEmit` (0 errors).
- [x] Frontend production build passes: `npm run build` (0 errors).
- [x] View mode scannability: Projects section (15 items) and Experiences section render within structured scrollable containers with custom scrollbars.
- [x] Edit mode manual CRUD: Experiences and projects can be edited, added, and deleted; changes persist to MongoDB upon form submission.

## Steps
- [x] Step 1: In `frontend/src/components/profile/CandidateProfileSection.tsx`, wrap the Projects grid and Experiences list with responsive scrollable containers (`max-h-[500px] overflow-y-auto pr-1.5`) and visual counter badges.
- [x] Step 2: In `frontend/src/components/profile/CandidateProfileSection.tsx`, add interactive manual editors in Edit Mode for `experiences` (fields: role, company, location, start, end, stack, add/delete) and `projects` (fields: name, description, stack, url, repo, add/delete).
- [x] Step 3 (teardown): Run `npx tsc --noEmit`, test build with `npm run build`, verify interactive state, and log completion.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- Step 1: Added bounded scrollable viewports (`max-h-[520px]`, `max-h-[560px]`, and `max-h-[460px]`) with `.custom-scrollbar` on Projects, Experiences, and Education grids.
- Step 2: Added full interactive CRUD in Edit Mode for `experiences` (`handleUpdateExperience`, `handleAddExperience`, `handleRemoveExperience`) and `projects` (`handleUpdateProject`, `handleAddProject`, `handleRemoveProject`).
- Step 3: Verified TypeScript compilation (`tsc --noEmit` exit code 0) and Next.js production build (`npm run build` exit code 0, 15 pages generated).

## Notes
- None.
