#!/bin/bash
set -e

echo "Attente de la disponibilité de MongoDB..."
# Ajouter un compteur pour limiter les tentatives
max_attempts=30
attempt=0

# Attendre que MongoDB soit prêt avec les identifiants d'authentification
until mongosh --host mongodb --port 27017 -u $MONGO_USER -p $MONGO_PASSWORD --authenticationDatabase admin --eval "db.adminCommand('ping')" &>/dev/null; do
  attempt=$((attempt+1))
  if [ $attempt -ge $max_attempts ]; then
    echo "MongoDB n'est pas disponible après $max_attempts tentatives. Abandon."
    exit 1
  fi
  echo "MongoDB n'est pas encore disponible, nouvelle tentative dans 2 secondes... ($attempt/$max_attempts)"
  sleep 2
done

echo "MongoDB est disponible, configuration de la base de données de test..."
# Créer la base de données de test si nécessaire
mongosh --host mongodb --port 27017 -u $MONGO_USER -p $MONGO_PASSWORD --authenticationDatabase admin --eval "use $TEST_DATABASE_NAME"

echo "Lancement des tests..."
exec "$@"