from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from bson import ObjectId
from pydantic import BaseModel, Field, GetCoreSchemaHandler, HttpUrl
from pydantic_core import core_schema


# Classe personnalisée pour gérer les ObjectId de MongoDB
class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.str_schema(
            metadata={"title": "ObjectId", "description": "MongoDB ObjectId"}
        )

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)


# Modèle utilisateur
class UserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str = Field(...)
    email: str = Field(...)
    hashed_password: str = Field(...)
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "username": "johndoe",
                "email": "john.doe@example.com",
                "full_name": "John Doe",
                "disabled": False,
            }
        },
    }


# Modèle pour la création d'utilisateur (sans les champs générés automatiquement)
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "johndoe",
                "email": "john.doe@example.com",
                "password": "strongpassword",
                "full_name": "John Doe",
            }
        }
    }


# Modèle pour les réponses (sans le mot de passe)
class UserResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str
    email: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    created_at: datetime

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# Énumération pour le statut de candidature
class ApplicationStatus(str, Enum):
    ETUDE = "En étude"
    APPLIED = "Candidature envoyée"
    SCREENING = "Première sélection"
    INTERVIEW = "Entretien"
    TECHNICAL_TEST = "Test technique"
    NEGOTIATION = "Négociation"
    OFFER = "Offre reçue"
    ACCEPTED = "Offre acceptée"
    REJECTED = "Refusée"
    WITHDRAWN = "Retirée"


# Modèle pour les candidatures
class JobApplication(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId = Field(...)
    company: str = Field(...)
    position: str = Field(...)
    location: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: datetime = Field(default_factory=datetime.utcnow)
    status: ApplicationStatus = Field(default=ApplicationStatus.APPLIED)
    description: Optional[str] = None
    notes: Optional[List[str]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

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


# Modèle pour la création d'une candidature
class JobApplicationCreate(BaseModel):
    company: str
    position: str
    url: Optional[HttpUrl] = None
    application_date: Optional[datetime] = None
    location: Optional[str] = None
    status: ApplicationStatus = ApplicationStatus.APPLIED
    description: Optional[str] = None

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
            }
        }
    }


# Modèle pour la mise à jour d'une candidature
class JobApplicationUpdate(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    location: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: Optional[datetime] = None
    status: Optional[ApplicationStatus] = None
    description: Optional[str] = None
    notes: Optional[List[str]] = None

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


# Modèle pour les réponses de candidature
class JobApplicationResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    company: str
    position: str
    url: Optional[HttpUrl] = None
    application_date: datetime
    status: ApplicationStatus
    location: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[List[str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
