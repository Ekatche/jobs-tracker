"""Main job-offer verification workflow, Airflow entrypoint, and false-delete recovery."""

import asyncio
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from .html_checks import DEFAULT_HEADERS
from .indeed_and_single import extract_indeed_job_key


def _unknown_reason_key(result: Dict[str, Any]) -> str:
    """Format `<root-domain> <reason>` for diagnostic grouping of unknown results."""
    host = urlparse(result.get("url") or "").hostname or "?"
    reason = str(result.get("reason") or "unknown").split(":")[0].strip()
    return f"{'.'.join(host.split('.')[-2:])} {reason}"


async def _fetch_offers_to_verify(collection: Any, limit: Optional[int]) -> List[Dict[str, Any]]:
    query = {
        "is_deleted": {"$ne": True},
        "$or": [
            {"url": {"$exists": True, "$nin": [None, ""]}},
            {"source_url": {"$exists": True, "$nin": [None, ""]}},
        ],
    }
    # Prioritize user-visible offers first so closed ones don't linger in rotation
    is_visible = {"$and": [{"$isArray": "$matched_user_ids"}, {"$gt": [{"$size": "$matched_user_ids"}, 0]}]}
    pipeline: List[Dict[str, Any]] = [
        {"$match": query},
        {"$project": {
            "url": 1,
            "source_url": 1,
            "last_verified_at": 1,
            "created_at": 1,
            "_visible": {"$cond": [is_visible, 1, 0]},
        }},
        {"$sort": {"_visible": -1, "last_verified_at": 1, "created_at": -1}},
    ]
    if limit:
        pipeline.append({"$limit": limit})
    return await collection.aggregate(pipeline).to_list(length=limit)


async def _persist_verification_result(
    collection: Any,
    offer: Dict[str, Any],
    result: Dict[str, Any],
    dry_run: bool,
    logger: Any,
) -> int:
    if dry_run:
        return 0
    now = datetime.now(timezone.utc)
    fields: Dict[str, Any] = {"last_verified_at": now}
    is_closed = result.get("is_valid") is False
    if is_closed:
        fields.update({
            "is_deleted": True,
            "pipeline_stage": "expired",
            "deleted_date": now,
            "deletion_reason": result["reason"],
            "updated_at": now,
        })
    try:
        update_res = await collection.update_one({"_id": offer["_id"]}, {"$set": fields})
        return 1 if (is_closed and update_res.modified_count > 0) else 0
    except Exception as e:
        logger.error(f"💥 Erreur lors de l'écriture de l'offre {result['offer_id']}: {e}")
        return 0


def _build_verify_summary(
    processed_results: List[Dict[str, Any]],
    found: int,
    updated_db_count: int,
    dry_run: bool,
    logger: Any,
) -> Dict[str, Any]:
    total = len(processed_results)
    deferred_count = found - total
    if deferred_count:
        logger.info(f"⏱️ Budget de temps atteint : {deferred_count} offres reportées au prochain run.")

    valid_count = sum(1 for r in processed_results if r.get("is_valid") is True)
    closed_offers = [r for r in processed_results if r.get("is_valid") is False]
    closed_count = len(closed_offers)
    unknown_count = sum(1 for r in processed_results if r.get("is_valid") is None)
    unknown_reasons = dict(Counter(
        _unknown_reason_key(r) for r in processed_results if r.get("is_valid") is None
    ).most_common())

    logger.info(
        f"📊 Résultat vérification: {valid_count} actives, {closed_count} closes confirmées, "
        f"{unknown_count} inconnues (ignorées)"
    )
    if unknown_reasons:
        logger.info(f"❔ Inconnues par site et raison : {unknown_reasons}")
    if not dry_run and closed_offers:
        logger.info(f"🗑️ Soft-delete appliqué à {updated_db_count} offres closes confirmées.")

    return {
        "total_checked": total,
        "valid_count": valid_count,
        "closed_count": closed_count,
        "unknown_count": unknown_count,
        "updated_db_count": updated_db_count,
        "deferred_count": deferred_count,
        "unknown_reasons": unknown_reasons,
        "dry_run": dry_run,
        "closed_details": closed_offers[:20],
        "summary": (
            f"Vérification terminée: {total} testées, {valid_count} valides, "
            f"{closed_count} closes, {unknown_count} inconnues/transitoires "
            f"({updated_db_count} marquées supprimées, {deferred_count} reportées)"
        ),
    }


