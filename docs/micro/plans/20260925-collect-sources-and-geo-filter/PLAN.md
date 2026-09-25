# Collecte : sources structurées (France Travail, Indeed, LinkedIn), Tavily en complément, filtre géographique

Statut : **en cours d'exécution** (2026-09-25) — étapes 1-8 terminées ; points ouverts : constats 5, 6, 7 (décisions utilisateur).

## Constat (vérifié)
- La collecte n'interroge que l'index Tavily : 3 appels par requête (12 job boards / 10 ATS / 8 LinkedIn),
  plafonds atteints à chaque run (logs Airflow 24/09). HelloWork et France Travail occupent les 12 places
  de la passe 1 ; Indeed = 1 offre en base, WTTJ = 9.
- Aucun contrôle de localisation après crawl : Workday `fr-CA` avec `localisation: "Non spécifié"` passé
  puis rattaché au profil via source_query.
- `get_urls` (app/services/job_offers.py:178) ne dédoublonne que ses propres URLs : une URL Tavily déjà en
  base ou déjà trouvée par une autre source est re-crawlée et re-résumée par LLM.

## Rôle de chaque source
| Source | Couvre | Pourquoi |
|---|---|---|
| API France Travail | francetravail.fr | officielle, filtre commune + rayon + contrat + date ; clés à créer |
| jobspy Indeed | indeed.fr | Tavily ne remonte presque rien d'Indeed (1 offre en base) |
| jobspy LinkedIn | linkedin.com/jobs | rayon géo réel, 25 offres/requête vs 8 via Tavily |
| **Tavily (conservé)** | ce qui n'est trouvé nulle part ailleurs : pages carrière / ATS d'entreprises (Greenhouse, Lever, Workday…), WTTJ, APEC, Cadremploi, HelloWork, Free-Work, LesJeudis ; LinkedIn en secours | aucune API accessible pour ces sites |

