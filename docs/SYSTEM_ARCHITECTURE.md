# Conception Architecture Système : SaaS Job-Tracker

Ce plan détaille la structure technique de la plateforme SaaS pour garantir une expérience utilisateur (UX) fluide, particulièrement lors de l'exécution de tâches longues (scraping, évaluations IA, génération de PDF) sans jamais bloquer l'interface.

> **Ref.** : Ce document est le volet *technique* (comment construire). Le volet *produit* (quoi construire) est dans `CAREER_OPS_INTEGRATION_PLAN.md`.

---

## 1. UX & Disposition des Pages (Next.js)

L'interface est segmentée logiquement pour une navigation SaaS fluide.

### A. Structure du Routing (App Router)

| Route | Rôle | État |
|---|---|---|
| `/onboarding` | Wizard multi-étapes : poste, prétentions, upload CV, filtres | ✅ Existe (`app/onboarding/page.tsx`) |
| `/dashboard` | Vue "Summarize" : KPIs globaux, taux de conversion, offres à relancer | ✅ Existe (`app/dashboard/page.tsx`) |
| `/offers` | Liste des offres scrapées (Discovered / Evaluated, filtres min_score & favoris) | ✅ Existe (`app/offers/page.tsx`) |
| `/offers/[id]` | Vue détaillée d'une offre : Match CV Two-Pass (Blocs A-G), verbatim quotes, actions | ✅ Existe (`app/offers/[id]/page.tsx`) |
| `/applications` | Vue unifiée Kanban & Tableau des candidatures, cadences relances J+7/J+1, sidebar | ✅ Existe (`app/applications/page.tsx`) |
| `/pipeline` | Redirection transparente vers `/applications` (vue Kanban par défaut) | ✅ Existe (`app/pipeline/page.tsx`) |
| `/tasks` | Tâches manuelles de l'utilisateur | ✅ Existe (`app/tasks/page.tsx`) |
| `/profile` | Mise à jour du profil candidat (Single Source of Truth, CV, Voice DNA, CRUD) | ✅ Existe (`app/profile/page.tsx`) |
| `/settings/usage` | Suivi de consommation API et quotas (backend `/usage/summary`) | ✅ Backend actif (`routers/usage.py`) |

### B. Feedback Visuel (Spinners & Skeletons)
- **Actions courtes (< 2 secondes)** : Spinners classiques sur les boutons + désactivation pour éviter le double clic.
- **Chargements de page** : Skeleton Loaders (via Tailwind) pour éviter les sauts de contenu lors du fetch depuis MongoDB.

---

## 2. Authentification & Sécurité

### A. Flow JWT (déjà implémenté)
- Module `app/auth.py` avec `get_current_user` injecté via `Depends()` sur les routes protégées.
- Support optionnel `get_current_user_optional` pour les routes de consultation publique/catalogue.
- Tokens JWT signés avec `SECRET_KEY`, expiration configurable (`ACCESS_TOKEN_EXPIRE_MINUTES=30`).

### B. Isolation Multi-Tenant
- **Données Utilisateur Privées** : Chaque document `applications`, `tasks`, `candidate_profile`, `cover_letters`, `api_usage` et `user_quotas` porte un champ `user_id` obligatoire. Toutes les requêtes/mutations filtrent strictement par le `user_id` du token JWT (rejet avec HTTP 403 en cas de mismatch).
- **Catalogue Global d'Offres (`job_offers`)** : Pool partagé alimenté par Zero-Token ATS, Airflow et Crawl4AI. L'état personnel d'un utilisateur vis-à-vis d'une offre (favori, masqué, match score) est découplé dans `user_offer_interactions` (index unique `user_id + offer_id`) pour ne jamais polluer le catalogue commun.
- *(Détails complets dans `JOB_INGESTION_AND_NORMALIZATION.md`)*.

### C. Rate Limiting
- Protéger les routes IA pour éviter qu'un utilisateur ne lance 50 évaluations simultanées (épuisement des quotas API).
- Verrous d'idempotence : la même action (ex: générer une lettre pour la même candidature) ne s'exécute pas deux fois en parallèle.

---

## 3. Schéma de Données (MongoDB)

### A. Modèle Relationnel

```
User (users)
 ├── CandidateProfile (candidate_profile)           [1:1, CV + GitHub + Website + Voice DNA]
 ├── JobOffer (job_offers)                           [Catalogue global partagé]
 │    ├── canonical_title, seniority_level, poste
 │    ├── url (priorité ATS), alternative_urls (multidiffusions)
 │    └── pipeline_stage: discovered | evaluated | expired
 ├── UserOfferInteraction (user_offer_interactions) [1:N, statut perso sur catalogue]
 │    ├── offer_id → JobOffer._id
 │    ├── status: saved | hidden | applied | dismissed
 │    ├── notes: string
 │    └── updated_at: datetime
 ├── JobApplication (applications)                   [1:N]
 │    ├── offer_id → JobOffer._id                    [optionnel, lien offre d'origine]
 │    ├── status: ApplicationStatus enum             [9 valeurs]
 │    └── CoverLetter (cover_letters)                [1:1 par application]
 │         └── versions[]                            [versioning avec guard_report + critic]
 ├── Task (tasks)                                    [1:N, tâches manuelles]
 ├── ApiUsageRecord (api_usage)                      [1:N, logs de consommation]
 └── UserQuota (user_quotas)                         [1:1, limites par tier]
```

