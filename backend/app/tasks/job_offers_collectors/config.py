"""Configuration constants, logger setup, and schedule guards for collectors."""

from datetime import datetime, timezone
import logging
import os

# httpx logue chaque requête en INFO, URL complète comprise : l'URL Gemini de litellm
# porte la clé API en `?key=...`, qui finirait en clair dans les logs Airflow.
logging.getLogger("httpx").setLevel(logging.WARNING)

# Borne par requête pour collect_offers_sync : jusqu'à 8 requêtes × 7 min = 56 min,
# sous l'execution_timeout de 60 min de la tâche Airflow. Sans cette borne,
# une requête qui pend consomme tout le budget et tue les autres.
COLLECT_QUERY_TIMEOUT = 420
MAX_QUERIES_PER_PROFILE = 3
MAX_TOTAL_QUERIES = 8
# Appels LLM de résumé simultanés (offres ATS et sources structurées).
SUMMARY_CONCURRENCY = 8
# La recherche web (crew + Tavily, payée au crédit) ne tourne qu'au run du matin du DAG
# (0 7,16 UTC) ; jobspy, gratuit, tourne aux deux runs.
WEB_SEARCH_MAX_HOUR_UTC = 12

DEFAULT_QUERIES: list[str] = [
    "Je recherche un poste de data scientist",
    "Je recherche un poste d'ingénieur IA (AI engineer)",
    "Je recherche un poste de data engineer",
    "Je recherche un poste de machine learning engineer",
    "Je recherche un poste d'ingénieur MLOps",
    "Je recherche un poste de LLM engineer / ingénieur IA générative",
]


def setup_logger() -> logging.Logger:
    """Configure le logger selon l'environnement."""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        level = logging.WARNING
    elif env == "airflow":
        level = logging.INFO
    else:
        level = logging.DEBUG

    pkg_logger = logging.getLogger("app.tasks.job_offers_collectors")
    pkg_logger.setLevel(level)
    return pkg_logger


logger = setup_logger()


def is_web_search_run(now: datetime) -> bool:
    """Vrai si un run démarré à `now` doit lancer la recherche web (crew + Tavily)."""
    return now.astimezone(timezone.utc).hour < WEB_SEARCH_MAX_HOUR_UTC
