import logging

from fastapi import APIRouter

from ...llm.provider_errors import classify_llm_error, llm_http_exception
from ...llm.utils import fetch_documents, split_documents, summarize_chunks
from ...services.analytics.calibration import compute_score_calibration
from ...services.ats_score import clean_invisible_markers
from ...services.evaluation.evaluator import evaluate_offer_two_pass
from ...services.normalization import clean_job_title_syntax, compute_unique_key
from ...services.offer_dedup import find_company_variant_duplicate, find_offer_by_identity
from ...services.usage_tracker import record_api_usage, require_user_quota
from ...utils import capitalize_words
from .background import (
    _append_letter_version,
    _generate_cover_letter_bg,
    _generate_description_bg,
    enrich_application_with_cadences,
)
from .crud import (
    add_note,
    create_application,
    delete_application,
    get_application,
    get_applications,
    router as _crud_router,
    update_application,
)
from .offer_linking import (
    _ensure_offer_for_application,
    _migrate_user_offer_data,
    evaluate_application_offer,
    get_application_evaluation,
    link_application_offer,
    regenerate_application_description,
    router as _offer_linking_router,
)
from .pipeline import (
    calibrate_pipeline_scores,
    get_pipeline_summary,
    router as _pipeline_router,
)

logger = logging.getLogger(__name__)

job_router = APIRouter(prefix="/applications", tags=["applications"])
job_router.include_router(_pipeline_router)
job_router.include_router(_crud_router)
job_router.include_router(_offer_linking_router)

__all__ = [
    "_append_letter_version",
    "_ensure_offer_for_application",
    "_generate_cover_letter_bg",
    "_generate_description_bg",
    "_migrate_user_offer_data",
    "add_note",
    "calibrate_pipeline_scores",
    "capitalize_words",
    "classify_llm_error",
    "clean_invisible_markers",
    "clean_job_title_syntax",
    "compute_score_calibration",
    "compute_unique_key",
    "create_application",
    "delete_application",
    "enrich_application_with_cadences",
    "evaluate_application_offer",
    "evaluate_offer_two_pass",
    "fetch_documents",
    "find_company_variant_duplicate",
    "find_offer_by_identity",
    "get_application",
    "get_application_evaluation",
    "get_applications",
    "get_pipeline_summary",
    "job_router",
    "link_application_offer",
    "llm_http_exception",
    "logger",
    "record_api_usage",
    "regenerate_application_description",
    "require_user_quota",
    "split_documents",
    "summarize_chunks",
    "update_application",
]
