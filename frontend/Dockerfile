FROM node:20-alpine

WORKDIR /app

# Copier package.json et package-lock.json
COPY package*.json ./

# Installer les dépendances
RUN npm ci

# Copier le code source
COPY . .

# Linter le code avant la construction
RUN npm run lint

# Construire l'application
RUN npm run build

# Exposer le port
EXPOSE 3000

# Commande pour exécuter l'application
CMD ["npm", "run", "start"]