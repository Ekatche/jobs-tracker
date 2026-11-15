from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class JobOfferCreate(BaseModel):
    poste: str
    entreprise: str
    description: Optional[str] = None
    localisation: Optional[str] = None
    date: Optional[str] = None
    type_contrat: Optional[str] = None
    salaire: Optional[str] = None
    mode_travail: Optional[str] = None
    competences_cles: Optional[List[str]] = None
    is_deleted: Optional[bool] = False
    deleted_date: Optional[datetime] = None
    deletion_reason: Optional[str] = None
    url: Optional[str] = None
    source_url: Optional[str] = None
    pipeline_stage: Optional[str] = "discovered"
    evaluation_score: Optional[float] = None
    canonical_title: Optional[str] = None
    seniority_level: Optional[str] = None
    alternative_urls: Optional[List[str]] = None


class JobOfferResponse(BaseModel):
    id: str
    poste: str
    entreprise: str
    description: Optional[str] = None
    localisation: Optional[str] = None
    date: Optional[str] = None
    type_contrat: Optional[str] = None
    salaire: Optional[str] = None
    mode_travail: Optional[str] = None
    competences_cles: Optional[List[str]] = None
    url: Optional[str] = None
    is_deleted: Optional[bool] = False
    deleted_date: Optional[datetime] = None
    deletion_reason: Optional[str] = None
    source_url: Optional[str] = None
    pipeline_stage: Optional[str] = "discovered"
    evaluation_score: Optional[float] = None
    canonical_title: Optional[str] = None
    seniority_level: Optional[str] = None
    alternative_urls: Optional[List[str]] = None
    user_interaction: Optional[str] = None
    seen: Optional[bool] = False
    sector: Optional[str] = None
    company_size: Optional[str] = None
    failed_conditions: List[str] = []
    unknown_components: List[str] = []
    relevance_level: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserOfferInteractionRequest(BaseModel):
    status: Literal["saved", "hidden", "applied", "dismissed", "none"]
    notes: Optional[str] = None


class UserOfferInteractionResponse(BaseModel):
    id: Optional[str] = None
    user_id: str
    offer_id: str
    status: str
    seen: Optional[bool] = False
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SeenStatusRequest(BaseModel):
    seen: bool = True


class CollectionScheduleResponse(BaseModel):
    next_collection_at: datetime
    # Profile created since the last collection: targeted queries have not run yet.
    awaiting_first_collection: bool


class JobOfferFilter(BaseModel):
    keywords: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    companies: Optional[List[str]] = None
    min_score: Optional[float] = None
    pipeline_stage: Optional[str] = None
    limit: int = 50
    skip: int = 0
