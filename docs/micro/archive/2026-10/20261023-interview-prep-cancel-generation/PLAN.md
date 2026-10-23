---
task: Bouton « Annuler » pendant une génération du kit d'entretien, sans écraser le contenu actuel
description: "interview prep annuler génération en cours — AbortController axios signal (api.ts fetchApi RequestOptions, interviewPrepApi.generate*), InterviewPrepTab.tsx bouton Annuler à côté de Génération..., FastAPI Request.is_disconnected dans interview_prep.py (generate stories / audience-packs / questions / reverse-questions / all) : résultat jeté si le client a annulé, Tout générer s'arrête avant la section suivante, réponse 499"
status: done
created: 2026-10-23
---

# Annuler une génération du kit d'entretien

## Context
- Existing code checked :
  - `frontend/src/components/interview/InterviewPrepTab.tsx` : `handleGenerateModule` (L66-105) attend un seul `POST` par module. Pendant l'attente, le bouton affiche « Génération... » et reste désactivé (`disabled={generatingModule !== null}`, L171, L306, L341, L376, L407). Rien ne permet d'arrêter l'attente.
  - `frontend/src/lib/api.ts` : `interviewPrepApi.generateStories/AudiencePacks/Questions/ReverseQuestions/All` (L901-919) appellent `fetchApi` (L76), qui passe par axios. `RequestOptions` (L70-73) n'a pas de `signal`. Une erreur sans réponse HTTP (requête annulée) est relancée telle quelle (L136).
  - `backend/app/routers/interview_prep.py` : les 5 endpoints `generate_*` appellent le LLM, puis écrivent dans `interview_preps` (`update_one` upsert). Par exemple `generate_stories_endpoint` (L100-148). `generate_all_endpoint` (L287-344) enchaîne 4 générateurs avant l'unique écriture. Aucun ne regarde si le client est encore là : une requête abandonnée par le navigateur va jusqu'au bout, et l'appel est payé et enregistré.
  - Logs du 2026-10-23 : `POST /offers/6adbafa6…/interview-prep/generate/stories` met environ 37 s (19:04:10 à 19:04:47).
  - Versions dans le conteneur : fastapi 0.115.9, starlette 0.45.3, uvicorn 0.34.2. Seul middleware : `CORSMiddleware`, en ASGI pur, qui n'enveloppe pas `receive`.
  - En prod, le navigateur joint l'API via Caddy (`frontend/src/lib/apiBase.ts`). En local, il appelle `:8000` directement (CORS).
  - Tests : `tests_for(generate_all_endpoint)` ne renvoie que des tests de service indirects. `backend/tests/test_interview_prep_api.py` teste les endpoints avec `patch("app.routers.interview_prep.generate_*", new_callable=AsyncMock)` et le fixture `test_db`.
- Fresh info looked up : sources installées lues dans le conteneur (`inspect.getsource`).
  - `starlette.requests.Request.is_disconnected` appelle `receive()` dans un `CancelScope` déjà annulé. Il renvoie `True` seulement si le message reçu est `http.disconnect`.
  - Côté uvicorn (`httptools_impl.RequestResponseCycle.receive`), ce message est renvoyé dès que `self.disconnected` est vrai. C'est `connection_lost` qui le positionne.
  - Un `send` après déconnexion est ignoré par uvicorn.
- Git status checked :
  - `InterviewPrepTab.tsx`, `interview_prep.py` et `test_interview_prep_api.py` portent les changements non commités du plan A (`20261023-interview-prep-edit-stories-confirm-regen`), faits dans cette même session. Ce plan s'appuie dessus et ne les modifie pas : `confirm()`, `handleSaveStory` et le nettoyage des `mapped_story_id` restent tels quels.
  - `api.ts` est propre.
  - Les autres fichiers modifiés (`verify_job_offers.py`, `applications/page.tsx`, `types/application.ts`, docs) sont hors périmètre.

## Simpler Alternative Considered
1. **Annuler côté écran seulement** (abandon de la requête axios). Écarté par l'utilisateur : le serveur termine quand même, l'appel est payé et le contenu actuel est remplacé à la fin.
2. **Route `POST …/cancel` avec un drapeau en base.** Elle fonctionne derrière n'importe quel proxy, mais ajoute une route, un champ d'état et une course entre l'annulation et l'écriture. Écartée : la coupure de la connexion porte déjà le signal, et Caddy annule la requête amont quand le client abandonne.
3. **Interrompre l'appel LLM en cours** (tâche mise en course contre la déconnexion). Cela économiserait une partie de l'appel déjà lancé, mais complique les 5 endpoints. De plus, le fournisseur peut facturer malgré tout. Écarté : l'utilisateur a accepté que l'appel en cours reste payé.

