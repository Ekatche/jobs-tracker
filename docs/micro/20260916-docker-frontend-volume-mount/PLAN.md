---
task: Mount frontend volume in docker-compose.yml and rebuild frontend container for live hot-reloading
status: complete
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Mount Frontend Volume and Rebuild Container for Hot Reloading

## Context
- Existing code checked:
  - `docker-compose.yml`: `frontend` service lacks `volumes` directive, causing container to run stale baked-in code.
  - `frontend/Dockerfile`: Builds static production bundle into container and runs `npm run start`.
  - `frontend/package.json`: Contains `"dev": "next dev -p 3875 --turbopack"` and `"start": "next start -p 3875"`.
- Fresh info looked up:
  - Next.js inside Docker requires `HOSTNAME=0.0.0.0` to accept external connections through port 3875.
  - Mounting `./frontend:/app` must preserve container `/app/node_modules` and `/app/.next` to prevent cross-platform OS mismatch (macOS vs Linux Alpine).
- Git status checked: Active branch `fix/profile-multi-sources`.

## Simpler Alternative Considered
- Rebuilding container every time code changes without volume: REJECTED by user request ("met a jour mon docker pour monter le volume et rebuild le front").

## Surgical Scope
- **Files touched**:
  - `docker-compose.yml` (configure `volumes`, `command`, `environment.HOSTNAME` for `frontend` service)
- **Files NOT touched**:
  - `frontend/Dockerfile`
  - All backend files
- **Symbols replaced**: none
- **Symbols extended**: `frontend` service configuration in `docker-compose.yml`

## Definition of Done
- [x] Config check passes: `docker compose config` exits with code 0
- [x] Container build passes: `docker compose build frontend` exits with code 0
- [x] Container run passes: `docker compose up -d frontend` runs `jobtracker-frontend`
- [x] Health / HTTP check: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3875/applications` returns 200
- [x] Volume confirmed mounted: `docker exec jobtracker-frontend ls -la /app` matches host directory

## Steps
- [x] Step 1: In `docker-compose.yml`, update `frontend` service with `volumes` (`./frontend:/app`, `/app/node_modules`, `/app/.next`), `command: ["npm", "run", "dev"]`, and `environment: [HOSTNAME=0.0.0.0]`.
- [x] Step 2: Validate compose file syntax with `docker compose config`.
- [x] Step 3: Rebuild and start container: `docker compose build frontend && docker compose up -d frontend`.
- [x] Step 4: Verify HTTP 200 response on `http://localhost:3875/applications`.
- [x] Step 5 (teardown): Update plan to complete and record in `DAILY_LOG-2026-09-16.md`.

## Code Review
- Dead code removed: yes (no obsolete config)
- Build status: pass (`docker compose build` and `up -d` exit code 0)
- Type errors: none
- Unintended side effects: none (container now tracks host edits in real-time)
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 10:49 | agy | step 1 | started
- 10:50 | agy | step 1 | done | Added volumes and dev command to docker-compose.yml
- 10:50 | agy | step 2 | started
- 10:50 | agy | step 2 | done | docker compose config exit code 0
- 10:50 | agy | step 3 | started
- 10:50 | agy | step 3 | done | Container rebuilt and started (exit code 0)
- 10:51 | agy | step 4 | started
- 10:51 | agy | step 4 | done | HTTP 200 received from http://localhost:3875/applications, volume mounted verified
- 10:51 | agy | step 5 | started
- 10:51 | agy | step 5 | done | Marked complete and recorded in daily log

