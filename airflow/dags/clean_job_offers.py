from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import sys
import logging

sys.path.append("/app")


def cleanup_offers_task():
    """Tâche de nettoyage des anciennes offres"""
    import asyncio

    logger = logging.getLogger("airflow.task")
    try:
        from app.tasks.clean_job_offers import cleanup_workflow

        logger.info("Début du nettoyage des anciennes offres")
        result = asyncio.run(cleanup_workflow())
        logger.info(f"Nettoyage terminé: {result}")
        return result

    except Exception as e:
        logger.error(f"Erreur lors du nettoyage: {str(e)}")
        raise


default_args = {
    "owner": "job-tracker",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "cleanup_job_offers",
    default_args=default_args,
    description="Nettoyage des anciennes offres d'emploi",
    schedule="0 3 * * *",
    tags=["job-tracker", "maintenance"],
)

cleanup_task = PythonOperator(
    task_id="cleanup_old_offers",
    python_callable=cleanup_offers_task,
    dag=dag,
)