### B. State Machine Unifiée (Décision Architecturale)

Deux domaines de responsabilité, un seul flux :

**Offer Pipeline** (automatique, sur `JobOffer.pipeline_stage`) :
```
discovered → evaluated → expired
```
- `discovered` : offre collectée par Airflow/Crawl4AI
- `evaluated` : offre évaluée par l'Auto-Pipeline IA (score 1.0-5.0)
- `expired` : offre détectée comme non-viable (Liveness Gate). Mappe vers `is_deleted=True` existant.

**Application Pipeline** (utilisateur, sur `JobApplication.status`) :
```python
class ApplicationStatus(str, Enum):
    APPLIED = "Candidature envoyée"
    SCREENING = "Première sélection"
    INTERVIEW = "Entretien"
    TECHNICAL_TEST = "Test technique"
    NEGOTIATION = "Négociation"
    OFFER_RECEIVED = "Offre reçue"
    ACCEPTED = "Offre acceptée"
    REJECTED = "Refusée"
    WITHDRAWN = "Retirée"
```

**Pont entre les deux** : un bouton "Postuler" sur une offre `evaluated` crée un `JobApplication` avec `offer_id` lié, et pré-remplit company/position/url/description.

### C. Lien JobOffer ↔ JobApplication

```python
class JobApplication(BaseModel):
    # ... champs existants ...
    offer_id: Optional[PyObjectId] = None  # Lien vers l'offre scrapée d'origine
```

- `offer_id` est `Optional` : les candidatures manuelles (sans offre scrapée) restent possibles.
- Index MongoDB : `db.applications.create_index("offer_id", sparse=True)`.

---

## 4. Architecture Backend & Tâches Asynchrones (FastAPI)

L'IA et le scraping (Crawl4AI) prennent de 15 secondes à plusieurs minutes. Le backend ne doit **jamais** bloquer la requête HTTP du navigateur.

### A. Frontière Airflow vs BackgroundTasks (Décision Architecturale)

| Trigger | Outil | Justification |
|---|---|---|
| **Cron / Batch** (scraping planifié, nettoyage, liveness) | **Airflow** | Déjà en place, orchestration complexe avec retry/dépendances |
| **User-triggered** (générer lettre, évaluer offre, parser CV, scrape URL on-demand) | **FastAPI `BackgroundTasks`** | Suffisant pour mono-instance, léger, pas de broker externe |
| **Scale-up** (>50 users concurrents) | **Migration vers Celery + Redis** | Quand BackgroundTasks sature le process FastAPI |

> **Stratégie de Collecte Airflow ("Demand-Driven")** :
> - Airflow génère les requêtes **dynamiquement** depuis les préférences actives (`CandidateProfile.preferences`) des utilisateurs en base MongoDB, au lieu de requêtes figées.
> - **Pipeline de Normalisation des Rôles** : Chaque rôle cible est normalisé via embeddings sémantiques (`text-embedding-3-small`) + registre d'alias auto-alimenté. Fast path : recherche exacte MongoDB. Slow path : similarité cosinus ≥ 0.85 pour regrouper variantes FR/EN d'un même métier, sans table statique à maintenir manuellement. Permet la **mutualisation multi-utilisateurs** : 100 candidats recherchant `"Ingénieur IA"` et `"AI Engineer"` = 1 seule requête Airflow.
> - **Fréquences optimisées** :
>   - Collecte (`collect_job_offers`) : `0 7,16 * * 1-5` (2x/jour en semaine, captures des parutions nuit + fin matinée).
>   - Liveness (`verify_job_offers`) : `0 2 * * *` (1x/jour la nuit, détection 404/expirations).
>   - Nettoyage (`clean_job_offers`) : `0 4 * * *` (1x/jour la nuit, déduplication et archivage des offres > 30 jours non référencées).
> - *(Détails complets dans `JOB_INGESTION_AND_NORMALIZATION.md`)*.

> Celery + Redis ne sont **pas** ajoutés au docker-compose à ce stade. La migration future est préparée via un module `task_dispatcher.py` qui encapsule les appels `background_tasks.add_task(...)`.

### B. Pattern Asynchrone (BackgroundTasks)

Lorsqu'un utilisateur clique sur *"Générer une Lettre de Motivation"* :
1. **Next.js** envoie un POST `/api/applications/{id}/cover-letter/regenerate`.
2. **FastAPI** valide la demande, crée un document `cover_letters` en statut `pending` dans MongoDB, et retourne un code `202 Accepted`.
3. Le travail lourd est délégué via `background_tasks.add_task()` dans le thread pool FastAPI.
4. Le pipeline LiteLLM exécute 4 agents séquentiels (analyst → writer → critic → reviser) via `litellm.completion()`.
5. Une fois terminé, le statut passe à `ready` dans MongoDB.

