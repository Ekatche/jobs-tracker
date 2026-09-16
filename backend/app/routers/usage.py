import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.database import get_database
from app.models import (
    ApiUsageAction,
    ApiUsageRecord,
    UserModel,
    UserQuotaSummary,
    UserTier,
)
from app.services.usage_tracker import (
    TIER_MONTHLY_LIMITS,
    get_user_monthly_usage,
)
from app.utils import serialize_mongodb_doc

logger = logging.getLogger(__name__)

usage_router = APIRouter(prefix="/usage", tags=["usage"])

TIER_PRICING_INFO = {
    UserTier.FREE: {
        "name": "Free",
        "price_eur": 0.0,
        "billing_period": "forever",
        "limits": {action.value: limit for action, limit in TIER_MONTHLY_LIMITS[UserTier.FREE].items()},
    },
    UserTier.ADVANCED: {
        "name": "Advanced",
        "price_eur": 9.90,
        "billing_period": "monthly",
        "limits": {action.value: limit for action, limit in TIER_MONTHLY_LIMITS[UserTier.ADVANCED].items()},
    },
    UserTier.PRO: {
        "name": "Pro",
        "price_eur": 24.90,
        "billing_period": "monthly",
        "limits": {action.value: limit for action, limit in TIER_MONTHLY_LIMITS[UserTier.PRO].items()},
    },
}


@usage_router.get("/me", response_model=List[ApiUsageRecord])
async def get_my_usage_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[ApiUsageAction] = None,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Retrieve paginated usage records for the authenticated user."""
    query: Dict[str, Any] = {"user_id": str(current_user.id)}
    if action is not None:
        query["action"] = action.value

    cursor = db["api_usage"].find(query).sort("created_at", -1).skip(skip).limit(limit)
    records = []
    async for doc in cursor:
        records.append(ApiUsageRecord(**serialize_mongodb_doc(doc)))
    return records


@usage_router.get("/me/summary", response_model=UserQuotaSummary)
async def get_my_usage_summary(
    year: Optional[int] = Query(None, ge=2020, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Retrieve current monthly consumption and quota limits for the authenticated user."""
    summary = await get_user_monthly_usage(db, current_user.id, year=year, month=month)
    return summary


@usage_router.get("/tiers")
async def get_available_tiers():
    """Public endpoint returning available subscription tiers and their respective limits."""
    return TIER_PRICING_INFO
