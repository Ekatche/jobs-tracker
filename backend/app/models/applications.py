from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .common import PyObjectId, utcnow_with_timezone


class ApplicationStatus(str, Enum):
    ETUDE = "En étude"
    APPLIED = "Candidature envoyée"
    SCREENING = "Première sélection"
    INTERVIEW = "Entretien"
    TECHNICAL_TEST = "Test technique"
    NEGOTIATION = "Négociation"
    OFFER = "Offre reçue"
    OFFER_RECEIVED = "Offre reçue"
    ACCEPTED = "Offre acceptée"
    REJECTED = "Refusée"
    WITHDRAWN = "Retirée"


class JobApplication(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId = Field(...)
    offer_id: Optional[str] = None
    company: str = Field(...)
    position: str = Field(...)
    location: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: datetime = Field(default_factory=utcnow_with_timezone)
    status: ApplicationStatus = Field(default=ApplicationStatus.APPLIED)
    description: Optional[str] = None
    notes: Optional[List[str]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: Optional[datetime] = None
    archived: Optional[bool] = False

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "company": "Entreprise XYZ",
                "position": "Développeur Full Stack",
                "url": "https://www.entreprisexyz.com/jobs/123",
                "application_date": "2025-04-08T10:00:00Z",
                "status": "Candidature envoyée",
                "description": "Poste de développeur full stack avec React et Python",
                "notes": ["Entretien téléphonique prévu le 15 avril"],
            }
        },
    }


class JobApplicationCreate(BaseModel):
    company: str
    position: str
    offer_id: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: Optional[datetime] = None
    location: Optional[str] = None
    status: ApplicationStatus = ApplicationStatus.APPLIED
    description: Optional[str] = None
    notes: Optional[List[str]] = None
    archived: Optional[bool] = False

    model_config = {
        "json_schema_extra": {
            "example": {
                "company": "Entreprise XYZ",
                "position": "Développeur Full Stack",
                "location": "Paris, France",
                "url": "https://www.entreprisexyz.com/jobs/123",
                "application_date": "2025-04-08T10:00:00Z",
                "status": "Candidature envoyée",
                "description": "Poste de développeur full stack avec React et Python",
                "offer_id": "673f1c9d8e5f2a1b3c4d5e6f",
            }
        }
    }


class JobApplicationUpdate(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    offer_id: Optional[str] = None
    location: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: Optional[datetime] = None
    status: Optional[ApplicationStatus] = None
    description: Optional[str] = None
    notes: Optional[List[str]] = None
    archived: Optional[bool] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "Entretien",
                "notes": [
                    "Entretien téléphonique prévu le 15 avril",
                    "Prévoir de poser des questions sur l'équipe",
                ],
            }
        }
    }


class JobApplicationResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    company: str
    position: str
    offer_id: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: datetime
    status: ApplicationStatus
    location: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[List[str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    archived: Optional[bool] = False
    days_since_application: Optional[int] = None
    follow_up_alert: Optional[str] = None

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class PipelineSummaryResponse(BaseModel):
    total_active: int
    total_archived: int
    status_counts: Dict[str, int]
    interview_conversion_rate: float
    offer_conversion_rate: float
    follow_ups_due_count: int
    thank_yous_due_count: int
    evaluated_offers_ready_count: int = 0


class TaskStatus(str, Enum):
    TODO = "À faire"
    IN_PROGRESS = "En cours"
    DONE = "Terminée"


class Task(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId = Field(...)
    title: str = Field(...)
    description: Optional[str] = None
    status: TaskStatus = Field(default=TaskStatus.TODO)
    priority: Optional[str] = "normale"
    category: Optional[str] = "Général"
    company: Optional[str] = None
    archived: Optional[bool] = False
    due_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "title": "Préparer le CV",
                "description": "Mettre à jour le CV avec les dernières expériences.",
                "status": "À faire",
                "priority": "haute",
                "category": "Candidature",
                "due_date": "2025-04-10T10:00:00Z",
            }
        },
    }


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    company: Optional[str] = None
    due_date: Optional[datetime] = None
    archived: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = "normale"
    category: Optional[str] = "Général"
    company: Optional[str] = None
    due_date: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")