async def verify_job_offers_workflow(
    limit: Optional[int] = 100,
    max_concurrency: int = 5,
    dry_run: bool = False,
    time_budget_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Verify active offers by priority/age and soft-delete confirmed closed offers."""
    pkg = sys.modules["app.tasks.verify_job_offers"]
    pkg.logger.info("🔍 Lancement du workflow de vérification des offres d'emploi...")
    db = await pkg.get_database()
    collection = db["job_offers"]

    offers = await _fetch_offers_to_verify(collection, limit)
    found = len(offers)
    pkg.logger.info(f"📊 {found} offres actives trouvées pour vérification.")
    if found == 0:
        return {
            "total_checked": 0,
            "valid_count": 0,
            "closed_count": 0,
            "unknown_count": 0,
            "updated_db_count": 0,
            "summary": "Aucune offre active à vérifier",
        }

    semaphore = asyncio.Semaphore(max_concurrency)
    updated_db_count = 0
    indeed_verdicts: Dict[str, Dict[str, Any]] = {}

    async def verify_and_persist(offer: Dict[str, Any], http_client: httpx.AsyncClient) -> Dict[str, Any]:
        nonlocal updated_db_count
        url = offer.get("url") or offer.get("source_url")
        try:
            verdict = indeed_verdicts.get(extract_indeed_job_key(url))
            if verdict and verdict["is_valid"] is not None:
                result = {"offer_id": str(offer.get("_id", "")), **verdict, "url": url}
            else:
                result = await pkg.verify_single_offer(offer, semaphore, http_client=http_client)
        except Exception as e:
            pkg.logger.error(f"💥 Exception non interceptée sur l'offre {offer.get('_id')}: {e}")
            result = {
                "offer_id": str(offer.get("_id", "")),
                "status": "unknown",
                "is_valid": None,
                "reason": f"gather_exception: {str(e)}",
                "url": url,
            }
        updated_db_count += await _persist_verification_result(collection, offer, result, dry_run, pkg.logger)
        return result

    deadline = pkg.monotonic() + time_budget_seconds if time_budget_seconds else None
    pending = iter(offers)
    processed_results: List[Dict[str, Any]] = []

    async def worker(http_client: httpx.AsyncClient) -> None:
        for offer in pending:
            if deadline is not None and pkg.monotonic() >= deadline:
                return
            processed_results.append(await verify_and_persist(offer, http_client))

    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
        timeout=10.0,
        transport=pkg.public_only_transport(),
    ) as http_client:
        indeed_keys = list(dict.fromkeys(
            key for o in offers
            if (key := extract_indeed_job_key(o.get("url") or o.get("source_url")))
        ))
        indeed_verdicts = await pkg.check_indeed_jobs(indeed_keys, http_client)
        if indeed_keys:
            decided = sum(1 for v in indeed_verdicts.values() if v["is_valid"] is not None)
            pkg.logger.info(f"🔎 API Indeed : {decided}/{len(indeed_keys)} offres tranchées.")
        await asyncio.gather(*(worker(http_client) for _ in range(max_concurrency)))

    return _build_verify_summary(processed_results, found, updated_db_count, dry_run, pkg.logger)


def verify_job_offers_sync(
    limit: Optional[int] = 100,
    max_concurrency: int = 5,
    dry_run: bool = False,
    time_budget_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Synchronous entrypoint for Airflow PythonOperator."""
    pkg = sys.modules["app.tasks.verify_job_offers"]
    return asyncio.run(
        pkg.verify_job_offers_workflow(
            limit=limit,
            max_concurrency=max_concurrency,
            dry_run=dry_run,
            time_budget_seconds=time_budget_seconds,
        )
    )


async def restore_falsely_deleted_offers(dry_run: bool = True) -> Dict[str, Any]:
    """Restore offers wrongly soft-deleted due to transient HTTP/network failures."""
    pkg = sys.modules["app.tasks.verify_job_offers"]
    db = await pkg.get_database()
    collection = db["job_offers"]

    query = {
        "is_deleted": True,
        "deletion_reason": {"$regex": "^(server_error_|connection_error|timeout|http_error:)"},
    }
    count = await collection.count_documents(query)
    restored = 0

    if not dry_run and count > 0:
        res = await collection.update_many(
            query,
            {
                "$set": {
                    "is_deleted": False,
                    "pipeline_stage": "discovered",
                    "updated_at": datetime.now(timezone.utc),
                },
                "$unset": {
                    "deleted_date": "",
                    "deletion_reason": "",
                },
            },
        )
        restored = res.modified_count

    return {
        "matched": count,
        "restored": restored,
        "dry_run": dry_run,
    }
