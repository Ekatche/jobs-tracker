from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Arguments par défaut pour le DAG
default_args = {
    "owner": "job-tracker",
    "retries": 0,  # ✅ Pas de retry pour arrêter immédiatement
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    # ✅ Ajouter pour arrêter en cas d'erreur
    "on_failure_callback": None,
    "email_on_failure": False,
    "email_on_retry": False,
    "execution_timeout": timedelta(minutes=20),  # ✅ Timeout explicite pour la tâche
}

# Créer le DAG
dag = DAG(
    "collect_job_offers",
    default_args=default_args,
    description="Collecte automatique d'offres d'emploi",
    schedule="0 5 * * 1,4",  # ✅ Lundi et Jeudi à 9h00 (2 fois par semaine)
    catchup=False,
    max_active_runs=1,  # ✅ Une seule exécution à la fois
    tags=["job-tracker", "collection"],
    dagrun_timeout=timedelta(minutes=20),  # ✅ Timeout pour tout le DAG
)


def collect_offers_task(**context):
    """Tâche de collecte d'offres"""
    import sys
    import logging

    logger = logging.getLogger("airflow.task")
    sys.path.append("/app")

    try:
        from app.tasks.job_offers_collectors import collect_offers_sync

        # Requêtes de test
        queries = [
            "Je recherche un poste de data scientist proche de Lyon",
        ]

        total_results = {"saved": 0, "updated": 0}

        for query in queries:
            logger.info(f"Collecte pour la requête: {query}")

            # ✅ Gestion d'erreur stricte
            try:
                result = collect_offers_sync(query)
                total_results["saved"] += result["saved"]
                total_results["updated"] += result["updated"]
                logger.info(f"Résultat pour '{query}': {result}")

            except Exception as e:
                logger.error(f"Erreur pour la requête '{query}': {e}")
                # ✅ Arrêter complètement le DAG
                raise Exception(f"Échec de collecte pour '{query}': {e}")

        logger.info(f"Collecte totale terminée: {total_results}")
        return total_results

    except Exception as e:
        logger.error(f"Erreur critique dans collect_offers_task: {e}")
        # ✅ Re-raise pour faire échouer le DAG
        raise


# ✅ Configuration stricte de la tâche
collect_task = PythonOperator(
    task_id="collect_job_offers",
    python_callable=collect_offers_task,
    dag=dag,
    # ✅ Paramètres pour arrêter en cas d'erreur
    retries=0,
    retry_delay=timedelta(minutes=1),
    execution_timeout=timedelta(minutes=20),  # ✅ Timeout spécifique à cette tâche
)
