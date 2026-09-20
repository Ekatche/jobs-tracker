import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from bson import ObjectId
from fastapi import HTTPException

from app.models import (
    ActionQuotaUsage,
    ApiUsageAction,
    ApiUsageRecord,
    PyObjectId,
    UserQuotaSummary,
    UserTier,
    utcnow_with_timezone,
)

logger = logging.getLogger(__name__)

# Predefined monthly limits by tier
TIER_MONTHLY_LIMITS: Dict[UserTier, Dict[ApiUsageAction, Optional[int]]] = {
    UserTier.FREE: {
        ApiUsageAction.COVER_LETTER: 5,
        ApiUsageAction.EVALUATION: 20,
        ApiUsageAction.CV_TAILORING: 2,
        ApiUsageAction.CV_PARSING: 2,
        ApiUsageAction.INTERVIEW_PREP: 1,
        ApiUsageAction.OFFER_SUMMARY: 30,
        ApiUsageAction.ROLE_SUGGESTION: 10,
    },
    UserTier.ADVANCED: {
        ApiUsageAction.COVER_LETTER: 30,
        ApiUsageAction.EVALUATION: 100,
        ApiUsageAction.CV_TAILORING: 15,
        ApiUsageAction.CV_PARSING: 10,
        ApiUsageAction.INTERVIEW_PREP: 10,
        ApiUsageAction.OFFER_SUMMARY: 150,
        ApiUsageAction.ROLE_SUGGESTION: 50,
    },
    UserTier.PRO: {
        ApiUsageAction.COVER_LETTER: None,  # Unlimited
        ApiUsageAction.EVALUATION: None,
        ApiUsageAction.CV_TAILORING: None,
        ApiUsageAction.CV_PARSING: None,
        ApiUsageAction.INTERVIEW_PREP: None,
        ApiUsageAction.OFFER_SUMMARY: None,
        ApiUsageAction.ROLE_SUGGESTION: None,
    },
}

# Pricing table fallback for estimated costs per 1K tokens in USD
MODEL_COST_PER_1K_TOKENS: Dict[str, Dict[str, float]] = {
    # OpenAI
    "gpt-5.6-luna": {"input": 0.002, "output": 0.006},
    "gpt-5.6-sol": {"input": 0.003, "output": 0.012},
    "gpt-5-nano": {"input": 0.0005, "output": 0.0015},
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "o1": {"input": 0.015, "output": 0.060},
    "o3-mini": {"input": 0.0011, "output": 0.0044},
    # Google (prix Standard tier vérifiés sur ai.google.dev/gemini-api/docs/pricing, 2026-09-16,
    # valables jusqu'au 31/12/2026 — gemini-3.8-flash et gemini-3.7-flash montent ensuite à 1.50/7.50)
    "gemini-3.8-flash": {"input": 0.00075, "output": 0.00375},
    "gemini-3.7-flash": {"input": 0.00075, "output": 0.00375},
    "gemini-2.5-flash": {"input": 0.0003, "output": 0.0025},
    "gemini-3.5-flash-lite": {"input": 0.000075, "output": 0.0003},
    "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    # Mistral
    # pixtral-12b-2409 déprécié par Mistral le 2/12/2025 (docs.mistral.ai/models/pixtral-12b-24-09).
    # Son remplacement officiel (ministral-14b-2512) n'a pas de preuve chiffrée de parité
    # vision/OCR publiée ; pixtral-large-2411 (alternative envisagée) est lui-même déprécié
    # depuis le 27/2/2026. cv_parser.py::parse_cv_with_vlm utilise donc désormais
    # mistral-medium-3-5-26-04 (déjà dans cette table), remplacement officiel de Pixtral Large.
    "mistral-large-2407": {"input": 0.002, "output": 0.006},
    "mistral-large-3-25-12": {"input": 0.0005, "output": 0.0015},
    "mistral-medium-3-5-26-04": {"input": 0.0015, "output": 0.0075},
    "mistral-small-4-0-26-03": {"input": 0.00015, "output": 0.0006},
    # Default fallback
    "default": {"input": 0.0015, "output": 0.005},
}


def _normalize_model_name(model: str) -> str:
    """Normalize model string by removing provider prefixes."""
    clean = model.strip().lower()
    if "/" in clean:
        clean = clean.split("/")[-1]
    return clean


