from datetime import datetime, timedelta
import logging
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator

# Configuration des arguments par défaut du DAG
default_args = {
    "owner": "job-tracker",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Définition du DAG
dag = DAG(
    "verify_active_job_offers",
    default_args=default_args,
    description="Vérifie si les offres actives sont toujours ouvertes (HTTP + JS headless) et soft-delete les offres closes",
    schedule="0 7 * * *",  # Exécution quotidienne à 7h00 UTC
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=30),
    tags=["job-tracker", "verification", "maintenance", "crawler"],
)


def verify_active_offers_task():
    """Tâche Airflow qui exécute l'inspection 2-tier des offres d'emploi."""
    logger = logging.getLogger("airflow.task")
    sys.path.append("/app")

    try:
        from app.tasks.verify_job_offers import verify_job_offers_sync

        logger.info("🚀 Lancement de la vérification de validité des offres (HTTP + JS)...")
        result = verify_job_offers_sync(
            limit=200,
            max_concurrency=5,
            dry_run=False,
        )
        logger.info(f"✅ Résultat de la vérification: {result.get('summary', '')}")
        return result

    except Exception as e:
        logger.error(f"💥 Erreur lors de la vérification des offres: {str(e)}")
        raise


verify_task = PythonOperator(
    task_id="verify_and_cleanup_closed_offers",
    python_callable=verify_active_offers_task,
    execution_timeout=timedelta(minutes=25),
    dag=dag,
)
