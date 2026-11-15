from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import PyObjectId, utcnow_with_timezone


class CoverLetterVersion(BaseModel):
    n: int
    body: str
    origin: Literal["generated", "edited"]
    models: Dict[str, str] = Field(default_factory=dict)
    prompt_version: str = "1.0"
    guard_report: Dict[str, Any] = Field(default_factory=dict)
    critic_verdict: Optional[Dict[str, Any]] = None
    revised: bool = False
    created_at: datetime = Field(default_factory=utcnow_with_timezone)


class CoverLetter(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    application_id: PyObjectId
    status: Literal["pending", "ready", "needs_review", "failed"] = "pending"
    guard_context: Optional[Dict[str, Any]] = None
    versions: List[CoverLetterVersion] = Field(default_factory=list)
    current_version: int = 1
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class TailoredExperienceItem(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: str
    end_date: Optional[str] = "Présent"
    bullet_points: List[str] = Field(
        default_factory=list,
        description="Puces d'impact réordonnées et alignées sur l'offre",
    )
    relevant_technologies: List[str] = Field(default_factory=list)
    relevance: Optional[str] = Field(
        default=None,
        description="« principale » si l'expérience prouve des exigences de l'offre, sinon « secondaire »",
    )


class TailoredProjectItem(BaseModel):
    name: str
    description: str
    technologies: List[str] = Field(default_factory=list)
    url: Optional[str] = None


class TailoredSkillGroup(BaseModel):
    category: str
    skills: List[str] = Field(default_factory=list)


class TailoredLanguage(BaseModel):
    language: str
    level: str


class TailoredEducationItem(BaseModel):
    degree: str
    institution: str
    year: str
    details: Optional[str] = None


def _format_certification_item(item: Any) -> Optional[str]:
    """Flatten a certification string or CandidateCertification-like dict into a clean display label."""
    if isinstance(item, str):
        return item.strip() or None
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("title") or item.get("certification") or "").strip()
        if not name:
            return None
        issuer = str(item.get("issuer") or item.get("organization") or "").strip()
        year = str(item.get("year") or item.get("date") or "").strip()
        parts = [name]
        if issuer and issuer.lower() not in name.lower():
            parts.append(issuer)
        label = " — ".join(parts)
        if year and year not in label:
            label = f"{label} ({year})"
        return label
    return None


class TailoredCVSchema(BaseModel):
    target_role_title: str
    professional_summary: str = Field(..., description="Accroche ciblée 3-4 lignes")
    prioritized_skills: List[TailoredSkillGroup] = Field(default_factory=list)
    experiences: List[TailoredExperienceItem] = Field(default_factory=list)
    featured_projects: List[TailoredProjectItem] = Field(default_factory=list)
    education: List[TailoredEducationItem] = Field(default_factory=list)
    languages: List[TailoredLanguage] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)

    @field_validator("certifications", mode="before")
    @classmethod
    def normalize_certifications(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            v = [v]
        result: List[str] = []
        for item in v:
            formatted = _format_certification_item(item)
            if formatted:
                result.append(formatted)
        return result


class TailoredResumeInDB(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    offer_id: PyObjectId
    application_id: Optional[PyObjectId] = None
    target_role: str
    target_company: str
    template: str = "sidebar_elegance"
    accent: str = "marine"
    with_photo: bool = False
    content: TailoredCVSchema
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
