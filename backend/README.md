# Job Tracker Backend

Backend pour l'application Job Tracker, développé avec FastAPI et MongoDB. Cette API permet de gérer les candidatures d'emploi avec des fonctionnalités avancées comme la génération automatique de descriptions d'offres et l'orchestration de tâches.

## Technologies

- **FastAPI**: Framework web Python haute performance
- **MongoDB**: Base de données NoSQL avec Motor (driver asynchrone)
- **Docker**: Containerisation de l'application
- **uv**: Gestionnaire de packages Python rapide
- **Pydantic**: Validation des données et sérialisation
- **Apache Airflow**: Orchestration de tâches automatisées
- **OpenAI + LangChain**: Génération automatique de descriptions d'offres
- **Playwright + crawl4ai**: Web scraping intelligent
- **JWT**: Authentification avec tokens d'accès et de rafraîchissement

## Architecture

```
backend/
├── app/
│   ├── auth.py           # Authentification JWT
│   ├── database.py       # Configuration MongoDB
│   ├── models.py         # Modèles Pydantic
│   ├── routers.py        # Points de terminaison API
│   ├── utils.py          # Fonctions utilitaires
│   ├── llm/              # Intelligence artificielle
│   │   └── utils.py      # Génération de descriptions
│   ├── migrations/       # Scripts de migration
│   │   └── descriptions.py
│   ├── routers/          # Routeurs modulaires
│   ├── services/         # Logique métier
│   └── tasks/            # Tâches automatisées
│       ├── archive_old_applications.py
│       ├── clean_job_offers.py
│       └── job_offers_collectors.py
├── job_crawler/          # Module de scraping personnalisé
├── airflow/              # Configuration Airflow
├── tests/                # Tests unitaires et d'intégration
├── Dockerfile            # Image Docker backend
├── Dockerfile.airflow    # Image Docker Airflow
├── pyproject.toml        # Configuration du projet
└── requirements.txt      # Dépendances générées
```

## Configuration

### Prérequis
- Python 3.12+
- Docker & Docker Compose
- uv (gestionnaire de packages)

### Variables d'environnement
Créez un fichier `.env` à la racine du projet avec :

```env
# Configuration de l'API
SECRET_KEY=votre-clé-secrète-générée
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# MongoDB Configuration
DATABASE_NAME=job_tracker
MONGO_USER=mongo_user
MONGO_PASSWORD=votre_mot_de_passe_mongodb
MONGO_HOST=mongodb

# Configuration OpenAI (pour génération de descriptions)
OPENAI_API_KEY=votre_clé_api_openai

# Configuration Tavily (pour recherche web)
TAVILY_API_KEY=votre_clé_api_tavily

# Configuration Airflow
AIRFLOW_SECRET_KEY=votre_clé_airflow

# Configuration MongoDB Express (interface d'administration)
MONGO_EXPRESS_USER=admin
MONGO_EXPRESS_PASSWORD=admin_password
```

### Générer une clé secrète sécurisée :
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Installation et démarrage

### Avec Docker (recommandé)

```bash
# Cloner le projet
git clone <votre-repo>
cd job-tracker

# Générer requirements.txt depuis pyproject.toml
cd backend
uv pip compile pyproject.toml -o requirements.txt

# Lancer tous les services
docker-compose up -d

# Ou lancer seulement le backend
docker-compose up -d backend mongodb
```

### Développement local

