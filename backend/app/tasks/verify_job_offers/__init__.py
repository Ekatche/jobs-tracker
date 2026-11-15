"""Package facade preserving backward-compatible verify_job_offers imports and mock targets."""

import logging
from time import monotonic

from app.database import get_database
from app.services.egress_guard import (
    browser_config_behind_proxy,
    public_only_proxy,
    public_only_transport,
)

from .html_checks import (
    CLOSED_TEXT_PATTERNS,
    DEFAULT_HEADERS,
    VisibleTextParser,
    _iter_json_ld_nodes,
    _parse_iso_datetime,
    detect_closure_in_text,
    extract_json_ld_valid_through,
    extract_visible_text,
    is_redirected_to_generic_listing,
)
from .http_and_js import check_url_headless_js, check_url_http_fast
from .indeed_and_single import (
    INDEED_GRAPHQL_URL,
    INDEED_JOB_KEY_RE,
    check_indeed_jobs,
    extract_indeed_job_key,
    verify_single_offer,
)
from .workflow import (
    _unknown_reason_key,
    restore_falsely_deleted_offers,
    verify_job_offers_sync,
    verify_job_offers_workflow,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CLOSED_TEXT_PATTERNS",
    "DEFAULT_HEADERS",
    "INDEED_GRAPHQL_URL",
    "INDEED_JOB_KEY_RE",
    "VisibleTextParser",
    "_iter_json_ld_nodes",
    "_parse_iso_datetime",
    "_unknown_reason_key",
    "browser_config_behind_proxy",
    "check_indeed_jobs",
    "check_url_headless_js",
    "check_url_http_fast",
    "detect_closure_in_text",
    "extract_indeed_job_key",
    "extract_json_ld_valid_through",
    "extract_visible_text",
    "get_database",
    "is_redirected_to_generic_listing",
    "logger",
    "monotonic",
    "public_only_proxy",
    "public_only_transport",
    "restore_falsely_deleted_offers",
    "verify_job_offers_sync",
    "verify_job_offers_workflow",
    "verify_single_offer",
]
