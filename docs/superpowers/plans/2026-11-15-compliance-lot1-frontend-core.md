# Code-Size Compliance Lot 1 — Frontend Core (`api.ts` & `offers/page.tsx`) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor `frontend/src/lib/api.ts` (1195 lines) and `frontend/src/app/offers/page.tsx` (1639 lines) into modular TypeScript/React modules with every resulting file strictly ≤ 300 lines and zero regression on existing `@/lib/api` imports or UI behavior.

**Architecture:** Extract a barrel-exported `frontend/src/lib/api/` package (including shared `downloadAuthorizedBlob` to remove 3 duplicated fetch-blob-download handlers) and decompose `offers/page.tsx` into pure formatters, hooks (`useOfferFilters`, `useOffersCatalog`), and focused UI components (`OfferCardBadges`, `OfferCard`, `OffersPagination`, `OffersStatsView`, `OffersFilterBar`, `OffersAdvancedFilters`).

**Tech Stack:** TypeScript 5, React 19, Next.js 15 App Router, Axios, Tailwind CSS 4.

---

### Task 1: Split `frontend/src/lib/api.ts` into `frontend/src/lib/api/*` Modules
**Files:**
- Create: `frontend/src/lib/api/tokenRefresh.ts`
- Create: `frontend/src/lib/api/client.ts`
- Create: `frontend/src/lib/api/types.ts`
- Create: `frontend/src/lib/api/coreApis.ts`
- Create: `frontend/src/lib/api/offersApi.ts`
- Create: `frontend/src/lib/api/generationApi.ts`
- Create: `frontend/src/lib/api/coachingUsageApi.ts`
- Modify: `frontend/src/lib/api.ts` (strict backward-compatible barrel re-export ≤ 45 lines)

- [ ] **Step 1:** Create `tokenRefresh.ts`, `client.ts` (wiring 401 refresh interceptor + `downloadAuthorizedBlob`), `types.ts`, and domain API modules (`coreApis.ts`, `offersApi.ts`, `generationApi.ts`, `coachingUsageApi.ts`).
- [ ] **Step 2:** Replace `frontend/src/lib/api.ts` body with strict barrel re-exports + default `api` export.
- [ ] **Step 3:** Verify `wc -l frontend/src/lib/api.ts frontend/src/lib/api/*.ts` (all ≤ 300 lines) and `cd frontend && npm run lint && npm run build`.

### Task 2: Split `frontend/src/app/offers/page.tsx` into Pure Formatters, Hooks & Components
**Files:**
- Create: `frontend/src/lib/offerFormatters.ts`
- Create: `frontend/src/components/offers/OfferCardBadges.tsx`
- Create: `frontend/src/components/offers/OfferCard.tsx`
- Create: `frontend/src/components/offers/OffersPagination.tsx`
- Create: `frontend/src/components/offers/OffersStatsView.tsx`
- Create: `frontend/src/components/offers/OffersAdvancedFilters.tsx`
- Create: `frontend/src/components/offers/OffersFilterBar.tsx`
- Create: `frontend/src/hooks/useOfferFilters.ts`
- Create: `frontend/src/hooks/useOffersCatalog.ts`
- Modify: `frontend/src/app/offers/page.tsx` (orchestrator ≤ 220 lines)

- [ ] **Step 1:** Extract pure formatters (`offerFormatters.ts`), card UI (`OfferCardBadges.tsx`, `OfferCard.tsx`), and pagination/stats (`OffersPagination.tsx`, `OffersStatsView.tsx`).
- [ ] **Step 2:** Extract filter/catalog state hooks (`useOfferFilters.ts`, `useOffersCatalog.ts`) and filter UI (`OffersAdvancedFilters.tsx`, `OffersFilterBar.tsx`).
- [ ] **Step 3:** Slim `frontend/src/app/offers/page.tsx` down to clean page orchestration.
- [ ] **Step 4:** Verify all modified/created files are ≤ 300 lines with `wc -l`, run `cd frontend && npm run lint && npm run build`, and commit Lot 1 cleanly.