```bash
# Installer uv si pas déjà fait
curl -LsSf https://astral.sh/uv/install.sh | sh

# Créer l'environnement virtuel
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Installer les dépendances
uv pip install -e .

# Lancer le serveur de développement
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Authentification (`/auth`)
- `POST /auth/register` - Inscription utilisateur
- `POST /auth/token` - Connexion et obtention de tokens
- `POST /auth/refresh` - Rafraîchissement du token
- `POST /auth/change-password` - Changement de mot de passe
- `GET /auth/me` - Informations utilisateur actuel

### Utilisateurs (`/users`)
- `GET /users/` - Liste des utilisateurs
- `POST /users/` - Créer un utilisateur
- `PUT /users/{user_id}` - Mettre à jour un utilisateur
- `POST /users/upload-cv` - Télécharger un CV

### Candidatures (`/applications`)
- `GET /applications/` - Liste des candidatures (avec filtres)
- `POST /applications/` - Créer une candidature
- `PUT /applications/{id}` - Mettre à jour une candidature
- `DELETE /applications/{id}` - Supprimer une candidature
- `POST /applications/{id}/notes` - Ajouter une note

### Tâches (`/tasks`)
- `GET /tasks/` - Liste des tâches
- `POST /tasks/` - Créer une tâche
- `PUT /tasks/{id}` - Mettre à jour une tâche
- `DELETE /tasks/{id}` - Supprimer une tâche

### Offres d'emploi (`/job-offers`)
- `POST /job-offers/collect` - Collecter des offres automatiquement

## Fonctionnalités avancées

### 🤖 Génération automatique de descriptions
- Scraping intelligent des pages d'offres d'emploi
- Génération de descriptions structurées via OpenAI
- Traitement en arrière-plan pour ne pas bloquer l'API

### 🔄 Tâches automatisées (Airflow)
- Archivage automatique des anciennes candidatures
- Collecte périodique d'offres d'emploi
- Nettoyage de base de données

### 🔍 Web Scraping intelligent
- Module `job_crawler` personnalisé
- Support Playwright pour sites dynamiques
- Gestion des erreurs et retry automatique

### 🔐 Sécurité
- Authentification JWT avec refresh tokens
- Hachage sécurisé des mots de passe (bcrypt)
- Validation stricte des données avec Pydantic

## Accès aux services

Une fois les conteneurs démarrés :

- **API Backend** : http://localhost:8000
- **Documentation API** : http://localhost:8000/docs
- **Interface Airflow** : http://localhost:8080
- **MongoDB Express** : http://localhost:8081

## Tests

```bash
# Lancer tous les tests
pytest

# Tests avec couverture
pytest --cov=app

# Tests spécifiques
pytest tests/test_users.py
pytest tests/test_applications.py
```

## Développement

### Structure des modèles
- `UserModel` - Gestion des utilisateurs
- `JobApplication` - Candidatures d'emploi
- `Task` - Tâches personnelles
- `JobOffer` - Offres d'emploi collectées

### Base de données
- Collections MongoDB : `users`, `applications`, `tasks`, `job_offers`
- Index automatiques pour les performances
- Sérialisation ObjectId vers string

### Logging
- Logs structurés avec le module `logging`
- Différents niveaux selon l'environnement
- Logs Airflow séparés

## Scripts utiles

```bash
# Générer requirements.txt
uv pip compile pyproject.toml -o requirements.txt

# Migration de descriptions
python -m app.migrations.descriptions

# Archivage manuel
python -m app.tasks.archive_old_applications

# Rebuild Docker sans cache
docker-compose build --no-cache

# Voir les logs en temps réel
docker-compose logs -f backend
docker-compose logs -f airflow
```

## Dépannage

### Problèmes courants

**Erreur de connexion MongoDB :**
```bash
docker-compose logs mongodb
docker-compose restart mongodb
```

**Problème avec crawl4ai/Playwright :**
```bash
# Reconstruire l'image Airflow
docker-compose build --no-cache airflow
```

**Variables d'environnement manquantes :**
```bash
# Vérifier le fichier .env
cat .env
# Redémarrer les services
docker-compose down && docker-compose up -d
```

## Performance et monitoring

- Rate limiting configuré via FastAPI
- Monitoring des performances avec logs
- Base de données indexée pour les requêtes fréquentes
- Cache des sessions utilisateur

## Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commiter les changements (`git commit -am 'Ajout nouvelle fonctionnalité'`)
4. Push vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer une Pull Request

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.


