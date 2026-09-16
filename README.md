# Job Tracker 🚀

Job Tracker est une application web moderne et automatisée pour centraliser vos candidatures, automatiser la veille et le scraping intelligent d'offres d'emploi (via IA, CrewAI, Tavily et Crawl4AI) et suivre vos entretiens et relances.

---

## 🏗️ Architecture & Technologies

- **Frontend** : Next.js (App Router), React, TailwindCSS, Axios, React Icons, Cookies de session proactifs, Vue unifiée Kanban & Tableau (`/applications`), Wizard d'onboarding (`/onboarding`).
- **Backend API** : FastAPI, Pydantic v2, Motor / PyMongo, JWT Auth (Access + Refresh Tokens avec support optionnel pour catalogue).
- **Automatisation & Scheduling** : Apache Airflow (DAGs de collecte quotidienne, nettoyage des doublons et soft-delete synchronisé).
- **Ingestion & Normalisation en 4 Couches** :
  - **Zero-Token ATS & JSON-LD Router** : Connecteurs HTTP directs pour Greenhouse, Lever, Workable et Schema.org JSON-LD (Ashby, Teamtailor, Personio, Recruitee) extrayant du JSON structuré à coût token nul (0 token LLM).
  - **Funnel de Recherche Additif (CrewAI & Tavily)** : Partitionnement équilibré en 3 passes (Job boards nationaux max 12, ATS direct entreprises max 10, LinkedIn Jobs max 8).
  - **Normalisation en 4 Couches** : Nettoyage syntaxique des scories employeur `(H/F), CDI, [LYON], 🚀`, extraction de séniorité, déduplication floue Levenshtein + Jaccard de descriptions, et fusion multi-sources avec priorité aux URLs ATS et consolidation des salaires et liens alternatifs.
  - **Découplage Multi-Tenant** : Isolation des statuts personnels (Sauvegardée, Masquée, Postulée, Score de matching) dans `user_offer_interactions` pour préserver l'intégrité du pool partagé `job_offers`.
- **Évaluation d'Offre Two-Pass (Career-Ops IA)** :
  - Sas d'évaluation en 2 passages avec Gemini 3.7 Flash : extraction d'exigences pondérées suivie du matching contre le profil candidat complet (CV, stack, formations, projets GitHub).
  - Score 1.0 à 5.0, citations *verbatim* obligatoires et drapeaux rouges consultables sur `/offers/[id]` et directement dans la sidebar du Kanban.
- **Génération de Lettres de Motivation (Multi-Agents CrewAI)** :
  - Pipeline à 4 rôles : Analyste de cadrage (GPT-5.6 Luna), Rédacteur de premier jet (GPT-5.6 Sol), Critique de style multi-fournisseur obligatoire (Gemini 3.8 Flash, cross-provider) et Réviseur conditionnel (GPT-5.6 Sol).
  - Recherche en direct sur l'entreprise via Tavily et intégration du style rédactionnel personnel du candidat (Voice DNA).
  - Garde-fous déterministes stricts (longueur, connecteurs, ponctuation, entités autorisées, anti-hallucination).
- **Base de données** : MongoDB avec index composites uniques, soft-delete (`pipeline_stage: "expired"`), et protection contre la suppression physique des offres liées à des candidatures.

---

## 📋 Prérequis

