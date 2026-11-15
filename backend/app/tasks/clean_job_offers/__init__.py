"""Package facade preserving backward-compatible clean_job_offers imports and mock targets."""

import logging

from app.database import get_database
from app.services.job_offers import clean_job_offer_duplicates_optimized
from app.services.normalization import extract_domain, normalize_city, normalize_company
from app.services.offer_dedup import merge_duplicate_offers

from .normalize_and_dedup import (
    normalize_existing_data,
    prevent_duplicate_insertion,
    remove_exact_duplicates,
    remove_similarity_duplicates,
)
from .protection import is_offer_referenced_by_application, safe_delete_or_expire_offer
from .purge_rules import cleanup_invalid_offers, cleanup_old_offers
from .workflow import cleanup_workflow, cleanup_workflow_sync

logger = logging.getLogger(__name__)

__all__ = [
    "clean_job_offer_duplicates_optimized",
    "cleanup_invalid_offers",
    "cleanup_old_offers",
    "cleanup_workflow",
    "cleanup_workflow_sync",
    "extract_domain",
    "get_database",
    "is_offer_referenced_by_application",
    "logger",
    "merge_duplicate_offers",
    "normalize_city",
    "normalize_company",
    "normalize_existing_data",
    "prevent_duplicate_insertion",
    "remove_exact_duplicates",
    "remove_similarity_duplicates",
    "safe_delete_or_expire_offer",
]
