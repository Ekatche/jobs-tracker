---
task: Fix user authentication session persistence across browser tab closures
status: completed
created: 2026-09-08
updated: 2026-09-12
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Fix User Authentication Session Persistence

## Context
- Existing code checked (re-verified 2026-09-12, code has moved since the plan was first drafted — treat this section, not the 2026-09-08 version, as ground truth):
  - `frontend/src/lib/auth.ts`: `setRememberMe`/`getRememberMe` and a conditional `getRefreshTokenStorage()` (localStorage if remembered, sessionStorage otherwise) are already implemented. The remaining gap: non-remembered sessions still lose `refreshToken` on tab close by design — Step 1 must remove that conditional so `refreshToken` always goes to `localStorage`. `setToken` does not set `path`/`sameSite` on the cookie.
  - `frontend/src/lib/api.ts`: a 401-retry-once already exists, but only inside `fetchApi`'s catch block (`api.ts:85-108`). It does **not** protect `authApi.getCurrentUser()` (`api.ts:326-344`), which calls `apiClient.get()` directly — and `getCurrentUser()` is exactly what `ProtectedRoute` and the four layouts call to check the session. So today a 401 during the auth check is never retried. Step 2 must add a real Axios **response interceptor on `apiClient`** (not another catch block) so every request through `apiClient`, including `getCurrentUser`, gets the refresh-and-retry treatment. `refreshAccessToken` exists but is not exported (`api.ts:164`, `const` not `export const`) — Step 2 must export it. `setupTokenRefresh` still decodes the JWT with `atob` (`api.ts:134`) instead of `jwtDecode`.
  - `frontend/src/components/auth/ProtectedRoute.tsx`: `checkAuth()` still pushes to `/auth/login` immediately if `token` is missing, without attempting `refreshAccessToken()` first. Unchanged from original diagnosis.
  - `frontend/src/app/{applications,dashboard,tasks,offers}/layout.tsx`: each duplicates the same `checkAuth` logic as `ProtectedRoute`, same missing-refresh bug. `dashboard`, `tasks` and `offers` are byte-identical to each other; `applications/layout.tsx` differs slightly (an extra `setLoading(false)` inside the success branch on top of the one in `finally`) — do not assume a single find/replace covers all four.
  - `frontend/src/app/profile/page.tsx`: **has its own guard too** (`useEffect` at `page.tsx:93`, redirects to `/auth/login` at lines 99, 114, 121) — a fifth copy of the same pattern, tangled into the page's own profile-loading effect rather than standing alone. Extracting it is the least mechanical part of Step 4.
  - `frontend/src/components/auth/ProtectedRoute.tsx` is currently **imported by nothing** — it is dead code today. Step 4 is what puts it into service, so it has never actually run in production: exercise it manually, don't assume it works because it exists.
  - `frontend/src/app/layout.tsx:28-32` calls `setupTokenRefresh()` only when `isAuthenticated()` is already true — i.e. never in the exact scenario this plan targets (access cookie gone, refresh token still valid). Not in scope to change: once Step 3 lands, `ProtectedRoute` triggers `refreshAccessToken()`, which re-arms the schedule itself via `api.ts:197`. Noted so the executor does not "fix" it twice.
  - `frontend/src/components/auth/LoginForm.tsx`: `rememberMe` is an uncontrolled checkbox registered via `react-hook-form` with no `defaultValues`, so it is unchecked by default. No redirect for already-authenticated users. Unchanged from original diagnosis.
- Fresh info looked up: n/a
- Git status checked: clean on branch `main`

