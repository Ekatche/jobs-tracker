---
task: Mesurer les pertes du crawl Crawl4AI par domaine et récupérer les offres perdues sans LLM supplémentaire
description: pertes crawl Crawl4AI — métriques par domaine et par statut (success, no_extraction, llm_error, grounding_rejected, dead_link + dead_signal, empty_content, jsonld_fallback) dans summary by_domain de crawl_and_extract_jobs_optimized (job_crawler/crawler1.py) ; extraction LLM lue avant _is_empty_crawl (fit_markdown < 500 chars) ; repli JSON-LD JobPosting sur result.html (parse_jsonld_job_posting, garde validThrough extract_json_ld_valid_through + detect_closure_in_text) ; ancrage _offer_grounded_in_page normalisé (normalize_text, accents, apostrophes, tirets, bornes de mots) ; résumé LLM des offres de repli dans crawl_urls_for_offers ; pytest test_job_offers_pipeline ; docs JOB_INGESTION_AND_NORMALIZATION
status: done
created: 2026-10-23
---

# Mesurer les pertes du crawl et récupérer les offres perdues

## Context
- Existing code checked (`backend/job_crawler/crawler1.py`, `crawl_and_extract_jobs_optimized` L445-682) :
  - L514 : `_is_dead_or_expired` (L721-754) cherche `DEAD_OR_EXPIRED_PATTERNS` (L699-718, ex. « page introuvable », « erreur 404 », « offre non disponible ») dans tout le `fit_markdown`. Le motif retenu n'est pas journalisé.
  - L530 : `_is_empty_crawl` (L757-765) classe la page vide sous `MIN_PAGE_TEXT_CHARS = 500` caractères de `fit_markdown` (`PruningContentFilter` 0.45, L172). Ce test passe **avant** la lecture de `result.extracted_content`. Or l'extraction LLM tourne pendant `arun_many` sur ce même `fit_markdown` (`input_format="fit_markdown"`, L262). Une offre courte extraite et ancrée est donc jetée alors que le LLM a déjà été payé.
  - L572 : seuls `None` et `""` donnent `no_extraction`. Un `"[]"` du LLM, ou les blocs d'erreur de `RobustLLMExtractionStrategy.extract` (L138 `{"error": True, ...}`), finissent en `status: "success"` avec `offers_count: 0`. La perte est invisible dans `summary["successful_crawls"]`. Aucun repli ne lit le JSON-LD de `result.html`.
  - L618-627 : `_offer_grounded_in_page` (L768-800) teste une sous-chaîne exacte après `lower()` seulement. Une apostrophe typographique (’ / '), un tiret (– / -) ou un accent reformulé par le LLM fait rejeter l'offre.
  - Aucune métrique par domaine. Le summary (L656-669) ne compte que success, empty, dead et retried.
- Chemin amont `backend/app/tasks/job_offers_collectors.py:194-243`, `crawl_urls_for_offers` :
  - zero-token d'abord, avec `extract_ats_or_jsonld_offer` par httpx (`ats/router.py:420`) ;
  - les offres zero-token passent par `summarize_offers` ;
  - le reste part vers `get_job_offers_from_query` (`services/job_offers.py:206`), puis vers le crawler.
- Code réutilisable, sans cycle d'import (aucun des deux modules n'importe `job_crawler`) :
  - `parse_jsonld_job_posting(html, url)` (`ats/router.py:338`), qui ne vérifie pas `validThrough` ;
  - `extract_json_ld_valid_through`, `detect_closure_in_text`, `extract_visible_text` (`tasks/verify_job_offers.py:160`, `:192`, `:83`) ;
  - `normalize_text` (`services/relevance.py:21`, module pur : minuscules, NFKD sans diacritiques, non-alphanumérique remplacé par une espace).
- Tests : `backend/tests/test_job_offers_pipeline.py`.
  - `test_crawler_dead_or_expired_detection` (L198) teste `_is_dead_or_expired` `is True` / `is False` et `_offer_grounded_in_page`.
  - `test_crawler_preserves_user_facing_urls_with_optimization` (L267) donne le modèle de mock `AsyncWebCrawler` / `arun_many`.
  - Baseline 2026-10-23 : `uv run pytest tests/test_job_offers_pipeline.py tests/test_offer_sources.py -q` → 59 passed en 121 s.
