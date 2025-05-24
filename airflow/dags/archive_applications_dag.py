from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Arguments par défaut pour le DAG
default_args = {
    "owner": "job-tracker",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
}

# Créez le DAG
dag = DAG(
    "archive_old_applications",
    default_args=default_args,
    description="Archive les candidatures plus anciennes que 40 jours",
    schedule="0 3 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["job-tracker", "maintenance"],
)


def run_archive_task():
    import sys
    import logging

    # Configuration du logging pour Airflow
    logger = logging.getLogger("airflow.task")

    # Ajouter le chemin backend
    sys.path.append("/app")

    try:
        # Importer la fonction d'archivage
        from app.tasks.archive_old_applications import archive_old_applications

        logger.info("Début de l'archivage des candidatures")
        # Exécuter la fonction d'archivage
        result = archive_old_applications(threshold_days=40)
        logger.info(f"Archivage terminé: {result} candidatures archivées")
        return result
    except Exception as e:
        logger.error(f"Erreur lors de l'archivage: {e}")
        raise


# Tâche pour exécuter la fonction d'archivage
archive_task = PythonOperator(
    task_id="archive_old_applications",
    python_callable=run_archive_task,
    dag=dag,
)
