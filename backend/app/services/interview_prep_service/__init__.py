"""Interview prep AI generation, STAR+R matching, practice grading, and Markdown export."""

import logging

from litellm import acompletion

from app.services.interview_prep_service.context import (
    _offer_role_and_company,
    format_candidate_profile_context,
    format_evaluation_context,
)
from app.services.interview_prep_service.generators import (
    PRACTICE_CRITERIA,
    evaluate_practice_answer,
    generate_anticipated_questions,
    generate_audience_packs,
    generate_reverse_questions,
)
from app.services.interview_prep_service.llm_client import (
    DEFAULT_INTERVIEW_MODEL,
    PROMPTS_DIR,
    _clean_json_output,
)
from app.services.interview_prep_service.markdown_export import (
    FIT_LABELS,
    export_interview_prep_markdown,
)
from app.services.interview_prep_service.story_matching import (
    BANK_SUMMARY_LIMIT,
    MAX_STORY_SLOTS,
    WEIGHT_RANK,
    RequirementPick,
    _build_matched_slot,
    _resolve_match_fit,
    format_bank_summary,
    format_requirements_block,
    match_bank_stories,
    select_requirements,
)
from app.services.interview_prep_service.story_writer import (
    _REQUIRED_STORY_FACTS,
    _build_written_result,
    _has_required_story_facts,
    _no_story_fit,
    _resolve_story_experience,
    _resolve_write_fit,
    build_story_slots,
    carry_over_edited_angles,
    write_stories_for_requirements,
)
from app.services.star_bank_rules import _mask_invented_numbers
from app.services.usage_tracker import record_api_usage

logger = logging.getLogger(__name__)

__all__ = [
    "BANK_SUMMARY_LIMIT",
    "DEFAULT_INTERVIEW_MODEL",
    "FIT_LABELS",
    "MAX_STORY_SLOTS",
    "PRACTICE_CRITERIA",
    "PROMPTS_DIR",
    "RequirementPick",
    "WEIGHT_RANK",
    "_REQUIRED_STORY_FACTS",
    "_build_matched_slot",
    "_build_written_result",
    "_clean_json_output",
    "_has_required_story_facts",
    "_mask_invented_numbers",
    "_no_story_fit",
    "_offer_role_and_company",
    "_resolve_match_fit",
    "_resolve_story_experience",
    "_resolve_write_fit",
    "acompletion",
    "build_story_slots",
    "carry_over_edited_angles",
    "evaluate_practice_answer",
    "export_interview_prep_markdown",
    "format_bank_summary",
    "format_candidate_profile_context",
    "format_evaluation_context",
    "format_requirements_block",
    "generate_anticipated_questions",
    "generate_audience_packs",
    "generate_reverse_questions",
    "logger",
    "match_bank_stories",
    "record_api_usage",
    "select_requirements",
    "write_stories_for_requirements",
]