## Surgical Scope
- **Files touched** :
  - `backend/app/routers/interview_prep.py` : import `Request`, helper `_generation_cancelled`, paramètre `request` sur les 5 endpoints `generate_*`, vérifications avant écriture.
  - `backend/tests/test_interview_prep_api.py` : 2 tests ajoutés en fin de fichier.
  - `frontend/src/lib/api.ts` : `RequestOptions.signal`, `fetchApi`, les 5 `interviewPrepApi.generate*`.
  - `frontend/src/components/interview/InterviewPrepTab.tsx` : `abortRef`, `handleGenerateModule`, `handleCancelGeneration`, `renderCancelButton`, 5 emplacements de bouton.
- **Files NOT touched** : `backend/app/services/interview_prep_service.py`, `backend/app/services/usage_tracker.py`, `StarStoryCard.tsx`, les 3 visionneuses (`AudiencePacksViewer`, `AnticipatedQuestionsViewer`, `ReverseQuestionsViewer`), les autres fonctions de `api.ts`, tout le reste.
- **Symbols replaced** (→ to delete before done) : none. Les boutons existants restent, le bouton « Annuler » s'ajoute à côté.
- **Symbols extended** (→ keep) :
  - `interview_prep.py::_generation_cancelled(request, module) -> bool` (nouveau). Il renvoie `await request.is_disconnected()` et journalise `Génération <module> annulée par le client : résultat ignoré`.
  - `interview_prep.py::generate_stories_endpoint`, `generate_audience_packs_endpoint`, `generate_questions_endpoint` et `generate_reverse_questions_endpoint` reçoivent `request: Request`. Après l'appel LLM et avant toute écriture, `if await _generation_cancelled(request, "<module>"): return Response(status_code=499)`.
  - `interview_prep.py::generate_all_endpoint` reçoit `request: Request`. La même vérification a lieu après chacun des 4 générateurs : les générateurs suivants ne sont pas appelés et rien n'est écrit.
  - `api.ts::RequestOptions` gagne `signal?: AbortSignal`, que `fetchApi` copie dans `config.signal`. Les 5 `interviewPrepApi.generate*(offerId, signal?: AbortSignal)` le transmettent via `fetchApi(url, "POST", undefined, { signal })`.
  - `InterviewPrepTab.tsx` :
    - `abortRef = useRef<AbortController | null>(null)`.
    - `handleGenerateModule` crée le contrôleur et passe `controller.signal`. Si `controller.signal.aborted`, le `catch` sort sans erreur. Le `finally` ne remet l'état à zéro que si `abortRef.current === controller`.
    - `handleCancelGeneration` appelle `abortRef.current?.abort()`.
    - `renderCancelButton(moduleType)` affiche un bouton « Annuler » (`FiX`) seulement si `generatingModule === moduleType`. Il est placé à côté du bouton « Tout générer » et des 4 boutons de section. Pour chaque section, le bouton existant et « Annuler » sont enveloppés dans un `div className="flex items-center gap-2 shrink-0"`.