## Décisions
- Tavily reste une source à part entière, en complément : il n'apporte que des offres **absentes** des sources
  structurées et de la base. Ses URLs sont filtrées AVANT crawl (voir ordre d'exécution) pour ne pas payer
  crawl + résumé LLM sur un doublon.
- Clé d'identité d'une offre : identifiant LinkedIn (`linkedin:<id>`, l'URL varie selon slug/sous-domaine),
  sinon URL. Base : `url` + `alternative_urls`, soft-deleted incluses (bruit déjà trié).
- Offres structurées injectées au même point que les offres Zero-Token ATS :
  dict brut -> résumé LLM (`summarize_offers`, sémaphore 8) -> `enrich_offers` -> dédup -> save.
- (rôle, ville) via `parse_source_query`, contrat via le suffixe `(...)` + `normalize_contract`.
- Filtre de pertinence des intitulés (sources structurées seulement, Tavily a déjà son filtre CrewAI) :
  embedding rôle vs intitulé, seuil 0.40, fail-open. Mesuré : Data Scientist vs Data Analyst 0.52-0.59,
  Lead Tech Data 0.41, AI Engineer 0.35, métiers hors sujet < 0.33.
- Filtre géo « fail-open », appliqué à TOUTES les sources : rejet seulement sur preuve (pays étranger explicite,
  commune française > 50 km, localisation inconnue + locale d'URL étrangère hors `en-*`).
  Géocodage geo.api.gouv.fr (gratuit, sans clé), nom exact sans accents.
- France Travail : Paris/Lyon/Marseille = code d'arrondissement (69123 -> 69381), 400 sinon.
  Clés FRANCE_TRAVAIL_CLIENT_ID/SECRET créées par l'utilisateur sur francetravail.io ; source ignorée si absentes,
  et dans ce cas francetravail.fr reste interrogé via Tavily.
- Passe 1 Tavily découpée par groupe de sites (WTTJ 8 ; apec+cadremploi 6 ; hellowork 6 ; free-work+lesjeudis 6 ;
  francetravail.fr 6 si API non configurée). indeed.fr retiré (couvert par jobspy).
  Passe 2 ATS inchangée. Passe 3 LinkedIn conservée en secours (429 jobspy).
  Coût Tavily : 3 -> 6-7 appels « advanced » par requête.
- Une source en échec n'interrompt pas la collecte ; erreur levée seulement si Tavily échoue ET aucune offre structurée.
- jobspy impose numpy==1.26.3 : override uv `numpy>=2` plutôt que rétrograder crawl4ai/chromadb/onnxruntime
  (sans override, le résolveur retombe sur jobspy 1.1.13, trop ancien).
- Rattachement au profil (matcher) inchangé : une offre hors zone n'atteint plus la base grâce au filtre en amont ;
  l'existant est traité par le script de l'étape 7.

## Ordre d'exécution par requête (cible)
1. En parallèle : recherche Tavily (URLs seulement) ‖ sources structurées (fetch + dédup base + pertinence + géo).
2. URLs Tavily : retrait de celles déjà en base ou déjà couvertes par une offre structurée (clé d'identité).
3. En parallèle : crawl des URLs Tavily restantes + filtre géo ‖ résumé LLM des offres structurées.
4. Fusion -> enrich -> dédup (clean_duplicate_offers, rattrape les doublons inter-sites par entreprise/poste/ville)
   -> save -> tag_new_offers.

## État réel (2026-09-25)
- `app/services/sources/` : `geo.py`, `france_travail.py`, `jobboards.py` (jobspy), `__init__.py`
  (`collect_structured_offers`, `drop_known_offers`, `drop_known_urls`, `keep_relevant_titles`, `offer_identity`).
- `collect_and_save_offers` suit l'« Ordre d'exécution » (gather 1, `drop_known_urls`, gather 3, save).
- `custom_tool.py` : passe 1 par groupe, indeed.fr retiré, francetravail.fr conditionnel.
- Tests : `tests/test_offer_sources.py` (nouveau), `test_crew_models_and_tools.py` et
  `test_job_offers_pipeline.py` adaptés. Suite complète : 603 passed, 1 échec préexistant
  (`test_usage_tier_api::test_update_user_tier`, dépend de l'ordre, passe seul).

## Constats des runs réels (Data Engineer proche de Lyon, CDI) et correctifs
1. `get_urls` appelait `run_crew` en synchrone : boucle bloquée ~2 min 50, sources structurées lancées après.
   Correctif : `await asyncio.to_thread(run_crew, ...)` (app/services/job_offers.py). Vérifié : jobspy tourne
   pendant le crew.
2. Filtre CrewAI trop strict (2 URLs gardées sur 49, fiches ATS rejetées faute de ville dans l'URL, listings
   gardés). Correctif `filter_urls_task` : exclusion seulement si autre métier, jamais pour ville absente,
   toute page listing/SEO exclue, pas de plafond, liste vide autorisée.
3. search_executor (gpt-5-nano) a répondu SANS appeler l'outil Tavily : 11 URLs inventées (listings,
   pole-emploi.fr). Correctif : `TavilyJobBoardSearchTool(result_as_answer=True)` (sortie brute de l'outil =
   réponse de la tâche), `run_crew` vérifie `agent.tools_results` et relance une fois, sinon échec explicite ;
   consigne « appelle l'outil, n'écris jamais d'URL ». Tests `TestRunCrewSearchToolGuard`.
4. **Sécurité** : httpx logue en INFO l'URL Gemini de litellm avec `?key=...` : clé en clair dans les logs
   Airflow. Correctif : `logging.getLogger("httpx").setLevel(logging.WARNING)` dans job_offers_collectors.py.
   Rotation de la clé Gemini recommandée à l'utilisateur.
5. Pages listing déjà crawlées : plusieurs offres fusionnées sous l'URL du listing, document inutilisable
   `6ab5b34a51c97a76cc95c07a` (WTTJ `/fr/pages/emploi-data-engineer-lyon-69001`). Suppression : utilisateur.
6. Filtre de pertinence (embedding 0.40) imparfait : bruit « … Engineer » (Data Center Ops 0.655, IT Support
   0.518, QA 0.491) au-dessus de vraies offres (0.48-0.72). Seuil conservé ; option : règle hybride
   score + mot-clé commun du rôle (non implémentée, décision utilisateur).
8. Offres Greenhouse expirées : API 404, page en 302 vers `<board>?error=true` ; le crawl de repli
   extrayait toute la liste des postes (Executive Assistant, PM… pour « Data Engineer »), fusionnés en un
   document inutilisable `6ab5b7796384af854c29eecd`. Correctif : `ExpiredOfferError` (ats/router.py),
   URL écartée dans `crawl_urls_for_offers`. Vérifié en réel sur les 3 URLs Mirakl.
9. Filtre géo : « Saint-Étienne / Lyon, France » rejetée (seule la 1re ville était géocodée). Correctif :
   ville cible citée comme mot entier = conservée.
10. Run réel après correctifs : 132 s (contre 407 s), 49 URLs Tavily, 9 fiches retenues par le filtre (toutes
   individuelles), aucune clé dans les logs. Audit purge : 31 offres hors zone, 0 liée à une candidature.
7. Ouvert : `get_urls` lève `ValueError` sur liste vide, alors qu'une liste vide est désormais légitime ;
   si toutes les offres structurées sont déjà connues, la requête finit en échec au lieu de « 0 nouvelle ».

## Étapes
1. [x] Test live jobspy (Indeed FR 15 offres/1 s, LinkedIn 25 offres/30 s, descriptions complètes)
2. [x] Module `app/services/sources/` (geo, france_travail, jobboards, orchestrateur) — tests écrits, non lancés
3. [ ] Pipeline : réordonner selon « Ordre d'exécution » (filtrage URLs Tavily avant crawl : `drop_known_offers`
       sur les URLs + clés des offres structurées), filtre géo sur toutes les sources ; test du filtrage
4. [x] custom_tool.py : passe 1 par groupe de sites, indeed.fr retiré, francetravail.fr conditionnel ; tests adaptés
5. [x] Dépendances : `python-jobspy>=1.1.82` dans pyproject, override numpy>=2.1 via `--override` dans
       `Dockerfile` et `Dockerfile.airflow` (uv pip install ne lit pas pyproject.toml) ;
       FRANCE_TRAVAIL_CLIENT_ID/SECRET dans docker-compose (services backend + airflow) ; rebuild conteneurs ✅
6. [x] Suite de tests complète, run réel (Data Engineer Lyon, 132 s), semgrep p/python + p/secrets (0 finding sur les nouveaux fichiers)
7. [x] Script rejouable `backend/scripts/purge_out_of_zone_offers.py` (audit + --delete interactif) ;
       suppression lancée par l'utilisateur
8. [x] Doc : `docs/JOB_INGESTION_AND_NORMALIZATION.md` (sources, ordre, filtres, override numpy, script purge)

## Action utilisateur requise
- Créer une application sur francetravail.io abonnée à « Offres d'emploi v2 », renseigner
  FRANCE_TRAVAIL_CLIENT_ID / FRANCE_TRAVAIL_CLIENT_SECRET dans `.env`, puis recréer les conteneurs.
- Risque CGU : jobspy scrape les pages publiques Indeed/LinkedIn (pas d'API officielle) ; blocage 429 possible,
  Tavily LinkedIn prend alors le relais.
