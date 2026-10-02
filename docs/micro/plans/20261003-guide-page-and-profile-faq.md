# Plan: Page Guide & FAQ Frontend (Fonctionnement Profil, Airflow, CRONs, IA)

## Context & Needs
The user wants an informative Guide & FAQ page on the frontend explaining:
1. How automated CRON / Airflow scrapers work (sources, cadences, dynamic keyword generation from candidate preferences, active/pause toggle, relevance filtering).
2. How to configure candidate profiles (multi-source ingestion with Mistral VLM for CVs, website, GitHub, manual edits; priority hierarchy `manual` > `cv` > `website` > `github`; conflict detection and dismissal).
3. How AI job offer matching (1.0-5.0 score), tailored CV generation, and cover letters work.
4. How Kanban pipeline tracking and France Travail job search logs operate.

Note: The route will be `/guide` (rather than `/docs` to prevent collisions with FastAPI's native `/docs` Swagger UI proxy).

## Solution
1. **Frontend Page (`frontend/src/app/guide/page.tsx`)**:
   Create a responsive, modern, interactive documentation and FAQ guide featuring:
   - Category navigation / filter pills: "Veille & Airflow (CRONs)", "Profil Multi-Sources & VLM", "Génération IA & Matching", "Candidatures & Kanban".
   - Search bar to quickly find answers.
   - Accordion-style expandable questions/answers with clear diagrams and examples.
   - Callout tips (e.g., how to pause automated crawling, how to trigger profile updates).
2. **Header Navigation (`frontend/src/components/layout/Header.tsx`)**:
   Add a direct link to "/guide" ("Guide") in desktop navigation, mobile navigation, and user profile dropdown.
3. **Profile Page Link (`frontend/src/components/profile/CandidateProfileSection.tsx`)**:
   Add a subtle helpful link near the source sync area ("Comprendre la synchronisation multi-sources").
4. **Validation**:
   Build the Next.js frontend to verify zero TypeScript or linting errors.

## Steps
- [x] 1. Create `/guide` page in `frontend/src/app/guide/page.tsx`.
- [x] 2. Add navigation link to `/guide` in `frontend/src/components/layout/Header.tsx`.
- [x] 3. Add contextual guide link in `frontend/src/components/profile/CandidateProfileSection.tsx`.
- [x] 4. Build and validate with `npm --prefix frontend run build`.
- [x] 5. Update `docs/micro/DAILY_LOG-2026-10-03.md` and `docs/micro/INDEX.md`.