def estimate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD based on model pricing table."""
    norm = _normalize_model_name(model)
    rates = MODEL_COST_PER_1K_TOKENS.get(norm, MODEL_COST_PER_1K_TOKENS["default"])
    cost = (input_tokens / 1000.0) * rates["input"] + (output_tokens / 1000.0) * rates["output"]
    return round(cost, 6)


async def record_api_usage(
    db,
    user_id: Union[str, ObjectId, PyObjectId],
    action: Union[ApiUsageAction, str],
    models_used: Optional[List[str]] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    estimated_cost_usd: Optional[float] = None,
    latency_ms: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> ApiUsageRecord:
    """Record an API usage event in the api_usage collection."""
    if isinstance(action, str):
        action = ApiUsageAction(action)

    if models_used is None and model:
        models_used = [model]
    models_list = models_used or []
    total_tokens = input_tokens + output_tokens

    if estimated_cost_usd is None:
        if models_list:
            estimated_cost_usd = sum(
                estimate_llm_cost(m, input_tokens // len(models_list), output_tokens // len(models_list))
                for m in models_list
            )
        else:
            estimated_cost_usd = estimate_llm_cost("default", input_tokens, output_tokens)

    record_dict = {
        "user_id": str(user_id),
        "action": action.value,
        "models_used": models_list,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(estimated_cost_usd, 6),
        "latency_ms": latency_ms,
        "success": success,
        "error_message": error_message,
        "metadata": metadata or {},
        "created_at": utcnow_with_timezone(),
    }

    result = await db["api_usage"].insert_one(record_dict)
    record_dict["_id"] = str(result.inserted_id)

    return ApiUsageRecord(**record_dict)


async def get_user_tier(db, user_id: Union[str, ObjectId, PyObjectId]) -> UserTier:
    """Retrieve user tier from database, defaulting to Free."""
    user_doc = None
    try:
        user_doc = await db["users"].find_one({"_id": ObjectId(str(user_id))})
    except Exception:
        user_doc = await db["users"].find_one({"_id": str(user_id)})

    if not user_doc:
        return UserTier.FREE

    tier_val = user_doc.get("tier", UserTier.FREE.value)
    try:
        return UserTier(tier_val)
    except ValueError:
        return UserTier.FREE


async def get_user_monthly_usage(
    db,
    user_id: Union[str, ObjectId, PyObjectId],
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> UserQuotaSummary:
    """Calculate usage summary and remaining quotas for the specified year/month."""
    now = datetime.now(timezone.utc)
    target_year = year if year is not None else now.year
    target_month = month if month is not None else now.month

    # Boundary timestamps for month in UTC
    start_date = datetime(target_year, target_month, 1, 0, 0, 0, tzinfo=timezone.utc)
    if target_month == 12:
        end_date = datetime(target_year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    else:
        end_date = datetime(target_year, target_month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    user_tier = await get_user_tier(db, user_id)
    tier_limits = TIER_MONTHLY_LIMITS.get(user_tier, TIER_MONTHLY_LIMITS[UserTier.FREE])

    # Aggregation query to compute count per action and total costs
    pipeline = [
        {
            "$match": {
                "user_id": str(user_id),
                "created_at": {"$gte": start_date, "$lt": end_date},
                "success": True,
            }
        },
        {
            "$group": {
                "_id": "$action",
                "count": {"$sum": 1},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_cost": {"$sum": "$estimated_cost_usd"},
            }
        },
    ]

    cursor = db["api_usage"].aggregate(pipeline)
    raw_counts: Dict[str, int] = {}
    total_tokens = 0
    total_cost_usd = 0.0

    async for doc in cursor:
        action_name = doc["_id"]
        raw_counts[action_name] = doc.get("count", 0)
        total_tokens += doc.get("total_tokens", 0)
        total_cost_usd += doc.get("total_cost", 0.0)

    # Build detailed per-action summary
    usage_map: Dict[str, ActionQuotaUsage] = {}
    for action in ApiUsageAction:
        action_key = action.value
        used = raw_counts.get(action_key, 0)
        monthly_limit = tier_limits.get(action)
        remaining = max(0, monthly_limit - used) if monthly_limit is not None else None

        usage_map[action_key] = ActionQuotaUsage(
            action=action,
            used=used,
            monthly_limit=monthly_limit,
            remaining=remaining,
        )

    return UserQuotaSummary(
        user_id=PyObjectId(str(user_id)),
        tier=user_tier,
        year=target_year,
        month=target_month,
        usage=usage_map,
        total_cost_usd=round(total_cost_usd, 4),
        total_tokens=total_tokens,
    )


async def check_user_quota(
    db,
    user_id: Union[str, ObjectId, PyObjectId],
    action: Union[ApiUsageAction, str],
) -> Tuple[bool, int, Optional[int]]:
    """
    Check whether the user has quota remaining for the specified action.
    Returns: (is_allowed, current_used_count, monthly_limit)
    """
    if isinstance(action, str):
        action = ApiUsageAction(action)

    summary = await get_user_monthly_usage(db, user_id)
    action_usage = summary.usage.get(action.value)

    if not action_usage:
        return True, 0, None

    if action_usage.monthly_limit is None:
        return True, action_usage.used, None

    is_allowed = action_usage.used < action_usage.monthly_limit
    return is_allowed, action_usage.used, action_usage.monthly_limit


async def require_user_quota(
    db,
    user_id: Union[str, ObjectId, PyObjectId],
    action: Union[ApiUsageAction, str],
) -> None:
    """
    Raise HTTP 429 if the user has reached their monthly quota limit.
    Bypassed when DISABLE_QUOTA_BLOCKING is enabled (default: True).
    """
    if os.getenv("DISABLE_QUOTA_BLOCKING", "true").lower() in ("true", "1", "yes"):
        return

    allowed, used, limit = await check_user_quota(db, user_id, action)
    if not allowed:
        action_name = action.value if isinstance(action, ApiUsageAction) else str(action)
        raise HTTPException(
            status_code=429,
            detail=f"Monthly quota limit reached for action '{action_name}' ({used}/{limit}). Upgrade your plan to continue.",
        )