- **Docker** et **Docker Compose**
- **Git**
- Clés API :
  - `OPENAI_API_KEY` (requis — GPT-5.6 Sol pour la rédaction, Luna pour l'extraction)
  - `TAVILY_API_KEY` (pour la recherche d'offres ciblées)
  - `GEMINI_API_KEY` (requis — Gemini 3.8 Flash pour le critique cross-provider)

---

## 🚀 Installation & Démarrage

### 1. Cloner le dépôt
```bash
git clone https://github.com/votre-username/job-tracker.git
cd job-tracker
```

### 2. Configuration d'environnement
Créez un fichier `.env` à la racine du projet :

```env
# Sécurité & Authentification JWT
SECRET_KEY=votre_cle_secrete_generee_aleatoirement
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# MongoDB
DATABASE_NAME=job_tracker
MONGO_USER=mongo_user
MONGO_PASSWORD=votre_mot_de_passe_securise
MONGO_HOST=mongodb

# Interface d'administration Mongo Express (http://localhost:8081)
MONGO_EXPRESS_USER=admin
MONGO_EXPRESS_PASSWORD=admin_password

# Airflow
AIRFLOW_SECRET_KEY=votre_cle_airflow

# Moteurs IA & Scraping
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
GEMINI_API_KEY=AQ...
```

> **Astuce** : Pour générer une clé secrète sécurisée :
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```

### 3. Lancer l'application avec Docker Compose
```bash
docker compose up -d
```

Cette commande démarre les 6 services :
1. `frontend` : Interface utilisateur ([http://localhost:3875](http://localhost:3875))
2. `backend` : API REST FastAPI ([http://localhost:8000](http://localhost:8000), docs sur [/docs](http://localhost:8000/docs))
3. `airflow` : Orchestrateur et planificateur de tâches ([http://localhost:8080](http://localhost:8080))
4. `mongodb` : Base de données NoSQL
5. `mongo_test` : Base MongoDB isolée pour les tests
6. `mongo-express` : Interface visuelle pour explorer la base ([http://localhost:8081](http://localhost:8081))

---

## 🎯 Recherche Automatisée : Profil → Requêtes Dynamiques

Le système génère automatiquement les requêtes de collecte d'offres en temps réel depuis votre profil candidat, sans codage requérir. Deux niveaux de personnalisation :

### 1. Configurer votre Profil Candidat (Interface Web)
Accédez à `/profile` et remplissez vos préférences de recherche :

- **Rôles Cibles** : ex. `Data Engineer`, `AI Engineer`, `Machine Learning Engineer` (format libre, normalisés automatiquement via embeddings).
- **Villes** : ex. `Lyon`, `Paris`, `Remote`.
- **Politique de Télétravail** : `Full Remote`, `Hybrid`, `On-Site`.
- **Types de Contrat** : `CDI`, `Freelance`, `Stage`, etc.

Le système génère des requêtes multi-profils (si plusieurs utilisateurs), avec :
- **Normalisation sémantique** : `"Ingénieur IA"` et `"AI Engineer"` sont regroupés sous le même rôle canonique.
- **Round-Robin équitable** : chaque profil candidat contribue à la collecte sans favoritisme.
- **Plafonnement intelligent** : max 8 requêtes/run Airflow pour rester dans le budget de temps.

### 2. Ajuster la Fréquence de Collecte (Airflow Cron)
Fichier : [`airflow/dags/collect_job_offers.py`](file:///Users/elielkatche/job-tracker/airflow/dags/collect_job_offers.py)

Par défaut, le DAG s'exécute **2 fois par jour en semaine** (7h & 16h UTC, lun-ven) :
```python
schedule="0 7,16 * * 1-5"  # Capte les parutions de nuit et du jour
```

### 3. Affiner la Qualification IA (CrewAI)
Dossier : [`backend/job_trackers/src/job_trackers/config/`](file:///Users/elielkatche/job-tracker/backend/job_trackers/src/job_trackers/config/)

- **`agents.yaml`** : Expertise des agents (tech, marketing, finance, RH, etc.).
- **`tasks.yaml`** : Consignes de filtrage dans `filter_urls_task` :
  - Niveau d'expérience souhaité.
  - Modalités acceptées.
  - Technologies/compétences obligatoires ou mots-clés exclus.

### 4. Cibler ou Exclure des Sites d'Emploi (Tavily & Crawler)
Fichier : [`backend/job_trackers/src/job_trackers/tools/custom_tool.py`](backend/job_trackers/src/job_trackers/tools/custom_tool.py)

- **Plateformes vérifiées** (`verified_domains`) :
  ```python
  verified_domains = [
      # Job boards qualifiés (France & Cadres)
      "welcometothejungle.com",
      "apec.fr",
      "francetravail.fr",
      "hellowork.com",
      "cadremploi.fr",
      "free-work.com",
      "linkedin.com",
      "indeed.fr",

      # ATS directs d'entreprises (0 anti-bot, données pures)
      "myworkdayjobs.com",
      "greenhouse.io",
      "smartrecruiters.com",
      "lever.co",
      "teamtailor.com",
      "recruitee.com",
  ]
  ```
- **Agrégateurs exclus** (`spam_domains`) : Élimine automatiquement les fermes à clics et faux agrégateurs (`jooble`, `talent.com`, `neuvoo`, `adzuna`, `jobrapido`).
- **Fraîcheur des offres** : `time_range="month"` (ou `"week"` / `"day"` selon vos besoins).

### 4. Optimisations & Robustesse du Scraping (Crawl4AI)

Le scraper intègre plusieurs mécanismes intelligents pour garantir un taux d'extraction maximal :
* **Bypass Anti-bot LinkedIn (Guest API)** : Les URLs `linkedin.com/jobs/view/<id>` sont automatiquement converties vers l'endpoint public SEO `linkedin.com/jobs-guest/jobs/api/jobPosting/<id>`, garantissant l'accès complet sans aucun mur d'authentification (`/authwall`) ni compte requis.
* **Bypass Anti-bot Indeed (Mobile View)** : Les URLs bureau `indeed.com/viewjob?jk=<id>` sont automatiquement réécrites en vue mobile `indeed.com/m/viewjob?jk=<id>`, évitant les timeouts et challenges Cloudflare Turnstile de 45 secondes.
* **Conservation des URLs utilisateur** : Tout en crawlant les endpoints légers/non bloqués, le pipeline préserve et restitue les URLs canoniques cliquables pour la consultation par le candidat.
* **Détection instantanée des liens morts** : Les codes 404/410, pages expirées ou coquilles vides sont détectés dès la première passe (`_is_dead_or_expired`), supprimant plus de 2,5 minutes de retries inutiles par lien mort.
* **Fallback Entreprise déterministe** : Si le nom de l'entreprise est absent du DOM textuel (ex. carrières Workday), il est automatiquement extrait depuis l'URL (`extract_company_from_url`), sauvant ainsi les offres légitimes tout en prévenant les hallucinations LLM grâce à un ancrage strict du poste.

### 5. Configuration des modèles et des clés pour les Lettres de Motivation

Le générateur de lettres s'appuie sur une critique inter-fournisseurs obligatoire :
- **Clés nécessaires** : Définissez `OPENAI_API_KEY` et `GEMINI_API_KEY` dans votre `.env`. `MISTRAL_API_KEY` est optionnelle (fallback).
- **Règle multi-fournisseur** : Le critique évalue le style sans voir le profil candidat et doit obligatoirement provenir d'un fournisseur différent du rédacteur (ex: Rédacteur OpenAI GPT-5.6 Sol + Critique Google Gemini 3.8 Flash).
- **Vérification des crédits & quotas** : Les API d'OpenAI, Google AI Studio et Mistral ne proposent pas de point d'accès public sécurisé pour interroger le solde de crédit restant avec une clé API standard. L'application surveille automatiquement les erreurs d'appels et remonte immédiatement dans l'interface un message clair invitant à recharger son compte (ou à utiliser le palier gratuit Gemini).
- **Modèles configurables** via variables d'environnement :
  - `LETTER_MODEL_ANALYST` (défaut : `openai/gpt-5.6-luna` — extraction JSON rapide et économique)
  - `LETTER_MODEL_WRITER` (défaut : `openai/gpt-5.6-sol` — qualité rédactionnelle maximale)
  - `LETTER_MODEL_CRITIC` (défaut : `gemini/gemini-3.8-flash` — critique cross-provider gratuit)
  - `LETTER_MODEL_REVISER` (défaut : `openai/gpt-5.6-sol` — révision au même niveau que le rédacteur)

---


## 🧪 Tests

Les tests du backend s'exécutent avec `uv` :

```bash
cd backend
# Tests de génération de lettres de motivation
uv run --no-sync pytest tests/test_letter_guards.py tests/test_cover_letter_models.py tests/test_profile_seed.py tests/test_letter_llm.py tests/test_cover_letter_crew.py tests/test_cover_letter_trigger.py tests/test_cover_letters_api.py -v

# Tests de normalisation et scraping
uv run --no-sync pytest tests/test_normalization.py tests/test_job_offers_pipeline.py tests/test_crew_models_and_tools.py -v
```


---

## 🛠️ Commandes utiles

```bash
# Voir les logs d'un service
docker compose logs -f backend
docker compose logs -f airflow

# Forcer l'exécution manuelle de la collecte d'offres via Airflow
docker compose exec airflow airflow dags trigger collect_job_offers_granular

# Arrêter les services
docker compose down

# Reconstruire les images après modification de dépendances
docker compose build --no-cache backend
docker compose up -d
```