# Guide de Déploiement VPS & Gestion des Secrets

Ce guide détaille l'architecture de déploiement en production sur VPS, la protection des secrets sur un dépôt public (GitHub), et la procédure pour déployer vos évolutions quotidiennes depuis votre machine locale.

---

## 1. Sécurité des Secrets sur un Dépôt Public (GitHub)

Le dépôt étant public, **aucune variable d'environnement ni clé d'API ne doit jamais être envoyée sur GitHub**.

### Comment fonctionne l'isolation ?
1. **`.gitignore` strict** : Le fichier `.gitignore` bloque automatiquement tous les fichiers sensibles :
   - `.env`
   - `.env.*` (ex: `.env.local`, `.env.prod`)
   - `*.env`
   - *Seul le fichier `.env.example` (qui ne contient que des valeurs factices ou vides) est versionné.*
2. **Fichiers locaux indépendants** :
   - Votre fichier `.env` sur votre machine locale contient vos clés de développement.
   - Votre fichier `/opt/job-tracker/.env` sur le VPS contient vos clés de production.
   - Ces deux fichiers n'interagissent jamais avec Git.

### Bonnes pratiques quotidiennes
- **Avant chaque commit** : vérifiez systématiquement `git status` pour vous assurer qu'aucun fichier sensible n'est indexé.
- **Jamais de clés dans le code** : les clés doivent toujours être lues via `process.env.VAR_NAME` (frontend / Node) ou `os.getenv("VAR_NAME")` (Python).
- **En cas de fuite accidentelle** : révoquez et renouvelez immédiatement la clé sur la console du fournisseur (OpenAI, Gemini, etc.).

---

## 2. Cycle de Déploiement : Faire Évoluer l'Application (Local ➔ VPS)

Lorsque vous développez de nouvelles fonctionnalités ou corrigez des bugs en local, voici le workflow simple en 2 temps :

### Étape 1 : Sur votre machine locale (Développement & Push)
1. Développez et validez vos modifications en local.
2. Commitez selon la convention *Conventional Commits* et poussez vers GitHub :
   ```bash
   git add .
   git commit -m "feat: description claire de votre changement"
   git push origin main
   ```

### Étape 2 : Sur votre VPS (Mise à jour & Relance)
Connectez-vous en SSH à votre serveur :
```bash
ssh root@185.194.142.163
```

Puis exécutez ces deux commandes :
```bash
cd /opt/job-tracker
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```

> **Note importante** : `git pull` met à jour le code sans **JAMAIS** toucher à votre fichier `.env` existant sur le serveur. Vos clés et mots de passe restent intacts.

---

## 3. Astuces d'Optimisation des Déploiements

Pour éviter de tout recompiler si vous n'avez touché qu'à une seule partie du code :

### Si vous n'avez modifié que le Frontend (Next.js) :
```bash
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build frontend
```
*(Seul le conteneur Next.js est reconstruit et redémarré en ~45s, sans couper le backend ni la base de données).*

### Si vous n'avez modifié que le Backend (FastAPI / Airflow) :
```bash
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build backend
```

### Si vous ajoutez une NOUVELLE variable d'environnement :
1. En local : ajoutez la variable dans votre `.env` et dans `.env.example` (avec valeur vide).
2. Sur le VPS :
   ```bash
   nano /opt/job-tracker/.env
   # Ajoutez la nouvelle variable, puis sauvegardez
   docker compose -f docker-compose.prod.yml up -d
   ```
   *(Docker détecte le changement de variables et recrée automatiquement les conteneurs impactés).*

---

## 4. Maintenance & Commandes Utiles sur le VPS

| Action | Commande |
|---|---|
| **Voir l'état des conteneurs** | `docker compose -f docker-compose.prod.yml ps` |
| **Suivre les logs en direct** | `docker compose -f docker-compose.prod.yml logs -f` |
| **Logs d'un seul service** | `docker compose -f docker-compose.prod.yml logs -f backend` |
| **Redémarrer un service sans rebuild** | `docker compose -f docker-compose.prod.yml restart frontend` |
| **Créer une sauvegarde MongoDB** | `docker exec -t jobtracker-mongodb mongodump --username mongo_user --password <MDP> --authenticationDatabase admin --db job_tracker --archive=/root/backup_$(date +%Y%m%d).archive` |
| **Restaurer une sauvegarde MongoDB** | `docker exec -i jobtracker-mongodb mongorestore --username mongo_user --password <MDP> --authenticationDatabase admin --archive < /root/backup_xxx.archive` |