- Autre appelant : `backend/app/tasks/regenerate_descriptions.py:105`. Il lit `crawl_res["offers"]` et `crawl_res.get("results")`, une clé qui n'existe pas (bug préexistant, hors périmètre, voir Notes). Il ne dépend donc d'aucun nom de statut.
- Fresh info looked up: n/a. Pas d'API externe nouvelle : crawl4ai est déjà utilisé, et ses blocs d'erreur sont lus dans le code local L138.
- Git status checked: arbre sale hors périmètre. Les fichiers déjà modifiés par d'autres sessions ne sont pas dans le périmètre. `docs/JOB_INGESTION_AND_NORMALIZATION.md` porte déjà des modifications non commitées (plan verify) et sera aussi édité par le plan `20261023-jobspy-hellowork-source`. Ce plan n'ajoute qu'une sous-section nouvelle et ne touche pas ces lignes.

## Simpler Alternative Considered
- Mesure seule, sans correctif : écartée pour trois pertes certaines, indépendantes du volume :
  - une offre extraite, ancrée puis jetée par le test de longueur (LLM déjà payé) ;
  - aucun repli JSON-LD sur un HTML déjà téléchargé (zéro token) ;
  - l'ancrage cassé par la typographie.
- Deux décisions sont **reportées aux données** de l'étape 1, faute de preuve :
  - restreindre `DEAD_OR_EXPIRED_PATTERNS` (L514) ;
  - changer le seuil de 500 caractères (L530).
- Champ `statut` dans le schéma LLM : reporté, il ajoute des tokens de sortie à chaque offre.

## Surgical Scope
- **Files touched**:
  - `backend/job_crawler/crawler1.py`
  - `backend/app/tasks/job_offers_collectors.py` (`crawl_urls_for_offers` seulement : résumé LLM des offres de repli JSON-LD)
  - `backend/tests/test_job_offers_pipeline.py`
  - `docs/JOB_INGESTION_AND_NORMALIZATION.md` (nouvelle sous-section « Crawl4AI : statuts, métriques et replis »)
- **Files NOT touched**:
  - `app/services/ats/router.py`, `app/tasks/verify_job_offers.py`, `app/services/relevance.py` : importés seulement ;
  - `app/services/job_offers.py`, `app/tasks/regenerate_descriptions.py` ;
  - les Dockerfiles ;
  - tous les fichiers déjà modifiés par d'autres sessions.
- **Symbols replaced** (→ to delete before done): corps de `_is_dead_or_expired`, qui délègue à la nouvelle `_dead_or_expired_signal`. Plus de double logique.
- **Symbols extended** (→ keep):
  - `crawl_and_extract_jobs_optimized` (statuts, `domain`, `by_domain`, ordre extraction puis vide, repli) ;
  - `_offer_grounded_in_page` (comparaison normalisée) ;
  - `_is_dead_or_expired` (signature et retour bool conservés) ;
  - `crawl_urls_for_offers` ;
  - nouvelles fonctions privées `_dead_or_expired_signal`, `_jsonld_fallback_offer`.

