# Job Ingestion & Normalization

> Mis à jour : 2026-09-25 · Correspond à la session de travail `20260925-collect-sources-and-geo-filter`.

## Vue d'ensemble

Le pipeline de collecte s'exécute via une tâche Airflow (`collect_and_save_offers`) pour chaque requête de recherche générée dynamiquement depuis les préférences candidat (`candidate_profile`).

```
candidate_profile → generate_search_queries
     ↓  (N requêtes « Rôle Ville »)
collect_and_save_offers(query)
     ├─ Stage 1 (parallel): Tavily search (URLs) ‖ Sources structurées (jobspy)
     ├─ Stage 2: drop_known_urls → filtre URLs Tavily déjà en base ou couvertes par offres structurées
     ├─ Stage 3 (parallel): crawl URLs Tavily restantes ‖ résumé LLM offres structurées
     └─ Stage 4: merge → enrich → dedup → save → tag_new_offers
```

---

## Sources

France Travail n'est plus une source depuis le 2026-10-25. L'API « Offres d'emploi v2 » est passée en
accès restreint vers le 2026-10-20 (accès sur demande via francetravail.io), et le domaine n'est pas
cherché par Tavily. Les offres France Travail déjà en base restent traitées comme les autres
(vérification de clôture, priorité de source).

### 1. jobspy (Indeed + LinkedIn + HelloWork)

| Champ | Valeur |
|---|---|
| Module | `app/services/sources/jobboards.py` |
| Indeed | `indeed.fr`, ~15 offres/req, ~1 s |
| LinkedIn | `linkedin.com/jobs`, ~25 offres/req, ~30 s, rayon géo réel |
| HelloWork | `hellowork.com/fr-fr/emplois`, ~25 offres/req, ~12 s (une requête de détail par offre pour la description, `fetch_description=True`) |
| Dépendance | `python-jobspy>=1.4.1` (override numpy conservé, voir ci-dessous) |
| Risque | Scraping public ; un blocage (429 LinkedIn, Cloudflare) ne lève pas d'exception : jobspy le range dans `attrs["errors"]` du DataFrame, loggé en warning `⚠️ <site> en échec`. Les lignes déjà reçues sont gardées, les autres sites ne sont pas touchés |

### 2. Tavily (complément)

| Champ | Valeur |
|---|---|
| Module | `app/tasks/job_offers_collectors.py` + `custom_tool.py` |
| Passe 1 | WTTJ (8 résultats) · APEC+Cadremploi (6) · Free-Work+LesJeudis (6) |
| Passe 2 | ATS : Greenhouse, Lever, Workday, SmartRecruiters, Recruitee, BambooHR, Ashby, Notion |
| Coût | 4 appels « advanced » (2 crédits chacun) par requête |
| Fréquence | Au seul run de 07:00 UTC (`is_web_search_run`, seuil `WEB_SEARCH_MAX_HOUR_UTC = 12`) ; jobspy tourne aux deux runs. Un déclenchement manuel après 12:00 UTC ne lance pas Tavily |
| Indeed, LinkedIn, HelloWork | Retirés de Tavily (couverts par jobspy) |

Garde-fous du crew CrewAI :
- `TavilyJobBoardSearchTool(result_as_answer=True)` : la sortie brute de l'outil est la réponse de
  `execute_search_task`, l'agent ne peut pas y ajouter d'URLs.
- `run_crew` vérifie via `agent.tools_results` que l'outil a réellement été appelé ; sinon une relance,
  puis échec explicite (un agent qui répond sans outil invente des URLs de listing).
- `filter_urls_task` ne garde que des fiches individuelles (toute page listing/SEO exclue), sans plafond,
  et ne rejette jamais une fiche ATS parce que son URL ne cite pas de ville.
- `run_crew` est exécuté via `asyncio.to_thread` : il ne bloque pas les sources structurées.

