FROM python:3.12-slim-bookworm

WORKDIR /app

# Installation des dépendances système pour le backend
RUN apt-get update && apt-get install -y \
    wget curl ca-certificates build-essential \
    libpango-1.0-0 libcairo2 libasound2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Installation uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin/:$PATH"

# Configuration uv
ENV PYTHONUNBUFFERED=1
ENV UV_CACHE_DIR=/tmp/uv-cache
ENV UV_LINK_MODE=copy

# ✅ Créer l'environnement virtuel
RUN uv venv

# ✅ Installer les dépendances depuis requirements.txt
COPY requirements.txt .
RUN uv pip install -r requirements.txt

# Ajouter .venv au PATH
ENV PATH="/app/.venv/bin:$PATH"

# Setup crawl4ai
RUN echo "🚀 Setup crawl4ai..." && \
    (crawl4ai-setup && echo "✅ crawl4ai-setup OK") || \
    echo "⚠️ crawl4ai-setup échoué"

RUN playwright install --with-deps chromium


# Copier le code
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]