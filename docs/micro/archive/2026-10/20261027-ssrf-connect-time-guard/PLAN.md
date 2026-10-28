---
task: Garde SSRF au moment de la connexion (DNS rebinding, canaux aveugles du navigateur)
description: Valider l'adresse IP réellement connectée (httpx via backend réseau httpcore, Chromium via proxy local filtrant) au lieu de valider avant une seconde résolution DNS
status: done
created: 2026-10-27
---

# Garde SSRF au moment de la connexion

## Context
- Résiduels de la revue sécurité du 26/10 (commit 963f83b), validés par l'utilisateur le 27/10 (« ok pour tes options proposées ») :
  1. DNS rebinding : `validate_public_url_async` résout, puis httpx/Chromium résolvent une seconde fois.
  2. Canaux aveugles du navigateur hors `page.route` : WebSocket, popup, service worker.
  3. Saut de redirection HTTP suivi par Chromium (requête aveugle).
  4. DAG de vérification (`app/tasks/verify_job_offers.py`) non gardé (oracle booléen).
- Faits vérifiés :
  - httpx 0.28.1 / httpcore 1.0.9 : `httpcore.AsyncConnectionPool(network_backend=...)` existe ; httpx ne l'expose pas, `AsyncHTTPTransport._pool._network_backend`.
  - httpcore passe `server_hostname=origin.host` à `start_tls` : se connecter à l'IP validée garde SNI et vérification du certificat sur le nom.
  - crawl4ai 0.6.3 : `BrowserConfig(proxy=...)` => `--proxy-server` au lancement + proxy de contexte ; `BrowserConfig.clone(**kw)`.
  - Playwright force `--proxy-bypass-list=<-loopback>` : le loopback passe aussi par le proxy.
- `BrowserConfig.clone()` (crawl4ai 0.6.3) perd `verbose` (`from_kwargs` l'ignore) : `egress_guard.browser_config_behind_proxy` le recopie.
- Choix écarté : pare-feu de sortie sur le VPS (risque de couper Mongo/Airflow, ne couvre pas les canaux aveugles sans liste de ports).

## Surgical Scope
- Créé : `backend/app/services/egress_guard.py` (résolution validée, backend réseau httpcore, transport httpx, proxy local).
- Modifiés :
  - `backend/app/services/pdf_job_offer.py` (2 clients), `backend/app/services/ats/router.py` (client par défaut), `backend/app/services/profile/collectors/website.py` (`_default_fetch` + crawler interne) : transport public uniquement.
  - `backend/job_crawler/crawler1.py` (`get_filtered_markdown`, `crawl_and_extract_jobs_optimized`) : navigateur derrière le proxy.
  - `backend/app/tasks/verify_job_offers.py` : client httpx + navigateur gardés.
- Tests : `backend/tests/test_egress_guard.py` (nouveau), `backend/tests/test_offer_fetch_ssrf_guard.py`, helpers de mock adaptés si `transport=` entre en conflit.
- Non touchés : `page.route` / `landed_on_public_host` (restent en défense en profondeur), github.py (hôte fixe api.github.com), `scripts/crawl_bakeoff.py`.

## Steps
- [x] 1. RED : test rebinding httpx (serveur local 127.0.0.1, `socket.getaddrinfo` patché : public au 1er appel, 127.0.0.1 ensuite) sur `download_pdf_bytes` => doit échouer aujourd'hui.
- [x] 2. GREEN : `egress_guard.resolve_public_ip`, `PublicOnlyNetworkBackend`, `public_only_transport()` ; brancher pdf_job_offer, ats router, website `_default_fetch`.
- [x] 3. RED/GREEN proxy : CONNECT et GET absolu vers hôte interne/rebindé => 403, serveur non contacté ; hôte public => relayé (origin-form, `Connection: close`).
- [x] 4. Brancher le proxy dans crawler1 (2 fonctions), website (crawler interne), verify_job_offers (navigateur + client).
- [x] 5. Smoke Chromium réel (scratch) : rebinding via `--host-resolver-rules`, WebSocket, redirection => 0 hit ; page publique réelle OK ; temps comparé.
- [x] 6. Suite complète, flake8 sur copie scratch, semgrep ; commit `fix(security)`, push, CI, déploiement backend + Airflow, vérifs.

## Résiduels (acceptés)
- WebRTC/UDP depuis le navigateur ; port quelconque sur une IP publique.
- IPv6 compatibles IPv4 (`::a.b.c.d`), 6to4, NAT64 classées publiques par `_is_public_address` (préexistant) ; injoignables sans IPv6 ni passerelle sur le VPS.
- semgrep `request-data-write` sur le relai du proxy (`_handle_proxy_client`) : faux positif, la cible est une IP publique validée.
- Relecture : « Chromium contourne le proxy pour le loopback » réfuté — le driver Playwright force `<-loopback>` (`chromium.js`, `crBrowser.js`) et crawl4ai passe le proxy par l'option Playwright ; le smoke le confirme (0 hit sur 127.0.0.1).

## Verification
- `uv run pytest tests` (depuis backend/) : tout vert.
- Smoke : 0 hit interne sur rebinding / WebSocket / redirection ; page publique crawlée.
- Résultat smoke du 27/10 (Chromium réel) : sans proxy 10 hits internes (page rebindée, WebSocket IP et nom rebindé, popup, sendBeacon, fetch no-cors, img, favicon, redirection vers IP et vers nom rebindé) ; avec proxy 0. example.com et python.org/jobs : même contenu (859 / 2246 car.), même temps (4,7 s contre 4,8 s ; 6,1 s contre 6,7 s). `check_url_headless_js` sur nom rebindé : `unknown`, pas de suppression.
- 27/10 : suite 1433 passed, lint CI rejoué sur copie, CI verte ; `5539aa7` déployé ~07:20 UTC (backend rebuild prod, Airflow par `git pull`) : /docs 200, `mongodb` résolu, 0 erreur d'import Airflow. En prod (conteneurs airflow et backend) : Chromium derrière le proxy vers 127.0.0.1 = 403, 0 hit ; example.com OK.
