# Compliance Lot 3 — Frontend Pages, Hooks & Modals (`<= 300` lines target)

**Roadmap:** [2026-11-15-code-size-compliance-roadmap.md](../specs/2026-11-15-code-size-compliance-roadmap.md)  
**Scope:** Core Lot 3 (6 major pages & preview/generator flows) + Lot 3B (remaining 8 frontend `> 500`-line pages, modals & landing views) so that **0** `.ts`/`.tsx` files exceed 500 lines across `frontend/src/`.

## Architecture & Module Breakdown

### 1. Admin Dashboard
- `frontend/src/hooks/useAdminDashboard.ts` (166 lines) — state, data fetching & GDPR deletion actions
- `frontend/src/components/admin/AdminUsersTab.tsx` (246 lines) — user moderation table & filters
- `frontend/src/components/admin/AdminCostsTab.tsx` (242 lines) — token/cost analytics breakdown
- `frontend/src/components/admin/AdminGdprModal.tsx` (102 lines) — account erasure confirmation modal
- `frontend/src/app/admin/page.tsx` (187 lines) — admin shell & tab switcher

### 2. Applications Board (Kanban / Table & Notes)
- `frontend/src/lib/applicationsBoard.ts` (116 lines) — filtering, column grouping & note mutations
- `frontend/src/hooks/useApplicationNotes.ts` (91 lines) — isolated notes CRUD state
- `frontend/src/hooks/useApplicationsPage.ts` (281 lines) — board state, drag/status updates & filters
- `frontend/src/components/applications/ApplicationsHeaderBar.tsx` (214 lines)
- `frontend/src/components/applications/ApplicationsKanbanView.tsx` (165 lines)
- `frontend/src/components/applications/ApplicationsTableView.tsx` (108 lines)
- `frontend/src/app/applications/page.tsx` (100 lines)
- `frontend/src/contexts/NotificationContext.tsx` (89 lines) — exported `NotificationType`

### 3. Application Modals (`EditApplicationModal` & `NewApplicationModal`)
- `frontend/src/components/dashboard/application-modal/applicationFormSchema.ts` (36 lines) — shared Zod schema & status lists
- `frontend/src/components/dashboard/application-modal/ApplicationFormFields.tsx` (142 lines) — shared form fields
- `frontend/src/components/dashboard/application-modal/ApplicationNotesEditor.tsx` (131 lines) — inline note list editor
- `frontend/src/components/dashboard/EditApplicationModal.tsx` (263 lines)
- `frontend/src/components/dashboard/NewApplicationModal.tsx` (294 lines)

### 4. Job Offer Detail & Interview Prep
- `frontend/src/hooks/useOfferDetail.ts` (151 lines)
- `frontend/src/components/offers/detail/OfferDetailTopBar.tsx` (96 lines)
- `frontend/src/components/offers/detail/OfferDetailHeader.tsx` (228 lines)
- `frontend/src/components/offers/detail/OfferAnalysisTab.tsx` (162 lines)
- `frontend/src/components/offers/detail/OfferMatchingTab.tsx` (173 lines)
- `frontend/src/app/offers/[id]/page.tsx` (181 lines)
- `frontend/src/components/interview/InterviewPrepHeader.tsx` (220 lines)
- `frontend/src/components/interview/InterviewPrepSections.tsx` (219 lines)
- `frontend/src/components/interview/InterviewPrepTab.tsx` (187 lines)

### 5. Resumes Studio & Preview
- `frontend/src/hooks/useResumesPage.ts` (286 lines)
- `frontend/src/hooks/useResumePreview.ts` (252 lines)
- `frontend/src/components/resumes/ResumeContentEditor.tsx` (186 lines)
- `frontend/src/components/resumes/ResumeGeneratorModal.tsx` (273 lines)
- `frontend/src/components/resumes/ResumePreviewToolbar.tsx` (195 lines)
- `frontend/src/components/resumes/ResumePreviewModal.tsx` (140 lines)
- `frontend/src/app/resumes/page.tsx` (219 lines)

### 6. Onboarding, Tasks, Usage, Profile, Landing & Guide
- `frontend/src/components/onboarding/OnboardingStepper.tsx` (64 lines), `OnboardingStepCv.tsx` (118 lines), `OnboardingStepWeb.tsx` (233 lines), `frontend/src/app/onboarding/page.tsx` (222 lines)
- `frontend/src/hooks/useTasksPage.ts` (196 lines), `TasksFilterToolbar.tsx` (124 lines), `TasksListView.tsx` (119 lines), `frontend/src/app/tasks/page.tsx` (234 lines)
- `frontend/src/components/settings/UsageQuotaGauges.tsx` (116 lines), `UsageTierPlans.tsx` (191 lines), `UsageAuditLog.tsx` (150 lines), `frontend/src/app/settings/usage/page.tsx` (183 lines)
- `frontend/src/components/profile/AccountPasswordSection.tsx` (161 lines), `AccountSecurityTab.tsx` (192 lines), `frontend/src/app/profile/page.tsx` (129 lines)
- `frontend/src/components/landing/LandingHero.tsx` (145 lines), `LandingToolsAndPipeline.tsx` (229 lines), `LandingRgpdFaqFooter.tsx` (167 lines), `frontend/src/app/page.tsx` (20 lines)
- `frontend/src/components/guide/GuideSections.tsx` (262 lines), `GuideFaqSection.tsx` (257 lines), `frontend/src/app/guide/page.tsx` (61 lines)

## Verification Gates
- `frontend/src` files `> 500` lines: `0` remaining
- All 56 touched/created files under `frontend/src`: strictly `<= 294` lines (`0` files `> 300`)
- `cd frontend && npm run lint`: `No ESLint warnings or errors`
- `cd frontend && npm run build`: exit `0` (`20/20` static/dynamic Next.js routes compiled & typechecked)
- Backend Python files `> 500` lines remaining for Lots 4–6: 17 files under `backend/app/`
