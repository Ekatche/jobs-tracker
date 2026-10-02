#!/usr/bin/env bash
# ==============================================================================
# Script d'initialisation du serveur VPS Debian (Netcup) pour Job Tracker
# - Alloue 4 Go de Swap (évite les crashs OOM Killer de Playwright/Airflow)
# - Règle la swappiness à 10 (recommandé pour les SSD)
# - Verrouille le pare-feu UFW (ports 22, 80, 443 uniquement)
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo "🚀 Initialisation du serveur VPS Netcup pour Job Tracker"
echo "=========================================================="

# Vérification des privilèges root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Ce script doit être exécuté en tant que root (ou avec sudo)."
   exit 1
fi

# 1. GESTION DU SWAP (4 Go)
echo ""
echo "📦 [1/3] Vérification de l'espace Swap..."
SWAP_TOTAL=$(free -m | awk '/^Swap:/ {print $2}')

if [[ "$SWAP_TOTAL" -eq 0 ]]; then
    echo "⚙️ Aucun Swap détecté. Création d'un fichier Swap de 4 Go..."
    fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    
    # Persistance dans fstab
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
    echo "✅ Swap de 4 Go activé avec succès !"
else
    echo "ℹ️ Un espace Swap de ${SWAP_TOTAL} Mo est déjà actif."
fi

# Ajustement swappiness pour préserver les performances SSD
sysctl vm.swappiness=10
if ! grep -q 'vm.swappiness' /etc/sysctl.conf; then
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# 2. CONFIGURATION DU PARE-FEU UFW
echo ""
echo "🛡️ [2/3] Configuration du pare-feu UFW..."
apt-get update -qq && apt-get install -y -qq ufw

# Règles de sécurité strictes
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP Caddy Let-Encrypt'
ufw allow 443/tcp comment 'HTTPS Caddy'
ufw allow 443/udp comment 'HTTP/3 QUIC'

# Activer sans confirmation interactive
ufw --force enable
echo "✅ Pare-feu UFW configuré : seuls les ports 22, 80 et 443 sont ouverts."

# 3. VERIFICATION DE DOCKER
echo ""
echo "🐳 [3/3] Vérification des prérequis Docker..."
if ! command -v docker &> /dev/null; then
    echo "⚠️ Docker n'est pas encore installé. Vous pouvez l'installer via :"
    echo "   curl -fsSL https://get.docker.com | sh"
else
    echo "✅ Docker est installé ($(docker --version))."
fi

echo ""
echo "=========================================================="
echo "🎉 Serveur prêt pour le déploiement !"
echo "Pour démarrer la stack Job Tracker :"
echo "  1. Configurez votre .env avec votre domaine et vos clés d'API :"
echo "     DOMAIN=jobtracker.votredomaine.com"
echo "     INVITATION_CODE=votre_code_secret"
echo "  2. Lancez les conteneurs de production :"
echo "     docker compose -f docker-compose.prod.yml up -d --build"
echo "=========================================================="
