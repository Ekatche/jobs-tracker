---
task: Résoudre AxiosError Network Error sur refreshAccessToken et stabiliser le cycle de rafraîchissement
status: done
created: 2026-09-18
completed: 2026-09-18
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Résoudre AxiosError: Network Error sur refreshAccessToken

## Context
- Existing code checked:
  - `frontend/src/lib/api.ts`:
    - `setupTokenRefresh()` crée des `setTimeout` sans jamais nettoyer les timers précédents (`refreshTimerId`), et `refreshAccessToken()` appelle lui-même `setupTokenRefresh()` en plus de l'appelant, provoquant un dédoublement exponentiel et des tempêtes de requêtes (dizaines de `POST /auth/refresh` par seconde constatées dans les logs uvicorn).
    - Si `msToExpiry <= REFRESH_THRESHOLD`, `delay` vaut `0`, causant une boucle synchrone infinie saturant les sockets réseau.
    - Côté SSR/Node.js, `API_URL` vaut `http://localhost:8000` qui est inaccessible depuis l'intérieur du conteneur frontend Docker (seul `http://backend:8000` est joignable).
    - `console.error("Erreur refresh:", error.response?.data || error)` passe l'instance `AxiosError` à Next.js/Turbopack, ce qui déclenche l'Error Overlay rouge de développement en plein écran.
  - `frontend/src/components/auth/ProtectedRoute.tsx`: appelle `refreshAccessToken()` dès l'expiration ou absence de token.
  - `docker-compose.yml`: le conteneur `jobtracker-frontend` a `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- Fresh info looked up: n/a
- Git status checked: clean.

## Simpler Alternative Considered
- Supprimer complètement le rafraîchissement proactif en tâche de fond et ne se fier qu'à l'intercepteur 401 : rejeté car le rafraîchissement proactif prévient l'expiration en cours de session active, mais il doit être strictement borné avec un seul timer (`clearTimeout`) et un minimum de délai.

## Surgical Scope
- **Files touched**:
  - `frontend/src/lib/api.ts`
  - `docker-compose.yml`
- **Files NOT touched**:
  - `backend/*`
  - `frontend/src/components/*`
- **Symbols replaced**:
  - none
- **Symbols extended**:
  - `getApiBaseUrl()` in `frontend/src/lib/api.ts` (gère SSR `INTERNAL_API_URL` vs Client `NEXT_PUBLIC_API_URL`)
  - `setupTokenRefresh()` in `frontend/src/lib/api.ts` (timer unique avec `clearTimeout`, garde SSR, délai minimum de 15s)
  - `refreshAccessToken()` in `frontend/src/lib/api.ts` (timeout 10s, garde SSR, log soft sans lever l'error overlay Turbopack)

## Definition of Done
- [x] Build passes: `docker exec jobtracker-frontend npx tsc --noEmit` (exit 0)
- [x] No request storms: `docker logs --tail 20 jobtracker-backend` ne montre plus de requêtes `/auth/refresh` en rafale infinie
- [x] No dead code: confirm no abandoned timers or unused variables
- [x] Manual check: Vérifier que `/auth/refresh` fonctionne correctement sans afficher d'AxiosError Network Error

## Steps
- [x] Step 1: Config & Networking - Ajouter `INTERNAL_API_URL=http://backend:8000` dans `docker-compose.yml` pour le service frontend et implémenter `getApiBaseUrl()` dans `frontend/src/lib/api.ts` pour router correctement selon SSR ou Client.
- [x] Step 2: Timer & Anti-Loop - Sécuriser `setupTokenRefresh()` dans `frontend/src/lib/api.ts` : stocker `refreshTimerId`, appeler `clearTimeout` avant tout nouveau timer, imposer un délai minimum de 15s (`Math.max(delay, 15000)`), et supprimer le double appel redondant de `setupTokenRefresh()` dans le callback de timer.
- [x] Step 3: Error Handling & SSR Guard - Ajouter un guard `if (typeof window === "undefined") return false;` dans `refreshAccessToken()`, ajouter `timeout: 10000`, et remplacer `console.error(..., error)` par un message informatif textuel (`console.warn`) évitant l'écran rouge de crash de Turbopack.
- [x] Step 4: Verification & Teardown - Valider via `tsc --noEmit`, tester un appel refresh et vérifier l'absence de saturation dans les logs Docker.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 08:54 | agy | plan created
- 08:55 | agy | step 1 | added INTERNAL_API_URL in docker-compose.yml and getApiBaseUrl() in api.ts
- 08:55 | agy | step 2 | bound setupTokenRefresh with single timer and clearTimeout
- 08:55 | agy | step 3 | added SSR guards, timeout 10s, and soft warn logs in refreshAccessToken
- 08:56 | agy | step 4 | verified tsc --noEmit pass and confirmed backend logs calm without loop
