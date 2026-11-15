from fastapi import APIRouter

from app.services.interview_prep_service import (
    RequirementPick,
    build_story_slots,
    evaluate_practice_answer,
    export_interview_prep_markdown,
    generate_anticipated_questions,
    generate_audience_packs,
    generate_reverse_questions,
    write_stories_for_requirements,
)
from app.services.star_bank import (
    bank_story_ids,
    ensure_prep_migrated,
    get_bank_story,
    hydrate_prep,
    load_bank,
    slots_with_stories,
)
from app.services.star_bank_rules import guess_experience
from app.services.usage_tracker import require_user_quota

from .core import (
    export_interview_prep,
    get_interview_prep,
    practice_answer_endpoint,
    router as _core_router,
    update_interview_prep,
)
from .generation import (
    generate_all_endpoint,
    generate_audience_packs_endpoint,
    generate_questions_endpoint,
    generate_reverse_questions_endpoint,
    generate_stories_endpoint,
    router as _generation_router,
)
from .helpers import (
    PracticeAnswerRequest,
    UpdateInterviewPrepRequest,
    UpdateStorySlotRequest,
    generation_cancelled as _generation_cancelled,
    get_prep_or_empty as _get_prep_or_empty,
    get_profile_and_offer as _get_profile_and_offer,
)
from .slots import (
    delete_interview_prep_slot,
    manual_story_interview_prep_slot,
    router as _slots_router,
    update_interview_prep_slot,
    write_interview_prep_slot,
)

interview_prep_router = APIRouter(tags=["interview-prep"])
interview_prep_router.include_router(_core_router)
interview_prep_router.include_router(_generation_router)
interview_prep_router.include_router(_slots_router)

__all__ = [
    "PracticeAnswerRequest",
    "RequirementPick",
    "UpdateInterviewPrepRequest",
    "UpdateStorySlotRequest",
    "_generation_cancelled",
    "_get_prep_or_empty",
    "_get_profile_and_offer",
    "bank_story_ids",
    "build_story_slots",
    "delete_interview_prep_slot",
    "ensure_prep_migrated",
    "evaluate_practice_answer",
    "export_interview_prep",
    "export_interview_prep_markdown",
    "generate_all_endpoint",
    "generate_anticipated_questions",
    "generate_audience_packs",
    "generate_audience_packs_endpoint",
    "generate_questions_endpoint",
    "generate_reverse_questions",
    "generate_reverse_questions_endpoint",
    "generate_stories_endpoint",
    "get_bank_story",
    "get_interview_prep",
    "guess_experience",
    "hydrate_prep",
    "interview_prep_router",
    "load_bank",
    "manual_story_interview_prep_slot",
    "practice_answer_endpoint",
    "require_user_quota",
    "slots_with_stories",
    "update_interview_prep",
    "update_interview_prep_slot",
    "write_interview_prep_slot",
    "write_stories_for_requirements",
]
