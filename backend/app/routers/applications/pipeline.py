import sys
from typing import Any, Dict, List

from bson import ObjectId
from fastapi import APIRouter, Depends

from ...auth import get_current_user
from ...database import get_database
from ...models import ApplicationStatus, PipelineSummaryResponse, UserModel
from ...utils import serialize_mongodb_doc

router = APIRouter()

_INTERVIEW_STAGES = {
    ApplicationStatus.SCREENING.value,
    ApplicationStatus.INTERVIEW.value,
    ApplicationStatus.TECHNICAL_TEST.value,
    ApplicationStatus.NEGOTIATION.value,
    ApplicationStatus.OFFER.value,
    ApplicationStatus.OFFER_RECEIVED.value,
    ApplicationStatus.ACCEPTED.value,
}
_OFFER_STAGES = {
    ApplicationStatus.OFFER.value,
    ApplicationStatus.OFFER_RECEIVED.value,
    ApplicationStatus.ACCEPTED.value,
}


def _pkg():
    return sys.modules[__package__]


@router.get("/pipeline/summary", response_model=PipelineSummaryResponse)
async def get_pipeline_summary(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Calcule le résumé du pipeline, les taux de conversion et les cadences de relance."""
    pkg = _pkg()
    user_apps = (
        await db["applications"]
        .find({"user_id": current_user.id})
        .to_list(length=1000)
    )

    total_active = 0
    total_archived = 0
    status_counts: Dict[str, int] = {s.value: 0 for s in ApplicationStatus}
    follow_ups_due = 0
    thank_yous_due = 0
    interview_count = 0
    offer_count = 0
    total_started = 0

    for doc in user_apps:
        enriched = pkg.enrich_application_with_cadences(serialize_mongodb_doc(doc))
        status_val = enriched.get("status")

        if enriched.get("archived", False):
            total_archived += 1
        else:
            total_active += 1

        if status_val:
            status_counts[status_val] = status_counts.get(status_val, 0) + 1
            total_started += 1
            if status_val in _INTERVIEW_STAGES:
                interview_count += 1
            if status_val in _OFFER_STAGES:
                offer_count += 1

        # Alertes de cadences
        if enriched.get("follow_up_alert") == "relance_due":
            follow_ups_due += 1
        elif enriched.get("follow_up_alert") == "remerciement_due":
            thank_yous_due += 1

    interview_rate = (
        round((interview_count / total_started * 100), 1) if total_started > 0 else 0.0
    )
    offer_rate = (
        round((offer_count / total_started * 100), 1) if total_started > 0 else 0.0
    )

    # Décompte des offres évaluées avec score >= 3.5 prêtes à postuler
    eval_count = await db["offer_evaluations"].count_documents({
        "user_id": str(current_user.id),
        "score": {"$gte": 3.5},
    })

    return PipelineSummaryResponse(
        total_active=total_active,
        total_archived=total_archived,
        status_counts=status_counts,
        interview_conversion_rate=interview_rate,
        offer_conversion_rate=offer_rate,
        follow_ups_due_count=follow_ups_due,
        thank_yous_due_count=thank_yous_due,
        evaluated_offers_ready_count=eval_count,
    )


@router.get("/pipeline/calibrate")
async def calibrate_pipeline_scores(
    min_band_n: int = 5,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
) -> Dict[str, Any]:
    """Calibrate AI offer scores against observed pipeline outcomes (excluding in-flight apps)."""
    pkg = _pkg()
    user_id_str = str(current_user.id)
    user_id_filter: List[Dict[str, Any]] = [{"user_id": user_id_str}]
    if ObjectId.is_valid(user_id_str):
        user_id_filter.append({"user_id": ObjectId(user_id_str)})

    apps = await db["applications"].find({"$or": user_id_filter}).to_list(length=5000)
    evals = await db["offer_evaluations"].find({"$or": user_id_filter}).to_list(length=5000)
    return pkg.compute_score_calibration(apps, evals, min_band_n=max(1, min_band_n))