### C. Concurrence et Sécurité
- **Idempotence** : vérification `existing = await db["cover_letters"].find_one(...)` avant de relancer.
- **Verrous** : la même action ne s'exécute pas deux fois si l'utilisateur double-clique.
- **Quota Guard** : vérification du quota utilisateur avant chaque action LLM (cf. §6).

---

## 5. Connectivité & Notifications Temps Réel (Feedback Tâches Longues)

Pour que l'utilisateur sache que sa tâche longue est terminée sans avoir à rafraîchir la page.

### Implémentation (Server-Sent Events ou WebSockets)
- **Écoute côté Client** : le client Next.js ouvre une connexion persistante avec FastAPI.
- **États poussés au client** (Push Events) :
  - `{"type": "EVALUATION_STARTED", "job_id": 123, "message": "Analyse de l'offre en cours..."}`
  - `{"type": "EVALUATION_PROGRESS", "job_id": 123, "message": "Match avec votre CV..."}`
  - `{"type": "EVALUATION_SUCCESS", "job_id": 123, "score": 4.5}`
  - `{"type": "COVER_LETTER_READY", "application_id": 456, "message": "Lettre générée"}`
- **UI React (Toasts)** : le client écoute ces événements globalement. Une notification Toast apparaît avec une barre de progression. Les données de la page se mettent à jour automatiquement (Optimistic UI).

---

## 6. Suivi de Consommation API & Quotas (Décision Architecturale)

### A. Points d'Appel LLM Identifiés

**Stack LiteLLM** (pipeline cover letter — 5 rôles/agents par lettre, exécution 100% asynchrone) :

| Agent | Modèle par défaut | Coût estimé/appel |
|---|---|---|
| `offer_analyst` | `openai/gpt-5.6-luna` | ~$0.005 |
| `company_researcher` | `openai/gpt-5.6-luna` | ~$0.005 (recherche web Tavily avec cache TTL 7j) |
| `writer` | `openai/gpt-5.6-sol` | ~$0.015 |
| `critic` | `gemini/gemini-3.8-flash` (cross-provider) | ~$0.002 |
| `reviser` | `openai/gpt-5.6-sol` (conditionnel) | ~$0.015 |

**Stack LangChain** (résumé d'offre) : `gpt-5-nano` → ~$0.002/appel  
**Stack CrewAI** (scraping) : `CREW_LLM_MODEL` → ~$0.01/recherche

### B. Modèle de Tracking

Collection `api_usage` avec `ApiUsageRecord` : `user_id`, `action`, `models_used`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, `latency_ms`, `success`.

Deux points d'interception :
1. **LiteLLM callback** (`litellm.success_callback`) pour le pipeline cover letter.
2. **Wrapper LangChain** (`tracked_summarize()`) pour les résumés d'offre.

### C. Quotas par Tier

| | **Free** | **Advanced** (9.90€/mois) | **Pro** (24.90€/mois) |
|---|---|---|---|
| Lettres de motivation | 5/mois | 30/mois | Illimité |
| Évaluations IA | 20/mois | 100/mois | Illimité |
| CV Tailoring | 2/mois | 15/mois | Illimité |
| Parsing CV | 2/mois | 10/mois | Illimité |
| Interview Prep | 1/mois | 10/mois | Illimité |

### D. Endpoints

| Route | Description |
|---|---|
| `GET /api/usage/me` | Dashboard conso personnel |
| `GET /api/usage/me/summary` | Résumé mensuel |
| `GET /api/admin/usage` | Vue admin globale |
| `GET /api/admin/usage/{user_id}` | Détail par utilisateur |

---

## 7. Composants Existants (État Actuel)

| Composant | Fichier(s) | Statut |
|---|---|---|
| Authentification JWT | `app/auth.py` | ✅ En production |
| Profil candidat riche | `app/models.py` (`CandidateProfile`) | ✅ En production |
| Parsing CV → Profil | `app/services/cv_parser.py` | ✅ En production |
| Collecteurs GitHub/Website | `app/services/profile/collectors/` | ✅ En production |
| Fusion multi-sources profil | `app/services/profile/merge.py` | ✅ En production |
| Pipeline cover letter (5 agents, 100% async) | `job_trackers/cover_letter_crew.py` | ✅ En production, contexte réviseur complet, cache TTL 7j recherche entreprise |
| Letter guards (code pur) | `app/services/letter_guards.py` | ✅ En production |
| Champ voice DNA (style d'écriture) | `app/models.py` (`writing_style` in `CandidateProfile`) | ✅ Exposé en UI |
| Vérification liveness offres | `app/tasks/verify_job_offers.py` | ✅ En production |
| Nettoyage/normalisation offres | `app/services/normalization.py`, `app/tasks/clean_job_offers.py` | ✅ En production |
| Filtrage de pertinence métier | `app/services/relevance.py` | ✅ En production |
| Résumé d'offre via LLM | `app/llm/utils.py` | ✅ En production |
| Scraping CrewAI (3 agents) | `job_trackers/crew.py` | ✅ En production |
| Airflow DAGs | `airflow/dags/` | ✅ En production |
