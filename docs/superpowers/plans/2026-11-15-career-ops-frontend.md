# Career-Ops v1.32+ Frontend Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose all Career-Ops v1.32+ backend upgrades (`importance_evidence_tier`, `dropped_requirements_count`, `BlocG.risk_summary`, `company_history_note`, `BlocH`, ATS CV score & clean Markdown/TXT export, Score Calibration & JD Skill-Gaps analytics) and updated LLM model fallbacks across the Next.js frontend in modular components (each new file ≤ 300 lines).

**Architecture:** Isolate every new UI capability in focused sub-components under `frontend/src/components/{ui,offers,resumes,applications}/` while adding minimal typed contracts and client methods in `frontend/src/types/` and `frontend/src/lib/api.ts`. Analytics endpoints load on demand when tabs or native `<dialog>` modals open; evaluation types remain backward-compatible with optional fields.

**Tech Stack:** Next.js 15.2.4 (App Router), React 19, TypeScript 5, Tailwind CSS 4, `react-icons/fi`, native `<dialog>` + `overscroll-behavior: contain`.

---

### File Structure
- Create: `frontend/src/types/analytics.ts` (calibration & skill-gaps contracts)
- Modify: `frontend/src/types/jobOffer.ts` (optional Career-Ops v1.32+ Bloc B/G/H fields)
- Modify: `frontend/src/types/resume.ts` (ATS score & text export response types)
- Modify: `frontend/src/lib/api.ts` (add `calibrateScores`, `getSkillGaps`, `getAtsScore`, `exportText`, re-export new types)
- Modify: `frontend/src/app/globals.css` (native `<dialog>` scroll-containment styles)
- Create: `frontend/src/components/ui/AccessibleDialog.tsx` (shared native modal wrapper ≤ 90 lines)
- Create: `frontend/src/components/offers/OfferEvaluationExtras.tsx` (`EvidenceTierBadge`, `BlocGRiskSummary`, `BlocHDraftPanel` ≤ 220 lines)
- Modify: `frontend/src/app/offers/[id]/page.tsx` (render Bloc B dropped banner + `EvidenceTierBadge`, `BlocGRiskSummary`, `BlocHDraftPanel`)
- Modify: `frontend/src/components/applications/ApplicationDetails.tsx` (render `company_history_note` + compact `BlocHDraftPanel`)
- Create: `frontend/src/components/resumes/ResumeAtsTab.tsx` (ATS score 0–100 bars, keyword coverage, invisible-marker alert, Markdown/TXT export & copy ≤ 250 lines)
- Modify: `frontend/src/components/resumes/ResumePreviewModal.tsx` (add `"ats"` tab + auto-refresh after save)
- Create: `frontend/src/components/applications/CalibrationModal.tsx` (pipeline calibration table by band & archetype ≤ 240 lines)
- Modify: `frontend/src/app/applications/page.tsx` (add `"Calibration IA"` header button & modal)
- Create: `frontend/src/components/offers/SkillGapsModal.tsx` (recurring missing JD skills vs resume-supported matrix ≤ 220 lines)
- Modify: `frontend/src/app/offers/page.tsx` (add `"Lacunes JD"` header button & modal)
- Modify: `frontend/src/components/applications/CoverLetterPanel.tsx` (update default fallback model names)
- Modify: `frontend/src/app/guide/page.tsx` (update `airflow-sources` and add Career-Ops v1.32+ FAQ entries)

---

### Task 1: Update Model Fallbacks & User Guide FAQ
**Files:**
- Modify: `frontend/src/components/applications/CoverLetterPanel.tsx`
- Modify: `frontend/src/app/guide/page.tsx`

- [ ] **Step 1:** In `frontend/src/components/applications/CoverLetterPanel.tsx`, update fallback strings at lines 793 and 799 from `"gpt-4o-mini"` / `"mistral-small-2501"` to `"openai/gpt-5.6-terra"` and `"gemini/gemini-3.8-flash"`.
- [ ] **Step 2:** In `frontend/src/app/guide/page.tsx`, inspect `FAQ_ITEMS` around `airflow-sources` and `matching`, update `airflow-sources` to document Zero-Token direct ATS extractors (Ashby, Workday CXS, Greenhouse, Lever, SmartRecruiters) and non-content filtering (login walls, 404 shells, paywalls), and append FAQ items covering **Bloc H** form draft answers (`>= 4.0`), **ATS Score (0–100, A–D) & clean export**, and the **Calibration IA** / **Lacunes JD** analytics modals.
- [ ] **Step 3:** Run `cd frontend && npm run lint` to verify no syntax/lint issues.

