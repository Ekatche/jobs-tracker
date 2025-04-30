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


# Déplacer l'importation dans la fonction pour éviter qu'elle
# ne soit évaluée lors du chargement du DAG


def run_archive_task():
    import sys

    # Chemins alternatifs pour trouver les modules backend
    possible_paths = [
        "/app",
        "/opt/airflow",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
    ]

    for path in possible_paths:
        if path not in sys.path and os.path.exists(path):
            sys.path.append(path)

    try:
        from app.tasks.archive_old_applications import archive_old_applications

        return archive_old_applications()
    except ImportError as e:
        print(f"Erreur d'importation: {e}")
        print(f"sys.path = {sys.path}")
        raise


# Tâche pour exécuter la fonction d'archivage
archive_task = PythonOperator(
    task_id="archive_old_applications",
    python_callable=run_archive_task,
    dag=dag,
)
