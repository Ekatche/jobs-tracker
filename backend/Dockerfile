FROM python:3.12-slim

WORKDIR /app

# Installation des dépendances système pour Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Installer uv
RUN pip install uv

# Installer les dépendances
COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Installer les navigateurs avec Playwright (après installation du package)
RUN playwright install --with-deps chromium

# Copier le code de l'application
COPY . .

# Exposer le port
EXPOSE 8000

# Commande pour lancer l'application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]