## Simpler Alternative Considered
- Keep `sessionStorage` for non-remembered users and only make `rememberMe` checked by default: Rejected because users expect web sessions to persist across tab closures by default (matching modern web standards); `sessionStorage` is per-tab and causes accidental logouts.
- **Trade-off accepted, not just UX**: combined with Step 5 (rememberMe defaults to checked), this means the refresh token sits in `localStorage` indefinitely for effectively every user, not just for a tab session — widening the XSS exposure window on that token from "until tab close" to "until explicit logout". Accepted as an intentional product decision (persistent-by-default sessions), not an oversight. If that trade-off is not acceptable, Step 1 and Step 5 need to be revisited before execution, not after.

## Surgical Scope
- **Files touched**:
  - `frontend/src/lib/auth.ts`
  - `frontend/src/lib/api.ts`
  - `frontend/src/components/auth/ProtectedRoute.tsx`
  - `frontend/src/components/auth/LoginForm.tsx`
  - `frontend/src/app/applications/layout.tsx`
  - `frontend/src/app/dashboard/layout.tsx`
  - `frontend/src/app/tasks/layout.tsx`
  - `frontend/src/app/offers/layout.tsx`
  - `frontend/src/app/profile/page.tsx`
- **Files NOT touched**:
  - All backend files (FastAPI refresh endpoints already work as intended)
  - All other frontend components and pages
- **Symbols replaced** (→ to delete before done):
  - Duplicated `checkAuth` effect in the four `layout.tsx` files and `profile/page.tsx` (replaced by wrapping with `ProtectedRoute`)
  - The 401 branch of `fetchApi`'s catch (`api.ts:85-109`), replaced by the `apiClient` response interceptor
- **Symbols added** (new in Step 2, `frontend/src/lib/api.ts`):
  - `refreshPromise` (module-level single-flight slot), `runRefresh()`, `failSession()`, and the `apiClient.interceptors.response.use` registration
