# Job Ingestion & Normalization

> Mis à jour : 2026-09-25 · Correspond à la session de travail `20260925-collect-sources-and-geo-filter`.

## Vue d'ensemble

Le pipeline de collecte s'exécute via une tâche Airflow (`collect_and_save_offers`) pour chaque requête de recherche générée dynamiquement depuis les préférences candidat (`candidate_profile`).

```
candidate_profile → generate_search_queries
     ↓  (N requêtes « Rôle Ville »)
collect_and_save_offers(query)
     ├─ Stage 1 (parallel): Tavily search (URLs) ‖ Sources structurées (France Travail + jobspy)
     ├─ Stage 2: drop_known_urls → filtre URLs Tavily déjà en base ou couvertes par offres structurées
     ├─ Stage 3 (parallel): crawl URLs Tavily restantes ‖ résumé LLM offres structurées
     └─ Stage 4: merge → enrich → dedup → save → tag_new_offers
```

---

## Sources

### 1. API France Travail (officielle)

| Champ | Valeur |
|---|---|
| Module | `app/services/sources/france_travail.py` |
| Couverture | `francetravail.fr` (offres de l'opérateur public) |
| Filtre | commune + rayon 30 km + contrat + date (30 j) |
| Auth | `FRANCE_TRAVAIL_CLIENT_ID` / `FRANCE_TRAVAIL_CLIENT_SECRET` (env) |
| Fallback | Si clés absentes → source ignorée, `francetravail.fr` reste couvert via Tavily |

**Note codes communes** : Paris/Lyon/Marseille doivent utiliser le code d'arrondissement central :
- Paris (`75056`) → `75101`
- Lyon (`69123`) → `69381`
- Marseille (`13055`) → `13201`

### 2. jobspy (Indeed + LinkedIn)

| Champ | Valeur |
|---|---|
| Module | `app/services/sources/jobboards.py` |
| Indeed | `indeed.fr`, ~15 offres/req, ~1 s |
| LinkedIn | `linkedin.com/jobs`, ~25 offres/req, ~30 s, rayon géo réel |
| Dépendance | `python-jobspy>=1.1.82` (numpy override requis, voir ci-dessous) |
| Risque | Scraping public ; blocage 429 possible → Tavily LinkedIn prend le relais |

### 3. Tavily (complément)

| Champ | Valeur |
|---|---|
| Module | `app/tasks/job_offers_collectors.py` + `custom_tool.py` |
| Passe 1 | WTTJ (8 résultats) · APEC+Cadremploi (6) · HelloWork (6) · Free-Work+LesJeudis (6) · francetravail.fr si API absente (6) |
| Passe 2 | ATS : Greenhouse, Lever, Workday, SmartRecruiters, Recruitee, BambooHR, Ashby, Notion |
| Passe 3 | LinkedIn en secours (si jobspy 429) |
| Coût | 6-7 appels « advanced » / requête (était 3 avant) |
| Indeed | Retiré de Tavily (couvert par jobspy) |

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

---

## Déduplication (clé d'identité)

**Clé d'une offre** : `linkedin:<id>` si l'URL est LinkedIn (l'URL varie selon slug), sinon l'URL canonique.  
Lookup sur `url` + `alternative_urls`, soft-deleted inclus.

**`drop_known_urls`** (stage 2) : filtre les URLs Tavily avant crawl pour éviter de payer crawl + LLM sur un doublon.  
**`clean_duplicate_offers`** (stage 4) : rattrape les doublons inter-sources par `(entreprise normalisée, poste normalisé, ville)`.

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
| Pays étranger cité dans `localisation` | Rejet |
| Commune française > 50 km de la cible | Rejet |
| Localisation inconnue + locale d'URL étrangère (hors `en-*`) | Rejet |
| Localisation inconnue, URL neutre | **Conservée** (fail-open) |
| Télétravail / France entière / Remote | **Conservée** |
| Commune non résolue par l'API | **Conservée** |
| Multi-sites citant la ville cible (`Saint-Étienne / Lyon`) | **Conservée** |

---

## Dépendances notables

### numpy override (python-jobspy vs crawl4ai)

`python-jobspy>=1.1.82` exige `numpy==1.26.3`, incompatible avec `crawl4ai`, `chromadb` et `onnxruntime` (qui requièrent `numpy>=2`).

**Solution retenue** : override inline dans les Dockerfiles via `--override` :

```dockerfile
RUN echo "numpy>=2.1" > /tmp/numpy_override.txt && \
    uv pip install -r requirements.txt --override /tmp/numpy_override.txt
```

> `[tool.uv] override-dependencies` dans `pyproject.toml` n'est **pas** honoré par `uv pip install` (seulement par `uv sync`).

### Variables d'environnement requises

| Variable | Service(s) | Obligatoire |
|---|---|---|
| `FRANCE_TRAVAIL_CLIENT_ID` | backend, airflow | Non (source ignorée si absent) |
| `FRANCE_TRAVAIL_CLIENT_SECRET` | backend, airflow | Non |

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

---

## Limites connues et CGU

- **jobspy** scrape les pages publiques d'Indeed et LinkedIn sans API officielle. Blocages 429 possibles ; Tavily LinkedIn est le fallback.
- **Tavily** : plafond d'appels "advanced" par mois (surveiller la facturation).
- **France Travail API** : nécessite une application inscrite sur [francetravail.io](https://francetravail.io) abonnée à « Offres d'emploi v2 ».
