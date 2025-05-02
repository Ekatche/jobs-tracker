# Guide d'installation et d'utilisation de Job Tracker

Job Tracker est une application web qui vous permet de suivre vos candidatures d'emploi, d'organiser votre recherche et de visualiser vos progrès.

# Prérequis
Avant de commencer, assurez-vous d'avoir installé :

* Docker
* Docker Compose
* Git

# Installation
1. Cloner le dépôt
```bash
git clone https://github.com/votre-username/job-tracker.git
cd job-tracker
```
2. Configuration du backend
Créez un fichier `.env` à la racine du projet avec les variables d'environnement suivantes :

```
# Configuration de l'API
SECRET_KEY=votre-clé-secrète-à-générer
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# MongoDB Configuration
DATABASE_NAME=job_tracker

# Paramètres MongoDB
MONGO_USER=mongo_user
MONGO_PASSWORD=votre_mot_de_passe_mongodb
MONGO_HOST=mongodb

# Configuration MongoDB Express (interface d'administration)
MONGO_EXPRESS_USER=admin
MONGO_EXPRESS_PASSWORD=admin_password

# Configuration Airflow
AIRFLOW_SECRET_KEY=votre_clé_airflow

# Configuration OpenAI (si utilisé)
OPENAI_API_KEY=votre_clé_api_openai
```

Pour générer une clé secrète sécurisée, exécutez :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
3. Lancer l'application
Depuis la racine du projet, exécutez :

```bash
docker-compose up -d
```
Cette commande va :

Construire les images Docker pour le frontend et le backend
Démarrer les conteneurs pour le frontend, le backend et la base de données MongoDB
Configurer le réseau entre les services

# Accéder à l'application
Une fois les conteneurs démarrés, vous pouvez accéder à l'application :

* Frontend : http://localhost:3000
* API Backend : http://localhost:8000
* Documentation API : http://localhost:8000/docs


# Fonctionnalités principales
* Tableau de bord : Visualisez vos statistiques de candidature et suivez votre progression
* Suivi des candidatures : Organisez vos candidatures par statut (envoyée, entretien, offre reçue, refusée)
* Notes : Ajoutez des notes à chaque candidature pour garder des informations importantes
* Interface interactive : Interface utilisateur intuitive pour gérer facilement vos candidatures

# Arrêter l'application
Pour arrêter tous les services :

```bash
docker-compose down
```

# Mise à jour de l'application
Si vous souhaitez mettre à jour l'application après avoir effectué des modifications ou récupéré des mises à jour :

```bash
# Arrêter les conteneurs
docker-compose down

# Reconstruire les images
docker-compose build

# Redémarrer les services
docker-compose up -d
```

# Résolution des problèmes courants
Problèmes de connexion à la base de données
Si l'application ne peut pas se connecter à MongoDB :

```bash
# Vérifiez les logs du conteneur MongoDB
docker-compose logs mongo

# Redémarrez le conteneur MongoDB
docker-compose restart mongo
```

Problèmes avec le frontend
Si le frontend ne se charge pas correctement :

```bash
# Vérifiez les logs du frontend
docker-compose logs frontend

# Reconstruisez et redémarrez le frontend
docker-compose build frontend
docker-compose up -d frontend

# Reconstruisez et redémarrez le baskend
docker-compose build backend
docker-compose up -d backend
```

# Développement
Si vous souhaitez contribuer au développement :

1. Créez une branche pour vos modifications
2. Apportez vos modifications au code
3. Reconstruisez et testez l'application localement
4. Soumettez une pull request