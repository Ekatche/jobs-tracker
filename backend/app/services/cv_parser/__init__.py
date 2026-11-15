import logging

from litellm import acompletion

from .constants import (
    CV_OUTPUT_KEYS,
    DEFAULT_CV_PARSER_MODEL,
    DEFAULT_VLM_MODEL,
    EMPTY_CV_MESSAGE,
    PROFILE_JSON_SCHEMA,
    PROTECTED_PDF_MESSAGE,
    UNREADABLE_PDF_MESSAGE,
    VISION_UNAVAILABLE_MESSAGE,
    VLM_MAX_PAGES,
    CVResponseError,
    CVVisionUnavailable,
)
from .llm_extract import _parse_cv_text, parse_cv_with_vlm
from .normalization import (
    _build_import_report,
    _clean_parsed_cv,
    _find_excerpt,
    _flatten_contact_value,
    _has_usable_content,
    _item_key,
    _locate_evidence,
    _merge_cv_complement,
    _normalize,
    _pages_with_text,
    _read_json_response,
    _start_year,
    is_empty_extraction,
)
from .orchestrator import _complete_with_remaining_pages, parse_cv_with_llm
from .pdf_io import (
    extract_page_texts,
    extract_text_from_pdf,
    is_pdf_password_protected,
    is_pdf_readable,
    pdf_pages_all_blank,
    render_pdf_pages_to_base64_images,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CVResponseError",
    "CVVisionUnavailable",
    "CV_OUTPUT_KEYS",
    "DEFAULT_CV_PARSER_MODEL",
    "DEFAULT_VLM_MODEL",
    "EMPTY_CV_MESSAGE",
    "PROFILE_JSON_SCHEMA",
    "PROTECTED_PDF_MESSAGE",
    "UNREADABLE_PDF_MESSAGE",
    "VISION_UNAVAILABLE_MESSAGE",
    "VLM_MAX_PAGES",
    "_build_import_report",
    "_clean_parsed_cv",
    "_complete_with_remaining_pages",
    "_find_excerpt",
    "_flatten_contact_value",
    "_has_usable_content",
    "_item_key",
    "_locate_evidence",
    "_merge_cv_complement",
    "_normalize",
    "_pages_with_text",
    "_parse_cv_text",
    "_read_json_response",
    "_start_year",
    "acompletion",
    "extract_page_texts",
    "extract_text_from_pdf",
    "is_empty_extraction",
    "is_pdf_password_protected",
    "is_pdf_readable",
    "logger",
    "parse_cv_with_llm",
    "parse_cv_with_vlm",
    "pdf_pages_all_blank",
    "render_pdf_pages_to_base64_images",
]
