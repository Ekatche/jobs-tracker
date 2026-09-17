---
task: Change frontend port to 3875
status: complete
created: 2026-09-06
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Change frontend port from 3000 to 3875

## Context
- Existing code checked:
  - `frontend/package.json`: `dev` and `start` scripts default to port 3000.
  - `frontend/Dockerfile`: `EXPOSE 3000`.
  - `docker-compose.yml`: frontend port mapping `"3000:3000"`.
  - `README.md`: documentation mentions `http://localhost:3000`.
  - `backend/main.py`: CORS is configured with `allow_origins=["*"]`, so port 3875 is already allowed.
- Fresh info looked up: Next.js CLI accepts `-p <port>` flag for `next dev` and `next start`.
- Git status checked: clean.

## Simpler Alternative Considered
- Setting `PORT=3875` in environment only: explicit `-p 3875` in `package.json` plus `docker-compose.yml` ensures consistency whether running locally with `npm run dev` or in Docker containers.

## Surgical Scope
- **Files touched**:
  - `frontend/package.json`
  - `frontend/Dockerfile`
  - `docker-compose.yml`
  - `README.md`
  - `docs/micro/DAILY_LOG-2026-09-06.md`
- **Files NOT touched**: all other backend, airflow, and frontend source files
- **Symbols replaced**: none
- **Symbols extended**: none

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build` (exit code 0)
- [x] Tests pass: n/a — no frontend unit tests configured
- [x] No dead code: n/a — configuration change
- [x] Type check: clean (verified by `npm --prefix frontend run build`)
- [x] Manual check: verified port configurations across `package.json`, `Dockerfile`, and `docker-compose.yml`

## Steps
- [x] Step 1: Update `frontend/package.json` to configure port 3875 in `dev` and `start` scripts.
- [x] Step 2: Update `frontend/Dockerfile` to expose port 3875 (`EXPOSE 3875`).
- [x] Step 3: Update `docker-compose.yml` to map host and container port `"3875:3875"`.
- [x] Step 4: Update `README.md` to reference `http://localhost:3875`.
- [x] Step 5: Run frontend build `npm --prefix frontend run build` to verify configuration validity.
- [x] Step 6: Record entry in `docs/micro/DAILY_LOG-2026-09-06.md`.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- [x] 15:50 Updated `frontend/package.json` with `-p 3875` for `dev` and `start` scripts.
- [x] 15:51 Updated `frontend/Dockerfile` to `EXPOSE 3875`.
- [x] 15:51 Updated `docker-compose.yml` port mapping to `"3875:3875"`.
- [x] 15:51 Updated `README.md` to reference `http://localhost:3875`.
- [x] 15:53 Executed frontend build with `npm --prefix frontend run build`: clean exit (code 0).
- [x] 15:53 Appended entry to `docs/micro/DAILY_LOG-2026-09-06.md`.
- [x] 16:12 Built `job-tracker-frontend` image with host networking and started stack via `docker compose up -d`.
- [x] 16:12 Verified `jobtracker-frontend` running on `http://localhost:3875` (HTTP 200 OK).

## Notes
- None
