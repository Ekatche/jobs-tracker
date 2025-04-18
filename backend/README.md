# Job Tracker Backend

Backend pour l'application Job Tracker, développé avec FastAPI et MongoDB.

## Technologies

- **FastAPI**: Framework web Python haute performance
- **MongoDB**: Base de données NoSQL
- **Docker**: Containerisation de l'application
- **Pydantic**: Validation des données et serialisation

## Configuration

### Prérequis
- Python
- Docker

### Variables d'environnement
Créez un fichier `.env` dans le dossier backend avec:

```
SECRET_KEY=votre-clé-secrète
MONGODB_URL=mongodb://mongo:27017/job-tracker
MONGODB_DB=job-tracker
```

Générer une clé secrète:
```
python -c "import secrets; print(secrets.token_hex(32))"
```

## Démarrage rapide

```bash
# Lancer uniquement le backend et MongoDB
docker-compose up -d backend mongo

# Accéder à la documentation API
http://localhost:8000/docs
```

## Structure du projet

```
backend/
├── app/
│   ├── api/          # Points de terminaison API
│   ├── core/         # Configuration et paramètres
│   ├── models/       # Modèles de données
│   ├── services/     # Logique métier
│   └── utils/        # Fonctions utilitaires
├── tests/            # Tests unitaires et d'intégration
└── Dockerfile        # Configuration Docker
```

## API Endpoints

- `/api/users`: Gestion des utilisateurs
- `/api/jobs`: Gestion des candidatures
- `/api/stats`: Statistiques et analyses


