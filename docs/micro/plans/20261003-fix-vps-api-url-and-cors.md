---
task: Résolution de l'URL API dynamique navigateur et de la politique CORS sur VPS
status: completed
created: 2026-10-03
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Résolution de l'URL API dynamique navigateur et de la politique CORS sur VPS

## Context
- Lors de l'accès à l'application déployée sur VPS via `https://185.194.142.163.sslip.io/auth/register`, l'inscription et les appels API échouent :
  1. `frontend/src/lib/api.ts:getApiBaseUrl()` replie en dur sur `http://localhost:8000` si `NEXT_PUBLIC_API_URL` n'est pas fourni au build Docker, provoquant des requêtes vers `localhost:8000` depuis le navigateur client de l'utilisateur (Mixed Content / Network Error).
  2. `backend/main.py` n'autorise que `localhost` et `127.0.0.1` par défaut. L'origine `https://185.194.142.163.sslip.io` est bloquée par CORS si `CORS_ORIGINS` n'est pas explicitement injecté.
  3. `docker-compose.prod.yml` ne transmettait pas `DOMAIN` au backend, et la variable `CORS_ORIGINS` était vide par défaut.
  4. Dans `tests/conftest.py`, la présence de `INVITATION_CODE` dans le `.env` local fait échouer les tests d'utilisateurs qui n'envoient pas de code d'invitation.

## Simpler Alternative Considered
- Forcer l'utilisateur à définir `NEXT_PUBLIC_API_URL` au build en dur dans `Dockerfile` : rejeté car cela casserait la portabilité de l'image Docker si le domaine ou l'IP change.
- `window.location.origin` dynamique dans le navigateur est universel, zéro configuration, et s'aligne immédiatement sur n'importe quel domaine ou IP configuré derrière Caddy.

## Surgical Scope
- **Files touched**:
  - `frontend/src/lib/api.ts`
  - `backend/main.py`
  - `docker-compose.prod.yml`
  - `backend/tests/conftest.py`
- **Files NOT touched**: tous les autres
- **Symbols replaced**:
  - `getApiBaseUrl` dans `frontend/src/lib/api.ts`
- **Symbols extended**:
  - Configuration CORS dans `backend/main.py` (support auto de `DOMAIN` et regex wildcard `*.sslip.io`)
  - Variables d'environnement du backend dans `docker-compose.prod.yml`
  - Fixtures de test dans `backend/tests/conftest.py` (isolation d'environnement)

## Definition of Done
- [x] `getApiBaseUrl()` dans `frontend/src/lib/api.ts` renvoie `window.location.origin` sur navigateur hors localhost si `NEXT_PUBLIC_API_URL` n'est pas défini.
- [x] `backend/main.py` intègre automatiquement `https://{DOMAIN}` et autorise les domaines IP wildcard (`*.sslip.io`, `*.nip.io`) via regex.
- [x] `docker-compose.prod.yml` injecte `DOMAIN` et calcule un `CORS_ORIGINS` par défaut basé sur le domaine.
- [x] La suite de tests `tests/test_users.py` passe à 100% avec et sans `INVITATION_CODE`.
- [x] Le build frontend de production `npm run build` passe avec succès.

## Steps
- [x] Step 1: Adapter `getApiBaseUrl()` dans `frontend/src/lib/api.ts` pour utiliser `window.location.origin` en production navigateur.
- [x] Step 2: Mettre à jour `backend/main.py` pour ajouter `DOMAIN` aux origines autorisées et autoriser `*.sslip.io` / `*.nip.io` dans la regex CORS.
- [x] Step 3: Mettre à jour `docker-compose.prod.yml` pour transmettre `DOMAIN` et une valeur par défaut de `CORS_ORIGINS` au conteneur backend.
- [x] Step 4: Isoler `INVITATION_CODE` dans `backend/tests/conftest.py` pour garantir la conformité des tests unitaires locaux.
- [x] Step 5: Valider les tests backend (`uv run pytest tests/test_users.py -v`) et le build frontend (`npm run build`).
- [x] Step 6: Mettre à jour le journal `docs/micro/DAILY_LOG-2026-10-03.md` et `docs/micro/INDEX.md`.

## Code Review
- Dead code removed: yes
- Build status: pass (backend 11/11 tests pass, frontend npm run build pass)
- Type errors: none
- Unintended side effects: none
- Security surface touched: yes (CORS, URLs API)
- Verdict: ✅ DONE

## Execution Log
- 2026-10-03 00:22: Micro plan créé pour corriger l'URL API dynamique et la politique CORS sur VPS.
- 2026-10-03 00:23: `getApiBaseUrl` adapté pour détecter `window.location.origin` sur les déploiements hors localhost.
- 2026-10-03 00:23: `DOMAIN` auto-injecté aux origines autorisées et wildcard `*.sslip.io` / `*.nip.io` ajouté à la regex CORS dans `backend/main.py`.
- 2026-10-03 00:23: `docker-compose.prod.yml` mis à jour pour transmettre `DOMAIN` et une valeur par défaut cohérente de `CORS_ORIGINS`.
- 2026-10-03 00:23: `backend/tests/conftest.py` isole `INVITATION_CODE` pour garantir la stabilité de la suite de tests.
- 2026-10-03 00:23: Tests backend validés (11/11 passés).
- 2026-10-03 00:24: Build frontend Next.js validé (`npm run build` code 0). Plan complété.
