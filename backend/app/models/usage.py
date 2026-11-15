from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import PyObjectId, utcnow_with_timezone
from .users import UserRole, UserTier


class ApiUsageAction(str, Enum):
    COVER_LETTER = "cover_letter"
    EVALUATION = "evaluation"
    CV_TAILORING = "cv_tailoring"
    CV_PARSING = "cv_parsing"
    INTERVIEW_PREP = "interview_prep"
    OFFER_SUMMARY = "offer_summary"
    ROLE_SUGGESTION = "role_suggestion"
    LETTER_REWRITE = "letter_rewrite"


class ApiUsageRecord(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    action: ApiUsageAction
    models_used: List[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class TierQuota(BaseModel):
    action: ApiUsageAction
    monthly_limit: Optional[int] = None


class ActionQuotaUsage(BaseModel):
    action: ApiUsageAction
    used: int = 0
    monthly_limit: Optional[int] = None
    remaining: Optional[int] = None


class UserQuotaSummary(BaseModel):
    user_id: PyObjectId
    tier: UserTier
    year: int
    month: int
    usage: Dict[str, ActionQuotaUsage]
    total_cost_usd: float = 0.0
    total_tokens: int = 0


class AdminUserSummaryResponse(BaseModel):
    id: str
    pseudonym_email: str
    pseudonym_name: str
    tier: UserTier
    role: UserRole
    disabled: bool
    created_at: datetime
    last_active_at: Optional[datetime] = None
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_requests: int = 0


class AdminUserUpdateTierRequest(BaseModel):
    tier: UserTier


class AdminUserToggleStatusRequest(BaseModel):
    disabled: bool


class ModelCostItem(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    requests_count: int = 0


class ActionCostItem(BaseModel):
    action: str
    label: str
    total_tokens: int = 0
    cost_usd: float = 0.0
    requests_count: int = 0


class AdminCostSummaryResponse(BaseModel):
    period: str
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_requests: int = 0
    avg_cost_per_user: float = 0.0
    active_users_count: int = 0
    model_breakdown: List[ModelCostItem] = Field(default_factory=list)
    action_breakdown: List[ActionCostItem] = Field(default_factory=list)
