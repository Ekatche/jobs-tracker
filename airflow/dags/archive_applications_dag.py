import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Arguments par défaut pour le DAG
default_args = {
    "owner": "job-tracker",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Créez le DAG
dag = DAG(
    "archive_old_applications",
    default_args=default_args,
    description="Archive les candidatures plus anciennes que 1,5 mois",
    schedule="0 2 * * *",
    start_date=datetime(2025, 4, 25),
    catchup=False,
    tags=["job-tracker", "maintenance"],
)


def run_archive_task():
    import sys
    import logging

    # Configuration du logging pour Airflow
    logger = logging.getLogger("airflow.task")

    # Chemins alternatifs pour trouver les modules backend
    possible_paths = [
        "/app",
        "/opt/airflow",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
    ]

    for path in possible_paths:
        if path not in sys.path and os.path.exists(path):
            sys.path.append(path)
            logger.info(f"Ajout du chemin {path} au sys.path")

    try:
        # Vérifier si pymongo est disponible
        try:
            from pymongo import MongoClient

            logger.info("pymongo importé avec succès")
        except ImportError:
            logger.error("pymongo n'est pas installé !")
            raise

        # Importer la fonction d'archivage
        from app.tasks.archive_old_applications import archive_old_applications

        logger.info("Module archive_old_applications importé avec succès")

        # Exécuter la fonction d'archivage
        logger.info("Début de l'exécution de archive_old_applications")
        result = archive_old_applications()
        logger.info(f"Résultat de l'archivage: {result} candidatures archivées")
        return result
    except ImportError as e:
        logger.error(f"Erreur d'importation: {e}")
        logger.info(f"sys.path = {sys.path}")
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution: {e}")
        raise


# Tâche pour exécuter la fonction d'archivage
archive_task = PythonOperator(
    task_id="archive_old_applications",
    python_callable=run_archive_task,
    dag=dag,
)