Offre retirée côté ATS : un 404 de l'API Greenhouse lève `ExpiredOfferError`, l'URL est écartée sans
crawl de repli (la page redirige vers la liste des postes du board, qui serait extraite comme
plusieurs offres hors sujet).

### Crawl4AI : statuts, métriques et replis

Les URLs Tavily qui ne passent pas par un ATS ou par le JSON-LD zero-token sont crawlées par
`crawl_and_extract_jobs_optimized` (`job_crawler/crawler1.py`). L'extraction LLM tourne pendant
`arun_many`, sur le `fit_markdown` de la page. Chaque URL reçoit ensuite un statut final dans
`crawl_results`, avec son `domain` (`netloc` sans `www.`).

| Statut | Signification |
|---|---|
| `success` | Au moins une offre extraite et ancrée dans la page |
| `jsonld_fallback` | Aucune offre LLM gardée, offre récupérée dans le JSON-LD `JobPosting` du HTML ; `recovered_from` garde le statut d'origine |
| `no_extraction` | Le LLM n'a rien renvoyé (`None`, `""` ou `[]`) |
| `llm_error` | Uniquement des blocs `error: True` de `RobustLLMExtractionStrategy` (quota, contexte, réponse illisible) ; le message est dans `error` |
| `grounding_rejected` | Offres extraites, toutes rejetées par l'ancrage (poste et entreprise absents de la page) |
| `json_error` | `extracted_content` n'est pas du JSON valide |
| `empty_content` | Page sous `CRAWL_MIN_PAGE_CHARS` (500 par défaut) sans offre ancrée, après les retries réseau |
| `dead_link` | Lien mort ou offre expirée ; `dead_signal` vaut `http_<code>`, `redirect`, `text:<motif>` ou `html:<motif>` |

Ordre de traitement d'une page :
1. **Lien mort** : `_dead_or_expired_signal`. Sortie immédiate, sans retry ni repli.
2. **Extraction et ancrage** : `_extract_grounded_offers` retire les blocs d'erreur LLM, puis garde
   les offres ancrées. Une offre ancrée dans une page courte reste `success` si le crawl a réussi et
   si le texte de la page n'est pas vide : sur un texte vide, l'ancrage accepte tout par principe.
3. **Vide et retry** : `_is_empty_crawl` ne s'applique qu'en l'absence d'offre ancrée. Seuls les
   échecs réseau ou timeouts sont réessayés (`CRAWL_MAX_RETRIES`).
4. **Repli JSON-LD** : `_jsonld_fallback_offer` lit le HTML déjà téléchargé, sans appel LLM ni
   requête réseau, pour tout statut final autre que `success` et `dead_link`.

Gardes du repli JSON-LD, pour ne jamais réintroduire une offre close :
- `validThrough` passé (`extract_json_ld_valid_through`) : pas de repli ;
- motif de clôture dans le texte visible (`detect_closure_in_text`, par exemple « Ce poste a été
  pourvu ») : pas de repli.

L'offre récupérée porte `ats_platform: "json_ld"`. Dans `crawl_urls_for_offers`, ces offres passent
par `summarize_offers`, comme les offres zero-token. Les offres extraites par le LLM du crawler ne
sont pas résumées une seconde fois.

**Ancrage normalisé** (`_offer_grounded_in_page`) : poste et entreprise sont comparés au texte de
la page après `normalize_text` (minuscules, accents retirés, ponctuation remplacée par une espace).
Une apostrophe typographique, un tiret demi-cadratin ou un accent omis par le LLM ne font plus
rejeter l'offre. La borne de mot est à gauche seulement : un sigle court (« AXA ») ne s'ancre plus au
milieu d'un mot (« taxation »), un pluriel (« Data Engineers ») reste ancré.