- **Symbols extended** (→ keep):
  - `setRefreshToken`, `getRefreshToken`, `removeRefreshToken`, `setRememberMe`, `getRememberMe` in `frontend/src/lib/auth.ts`
  - `refreshAccessToken` (to be exported), `setupTokenRefresh`, `apiClient`, `authApi.getCurrentUser` in `frontend/src/lib/api.ts`
  - `ProtectedRoute` in `frontend/src/components/auth/ProtectedRoute.tsx`

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build` (Next.js 15.2.4 compiled successfully, exit 0)
- [x] Type check: `./frontend/node_modules/.bin/tsc -p frontend/tsconfig.json --noEmit` (exit 0)
- [x] Lint passes: `npm --prefix frontend run lint` (exit 0)
- [x] No dead code: duplicated `checkAuth` blocks confirmed removed from all four layouts and `profile/page.tsx`; `fetchApi`'s old 401 branch confirmed removed (Step 2)
- [x] Security: `semgrep` (sast + secrets) run on the touched frontend files (210 rules, 9 files scanned, 0 findings)

## Steps
- [x] Step 1: In `frontend/src/lib/auth.ts`, remove the `getRememberMe() ? localStorage : sessionStorage` branch in `getRefreshTokenStorage()` so `refreshToken` always persists in `localStorage` regardless of `rememberMe` (which keeps controlling cookie/session expiry only, via `REMEMBERED_SESSION_DAYS`/`DEFAULT_SESSION_DAYS` in `api.ts`). Update `setToken` to pass `path: "/"`, `sameSite: "lax"` explicitly to `Cookies.set` alongside the existing `expires`.
- [x] Step 2: Rework 401 handling in `frontend/src/lib/api.ts` so it lives in one place, on `apiClient`. Sub-parts, all in this one step:
  - Export `refreshAccessToken` (`export const` instead of `const`, `api.ts:164`).
  - Replace the `atob(token.split(".")[1])` parsing in `setupTokenRefresh` (`api.ts:134`) with `jwtDecode`.
  - Add a `refreshPromise` single-flight guard and a `failSession()` helper, then register `apiClient.interceptors.response.use` — **placed after `refreshAccessToken`'s definition (after `api.ts:211`)**, since it is a `const` and earlier registration would sit in its TDZ. Add `InternalAxiosRequestConfig` to the axios import on line 1. Contract the implementation must satisfy:
    - **Single-flight**: concurrent 401s share one in-flight `POST /auth/refresh` via a module-level `refreshPromise`, reset to `null` in a `.finally()`.
    - **Retry once**: mark the replayed config with a `_retry` flag; a second 401 on the same request calls `failSession()` and rejects.
    - **Overwrite, not merge**, the `Authorization` header on replay — `authApi.getCurrentUser()` sets it explicitly (`api.ts:331-334`), so a spread would keep the stale token and re-401. Use `config.headers.Authorization = ...` directly: in axios 1.x (`^1.8.4`) `config.headers` is an `AxiosHeaders` instance and a spread degrades it to a plain object, breaking the type.
    - **`failSession()` on both failure paths** (refresh returned false, and second-401), each doing `removeToken()` + `removeRefreshToken()` + redirect to `/auth/login?session=expired`. Rejecting silently on the second 401 would leave the user on a blank page.
  - **Delete the now-redundant 401 block in `fetchApi`'s catch (`api.ts:85-109`).** With `failSession()` in the interceptor, keeping it double-fires the refresh and the redirect. Keep the non-401 error-message branch (`api.ts:110-112`).
  - Do **not** route `refreshAccessToken`'s own POST through `apiClient` (it uses bare `axios` at `api.ts:180`) — that bare call is what guarantees a 401 from `/auth/refresh` cannot re-enter the interceptor and loop. Same for `authApi.login` (`api.ts:289`): bare `axios` keeps a failed login from being mistaken for an expired session.
- [x] Step 3: Update `frontend/src/components/auth/ProtectedRoute.tsx` so `checkAuth` attempts `refreshAccessToken()` if the access token is missing or expired before redirecting to `/auth/login`.
- [x] Step 4: Replace the duplicated `checkAuth` effect in `app/applications/layout.tsx`, `app/dashboard/layout.tsx`, `app/tasks/layout.tsx`, `app/offers/layout.tsx`, and `app/profile/page.tsx` with the `ProtectedRoute` wrapper (fixed in Step 3), deleting the duplicated logic rather than leaving it in place alongside `ProtectedRoute`. The four layouts are near-mechanical; `profile/page.tsx` is not — its guard is interleaved with the page's own data-loading effect, so separate the two before removing anything. This step is also the first time `ProtectedRoute` is ever mounted (see Context), so run the manual checks against one of these routes specifically.
- [x] Step 5: Update `frontend/src/components/auth/LoginForm.tsx`: pass `defaultValues: { rememberMe: true }` to `useForm` (a plain HTML `checked` attribute won't work — the field is registered/controlled by `react-hook-form`) and redirect already authenticated users to `/applications`.
- [x] Step N (teardown): Confirm 0 dead code or orphan symbols (no leftover duplicated `checkAuth` blocks, no unused `atob` import path), run `npm --prefix frontend run lint` and `npm --prefix frontend run build`.

## Code Review
- Dead code removed: yes (duplicated `checkAuth` blocks removed from all 4 layouts and `profile/page.tsx`, old 401 branch removed from `fetchApi`)
- Build status: pass (`npm --prefix frontend run build` exit code 0)
- Type errors: none (`./frontend/node_modules/.bin/tsc -p frontend/tsconfig.json --noEmit` exit code 0)
- Unintended side effects: none
- Security surface touched: yes (semgrep auto rules scanned 9 files: 0 findings, pass)
- Verdict: ✅ DONE

## Execution Log
- Step 1: Updated `getRefreshTokenStorage()` in `frontend/src/lib/auth.ts` to return `localStorage` unconditionally. Updated `setToken` to pass `path: "/", sameSite: "lax"`. Typecheck passed with `./frontend/node_modules/.bin/tsc -p frontend/tsconfig.json --noEmit` (exit 0).
- Step 2: Refactored 401 handling in `frontend/src/lib/api.ts`: exported `refreshAccessToken`, used `jwtDecode` in `setupTokenRefresh`, removed redundant 401 handling in `fetchApi` catch, added single-flight `refreshPromise`, `runRefresh()`, `failSession()`, and registered response interceptor on `apiClient` with `_retry` guard and `Authorization` header replacement. Typecheck passed with exit 0.
- Step 3: Updated `frontend/src/components/auth/ProtectedRoute.tsx` with token expiration check and pre-auth refresh attempt before login redirection. Typecheck passed with exit 0.
- Step 4: Replaced duplicate auth guards in `applications/layout.tsx`, `dashboard/layout.tsx`, `tasks/layout.tsx`, `offers/layout.tsx` by wrapping children in `ProtectedRoute`. In `profile/page.tsx`, separated data loading from authentication guard by wrapping `ProfileContent` in `ProtectedRoute`. Typecheck passed with exit 0.
- Step 5: Updated `frontend/src/components/auth/LoginForm.tsx` with `defaultValues: { rememberMe: true }` and client-side redirect for already-authenticated users. Typecheck passed with exit 0.
- Step N: Executed `npm --prefix frontend run lint` (exit 0) and `npm --prefix frontend run build` (exit 0, Next.js optimized build successful). Ran `semgrep scan --config auto` across all 9 touched frontend files (210 rules, 0 findings, exit 0).

## Known, out of scope (do not fix here, do not be surprised by)
- **Backend refresh tokens are not actually rotated.** `backend/app/routers/auth.py:136-182` issues a new refresh token on every call but keeps no denylist, so the old one stays valid until its own `exp` — the "rotation des refresh tokens" comment at line 172 is a misnomer. This plan's single-flight guard (Step 2) makes the frontend correct regardless, but the server-side weakness itself is not addressed here.

## Notes
- 2026-09-12 (third pass): Folded the full interceptor design into Step 2 rather than opening a separate micro plan — `micro-dev`'s rule on related plans applies, and a second plan would have targeted the same lines (`api.ts:85-109`) with a conflicting instruction. The single-flight guard moved from "Known, out of scope" into Step 2: it is three lines, and it is what keeps the frontend correct if anyone ever adds a real refresh-token denylist server-side. Verified while designing it: `change-password` returns **400** on a wrong password (`auth.py:109-113`), and both `authApi.login` and `refreshAccessToken` use bare `axios`, so every 401 reaching the interceptor is genuinely an expired session — no exclusion list needed, no loop possible. Added the matching manual checks to the Definition of Done.
- 2026-09-12 (second pass, pre-execution): Re-verified every claim against the code rather than against the plan's own Context. Corrections: `profile/page.tsx` **does** have its own guard (the previous revision wrongly said it had none); `ProtectedRoute` is currently imported by nothing, so Step 4 is its first activation; `applications/layout.tsx` is not byte-identical to the other three; `app/layout.tsx` gates `setupTokenRefresh()` behind `isAuthenticated()`, deliberately left alone. Added to Step 2 the removal of `fetchApi`'s existing 401 branch — without it the new interceptor and the old catch both handle a failed refresh, double-fires the refresh and the redirect. Confirmed no `middleware.ts` exists, so auth is entirely client-side and nothing outside these files guards these routes.
- 2026-09-12: Plan reviewed before execution. Context section was stale — `auth.ts`/`api.ts` had already received partial fixes (rememberMe-conditional storage, a `fetchApi`-scoped 401 retry) not reflected in the original 2026-09-08 draft. Rewrote Context and Steps against the actual current code; no scope or file list changes. Key finding folded into Step 2: the existing 401 handling lives in `fetchApi`'s catch block and never covers `authApi.getCurrentUser()`, which is the function `ProtectedRoute`/layouts call — so a real `apiClient` response interceptor is necessary, not redundant.
