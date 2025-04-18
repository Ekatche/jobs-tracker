FROM python:3.12-slim

WORKDIR /app
# Installer uv
RUN pip install uv

# Installer les dépendances
COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY . .

# Exposer le port
EXPOSE 8000

# Commande pour lancer l'application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]