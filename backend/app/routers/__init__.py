from .auth import auth_router
from .users import user_router
from .applications import job_router
from .tasks import task_router
from .job_offers import job_offers_router
from .cover_letters import cover_letters_router

__all__ = [
    "auth_router",
    "user_router",
    "job_router",
    "task_router",
    "job_offers_router",
    "cover_letters_router",
]
