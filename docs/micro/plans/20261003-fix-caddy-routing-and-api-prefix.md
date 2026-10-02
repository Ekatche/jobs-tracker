# Plan: Fix Caddy Reverse Proxy Routing & Frontend API Prefix

## Context & Problem
1. **`server: uvicorn` on `/auth/login`**:
   The user reported seeing `server: uvicorn` instead of Caddy when requesting `https://185.194.142.163.sslip.io/auth/login`.
   Caddy is indeed running as the TLS entrypoint, but it was proxying `/auth/login` to `backend:8000` (FastAPI / Uvicorn). FastAPI responded 404 with header `server: uvicorn`, which Caddy transparently relayed.
2. **Client-side exception on `/resumes`**:
   The frontend page `/resumes` (`src/app/resumes/page.tsx`) calls `resumeApi.getAll()`, fetching `/resumes`.
   Because `getApiBaseUrl()` returned `window.location.origin` without `/api`, the frontend requested `https://.../resumes`. In Caddy, path collision occurred between the Next.js page and the backend endpoint, returning HTML instead of JSON and throwing a JSON parsing client-side exception in React.

## Solution
1. **Unify client API routing under `/api`**:
   Update `getApiBaseUrl()` in `frontend/src/lib/api.ts` to return `${window.location.origin}/api` on non-localhost hosts.
2. **Harmonize `frontend/src/lib/auth.ts`**:
   Use `getApiBaseUrl()` for `API_URL` instead of raw fallback to `http://localhost:8000`.
3. **Clean up `Caddyfile`**:
   - `handle_path /api/*` strips `/api` and proxies to `backend:8000`.
   - Dedicated handler for `POST /auth/register` and direct API routes (`/docs*`, `/openapi.json`, etc.).
   - All standard pages (`/auth/login`, GET `/auth/register`, `/resumes`, `/applications`, etc.) are cleanly forwarded to Next.js (`frontend:3875`).
4. **Update `docker-compose.prod.yml`**:
   Default `NEXT_PUBLIC_API_URL` to `https://${DOMAIN:-localhost}/api`.

## Steps
- [x] 1. Update `frontend/src/lib/api.ts` so `getApiBaseUrl` returns `${window.location.origin}/api` in production browser.
- [x] 2. Update `frontend/src/lib/auth.ts` to use `getApiBaseUrl()` for `API_URL`.
- [x] 3. Update `Caddyfile` to cleanly separate `/api/*`, backend direct docs, and frontend page routing.
- [x] 4. Update `docker-compose.prod.yml` default `NEXT_PUBLIC_API_URL`.
- [x] 5. Test Caddyfile adaptation with Docker.
- [x] 6. Update `docs/micro/DAILY_LOG-2026-10-03.md` and `docs/micro/INDEX.md`.
