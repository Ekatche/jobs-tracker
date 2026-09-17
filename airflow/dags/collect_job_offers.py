from datetime import datetime, timedelta
from airflow import DAG
from airflow.decorators import task
import logging

# Arguments par défaut pour le DAG
default_args = {
    "owner": "job-tracker",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
}

# Créer le DAG
dag = DAG(
    "collect_job_offers_granular",
    default_args=default_args,
    description="Collecte automatique d'offres d'emploi - Version granulaire",
    schedule="0 7,16 * * 1-5",
    catchup=False,
    max_active_runs=1,
    tags=["job-tracker", "collection", "granular"],
    dagrun_timeout=timedelta(minutes=90),  # Augmenté pour le nettoyage
)


@task(dag=dag, execution_timeout=timedelta(minutes=5))
def validate_queries() -> list:
    """Tâche 1: Validation et génération dynamique des requêtes de recherche"""
    import sys
    sys.path.append("/app")

    logger = logging.getLogger("airflow.task")
    logger.info("📋 Validation des requêtes")

    from app.tasks.job_offers_collectors import build_search_queries_sync

    queries = build_search_queries_sync()
    valid_queries = [q.strip() for q in queries if len(q.strip()) > 5]

    if not valid_queries:
        raise Exception("Aucune requête valide définie pour la collecte")

    logger.info(f"✅ {len(valid_queries)} requêtes validées: {valid_queries}")
    return valid_queries


@task(dag=dag, execution_timeout=timedelta(minutes=60))
def execute_collection_pipeline(validated_queries: list) -> dict:
    """Tâche 2: Exécution complète du pipeline de collecte, déduplication et stockage"""
    import sys
    sys.path.append("/app")

    logger = logging.getLogger("airflow.task")
    from app.tasks.job_offers_collectors import collect_offers_sync

    total_saved = 0
    total_updated = 0
    query_results = []

    for query in validated_queries:
        logger.info(f"🚀 Lancement de la collecte pour: '{query}'")
        try:
            result = collect_offers_sync(query)
            saved = result.get("saved", 0)
            updated = result.get("updated", 0)
            total_saved += saved
            total_updated += updated
            query_results.append({"query": query, "status": "success", "saved": saved, "updated": updated})
            logger.info(f"✅ Succès pour '{query}': {saved} créées, {updated} mises à jour")
        except Exception as e:
            logger.error(f"💥 Erreur lors de la collecte pour '{query}': {e}")
            query_results.append({"query": query, "status": "error", "error": str(e)})

    failed_queries = [r for r in query_results if r.get("status") == "error"]
    if failed_queries and len(failed_queries) == len(validated_queries):
        error_details = "; ".join(f"[{r['query']}]: {r.get('error')}" for r in failed_queries)
        raise RuntimeError(
            f"Échec total du pipeline de collecte ({len(failed_queries)}/{len(validated_queries)} requêtes en erreur): {error_details}"
        )

    summary = {
        "status": "partial_failure" if failed_queries else "completed",
        "total_saved": total_saved,
        "total_updated": total_updated,
        "results": query_results,
    }
    logger.info(f"🏁 Pipeline de collecte terminé: {summary}")
    return summary


# Définition du flux
queries = validate_queries()
collection_summary = execute_collection_pipeline(queries)