## Definition of Done
- [x] Build passes : `cd backend && uv run python -m py_compile job_crawler/crawler1.py app/tasks/job_offers_collectors.py` → exit 0
- [x] Tests pass : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q` → 0 failed, dont les 4 nouveaux tests ; `test_crawler_dead_or_expired_detection` passe sans modification de ses assertions existantes
- [x] Pas de régression voisine : `cd backend && uv run pytest tests/test_offer_sources.py tests/test_job_offers_collectors_queries.py -q` → 0 failed
- [x] Métrique par domaine présente : `grep -c 'by_domain' backend/job_crawler/crawler1.py` → ≥ 2
- [x] Repli JSON-LD protégé contre les offres closes : `grep -c 'extract_json_ld_valid_through\|detect_closure_in_text' backend/job_crawler/crawler1.py` → ≥ 2
- [x] Extraction lue avant le test de vide : dans `crawl_and_extract_jobs_optimized`, la ligne `json.loads(result.extracted_content` précède `_is_empty_crawl(` (vérifié par `grep -n 'json.loads(result.extracted_content\|_is_empty_crawl(result' backend/job_crawler/crawler1.py`, ordre des numéros de ligne)
- [x] Tests sans service externe : les 4 nouveaux tests passent avec MongoDB et réseau coupés (mocks `AsyncWebCrawler`, aucun appel LLM). Vérification : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q -k "crawler_metrics or short_page or jsonld_fallback or grounding_normalized"` avec `docker stop job-tracker-mongodb-1 job-tracker-mongo_test-1`, puis `docker start` des deux
- [x] No dead code : `grep -c 'DEAD_OR_EXPIRED_PATTERNS' backend/job_crawler/crawler1.py` → 3 au plus (définition + boucles de `_dead_or_expired_signal` seulement), et `_is_dead_or_expired` réduit à un appel de `_dead_or_expired_signal`
- [x] Type check: n/a — pas de mypy/pyright configuré pour le backend
- [x] Manual check: n/a dans ce plan. La lecture des métriques réelles se fait après déploiement, sur une semaine de collecte (voir Notes) : c'est l'entrée du plan suivant (L514 / L530).

## Steps
- [x] Step 1: Métriques dans `crawl_and_extract_jobs_optimized`.
  - Chaque entrée de `processed_results` reçoit `domain`, le `netloc` de `orig_url` sans `www.`.
  - Statuts distincts :
    - `success` : au moins 1 offre gardée ;
    - `no_extraction` : `None`, `""` ou `[]` ;
    - `llm_error` : uniquement des blocs `error: True` ;
    - `grounding_rejected` : des offres extraites, toutes rejetées par l'ancrage ;
    - `dead_link`, avec `dead_signal` parmi `http_<code>`, `redirect`, `text:<motif>`, `html:<motif>` ;
    - `empty_content` et `json_error`, inchangés.
  - Les blocs `error: True` sont retirés avant l'ancrage.
  - Ajouter `_dead_or_expired_signal(result, page_text) -> Optional[str]` (logique actuelle, qui renvoie le signal) ; `_is_dead_or_expired` devient `return _dead_or_expired_signal(...) is not None`.
  - `summary` gagne `by_domain: {domain: {status: n}}` et des compteurs `no_extraction`, `llm_error`, `grounding_rejected`. Le log `🎯 Ultra-simple terminé` existant les imprime.
  - Test `test_crawler_metrics_by_domain_and_status` : 4 résultats mockés (succès ancré, bloc d'erreur LLM, offre non ancrée, page « offre expirée ») sur 3 domaines. Vérifier `by_domain` exact et `dead_signal == "text:offre expirée"`.
  - Vérification : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q`.
- [x] Step 2: Extraction avant le test de vide.
  - Après le test de lien mort, parser et ancrer `extracted_content` d'abord. S'il reste au moins une offre ancrée, `success`, même sous 500 caractères.
  - `_is_empty_crawl`, avec sa logique de retry réseau inchangée, ne s'applique qu'en l'absence d'offre ancrée.
  - Test `test_crawler_keeps_grounded_offer_on_short_page` : markdown de 200 caractères contenant poste et entreprise, extraction valide. Attendu : 1 offre, statut `success`, pas de retry.
  - Vérification : même commande pytest.
- [x] Step 3: Repli JSON-LD.
  - Nouvelle `_jsonld_fallback_offer(html, orig_url) -> Optional[dict]`, avec imports locaux de `parse_jsonld_job_posting`, `extract_json_ld_valid_through`, `detect_closure_in_text` et `extract_visible_text`.
  - Elle renvoie `None` si `validThrough` est passé ou si le texte visible contient un motif de clôture. Sinon, l'offre parsée avec `url` et `source_url` à `orig_url`.
  - Appelée sur `result.html` quand aucune offre ancrée n'existe et que le classement est final : `no_extraction`, `llm_error`, `grounding_rejected`, ou `empty_content` non réessayé. Jamais sur `dead_link`.
  - Succès : statut `jsonld_fallback`, compté dans `total_offers`.
  - Dans `crawl_urls_for_offers`, passer par `summarize_offers` les offres crawlées qui portent `ats_platform` (le repli JSON-LD le pose, l'extraction LLM non), comme les offres zero-token.
  - Test `test_crawler_jsonld_fallback_guards_closed_offers` : extraction `"[]"` avec un HTML JobPosting dont `validThrough` est futur, attendu 1 offre `jsonld_fallback` ; avec `validThrough` passé, 0 offre et `no_extraction` ; avec « Ce poste a été pourvu » visible (motif de `CLOSED_TEXT_PATTERNS`), 0 offre.
  - Vérification : même commande pytest.
- [x] Step 4: Ancrage normalisé dans `_offer_grounded_in_page`.
  - Comparer `f" {normalize_text(x)} "` dans `f" {normalize_text(page_text)} "` pour le poste et l'entreprise. Les bornes de mots évitent qu'un sigle court s'ancre dans un mot.
  - La règle de repli entreprise par URL reste inchangée.
  - Test `test_crawler_grounding_normalized_text` : « Chargé d’études » contre LLM « Chargé d'études », « Data Engineer – Senior » contre « Data Engineer - Senior », accents retirés, tous ancrés ; « SII » face à une page « assiette » seulement, non ancré.
  - Les assertions existantes de `test_crawler_dead_or_expired_detection` doivent passer inchangées.
  - Vérification : même commande pytest.
- [x] Step 5: Doc. Sous-section « Crawl4AI : statuts, métriques et replis » dans `docs/JOB_INGESTION_AND_NORMALIZATION.md`, après la section Tavily, avec :
  - le tableau des statuts ;
  - `by_domain` dans le log `🎯 Ultra-simple terminé` ;
  - l'ordre : lien mort, extraction et ancrage, vide et retry, repli JSON-LD ;
  - les gardes du repli ;
  - l'ancrage normalisé.
  - Vérification : `grep -c 'jsonld_fallback\|grounding_rejected\|by_domain' docs/JOB_INGESTION_AND_NORMALIZATION.md` → ≥ 3.
- [x] Step 6 (teardown): scan d'orphelins borné à `_is_dead_or_expired`.
  - Son corps n'appelle plus que `_dead_or_expired_signal`, sans boucle dupliquée sur `DEAD_OR_EXPIRED_PATTERNS`.
  - `callers_of _is_dead_or_expired` montre encore les appelants existants.
  - Aucune variable ni import laissé sans usage dans les fonctions modifiées, vérifié à la relecture du diff.
  - Relancer tout le DoD.

## Code Review
- Dead code removed: yes. Le corps de `_is_dead_or_expired` se réduit à `return _dead_or_expired_signal(...) is not None`. `DEAD_OR_EXPIRED_PATTERNS` = 3 occurrences (définition + 2 boucles de `_dead_or_expired_signal`). Appelants conservés : `scripts/crawl_bakeoff.py:347` et `test_crawler_dead_or_expired_detection`. Le bloc d'extraction et d'ancrage de la boucle a été déplacé dans `_extract_grounded_offers`, sans copie restante. pyflakes ne signale rien sur `crawler1.py` et `job_offers_collectors.py`.
- Build status: pass. `py_compile` exit 0 sur les deux fichiers, relancé après la dernière modification (un commentaire).
- Type errors: none. Pas de type checker configuré.
- Unintended side effects: none observé, deux changements voulus à connaître :
  - `successful_crawls` baisse mécaniquement : les anciens « success à 0 offre » sont classés `no_extraction` / `llm_error` / `grounding_rejected`. Aucun consommateur de `crawl_results` ne dépend de `status == "success"` (seul lecteur : `regenerate_descriptions.py`, qui lit déjà une mauvaise clé, voir Notes) ;
  - l'ancrage accepte désormais les variantes d'apostrophe, de tiret et d'accent, et refuse un nom d'entreprise ou un poste qui commence au milieu d'un mot. Effet attendu : moins de `grounding_rejected` à tort.
- Security surface touched: yes (lecture de HTML tiers : JSON-LD parsé par `parse_jsonld_job_posting`, un code existant). Semgrep CLI 1.170.0 `--config p/python --config p/secrets` sur `crawler1.py` et `job_offers_collectors.py` : 0 finding, 0 erreur, 2 fichiers scannés. Le MCP semgrep ne lit que les scans déjà envoyés à la plateforme, d'où le CLI local.
- Verdict: ✅ DONE

## Execution Log
- 2026-10-23T20:16Z | claude-code | preflight | done | 74 passed (baseline), py_compile exit 0
- 2026-10-23T20:16Z | claude-code | step 1 | started
- 2026-10-23T20:22Z | claude-code | step 1 | done | `uv run pytest tests/test_job_offers_pipeline.py -q` 23 passed (22 + test_crawler_metrics_by_domain_and_status)
- 2026-10-23T20:22Z | claude-code | step 2 | started
- 2026-10-23T20:25Z | claude-code | step 2 | done | pytest test_job_offers_pipeline 24 passed ; `json.loads(result.extracted_content` L539 avant `_is_empty_crawl(result` L553
- 2026-10-23T20:25Z | claude-code | step 3 | started
- 2026-10-23T20:29Z | claude-code | step 3 | done | pytest test_job_offers_pipeline 25 passed ; `extract_json_ld_valid_through|detect_closure_in_text` = 4 ; contrôle ad hoc collecteur (scratchpad) : 1 seul appel de résumé, sur l'offre JSON-LD
- 2026-10-23T20:29Z | claude-code | step 4 | started
- 2026-10-23T20:36Z | claude-code | step 4 | done | py_compile exit 0 ; pytest test_job_offers_pipeline 26 passed ; diff du fichier de test = 168 insertions, 0 suppression (assertions de `test_crawler_dead_or_expired_detection` intactes) ; baseline rouge sur HEAD : apostrophe, tiret, accents False, AXA/taxation True
- 2026-10-23T20:36Z | claude-code | step 5 | started
- 2026-10-23T20:37Z | claude-code | step 5 | done | `grep -c 'jsonld_fallback\|grounding_rejected\|by_domain' docs/JOB_INGESTION_AND_NORMALIZATION.md` = 5
- 2026-10-23T20:37Z | claude-code | step 6 | started
- 2026-10-23T20:40Z | claude-code | step 6 | done | `callers_of _is_dead_or_expired` : crawl_bakeoff.py + test ; grep `DEAD_OR_EXPIRED_PATTERNS` = 3 ; pyflakes vide sur les 2 fichiers
- 2026-10-23T20:40Z | claude-code | close-out | DoD complet | py_compile exit 0 ; test_job_offers_pipeline 26 passed ; test_offer_sources + test_job_offers_collectors_queries 52 passed ; by_domain 3 ; gardes 4 ; ordre L540 < L554 ; motifs 3 ; hors service (TEST-NET + proxy mort) 4 passed
- 2026-10-23T20:42Z | claude-code | close-out | done | diff relu en entier, commentaire d'ancrage corrigé (exemple AXA/taxation), py_compile exit 0 et tests `-k crawler` hors service 7 passed après correction ; semgrep 0 finding

## Notes
- Lecture des métriques après déploiement : une semaine de collecte, puis agréger les lignes `🎯 Ultra-simple terminé` des logs Airflow (`collect_job_offers_granular`) par domaine et par statut. Le chemin exact des logs sur le VPS est à confirmer au moment de la lecture. Décisions attendues des données :
  - (a) `text:<motif>` fréquent sur des domaines dont les offres sont vivantes : restreindre `DEAD_OR_EXPIRED_PATTERNS` (L514) ;
  - (b) `empty_content` élevé sur un domaine dont `result.html` contient l'offre : seuil 500 ou `raw_markdown` (L530) ;
  - (c) `llm_error` non nul : quota ou contexte du modèle de crawl.
- Coût : aucun appel LLM ajouté dans le crawler, le repli JSON-LD lit le HTML déjà téléchargé. Seul ajout : `summarize_offers` sur les offres récupérées par repli, au même coût unitaire que le chemin zero-token. Si le repli est très fréquent sur un domaine, c'est un domaine à passer en zero-token httpx en amont.
- Bug préexistant hors périmètre : `regenerate_descriptions.py:107` lit `crawl_res.get("results", [])`, alors que la clé est `crawl_results`. `results_meta` est donc toujours vide, et seule l'absence d'offres déclenche le repli de description. À traiter à part.
- Dépendance de doc : `docs/JOB_INGESTION_AND_NORMALIZATION.md` est aussi édité par `20261023-jobspy-hellowork-source`. Exécuter l'un après l'autre, pas en parallèle.
- Exécution 2026-10-23 (claude-code). Conventions lues : `CLAUDE.md` (identique à `AGENTS.md` et `GEMINI.md`), `.cursorrules`. Plan HelloWork déjà `done` : la doc partagée n'est plus éditée en parallèle.
- Revue critique (phase 2), deux précisions d'exécution, sans changement de périmètre :
  - Étape 2 : `_offer_grounded_in_page` renvoie `True` quand `page_text` est vide (« ne pas rejeter à l'aveugle »). Accepter une offre avant le test de vide sur cette seule base transformerait un crawl échoué ou vide en `success`. L'acceptation anticipée exige donc un crawl `success` et un texte de page non vide ; sinon le chemin vide / retry s'applique comme avant.
  - DoD « Tests sans service externe » : `docker stop` des conteneurs Mongo couperait la base locale aux autres sessions ouvertes. Preuve équivalente retenue : lancer les 4 tests avec `MONGO_LOCAL_TEST_HOST=192.0.2.1` (adresse TEST-NET, injoignable) et `HTTP_PROXY`/`HTTPS_PROXY=http://127.0.0.1:9` (tout appel réseau échoue). Le conftest n'a qu'une fixture autouse de nettoyage, sous `try/except`.
- Baseline préflight (2026-10-23T20:16Z) :
  - `py_compile` : exit 0 ;
  - `pytest tests/test_job_offers_pipeline.py tests/test_offer_sources.py tests/test_job_offers_collectors_queries.py -q` : 74 passed en 122 s ;
  - `by_domain` : 0, `extract_json_ld_valid_through|detect_closure_in_text` : 0 (attendu, rien d'implémenté) ;
  - ordre : `_is_empty_crawl(result` L530 avant `json.loads(result.extracted_content` L590 (à inverser) ;
  - `DEAD_OR_EXPIRED_PATTERNS` : 3 occurrences.
- Écarts d'exécution (étapes 1 à 3), sans élargissement des fichiers touchés :
  - nouveau helper privé `_extract_grounded_offers(blocks, page_text, url) -> (offers, status, error)`, absent de la liste des symboles du plan. Il porte le tri des blocs `error: True`, le repli entreprise par URL et la boucle d'ancrage, sortis de la boucle principale. Le `json.loads` reste dans la boucle, pour que le contrôle d'ordre du DoD reste lisible ;
  - `json_error` est classé après le test de vide (le retry réseau garde la priorité) et il est éligible au repli JSON-LD, que l'énumération de l'étape 3 omettait. Son log passe d'error à warning (format commun aux autres pertes) et son entrée gagne `domain` et `attempts` ;
  - l'entrée `jsonld_fallback` porte `recovered_from` (statut d'origine), pour garder la cause de perte dans les métriques ;
  - `test_crawler_keeps_grounded_offer_on_short_page` couvre aussi le cas négatif : texte vide, statut `empty_content`, conformément à la précision de revue de l'étape 2.
- Écarts d'exécution (étape 4) :
  - borne de mot à gauche seulement (`f" {x}"` dans `f" {page}"`), au lieu des deux côtés prévus. Une borne à droite rejetterait des cas que l'ancien code acceptait (« Data Engineer » face à « Data Engineers »), ce qui créerait de nouvelles pertes `grounding_rejected`. La borne gauche suffit à bloquer un sigle au milieu d'un mot. Ce choix est couvert par un cas « pluriel » dans le test ;
  - l'exemple « SII » / « assiette » du plan ne marche pas : « assiette » ne contient pas « sii », l'ancien code renvoyait déjà False. Il est remplacé par « AXA » / « taxation », que l'ancien code ancrait à tort (True sur HEAD) ;
  - `normalize_text` est importé au niveau du module, à côté de `app.services.normalization` : `relevance.py` est un module pur, sans dépendance lourde.