## Definition of Done
- [ ] Lint backend : `cd backend && uv run ruff check app/routers/interview_prep.py tests/test_interview_prep_api.py` (exit 0)
- [ ] Tests : `cd backend && uv run pytest tests/test_interview_prep_api.py tests/test_interview_prep_service.py -v`. Tous verts, y compris les 2 nouveaux tests (`-k cancel`).
- [ ] Les 5 endpoints vérifient l'annulation avant d'écrire (4 vérifications pour les sections + 4 dans `all`) : `grep -c "await _generation_cancelled(request" backend/app/routers/interview_prep.py` vaut 8.
- [ ] Le signal traverse le client API : `grep -c "signal?: AbortSignal" frontend/src/lib/api.ts` vaut 6 (`RequestOptions` + 5 fonctions).
- [ ] Un bouton « Annuler » par emplacement de génération : `grep -c "renderCancelButton(" frontend/src/components/interview/InterviewPrepTab.tsx` vaut 6 (définition + 5 usages).
- [ ] Type check : `cd frontend && npx tsc --noEmit` (exit 0)
- [ ] Lint frontend : `cd frontend && npx eslint src/components/interview/InterviewPrepTab.tsx src/lib/api.ts` (aucune nouvelle erreur par rapport à la baseline)
- [ ] Build : `cd frontend && npm run build` (exit 0)
- [ ] No dead code : n/a, aucun symbole remplacé. Aucun import inutilisé signalé par ruff ou eslint.
- [ ] Manual check (observateur : l'utilisateur, stack locale, offre `6adbafa6…` qui a 4 histoires) :
  - « Régénérer » sur les histoires, OK, puis « Annuler » dans les 30 s. Le bouton redevient « Régénérer » tout de suite, sans bandeau d'erreur. Après rechargement, les mêmes 4 histoires sont toujours là.
  - Le log backend contient `Génération stories annulée`.
  - Coût : 1 appel LLM payé.

## Steps
- [x] Step 1 : Tests rouges dans `backend/tests/test_interview_prep_api.py`.
  - (a) `test_cancelled_stories_generation_keeps_existing_stories` : prep existante avec une histoire, `is_disconnected` patché à `True`, puis `POST …/generate/stories`. Le document en base garde l'histoire d'origine.
  - (b) `test_cancelled_generate_all_stops_before_next_module` : `is_disconnected` patché à `True`, puis `POST …/generate/all`. `generate_star_stories` est appelé 1 fois, les 3 autres générateurs 0 fois, et aucun document n'est créé.
  - Patch de `starlette.requests.Request.is_disconnected` avec `new_callable=AsyncMock, return_value=True`.
  - Vérification : `cd backend && uv run pytest tests/test_interview_prep_api.py -k cancel -v`. Attendu : 2 échecs (histoire écrasée, générateurs suivants appelés).
- [x] Step 2 : `interview_prep.py`. Import `Request`, helper `_generation_cancelled`, paramètre `request: Request` sur les 5 endpoints, 8 vérifications avant écriture ou avant le générateur suivant.
  - Vérification : la commande pytest du DoD, toute verte ; ruff exit 0 ; le grep des 8 vérifications.
- [x] Step 3 : `api.ts`. `signal?: AbortSignal` dans `RequestOptions`, `config.signal = options.signal` dans `fetchApi`, paramètre `signal` optionnel sur les 5 `generate*`.
  - Vérification : `npx tsc --noEmit` exit 0 ; grep `signal?: AbortSignal` vaut 6.
- [x] Step 4 : `InterviewPrepTab.tsx`. `useRef` et `FiX` importés, `abortRef`, `handleGenerateModule` étendu, `handleCancelGeneration`, `renderCancelButton` placé aux 5 emplacements.
  - Vérification : `npx tsc --noEmit` exit 0 ; eslint sur le fichier ; grep `renderCancelButton(` vaut 6.
- [x] Step 5 : Contrôle manuel par l'utilisateur (voir le DoD), à mener dans la même session que les scénarios restants du plan A (C, A et B).
  - Vérification : `docker compose logs -t backend --since <ts> | grep -E "annulée|generate/"` montre la ligne `Génération stories annulée`. La lecture en base montre les 4 histoires d'origine. Plus la confirmation de l'utilisateur.
- [x] Step 6 (teardown) : aucun symbole remplacé, donc pas de recherche d'orphelins. Lancer `npm run build` et l'eslint du DoD, puis confirmer qu'aucun import n'est devenu inutile.

## Code Review
- Dead code removed : n/a, aucun symbole remplacé. Les imports ajoutés (`Request`, `useRef`, `FiX`) sont tous utilisés. Les 2 F401 préexistants (`TestClient`, `ReverseQuestion`) ont été retirés à la clôture, avec l'accord de l'utilisateur : ruff exit 0 sur les deux fichiers.
- Build status : pass (`npm run build` exit 0, 2026-10-23T19:45Z)
- Type errors : none (`npx tsc --noEmit` exit 0)
- Unintended side effects : none. Diff relu en entier : chaque ligne du plan C se rattache à une étape. Le reste du diff des mêmes fichiers (liens d'histoires périmés, `confirm()`, `handleSaveStory`) vient du plan A, non commité. Effet voulu : un 499 dans les logs à chaque annulation.
- Security surface touched : no (aucune auth, aucune validation d'entrée, aucun secret ; la vérification de déconnexion n'ajoute aucune entrée utilisateur). Semgrep non lancé pour cette raison.
- Verdict : ✅ DONE. Les 2 tests ajoutés exigent mongo_test, comme les 6 autres du fichier : convention acceptée par l'utilisateur (voir Notes).

## Execution Log
- 2026-10-23T19:20Z | claude-code | plan | written | en attente d'approbation
- 2026-10-23T19:33Z | claude-code | preflight | done | baseline dans Notes (ruff 5 F401 préexistants, pytest 18 passed, tsc/eslint/build exit 0)
- 2026-10-23T19:33Z | claude-code | step 1 | started
- 2026-10-23T19:34Z | claude-code | step 1 | done | `pytest -k cancel` : 2 failed, `assert 200 == 499` (rouge attendu, l'endpoint ignore l'annulation)
- 2026-10-23T19:34Z | claude-code | step 2 | started
- 2026-10-23T19:35Z | claude-code | step 2 | done | pytest 2 fichiers : 20 passed (18 + 2 cancel) ; ruff `interview_prep.py` exit 0 ; test file 2 F401 préexistants (5 → 2, aucun nouveau) ; grep vérifications = 8 ; backend rechargé, /docs 200
- 2026-10-23T19:35Z | claude-code | step 3 | started
- 2026-10-23T19:35Z | claude-code | step 3 | done | `npx tsc --noEmit` exit 0 ; grep `signal?: AbortSignal` = 6
- 2026-10-23T19:35Z | claude-code | step 4 | started
- 2026-10-23T19:37Z | claude-code | step 4 | done | `npx tsc --noEmit` exit 0 ; eslint 2 fichiers exit 0 ; grep `renderCancelButton(` = 6 ; dev server /applications 200
- 2026-10-23T19:39Z | claude-code | step 5 | waiting | sonde de déconnexion OK dans le conteneur (voir Notes) ; contrôle manuel en attente de l'utilisateur
- 2026-10-23T19:44Z | claude-code | step 5 | done | utilisateur : « le bouton annuler fonctionne bien » ; log 19:43:49 `INFO:app.routers.interview_prep:Génération stories annulée par le client : résultat ignoré` (appel parti à 19:43:02, 1 appel LLM payé) ; base : 4 histoires d'origine, `updated_at` 19:05:40 inchangé
- 2026-10-23T19:44Z | claude-code | step 6 | started
- 2026-10-23T19:45Z | claude-code | step 6 | done | `npm run build` exit 0 ; `npx eslint InterviewPrepTab.tsx api.ts` « No issues found », exit 0 ; imports `useRef` et `FiX` utilisés
- 2026-10-23T19:48Z | claude-code | close | blocked | DoD frais : pytest 20 passed, greps 8/6/6, tsc/eslint/build exit 0 ; ruff exit 1 (2 F401 préexistants) ; tests `cancel` en échec sans Mongo (ServerSelectionTimeoutError) — décision utilisateur requise, voir Notes
- 2026-10-23T20:07Z | claude-code | close | done | retrait des F401 L4 `TestClient` et L13 `ReverseQuestion` ; DoD frais : ruff exit 0 ; pytest 21 passed (3 fichiers interview prep), `-k cancel` 2 passed ; greps 8/6/6 ; tsc exit 0 ; build exit 0 (20:06Z) ; eslint (InterviewPrepTab, api.ts, StarStoryCard) « No issues found » exit 0 (20:08Z)

## Notes
- Réponse 499 (« client closed request », convention nginx) : le client n'est plus là pour la lire. Elle sert à distinguer l'annulation dans les logs.
- Hypothèse non vérifiée en prod : Caddy annule la requête amont quand le navigateur abandonne. C'est le comportement du reverse proxy Go. Le contrôle manuel ne la vérifie qu'en local, où l'appel est direct. En prod, la ligne `annulée` dans les logs backend la confirmera au premier usage.
- Coût : l'appel LLM déjà lancé reste payé et compté par `usage_tracker`. Seuls les générateurs suivants de « Tout générer » sont évités.
- Sections en onglets : le bouton « Annuler » d'une section n'est visible que sur son onglet. Celui de « Tout générer » est dans l'en-tête, toujours visible.
- Conventions lues (phase 3) : `CLAUDE.md` (identique à `AGENTS.md` et `GEMINI.md`) et `.cursorrules` (bloc code-review-graph seul). Aucune contradiction avec le plan.
- Baseline DoD (2026-10-23T19:33Z, avant toute modification) :
  - ruff : exit 1, 5 F401 dans `tests/test_interview_prep_api.py` (L4 `TestClient`, L9-11 `AudiencePack*`, L13 `ReverseQuestion`). Dette préexistante : le HEAD en avait 6, le plan A en a résorbé une (`AnticipatedQuestion`). `app/routers/interview_prep.py` est propre. Ce plan ne touche pas ces imports. Critère appliqué : aucune nouvelle violation ruff, et `interview_prep.py` reste à exit 0. Le nettoyage revient à l'utilisateur.
  - pytest (2 fichiers) : 18 passed.
  - greps : 0 / 0 / 0 (attendus après : 8 / 6 / 6).
  - `npx tsc --noEmit` : exit 0. `npx eslint` (2 fichiers) : exit 0, aucun problème. `npm run build` : exit 0.
  - Le build sur l'hôte ne gêne pas le serveur de dev : le conteneur `frontend` monte `/app/.next` dans un volume anonyme.
- Le grep `renderCancelButton(` compte la définition : elle est donc écrite en déclaration `function renderCancelButton(moduleType: string)`, et non en `const … = (…) =>`.
- Étape 1 : les tests utilisent `AudiencePackRecruiter`, `AudiencePackHiringManager` et `AudiencePackTechPanel` pour que le test (b) échoue en rouge sur l'assertion et non sur un déballage. Effet de bord : 3 des 5 F401 préexistants disparaissent. Restent `TestClient` (L4) et `ReverseQuestion` (L13), non touchés.
- `fetchApi` : `signal: options.signal` est posé dans le littéral `config`, ce qui équivaut au `config.signal = options.signal` prévu.
- Sonde de déconnexion réelle, sans LLM (2026-10-23T19:39Z) : `scratchpad/disconnect_probe.py`, lancé dans le conteneur `backend` (uvicorn 0.34.2, starlette 0.45.3, httptools). POST sans corps, client abandonné à 0,4 s pendant un `sleep(1.5)` : `first=False second=True third=True`. Témoin attendu jusqu'au bout : `False/False/False`, réponse 200. La coupure du client est donc bien vue par `is_disconnected`, y compris en appels répétés (cas de `all`). Seul le maillon Caddy reste à confirmer, en prod.
- Clôture (2026-10-23T19:48Z), DoD relancé à neuf : ruff exit 1 (2 F401 préexistants seulement ; `interview_prep.py` seul : exit 0) ; pytest 20 passed (dont les 2 `cancel`) ; greps 8 / 6 / 6 ; tsc exit 0 ; eslint exit 0 ; build exit 0 ; contrôle manuel OK (étape 5).
- Tests sans service externe : `MONGO_LOCAL_TEST_HOST=127.0.0.9 uv run pytest tests/test_interview_prep_api.py -k cancel` donne 2 failed (`pymongo.errors.ServerSelectionTimeoutError: 127.0.0.9:27018: timed out`). Les fixtures `client` et `test_db` de `conftest.py` exigent un vrai Mongo de test, comme les 6 autres tests du fichier, et le projet n'a ni marqueur ni skip. Pour les isoler, il faudrait toucher `conftest.py` (skip si Mongo injoignable), qui est hors scope.
- Décision de l'utilisateur (2026-10-23T20:05Z, « tout est bon ») : (1) retrait des 2 imports inutilisés, fait ; (2) les tests restent dépendants de mongo_test, selon la convention du fichier. Un skip dans `conftest.py` si Mongo est injoignable relèverait d'un plan séparé.
- Ancienne prochaine action, désormais close : l'utilisateur tranche deux points. (1) Supprimer les 2 imports inutilisés L4 et L13 du fichier de test : le DoD ruff passe alors à exit 0. (2) Accepter les tests Mongo selon la convention du fichier, ou ouvrir un plan séparé pour un skip dans `conftest.py`. Ensuite : relancer ruff et pytest, puis passer à `status: done`.
