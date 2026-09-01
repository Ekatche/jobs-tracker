from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import sys
import logging

sys.path.append("/app")


def cleanup_offers_task():
    """✨ MODIFIÉ: Tâche avec nettoyage global renforcé"""
    logger = logging.getLogger("airflow.task")
    try:
        from app.tasks.clean_job_offers import cleanup_workflow_sync

        logger.info("🚀 Début du nettoyage complet (mode global renforcé)")

        # ✅ Configuration pour détecter "ALTECA Data Scientist (H/F)" et similaires
        result = cleanup_workflow_sync(
            days=6,  # Supprimer offres > 6 jours
            enable_similarity_cleanup=False,  # Mode standard désactivé
            enable_global_similarity=True,  # Mode global renforcé activé
            company_similarity_threshold=0.80,  # ✅ Seuil entreprise légèrement augmenté
            position_similarity_threshold=0.75,  # ✅ Seuil poste légèrement abaissé pour plus de détection
        )

        logger.info(f"✅ Nettoyage terminé: {result['summary']}")
        return result

    except Exception as e:
        logger.error(f"💥 Erreur lors du nettoyage: {str(e)}")
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
    description="✨ Nettoyage complet des offres d'emploi (fonction optimisée)",
    schedule="0 6 * * *",  # Chaque jour à 6h du matin (UTC)
    tags=["job-tracker", "maintenance", "optimized"],
)

cleanup_task = PythonOperator(
    task_id="cleanup_offers_complete",
    python_callable=cleanup_offers_task,
    dag=dag,
)
