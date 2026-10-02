---
task: Optimisation des quotas Airflow, Caddyfile reverse-proxy et environnement de production VPS
description: "Optimisation des quotas Airflow, Caddyfile reverse-proxy et environnement de production VPS — docker-compose.yml, docker-compose.prod.yml, Caddyfile, scripts/setup_vps.sh"
status: done
created: 2026-10-02
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Optimisation des quotas Airflow, Caddyfile reverse-proxy et environnement de production VPS

## Context
- Existing code checked:
  - `docker-compose.yml` had Airflow limits at 5 GB memory and 3 GB reservation, which risked OOM killer on a VPS with 8 GB total / 5.7 GB available RAM and 0 GB swap.
  - Frontend in `docker-compose.yml` was run with `npm run dev` and `WATCHPACK_POLLING=true`, consuming high RAM/CPU.
  - No Caddy reverse-proxy configuration existed yet for automatic HTTPS / SSL on ports 80/443.
  - No VPS setup script existed to automate the 4 GB swap creation and UFW firewall rules.
- Fresh info looked up: Caddy v2 directive `handle_path` and `reverse_proxy`.
- Git status checked: clean on tracked files except uncommitted work from previous completed micro tasks.

## Simpler Alternative Considered
- Running Nginx with manual certbot cron: rejected; Caddy is lighter, 100% automated for Let's Encrypt renewal, and natively handles HTTP/2 + HTTP/3 with zero maintenance.

## Surgical Scope
- **Files touched**:
  - `docker-compose.yml`
  - `docker-compose.prod.yml` (new file)
  - `Caddyfile` (new file)
  - `scripts/setup_vps.sh` (new file)
- **Files NOT touched**: all application source code
- **Symbols replaced**: none
- **Symbols extended**: Docker Compose configuration, Airflow resource limits, production deployment bundle.

## Definition of Done
- [x] Airflow memory limits lowered to `3.5G` (limit) and `1.5G` (reservation) in compose files.
- [x] `Caddyfile` created with reverse-proxy rules for frontend, backend API prefixes, and `/api/*` path stripping.
- [x] `docker-compose.prod.yml` created with Caddy service (80/443), production frontend (`npm run start`), and zero public port exposures for databases.
- [x] `scripts/setup_vps.sh` created, executable, handling automated swapfile allocation and UFW firewall.
- [x] Docker compose config validation passes: `docker compose -f docker-compose.prod.yml config` exits 0.

## Steps
- [x] Step 1: Write and validate micro plan.
- [x] Step 2: Calibrate Airflow memory and CPU quotas in `docker-compose.yml`.
- [x] Step 3: Create `Caddyfile` with clean reverse-proxy routing for single-domain HTTPS setup.
- [x] Step 4: Create `docker-compose.prod.yml` for VPS production deployment.
- [x] Step 5: Create `scripts/setup_vps.sh` for Debian server initialization (Swap 4GB, UFW, swappiness).
- [x] Step 6: Validate configuration with `docker compose config`, append entry to `docs/micro/DAILY_LOG-2026-10-02.md`, and complete plan.

## Code Review
- Dead code removed: yes
- Build status: pass (`docker compose -f docker-compose.prod.yml config` and `docker compose config` exit 0)
- Type errors: none
- Unintended side effects: none
- Security surface touched: yes (firewall rules, reverse-proxy SSL, Docker network isolation)
- Verdict: ✅ DONE

## Execution Log
- 2026-10-02 11:06: Micro plan created and validated.
- 2026-10-02 11:07: Calibrated Airflow memory quotas in `docker-compose.yml` (3.5G limit / 1.5G reservation).
- 2026-10-02 11:07: Created `Caddyfile` with automatic HTTPS, HTTP/3, security headers, `/api/*` stripping, and unified single-domain routing.
- 2026-10-02 11:07: Created `docker-compose.prod.yml` for VPS production deployment with Caddy, Next.js production build (`npm run start`), and zero database port exposures.
- 2026-10-02 11:07: Created `scripts/setup_vps.sh` with automated 4 GB swap allocation, SSD swappiness tuning, and strict UFW firewall configuration. Made script executable.
- 2026-10-02 11:07: Validated production and development compose files with `docker compose config`. Plan completed.

## Notes
- `DOMAIN` environment variable in `.env` configures Caddy's domain for automatic SSL certificates.