### Task 2: Extend TypeScript Contracts & API Client
**Files:**
- Modify: `frontend/src/types/jobOffer.ts`
- Modify: `frontend/src/types/resume.ts`
- Create: `frontend/src/types/analytics.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1:** Update `frontend/src/types/jobOffer.ts` with `ImportanceEvidenceTier`, optional `importance_evidence_tier` on `RequirementMatch` and `MissingRequirement`, `dropped_requirements_count` on `BlocB`, `RiskSummaryItem` and extra signals (`employment_classification_risk`, `pay_range_width_warning`, `ai_buzzword_mismatch`, `company_history_note`, `risk_summary`) on `BlocG`, plus `DraftApplicationAnswer`, `BlocH`, and `bloc_h?: BlocH | null` on `OfferEvaluation`.
- [ ] **Step 2:** Update `frontend/src/types/resume.ts` with `AtsScoreBreakdown`, `AtsKeywordCoverage`, `ResumeAtsScoreResponse`, and `ResumeExportTextResponse`.
- [ ] **Step 3:** Create `frontend/src/types/analytics.ts` defining `ScoreCalibrationBucket`, `ScoreCalibrationResponse`, `SkillGapItem`, and `JdSkillGapsResponse`.
- [ ] **Step 4:** Add `applicationApi.calibrateScores(minBandN = 5)`, `jobOffersApi.getSkillGaps(minScore = 0)`, `resumeApi.getAtsScore(id, offerId?)`, `resumeApi.exportText(id, format)`, and re-exports in `frontend/src/lib/api.ts`.
- [ ] **Step 5:** Run `cd frontend && npx tsc --noEmit` to verify types compile cleanly.

### Task 3: Shared Native `<dialog>` Modal Wrapper
**Files:**
- Modify: `frontend/src/app/globals.css`
- Create: `frontend/src/components/ui/AccessibleDialog.tsx`

- [ ] **Step 1:** Add `dialog:modal` and `dialog::backdrop` scroll-containment & backdrop styling rules to `frontend/src/app/globals.css` (without altering global `html`/`body` overflow).
- [ ] **Step 2:** Create `frontend/src/components/ui/AccessibleDialog.tsx` using native `<dialog>` + `showModal()`, `closedby="any"`, `aria-labelledby`, safe outside-bounding-box `pointerdown`/`pointerup` light-dismiss fallback for Safari, and close button with `aria-label="Fermer"`. Keep under 95 lines.

### Task 4: Evaluation Bloc B / G / H Components & Integration
**Files:**
- Create: `frontend/src/components/offers/OfferEvaluationExtras.tsx`
- Modify: `frontend/src/app/offers/[id]/page.tsx`
- Modify: `frontend/src/components/applications/ApplicationDetails.tsx`

- [ ] **Step 1:** Create `frontend/src/components/offers/OfferEvaluationExtras.tsx` exporting:
  - `EvidenceTierBadge({ tier })` (`"stated"` → `Explicite`, `"structural"` → `Structurelle`, `"inferred"` → `Déduite`)
  - `BlocGRiskSummary({ blocG })` (renders `company_history_note` alert card + `risk_summary` rows + numeric/contract/buzzword warnings if any)
  - `BlocHDraftPanel({ blocH, compact? })` (renders when `blocH?.eligible` is true, showing draft Q&A cards with copy button + copied state, `key_achievements`, `gaps_flagged`, `jd_keywords`).
- [ ] **Step 2:** Wire `EvidenceTierBadge`, `dropped_requirements_count` banner, `BlocGRiskSummary`, and `BlocHDraftPanel` into `frontend/src/app/offers/[id]/page.tsx`.
- [ ] **Step 3:** Wire `company_history_note` + compact `BlocHDraftPanel` into `frontend/src/components/applications/ApplicationDetails.tsx`.

### Task 5: ATS CV Score & Clean Text/Markdown Export Tab
**Files:**
- Create: `frontend/src/components/resumes/ResumeAtsTab.tsx`
- Modify: `frontend/src/components/resumes/ResumePreviewModal.tsx`

- [ ] **Step 1:** Create `frontend/src/components/resumes/ResumeAtsTab.tsx` displaying score (`score / 100`) & grade badge (`A`/`B`/`C`/`D`), progress bars for the 6 breakdown axes (`text / 15`, `sections / 20`, `contact / 15`, `layout / 20`, `metrics_and_bullets / 15`, `charset_and_markers / 15`), `keyword_coverage` pills, invisible markers alert if non-empty, `issues` list, and Markdown / plain text export preview with **Copier** and **Télécharger** controls.
- [ ] **Step 2:** Extend `ResumePreviewModal.tsx` `activeTab` and `initialTab` union to include `"ats"`, add `"Score ATS & Export"` tab button, render `ResumeAtsTab` when selected, and bump a `refreshKey` counter when resume content is saved.

### Task 6: On-Demand Analytics Modals (`/applications` & `/offers`)
**Files:**
- Create: `frontend/src/components/applications/CalibrationModal.tsx`
- Modify: `frontend/src/app/applications/page.tsx`
- Create: `frontend/src/components/offers/SkillGapsModal.tsx`
- Modify: `frontend/src/app/offers/page.tsx`

- [ ] **Step 1:** Create `frontend/src/components/applications/CalibrationModal.tsx` using `AccessibleDialog`, KPI summary cards, `min_band_n` selector (`3`, `5`, `10`), warnings banner, score band conversion table (`<3.5`, `3.5-3.9`, `4.0-4.4`, `>=4.5`) and archetype breakdown table.
- [ ] **Step 2:** Add `"Calibration IA"` button in `frontend/src/app/applications/page.tsx` header and mount `<CalibrationModal />`.
- [ ] **Step 3:** Create `frontend/src/components/offers/SkillGapsModal.tsx` using `AccessibleDialog`, `min_score` filter (`0`, `3.5`, `4.0`), summary count, and sortable/badge-annotated list of missing requirements (`"Déjà dans le CV"` vs `"Lacune réelle"`, critical/high count vs total, archetype chips).
- [ ] **Step 4:** Add `"Lacunes JD"` button in `frontend/src/app/offers/page.tsx` header and mount `<SkillGapsModal />`.

### Task 7: Verification, Line-Count Audit & Deployment
- [ ] **Step 1:** Run `wc -l` on all newly created files to confirm each is strictly ≤ 300 lines.
- [ ] **Step 2:** Run `cd frontend && npm run lint && npm run build` and verify exit code `0` with zero TypeScript or Next.js build errors.
- [ ] **Step 3:** Commit changes on `main`, push to `origin/main`, and rebuild/restart `frontend` on `sentinel-vps` via `docker compose -f docker-compose.prod.yml up -d --build frontend` + inspect `ps` & `logs`.
