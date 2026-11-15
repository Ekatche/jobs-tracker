"""Job offer collectors package preserving Airflow and test monkeypatch surfaces."""

from app.database import get_database
from app.services.company_profiles import CompanyResolver
from app.services.job_offers import get_job_offers_from_query, get_urls
from app.services.offer_profile_matcher import tag_new_offers
from app.services.relevance import RELEVANCE_FILTER_ENABLED, is_off_domain_url, parse_source_query
from app.services.role_normalizer import normalize_role
from app.services.sources import collect_structured_offers, drop_known_urls, offer_identity
from app.services.sources.geo import filter_offers_by_location
from app.tasks.job_offers_collectors.config import (
    COLLECT_QUERY_TIMEOUT,
    DEFAULT_QUERIES,
    MAX_QUERIES_PER_PROFILE,
    MAX_TOTAL_QUERIES,
    SUMMARY_CONCURRENCY,
    WEB_SEARCH_MAX_HOUR_UTC,
    is_web_search_run,
    logger,
    setup_logger,
)
from app.tasks.job_offers_collectors.crawl import (
    crawl_urls_for_offers,
    get_urls_for_query,
    summarize_ats_offer_description,
    summarize_offers,
)
from app.tasks.job_offers_collectors.enrich import (
    clean_duplicate_offers,
    enrich_offers,
    enrich_offers_sync,
)
from app.tasks.job_offers_collectors.persistence import (
    _resolve_company_attributes,
    cleanup_resources,
    save_offers_to_database,
)
from app.tasks.job_offers_collectors.pipeline import (
    collect_and_save_offers,
    collect_offers_sync,
)
from app.tasks.job_offers_collectors.queries import (
    build_search_queries,
    build_search_queries_sync,
)

__all__ = [
    "COLLECT_QUERY_TIMEOUT",
    "CompanyResolver",
    "DEFAULT_QUERIES",
    "MAX_QUERIES_PER_PROFILE",
    "MAX_TOTAL_QUERIES",
    "RELEVANCE_FILTER_ENABLED",
    "SUMMARY_CONCURRENCY",
    "WEB_SEARCH_MAX_HOUR_UTC",
    "_resolve_company_attributes",
    "build_search_queries",
    "build_search_queries_sync",
    "clean_duplicate_offers",
    "cleanup_resources",
    "collect_and_save_offers",
    "collect_offers_sync",
    "collect_structured_offers",
    "crawl_urls_for_offers",
    "drop_known_urls",
    "enrich_offers",
    "enrich_offers_sync",
    "filter_offers_by_location",
    "get_database",
    "get_job_offers_from_query",
    "get_urls",
    "get_urls_for_query",
    "is_off_domain_url",
    "is_web_search_run",
    "logger",
    "normalize_role",
    "offer_identity",
    "parse_source_query",
    "save_offers_to_database",
    "setup_logger",
    "summarize_ats_offer_description",
    "summarize_offers",
    "tag_new_offers",
]
