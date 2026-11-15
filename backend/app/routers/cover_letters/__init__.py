import logging
from pathlib import Path

from fastapi import APIRouter

from app.routers.applications import _generate_cover_letter_bg
from app.services.cv_parser import (
    EMPTY_CV_MESSAGE,
    PROTECTED_PDF_MESSAGE,
    UNREADABLE_PDF_MESSAGE,
    VISION_UNAVAILABLE_MESSAGE,
    CVVisionUnavailable,
    extract_text_from_pdf,
    is_empty_extraction,
    is_pdf_password_protected,
    is_pdf_readable,
    parse_cv_with_llm,
)
from app.services.cv_pdf_renderer import generate_cv_pdf
from app.services.letter_guards import evaluate_letter_guards
from app.services.letter_pdf import build_candidate_info, render_letter_html, slugify
from app.services.normalization import clean_job_title_syntax
from app.services.offer_profile_matcher import rematch_user
from app.services.profile.collectors.github import collect_github
from app.services.profile.collectors.website import collect_website
from app.services.profile.merge import build_profile_from_sources
from app.services.profile.urls import validate_public_url_async
from app.services.role_normalizer import match_taxonomy_role, suggest_role_titles_from_profile
from app.services.usage_tracker import estimate_llm_cost, record_api_usage, require_user_quota

from .letters import (
    CoverLetterEdit,
    RewritePassageRequest,
    edit_cover_letter,
    get_cover_letter,
    get_cover_letter_pdf,
    regenerate_cover_letter,
    rewrite_cover_letter_passage,
    router as _letters_router,
)
from .profile_sources import (
    check_api_accounts_status,
    get_candidate_profile,
    import_cv_source,
    import_github_source,
    import_website_source,
    record_cv_parsing_usage as _record_cv_parsing_usage,
    router as _profile_sources_router,
    safe_rematch_user as _safe_rematch_user,
    safe_remove as _safe_remove,
    store_source as _store_source,
    update_candidate_preferences,
    update_candidate_profile,
)
from .roles import (
    MAX_SUGGESTED_ROLES,
    TITLE_ACRONYMS,
    canonicalize_roles as _canonicalize_roles,
    get_suggested_roles,
    restore_title_acronyms as _restore_title_acronyms,
    router as _roles_router,
    suggested_roles_profile_hash as _suggested_roles_profile_hash,
)

logger = logging.getLogger(__name__)

UPLOAD_DIR = str(Path(__file__).resolve().parent.parent.parent / "uploads")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF"

_rematch_running: set[str] = set()
_rematch_rerun: set[str] = set()

cover_letters_router = APIRouter(tags=["cover_letters"])
cover_letters_router.include_router(_letters_router)
cover_letters_router.include_router(_roles_router)
cover_letters_router.include_router(_profile_sources_router)

__all__ = [
    "CVVisionUnavailable",
    "CoverLetterEdit",
    "EMPTY_CV_MESSAGE",
    "MAX_SUGGESTED_ROLES",
    "MAX_UPLOAD_BYTES",
    "PDF_MAGIC",
    "PROTECTED_PDF_MESSAGE",
    "RewritePassageRequest",
    "TITLE_ACRONYMS",
    "UNREADABLE_PDF_MESSAGE",
    "UPLOAD_DIR",
    "VISION_UNAVAILABLE_MESSAGE",
    "_canonicalize_roles",
    "_generate_cover_letter_bg",
    "_record_cv_parsing_usage",
    "_rematch_rerun",
    "_rematch_running",
    "_restore_title_acronyms",
    "_safe_rematch_user",
    "_safe_remove",
    "_store_source",
    "_suggested_roles_profile_hash",
    "build_candidate_info",
    "build_profile_from_sources",
    "check_api_accounts_status",
    "clean_job_title_syntax",
    "collect_github",
    "collect_website",
    "cover_letters_router",
    "edit_cover_letter",
    "estimate_llm_cost",
    "evaluate_letter_guards",
    "extract_text_from_pdf",
    "generate_cv_pdf",
    "get_candidate_profile",
    "get_cover_letter",
    "get_cover_letter_pdf",
    "get_suggested_roles",
    "import_cv_source",
    "import_github_source",
    "import_website_source",
    "is_empty_extraction",
    "is_pdf_password_protected",
    "is_pdf_readable",
    "logger",
    "match_taxonomy_role",
    "parse_cv_with_llm",
    "record_api_usage",
    "regenerate_cover_letter",
    "rematch_user",
    "render_letter_html",
    "require_user_quota",
    "rewrite_cover_letter_passage",
    "slugify",
    "suggest_role_titles_from_profile",
    "update_candidate_preferences",
    "update_candidate_profile",
    "validate_public_url_async",
]
