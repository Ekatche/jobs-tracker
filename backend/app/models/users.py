from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl

from .common import PyObjectId, utcnow_with_timezone


class UserTier(str, Enum):
    FREE = "free"
    ADVANCED = "advanced"
    PRO = "pro"


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class UserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str = Field(...)
    email: str = Field(...)
    hashed_password: str = Field(...)
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    role: UserRole = UserRole.USER
    tier: UserTier = UserTier.FREE
    onboarding_completed: Optional[bool] = False
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: Optional[datetime] = None
    cv_url: Optional[HttpUrl] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "username": "johndoe",
                "email": "john.doe@example.com",
                "full_name": "John Doe",
                "disabled": False,
                "tier": "free",
                "onboarding_completed": False,
                "cv_url": "https://monapp.com/uploads/cv_johndoe.pdf",
            }
        },
    }


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    invitation_code: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "johndoe",
                "email": "john.doe@example.com",
                "password": "strongpassword",
                "full_name": "John Doe",
                "invitation_code": "secret-invite-token",
            }
        }
    }


class UserResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str
    email: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    role: UserRole = UserRole.USER
    tier: UserTier = UserTier.FREE
    onboarding_completed: Optional[bool] = False
    created_at: datetime

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