**Métriques** : le log `🎯 Ultra-simple terminé` imprime le `summary`, qui contient les compteurs
`successful_crawls`, `empty_crawls`, `dead_links`, `no_extraction`, `llm_error`,
`grounding_rejected`, `jsonld_fallback`, `retried_urls`, `total_offers`, plus `by_domain`
(`{domain: {statut: n}}`). Agréger ces lignes dans les logs Airflow par domaine et par statut montre
où le crawl perd des offres. Un `successful_crawls` plus bas qu'avant ce découpage n'est pas une
régression : les anciens « succès à 0 offre » sont désormais classés `no_extraction`, `llm_error`
ou `grounding_rejected`.

---

## Déduplication (clé d'identité)

**Clé d'une offre** : `linkedin:<id>` si l'URL est LinkedIn (l'URL varie selon slug), sinon l'URL canonique.  
Lookup sur `url` + `alternative_urls`, soft-deleted inclus.

**`drop_known_urls`** (stage 2) : filtre les URLs Tavily avant crawl pour éviter de payer crawl + LLM sur un doublon.  
**`clean_duplicate_offers`** (stage 4) : rattrape les doublons inter-sources par `(entreprise, poste, ville)`, en mémoire sur le lot puis contre la base à l'enregistrement (`save_offers_to_database`).

- **Entreprise** : `company_match_strength` compare les jetons alphanumériques sans accents du nom normalisé.
  - Règle forte : mêmes jetons (« BackMarket » / « Back Market », « Néosoft » / « Neosoft ») ou ratio ≥ 0.85. L'intitulé suffit alors à conclure (égal ou ratio ≥ 0.82).
  - Règle faible : les jetons d'un nom sont le début de l'autre (« JEMS » / « Jems Group »). La fusion exige en plus des descriptions proches (Jaccard ≥ 0.5).
- **Ville** : comparée sous forme repliée, sur le segment avant la première virgule. « Champagne-Au-Mont-D'Or » / « D’Or » et « Lyon, Auvergne-Rhône-Alpes, France » / « Lyon » sont donc compatibles. Une ville générique (Non spécifié, France, Télétravail, Remote) l'est avec toutes.
- **Doublons déjà en base** : `backend/retroactive_dedup_job_offers.py` liste les paires en simulation, sans écrire. `--apply` les fusionne. L'offre liée à une candidature, une évaluation ou un kit d'entretien survit. Une paire dont les deux offres sont liées est sautée et signalée. Les interactions du doublon sont rattachées au survivant.
- **Même règle partout** : chaque nuit, l'étape 3 du nettoyage `cleanup_job_offers` applique en écriture la fusion du script (`merge_duplicate_offers`, dans `app/services/offer_dedup.py`). L'offre créée depuis une candidature passe par la même recherche que l'insertion : clé unique, URL principale ou alternative, puis variante du nom d'entreprise.

---

## Filtres appliqués

### Filtre de pertinence des intitulés (sources structurées seulement)

- **Technique** : embedding cosinus rôle cible vs intitulé de l'offre.
- **Seuil** : 0.40 (fail-open : si le calcul échoue, l'offre est conservée).
- **Calibration** :

| Paire | Score |
|---|---|
| Data Scientist vs Data Analyst | 0.52–0.59 |
| Data Scientist vs Lead Tech Data | 0.41 |
| Data Scientist vs AI Engineer | 0.35 ✗ |
| Métiers hors sujet | < 0.33 ✗ |

> Tavily n'a pas ce filtre : le prompt CrewAI assure déjà la pertinence.

### Filtre géographique (toutes sources, fail-open)

**Module** : `app/services/sources/geo.py`  
**API** : `geo.api.gouv.fr` (gratuite, sans clé)  
**Rayon** : 50 km autour de la ville cible

Une offre est **rejetée uniquement sur preuve** :

| Condition | Action |
|---|---|
| Pays étranger cité dans `localisation` | Rejet, sauf ville frontalière connue (`BORDER_CITIES`) à 60 km ou moins de la ville cible (`BORDER_RADIUS_KM`) |
| Commune française > 50 km de la cible | Rejet |
| Localisation inconnue + locale d'URL étrangère (hors `en-*`) | Rejet |
| Localisation inconnue, URL neutre | **Conservée** (fail-open) |
| Télétravail / France entière / Remote | **Conservée** |
| Commune non résolue par l'API | **Conservée** |
| Multi-sites citant la ville cible (`Saint-Étienne / Lyon`) | **Conservée** |

---

## Dépendances notables

### numpy override (python-jobspy vs crawl4ai)

`python-jobspy` 1.1.x exigeait `numpy==1.26.3`, incompatible avec `crawl4ai`, `chromadb` et `onnxruntime` (qui requièrent `numpy>=2`). Depuis 1.4.1, jobspy ne pinne plus numpy : `requirements.txt` résout directement une numpy 2.x.

**Solution retenue** (conservée, inoffensive depuis 1.4.1) : override inline dans les Dockerfiles via `--override` :

```dockerfile
RUN echo "numpy>=2.1" > /tmp/numpy_override.txt && \
    uv pip install -r requirements.txt --override /tmp/numpy_override.txt
```

> `[tool.uv] override-dependencies` dans `pyproject.toml` n'est **pas** honoré par `uv pip install` (seulement par `uv sync`).

### Cooldown des dépendances (uv)

`backend/pyproject.toml`, section `[tool.uv]` :

```toml
exclude-newer = "7 days"
exclude-newer-package = { python-jobspy = false }
```

`uv lock` et `uv pip compile` ignorent toute version publiée depuis moins de 7 jours : une release compromise a le temps d'être retirée avant d'entrer dans le lock. `python-jobspy` 1.4.1 (publiée le 2026-10-23) en est exemptée ; **retirer l'exemption après le 2026-10-30**.

L'installeur uv est épinglé dans les deux images (`ADD https://astral.sh/uv/0.13.1/install.sh` dans `backend/Dockerfile` et `backend/Dockerfile.airflow`) : un rebuild n'embarque pas une nouvelle version d'uv sans changement explicite.

---

## Normalisation des offres entrantes

Toutes les offres (structurées ou Tavily) passent par le même chemin final :

```
dict brut
  → summarize_offers (LLM, semaphore=8)   # champ résumé, extraction poste/entreprise/localisation
  → normalize_city(localisation)            # accents, arrondissements, casse
  → enrich_offers                           # source_domain, favicon, score similarité
  → clean_duplicate_offers                  # dedup inter-sources
  → save_to_db                              # upsert sur url + alternative_urls
  → tag_new_offers                          # marquage `is_new=True`
```

### Type de contrat (`detect_contract_type`)

`enrich_offers` calcule `type_contrat` avec `detect_contract_type(type_contrat, poste, description)`
(`app/services/normalization.py`). L'appel se fait sur l'intitulé **brut** : `clean_job_title_syntax`
retire ensuite « Stage » du `poste` affiché. Ordre de décision :

1. « Stage » ou « Alternance » dans l'intitulé brut : la valeur est retenue même si la source dit CDI.
   Certains ATS déclarent CDI pour un stage (cas SmartRecruiters). Les deux mots ensemble donnent
   « Stage / Alternance ».
2. Sinon, la valeur de la source si elle est reconnue, mise sous forme canonique (`Permanent` → CDI,
   `CDD / Temporaire` → CDD, etc.).
3. Sinon, les autres mots-clés de l'intitulé (Freelance, CDI, CDD, Intérim).
4. Sinon, les marqueurs forts de la description, pour le stage et l'alternance seulement. Exemples :
   « Le stagiaire… » en début de phrase, « stage de 3 à 4 mois », « contrat d'apprentissage ».
5. Sinon, la valeur source d'origine si elle n'est pas vide, ou « Non spécifié ».

Garde-fous contre les faux stages, pour ne pas masquer un CDI :

- « early-stage » / « seed stage » (stade de startup) ne compte pas ;
- « apprentissage automatique » (machine learning) ne compte pas ;
- un CDI qui « encadrera des stagiaires » ne compte pas ;
- une mention optionnelle (« éventuellement sous la forme d'un stage ») ne compte pas.

Le filtre « Mes contrats ciblés » de la page Offres envoie `CDI|CDD|Freelance`. Côté API,
`_build_contract_type_filter` (`routers/job_offers.py`) exclut alors toute offre dont `type_contrat`
contient `stage` ou `alternance`. Les « Non spécifié » restent visibles. Un stage n'est donc masqué
que si son contrat a été déduit.

Rattrapage de la base existante avec `backend/backfill_contract_types.py`. Le script fonctionne en
simulation par défaut : il liste chaque changement et le décompte par transition. Avec `--apply`, il
écrit `type_contrat` sans toucher `updated_at`.

```bash
docker exec -w /app -e PYTHONPATH=/app jobtracker-backend python backfill_contract_types.py           # simulation
docker exec -w /app -e PYTHONPATH=/app jobtracker-backend python backfill_contract_types.py --apply   # écriture
```

### Données d'origine (`raw_data`)

`raw_data` conserve l'enregistrement renvoyé par la source, pas la copie normalisée de l'offre. On peut
ainsi ré-extraire un champ plus tard (niveau, salaire chiffré, secteur…) sans recollecter.

- Chaque mapper ou extracteur ajoute une clé `source_record` au dict de l'offre :
  - ligne jobspy (`map_jobboard_row`) : cellules vides retirées, dates en ISO, car BSON n'encode pas
    `datetime.date` ;
  - item France Travail (offres collectées avant le retrait de la source) ;
  - payload Greenhouse, Lever, Workable, SmartRecruiters ou Indeed GraphQL ;
  - objet JobPosting (JSON-LD).
- `enrich_offers` range cet enregistrement sous la clé de sa source, `{ats_platform: source_record}`
  (par exemple `{"linkedin": {...}}`). La clé `source_record` ne reste pas au premier niveau du
  document. Une offre extraite par le LLM du crawler n'a pas d'enregistrement d'origine : elle est
  stockée sous `llm_crawl`.
- `merge_multidiffusion_offers` (étape 13) fait l'union des enregistrements par source. Sur une même
  source, l'offre entrante l'emporte. Une offre multidiffusée garde donc à la fois la ligne LinkedIn
  (`job_level`, `job_function`) et la ligne Indeed (salaire chiffré, `company_industry`). Deux
  chemins partagent une clé : `indeed` (jobspy et GraphQL) et `hellowork` (jobspy et JSON-LD). Le
  plus récent l'emporte.
- Ancien format : avant ce changement, `raw_data` était une copie à plat de l'offre. Il est remplacé
  dès qu'une collecte retrouve l'offre avec un vrai enregistrement d'origine, et conservé sinon.
  Aucun rattrapage n'est possible, puisque l'origine n'a jamais été stockée.

---

## Purge des offres hors zone (base existante)

Script one-shot + rejouable : `backend/scripts/purge_out_of_zone_offers.py`

```bash
# Audit (aucune modification)
cd backend
python scripts/purge_out_of_zone_offers.py

# Appliquer (confirmation interactive)
python scripts/purge_out_of_zone_offers.py --delete

# Rayon personnalisé
python scripts/purge_out_of_zone_offers.py --radius 30 --delete
```

Le script extrait la ville cible depuis `source_query` de chaque offre.  
Les offres sans `source_query` sont skippées (pas de référence pour décider).  
Les offres liées à une candidature sont expirées (soft-delete) plutôt que supprimées.

### Suppression manuelle d'une offre (API)

`DELETE /job-offers/{id}` et `PATCH /job-offers/{id}/soft-delete` sont réservés aux administrateurs (`get_current_admin_user`).
`DELETE` passe par `safe_delete_or_expire_offer` (`app/tasks/clean_job_offers.py`), la même règle que les purges : une offre liée à une candidature est conservée et marquée expirée (réponse « Offre liée à une candidature : conservée et marquée expirée »), les autres sont supprimées.

Si l'offre d'origine d'une candidature a malgré tout disparu, `_ensure_offer_for_application` (`app/routers/applications.py`) lui rattache une nouvelle entrée `job_offers`, puis `_migrate_user_offer_data` y déplace l'évaluation (`offer_evaluations`) et le kit d'entretien (`interview_preps`) de l'utilisateur, sans écraser un document déjà présent pour le nouvel `offer_id`.

---

## Vérification de disponibilité (liveness)

DAG `verify_job_offers` (`0 7 * * *`, 200 offres par run) → `backend/app/tasks/verify_job_offers.py`.
Rotation : les offres jamais vérifiées passent d'abord, puis celles dont `last_verified_at` est le plus ancien. Chaque offre contrôlée (`valid`, `closed` ou `unknown`) reçoit `last_verified_at`, donc tout le stock actif est revérifié en N/200 jours environ.
Une offre close **confirmée** est archivée en soft-delete (`is_deleted=True`, `pipeline_stage: "expired"`, `deletion_reason`), écrit au fil de l'eau : un run coupé par `execution_timeout` garde les archivages déjà faits.
Toute erreur transitoire (5xx, timeout, connexion, échec headless) donne un statut `unknown` : aucune suppression.

Signaux de clôture, dans l'ordre (requête HTTP, puis rendu headless Crawl4AI si la page semble active, sauf Indeed) :

| Signal | `deletion_reason` |
|---|---|
| HTTP 404 / 410 | `http_status_404` / `http_status_410` |
| JSON-LD `JobPosting.validThrough` dépassé | `jsonld_valid_through_expired: <date>` |
| Redirection vers un listing générique (racine, `/jobs`, `/careers`…) ou LinkedIn `?trk=expired_jd_redirect` (offre purgée) | `redirected_to_generic_listing` |
| Texte de clôture dans le texte visible (`CLOSED_TEXT_PATTERNS`, sans `script`/`style`/`aside`) | `static_closed_text: '<extrait>'` (`js_dom_closed_text` en headless) |

Bandeaux plateformes couverts par `CLOSED_TEXT_PATTERNS` (liste non exhaustive) : LinkedIn « Les candidatures ne sont plus acceptées » / « No longer accepting applications », Indeed « Cette offre a expiré sur Indeed », WTTJ, Apec, France Travail, HelloWork. Un nouveau bandeau = un motif + un cas dans `test_detect_closure_in_text_real_world_platform_variants`.

---

## Limites connues et CGU

- **jobspy** scrape les pages publiques d'Indeed, LinkedIn et HelloWork sans API officielle. Blocages 429 possibles, signalés par `attrs["errors"]` et loggés en warning. Tavily ne cherche plus sur ces trois sites : un blocage n'y est pas compensé.
- **Tavily** : plafond d'appels "advanced" par mois (surveiller la facturation).
- **Liveness Indeed** : `viewjob` répond 401 Cloudflare en HTTP, et le rendu headless expirait (60 s, `networkidle`) : il est désormais sauté (`headless_skipped_antibot_domain`). Seules les clôtures visibles en HTTP (404/410, JSON-LD, redirection, bandeau) archivent une offre Indeed ; les autres restent `unknown`. La purge par âge `cleanup_old_offers` reste désactivée par choix (`enable_old_offers_cleanup=False` dans le DAG `clean_job_offers`) : la date seule n'est pas un signal de clôture.
- **France Travail** : source retirée le 2026-10-25. L'API « Offres d'emploi v2 » n'est plus en libre-service ; la réactiver demande un accès accordé sur demande via [francetravail.io](https://francetravail.io/contact).
