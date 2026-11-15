import logging

from fastapi import APIRouter

from ...services.analytics.calibration import compute_jd_skill_gaps
from ...services.collection_schedule import next_collection_at, previous_collection_at
from ...services.evaluation.evaluator import evaluate_offer_two_pass
from ...services.normalization import normalize_city, normalize_company
from ...tasks.clean_job_offers import safe_delete_or_expire_offer
from .actions import (
    delete_job_offer,
    evaluate_job_offer_endpoint,
    get_job_offer_evaluation_endpoint,
    regenerate_offer_description_endpoint,
    router as _actions_router,
    soft_delete_job_offer,
)
from .analytics import (
    get_collection_schedule,
    get_jd_skill_gaps,
    get_offers_stats,
    list_user_offer_interactions,
    router as _analytics_router,
)
from .catalog import (
    get_job_offer,
    get_job_offers,
    get_job_offers_count,
    router as _catalog_router,
)
from .filters import (
    ACCENT_VARIANTS,
    GENERIC_ROLE_MODIFIERS,
    STEM_PREFIXES,
    STOPWORDS,
    _accent_insensitive,
    _apply_search_filters,
    _build_company_size_filter,
    _build_contract_type_filter,
    _build_keywords_filter,
    _build_sector_filter,
    _stem_keyword,
    _strip_accents,
    restrict_to_profile_offers,
)
from .interactions import (
    get_user_offer_interaction,
    router as _interactions_router,
    set_offer_seen,
    set_user_offer_interaction,
)
from .pipeline import (
    _build_list_pipeline,
    _relevance_level_match,
    apply_user_interaction_filters,
    relevance_lookup_stages,
)

logger = logging.getLogger(__name__)

job_offers_router = APIRouter(prefix="/job-offers", tags=["job-offers"])
# Static routes (/user/interactions, /analytics/skill-gaps, /stats/summary, /collection/schedule)
# and list/count routes MUST register before dynamic /{offer_id}.
job_offers_router.include_router(_analytics_router)
job_offers_router.include_router(_catalog_router)
job_offers_router.include_router(_interactions_router)
job_offers_router.include_router(_actions_router)

__all__ = [
    "ACCENT_VARIANTS",
    "GENERIC_ROLE_MODIFIERS",
    "STEM_PREFIXES",
    "STOPWORDS",
    "_accent_insensitive",
    "_apply_search_filters",
    "_build_company_size_filter",
    "_build_contract_type_filter",
    "_build_keywords_filter",
    "_build_list_pipeline",
    "_build_sector_filter",
    "_relevance_level_match",
    "_stem_keyword",
    "_strip_accents",
    "apply_user_interaction_filters",
    "compute_jd_skill_gaps",
    "delete_job_offer",
    "evaluate_job_offer_endpoint",
    "evaluate_offer_two_pass",
    "get_collection_schedule",
    "get_jd_skill_gaps",
    "get_job_offer",
    "get_job_offer_evaluation_endpoint",
    "get_job_offers",
    "get_job_offers_count",
    "get_offers_stats",
    "get_user_offer_interaction",
    "job_offers_router",
    "list_user_offer_interactions",
    "logger",
    "next_collection_at",
    "normalize_city",
    "normalize_company",
    "previous_collection_at",
    "regenerate_offer_description_endpoint",
    "relevance_lookup_stages",
    "restrict_to_profile_offers",
    "safe_delete_or_expire_offer",
    "set_offer_seen",
    "set_user_offer_interaction",
    "soft_delete_job_offer",
]
