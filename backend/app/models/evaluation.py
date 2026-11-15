from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import PyObjectId, utcnow_with_timezone


class RequirementMatch(BaseModel):
    requirement: str
    weight: Literal["critical", "high", "meaningful"] = "high"
    importance_evidence_tier: Literal["stated", "structural", "inferred"] = "stated"
    candidate_evidence: str
    verbatim_quote: str
    status: Literal["full_match", "partial_match"] = "full_match"
    # "stated": explicit profile evidence; "inferred": deduced without explicit mention
    # (cannot alone justify full_match on critical/high requirements in evaluator.py).
    evidence_tier: Literal["stated", "inferred"] = "stated"
    quote_verified: bool = True


class MissingRequirement(BaseModel):
    requirement: str
    weight: Literal["critical", "high", "meaningful"] = "high"
    importance_evidence_tier: Literal["stated", "structural", "inferred"] = "stated"
    reason: str
    impact_on_role: Optional[str] = None


class PreferenceMismatch(BaseModel):
    """Deterministic mismatch between structured offer fields and candidate preferences."""

    criterion: str
    offer_value: str
    expected: str
    weight: Literal["critical", "high", "meaningful"] = "high"


class RiskSummaryItem(BaseModel):
    """Single deterministic risk status row in the aggregated Risk Summary."""

    signal: str
    status: str


class DraftApplicationAnswer(BaseModel):
    """Draft response for common application form questions (Block H)."""

    question: str
    answer: str


class BlocA(BaseModel):
    summary: str = ""
    archetype: str = ""
    red_flags: List[str] = Field(default_factory=list)
    geo_mismatch: bool = False
    visa_sponsoring_refused: bool = False
    domain_mismatch: bool = False
    domain_coherence: Literal["match", "partial", "mismatch", ""] = ""
    preference_mismatches: List[PreferenceMismatch] = Field(default_factory=list)
    notes: Optional[str] = None


class BlocB(BaseModel):
    matched_requirements: List[RequirementMatch] = Field(default_factory=list)
    missing_requirements: List[MissingRequirement] = Field(default_factory=list)
    score_justification: str = ""
    dropped_requirements_count: int = 0


class BlocG(BaseModel):
    is_ghost_job: bool = False
    is_scam_risk: bool = False
    reposted_frequency: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    employment_classification_risk: Optional[str] = None
    pay_range_width_warning: Optional[str] = None
    ai_buzzword_mismatch: Optional[str] = None
    company_history_note: Optional[str] = None
    risk_summary: List[RiskSummaryItem] = Field(default_factory=list)


class BlocH(BaseModel):
    """Auto-generated draft application answers and prep highlights when score >= 4.0."""

    eligible: bool = False
    answers: List[DraftApplicationAnswer] = Field(default_factory=list)
    key_achievements: List[str] = Field(default_factory=list)
    gaps_flagged: List[str] = Field(default_factory=list)
    jd_keywords: List[str] = Field(default_factory=list)


class OfferEvaluation(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    offer_id: PyObjectId
    score: float = 1.0
    headline: str = ""
    pipeline_stage: Literal["discovered", "evaluated", "expired"] = "evaluated"
    bloc_a: BlocA = Field(default_factory=BlocA)
    bloc_b: BlocB = Field(default_factory=BlocB)
    bloc_g: BlocG = Field(default_factory=BlocG)
    bloc_h: BlocH = Field(default_factory=BlocH)
    models_used: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class OfferEvaluationResponse(BaseModel):
    id: Optional[str] = None
    user_id: str
    offer_id: str
    score: float
    headline: str
    pipeline_stage: str
    bloc_a: BlocA
    bloc_b: BlocB
    bloc_g: BlocG
    bloc_h: BlocH = Field(default_factory=BlocH)
    created_at: datetime
    updated_at: datetime
