# Job Tracker 🚀

Job Tracker est une application web moderne et automatisée pour centraliser vos candidatures, automatiser la veille et le scraping intelligent d'offres d'emploi (via IA, CrewAI, Tavily et Crawl4AI) et suivre vos entretiens et relances.

---

## 🏗️ Architecture & Technologies

- **Frontend** : Next.js (App Router), React, TailwindCSS, Axios, React Icons, Cookies de session proactifs.
- **Backend API** : FastAPI, Pydantic v2, Motor / PyMongo, JWT Auth (Access + Refresh Tokens avec "Se souvenir de moi").
- **Automatisation & Scheduling** : Apache Airflow (DAGs de collecte quotidienne, nettoyage des doublons et soft-delete).
- **Intelligence Artificielle & Scraping** :
  - **CrewAI (v1.x)** : Multi-agents coordonnés pour convertir une intention de recherche en requêtes ciblées et filtrer les URLs pertinentes avec typage Pydantic structuré.
  - **Tavily Search API** : Moteur de recherche web avec fraîcheur mensuelle et ciblage de job boards qualifiés.
  - **Crawl4AI** : Web scraper asynchrone Chromium capable d'exécuter du JS (SPAs type APEC, HelloWork, WTTJ), de contourner les bandeaux cookies et d'extraire les données structurées via LLM (`gpt-4o-mini` ou `gemini-flash`).
- **Base de données** : MongoDB avec persistance des tombstones (soft-delete pour ne pas réimporter les offres supprimées).

---

## 📋 Prérequis

- **Docker** et **Docker Compose**
- **Git**
- Clés API :
  - `OPENAI_API_KEY` (recommandé pour une extraction rapide et stable)
  - `TAVILY_API_KEY` (pour la recherche d'offres ciblées)
  - `GEMINI_API_KEY` (optionnel)

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
1. `frontend` : Interface utilisateur ([http://localhost:3000](http://localhost:3000))
2. `backend` : API REST FastAPI ([http://localhost:8000](http://localhost:8000), docs sur [/docs](http://localhost:8000/docs))
3. `airflow` : Orchestrateur et planificateur de tâches ([http://localhost:8080](http://localhost:8080))
4. `mongodb` : Base de données NoSQL
5. `mongo_test` : Base MongoDB isolée pour les tests
6. `mongo-express` : Interface visuelle pour explorer la base ([http://localhost:8081](http://localhost:8081))

---

## 🎯 Personnaliser la recherche pour votre profil / métier

Le projet est conçu pour être facilement adapté à n'importe quel profil, localisation ou secteur d'activité. Voici les 3 fichiers clés à modifier :

### 1. Définir votre recherche et votre fréquence (Airflow)
Fichier : [`airflow/dags/collect_job_offers.py`](file:///Users/elielkatche/job-tracker/airflow/dags/collect_job_offers.py)

- **Requête de recherche** : modifiez la requête envoyée au pipeline dans la tâche `get_urls` :
  ```python
  # Exemple par défaut :
  queries = ["Je recherche un poste de data scientist proche de Lyon"]

  # Exemples d'adaptation :
  queries = ["Je recherche un poste de DevOps Cloud Kubernetes en télétravail ou à Paris"]
  queries = ["Chef de projet digital junior ou alternance à Nantes"]
  ```
- **Planification / Cron** : modifiez le paramètre `schedule_interval` :
  ```python
  schedule_interval="0 7 * * *"  # Tous les jours à 07h00 (heure locale)
  ```

### 2. Affiner les critères de qualification IA (CrewAI)
Dossier : [`backend/job_trackers/src/job_trackers/config/`](file:///Users/elielkatche/job-tracker/backend/job_trackers/src/job_trackers/config/)

- **`agents.yaml`** : Ajustez l'expertise de vos agents (par ex. pour cibler des postes tech, marketing, finance ou RH).
- **`tasks.yaml`** : Personnalisez les consignes de filtrage des URLs dans `filter_urls_task` :
  - Niveau d'expérience souhaité (Junior, Confirmé, Senior, Lead).
  - Modalités acceptées (Full Remote, Hybride, Présentiel).
  - Technologies, compétences obligatoires ou mots-clés éliminatoires.

### 3. Cibler ou exclure des sites d'emploi (Tavily & Crawler)
Fichier : [`backend/job_trackers/src/job_trackers/tools/custom_tool.py`](file:///Users/elielkatche/job-tracker/backend/job_trackers/src/job_trackers/tools/custom_tool.py)

- **Plateformes vérifiées** (`verified_domains`) :
  ```python
  verified_domains = [
      "welcometothejungle.com",
      "apec.fr",
      "francetravail.fr",
      "hellowork.com",
      "linkedin.com",
      "cadremploi.fr",
      "free-work.com",
      "lesjeudis.com",
      "indeed.fr",
  ]
  ```
- **Agrégateurs exclus** (`spam_domains`) : Élimine automatiquement les sites de spam ou faux agrégateurs (`jooble`, `talent.com`, `neuvoo`, `adzuna`, `jobrapido`).
- **Fraîcheur des offres** : `time_range="month"` (ou `"week"` / `"day"` selon vos besoins).

---

## 🧪 Tests

Les tests du backend s'exécutent avec `uv` ou `pytest` :

```bash
cd backend
uv run pytest tests/test_normalization.py tests/test_job_offers_pipeline.py tests/test_crew_models_and_tools.py
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