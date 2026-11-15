"""Airflow cleanup workflow orchestration and synchronous entrypoint."""

import asyncio
from datetime import datetime, timezone
import sys
from typing import Any, Dict, Optional, Tuple


def _compute_similarity_metrics(
    steps: Dict[str, Any], enable_global_similarity: bool
) -> Tuple[int, int]:
    if enable_global_similarity:
        global_step = steps.get("global_similarity", {})
        return global_step.get("merged", 0), global_step.get("skipped_referenced", 0)
    similarity_deleted = steps.get("similarity_duplicates", {}).get(
        "deleted_similarity_duplicates", 0
    )
    return similarity_deleted, 0


def _build_and_log_summary(
    results: Dict[str, Any],
    enable_global_similarity: bool,
    enable_similarity_cleanup: bool,
    logger: Any,
) -> Dict[str, Any]:
    steps = results["steps"]
    similarity_deleted, skipped_referenced = _compute_similarity_metrics(
        steps, enable_global_similarity
    )
    exact_deleted = steps.get("exact_duplicates", {}).get("deleted_exact_duplicates", 0)
    invalid_deleted = steps.get("invalid", {}).get("deleted_invalid", 0)
    old_deleted = steps.get("old_offers", {}).get("deleted", 0)
    total_deleted = sum([exact_deleted, similarity_deleted, invalid_deleted, old_deleted])
    total_normalized = steps.get("normalize", {}).get("normalized", 0)

    logger.info("🎯 Workflow de nettoyage terminé:")
    logger.info(f"  📊 Données normalisées: {total_normalized}")
    logger.info(f"  🔗 Doublons exacts supprimés: {exact_deleted}")
    if enable_global_similarity:
        logger.info(f"  🌍 Doublons similaires fusionnés (global): {similarity_deleted}")
        logger.info(f"  ⏭️ Paires sautées (deux offres référencées): {skipped_referenced}")
    elif enable_similarity_cleanup:
        logger.info(f"  🎯 Doublons similaires supprimés (standard): {similarity_deleted}")
    logger.info(f"  🧹 Offres invalides supprimées: {invalid_deleted}")
    logger.info(f"  🗑️ Offres anciennes supprimées: {old_deleted}")
    logger.info(f"  📊 Total supprimé: {total_deleted}")
    logger.info(f"  ⏱️ Durée: {results['duration']:.2f}s")

    return {
        "total_normalized": total_normalized,
        "total_deleted": total_deleted,
        "exact_duplicates_deleted": exact_deleted,
        "similarity_duplicates_deleted": similarity_deleted,
        "skipped_referenced": skipped_referenced,
        "invalid_deleted": invalid_deleted,
        "old_offers_deleted": old_deleted,
        "success": True,
    }


async def cleanup_workflow(
    days: Optional[int] = None,
    enable_similarity_cleanup: bool = True,
    enable_global_similarity: bool = True,
    company_similarity_threshold: float = 0.75,
    position_similarity_threshold: float = 0.80,
    enable_old_offers_cleanup: bool = False,
) -> Dict[str, Any]:
    """Run normalization, exact/global deduplication, invalid cleanup, and optional age purge."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    pkg.logger.info("🚀 Début du workflow de nettoyage Airflow (mode global renforcé)")
    results: Dict[str, Any] = {"start_time": datetime.now(timezone.utc), "steps": {}}

    try:
        pkg.logger.info("📝 Étape 1: Normalisation des données")
        results["steps"]["normalize"] = await pkg.normalize_existing_data()

        pkg.logger.info("🔍 Étape 2: Suppression des doublons exacts")
        results["steps"]["exact_duplicates"] = await pkg.remove_exact_duplicates()

        if enable_global_similarity:
            pkg.logger.info("🌍 Étape 3: Fusion des doublons (règle de l'insertion)")
            results["steps"]["global_similarity"] = await pkg.merge_duplicate_offers(
                await pkg.get_database(), apply=True
            )
        elif enable_similarity_cleanup:
            pkg.logger.info("🎯 Étape 3: Nettoyage par similarité (mode standard)")
            results["steps"]["similarity_duplicates"] = (
                await pkg.remove_similarity_duplicates(
                    company_similarity_threshold=company_similarity_threshold,
                    position_similarity_threshold=position_similarity_threshold,
                )
            )
        else:
            pkg.logger.info("⏭️ Étape 3: Nettoyage par similarité désactivé")
            results["steps"]["similarity_duplicates"] = {"deleted_similarity_duplicates": 0}

        pkg.logger.info("🧹 Étape 4: Suppression des offres invalides")
        results["steps"]["invalid"] = await pkg.cleanup_invalid_offers()

        if enable_old_offers_cleanup and days and days > 0:
            pkg.logger.info(f"🗑️ Étape 5: Suppression des offres > {days} jours")
            results["steps"]["old_offers"] = await pkg.cleanup_old_offers(days)
        else:
            pkg.logger.info(
                "⏭️ Étape 5: Purge aveugle par âge désactivée "
                "(la validité réelle est assurée par verify_job_offers)"
            )
            results["steps"]["old_offers"] = {
                "deleted": 0,
                "status": "disabled_in_favor_of_live_verification",
            }

        results["end_time"] = datetime.now(timezone.utc)
        results["duration"] = (results["end_time"] - results["start_time"]).total_seconds()
        results["summary"] = _build_and_log_summary(
            results, enable_global_similarity, enable_similarity_cleanup, pkg.logger
        )
        return results
    except Exception as e:
        pkg.logger.error(f"💥 Erreur dans le workflow de nettoyage: {e}")
        results["error"] = str(e)
        results["summary"] = {"success": False}
        return results


def cleanup_workflow_sync(
    days: Optional[int] = None,
    enable_similarity_cleanup: bool = False,
    enable_global_similarity: bool = True,
    company_similarity_threshold: float = 0.75,
    position_similarity_threshold: float = 0.80,
    enable_old_offers_cleanup: bool = False,
) -> Dict[str, Any]:
    """Synchronous entrypoint for Airflow DAG."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    return asyncio.run(
        pkg.cleanup_workflow(
            days=days,
            enable_similarity_cleanup=enable_similarity_cleanup,
            enable_global_similarity=enable_global_similarity,
            company_similarity_threshold=company_similarity_threshold,
            position_similarity_threshold=position_similarity_threshold,
            enable_old_offers_cleanup=enable_old_offers_cleanup,
        )
    )
