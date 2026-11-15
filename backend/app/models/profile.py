from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from .common import PyObjectId, utcnow_with_timezone

CandidateSource = Literal["cv", "github", "website", "manual", "saisie"]
# Includes "site" for backwards compatibility with existing provenance data.
CandidateProvenanceSource = Union[CandidateSource, Literal["site"]]


class CandidateAchievement(BaseModel):
    text: str
    metric: Optional[str] = None


class CandidateExperience(BaseModel):
    company: str
    role: Optional[str] = None
    location: Optional[str] = None
    contract: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    sector: Optional[str] = None
    missions: List[str] = Field(default_factory=list)
    missions_alt: List[str] = Field(default_factory=list)
    missions_source: Optional[str] = None
    achievements: List[CandidateAchievement] = Field(default_factory=list)
    stack: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)


class CandidateProject(BaseModel):
    name: str
    description: str = ""
    stack: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    repo: Optional[str] = None
    year: Optional[str] = None
    context: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)

    @field_validator("context", mode="before")
    @classmethod
    def clean_context(cls, v: Any) -> Optional[str]:
        """Coerce non-string LLM output to None instead of failing validation."""
        if isinstance(v, str):
            return v.strip() or None
        return None


class CandidateEducation(BaseModel):
    school: str = ""
    degree: str = ""
    years: Optional[str] = None
    topics: List[str] = Field(default_factory=list)


class CandidateCertification(BaseModel):
    name: str = ""
    issuer: str = ""
    year: Optional[str] = None
    topics: List[str] = Field(default_factory=list)


class CandidateConflict(BaseModel):
    company: str = ""
    field: str
    kept: Any = None
    kept_source: str = ""
    discarded: Any = None
    discarded_source: str = ""


class CandidateProvenance(BaseModel):
    field_path: str
    source: CandidateProvenanceSource


class RemotePolicy(str, Enum):
    FULL_REMOTE = "full_remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"
    FLEXIBLE = "flexible"


class CandidatePreferences(BaseModel):
    target_roles: List[str] = Field(default_factory=list)
    seniority_level: Optional[str] = None
    seniority_levels: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    remote_policy: RemotePolicy = RemotePolicy.FLEXIBLE
    min_salary: Optional[int] = None
    target_salary: Optional[int] = None
    currency: str = "EUR"
    contract_types: List[str] = Field(default_factory=list)
    notice_period: Optional[str] = None
    work_authorization: Optional[str] = None
    excluded_keywords: List[str] = Field(default_factory=list)
    preferred_industries: List[str] = Field(default_factory=list)
    preferred_company_sizes: List[str] = Field(default_factory=list)
    search_active: bool = True

    @model_validator(mode="after")
    def sync_seniority(self) -> "CandidatePreferences":
        if self.seniority_levels and not self.seniority_level:
            self.seniority_level = self.seniority_levels[0]
        elif self.seniority_level and not self.seniority_levels:
            self.seniority_levels = [self.seniority_level]
        return self


class CandidateProfile(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    headline: str = ""
    summary: str = ""
    contact: Dict[str, Optional[str]] = Field(default_factory=dict)
    preferences: CandidatePreferences = Field(default_factory=CandidatePreferences)
    experiences: List[CandidateExperience] = Field(default_factory=list)
    projects: List[CandidateProject] = Field(default_factory=list)
    education: List[CandidateEducation] = Field(default_factory=list)
    certifications: List[CandidateCertification] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    skills: Dict[str, List[str]] = Field(default_factory=dict)
    provenance: List[CandidateProvenance] = Field(default_factory=list)
    sources: Dict[str, dict] = Field(default_factory=dict)
    conflicts: List[CandidateConflict] = Field(default_factory=list)
    excluded_projects: List[str] = Field(default_factory=list)
    excluded_education: List[str] = Field(default_factory=list)
    excluded_certifications: List[str] = Field(default_factory=list)
    writing_style: Optional[str] = None
    writing_samples: Optional[str] = None
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
