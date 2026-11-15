"""End-to-end collection pipeline orchestration and Airflow sync entrypoint."""

import asyncio
import json
import os
import sys
from typing import Any

from app.services.collection_context import collection_query_id, query_fingerprint
from app.tasks.job_offers_collectors.config import COLLECT_QUERY_TIMEOUT


def _pkg() -> Any:
    return sys.modules["app.tasks.job_offers_collectors"]


async def _gather_initial_sources(
    pkg: Any, query: str, db: Any, use_web_search: bool
) -> tuple[list[str], list[dict]]:
    async def _search_urls() -> list[str]:
        if not use_web_search:
            pkg.logger.info(f"⏭️ Recherche web désactivée pour ce run, sources structurées seules: {query}")
            return []
        return await pkg.get_urls_for_query(query)

    search_urls_res, structured_res = await asyncio.gather(
        _search_urls(),
        pkg.collect_structured_offers(query, db),
        return_exceptions=True,
    )

    if isinstance(structured_res, Exception):
        pkg.logger.error(f"💥 Sources structurées en échec pour '{query}': {structured_res}")
        structured_offers: list[dict] = []
    else:
        structured_offers = structured_res or []

    if isinstance(search_urls_res, Exception):
        if not structured_offers:
            raise search_urls_res
        pkg.logger.error(
            f"💥 Recherche Tavily en échec pour '{query}', sources structurées seules: {search_urls_res}"
        )
        search_urls: list[str] = []
    else:
        search_urls = search_urls_res or []

    return search_urls, structured_offers


async def _crawl_and_summarize(
    pkg: Any,
    clean_search_urls: list[str],
    structured_offers: list[dict],
    city: str | None,
    query: str,
) -> list[dict]:
    async def _crawl_and_filter() -> list[dict]:
        if not clean_search_urls:
            return []
        crawled = await pkg.crawl_urls_for_offers(clean_search_urls)
        return await pkg.filter_offers_by_location(crawled, city)

    crawled_res, summarized_res = await asyncio.gather(
        _crawl_and_filter(),
        pkg.summarize_offers(structured_offers),
        return_exceptions=True,
    )

    if isinstance(crawled_res, Exception):
        pkg.logger.error(f"💥 Crawling des URLs Tavily en échec pour '{query}': {crawled_res}")
        if not structured_offers:
            raise crawled_res
        crawled_offers: list[dict] = []
    else:
        crawled_offers = crawled_res or []

    if isinstance(summarized_res, Exception):
        pkg.logger.error(f"💥 Résumé des offres structurées en échec pour '{query}': {summarized_res}")
        summarized_offers = structured_offers
    else:
        summarized_offers = summarized_res or []

    return crawled_offers + summarized_offers


async def collect_and_save_offers(query: str, use_web_search: bool = True) -> dict:
    """Version asynchrone complète pour collecter, nettoyer et enregistrer les offres."""
    pkg = _pkg()
    pkg.logger.info(f"🚀 Collecte async démarrée: {query}")
    query_token = collection_query_id.set(query_fingerprint(query))
    try:
        db = await pkg.get_database()
        _, city = pkg.parse_source_query(query)

        search_urls, structured_offers = await _gather_initial_sources(pkg, query, db, use_web_search)

        if search_urls:
            covered_identities = {pkg.offer_identity(o["url"]) for o in structured_offers if o.get("url")}
            clean_search_urls = await pkg.drop_known_urls(search_urls, db, extra_known=covered_identities)
            pkg.logger.info(
                f"🎯 URLs Tavily après dédup (base + structurées): {len(clean_search_urls)}/{len(search_urls)} retenues"
            )
        else:
            clean_search_urls = []

        offers = await _crawl_and_summarize(pkg, clean_search_urls, structured_offers, city, query)
        enriched = await pkg.enrich_offers(offers, query)
        cleaned = await pkg.clean_duplicate_offers(enriched)
        result = await pkg.save_offers_to_database(cleaned)
        await pkg.tag_new_offers(result["offer_ids"], db)
        pkg.logger.info(
            "collection_result %s",
            json.dumps({
                "query_id": collection_query_id.get(),
                "saved": result.get("saved", 0),
                "updated": result.get("updated", 0),
                "web_enabled": use_web_search,
            }),
        )
        return result
    finally:
        try:
            await pkg.cleanup_resources()
        finally:
            collection_query_id.reset(query_token)


def collect_offers_sync(query: str, use_web_search: bool = True) -> dict:
    """Version sync pour Airflow — une seule boucle d'événements par requête."""
    pkg = _pkg()
    os.environ.setdefault("ENVIRONMENT", "airflow")
    try:
        pkg.logger.info(f"🚀 Collecte complète démarrée: {query}")
        result = asyncio.run(
            asyncio.wait_for(
                pkg.collect_and_save_offers(query, use_web_search=use_web_search),
                timeout=COLLECT_QUERY_TIMEOUT,
            )
        )
        pkg.logger.info(f"🎯 Collecte terminée: {result}")
        return result
    except Exception as e:
        pkg.logger.error(f"💥 Erreur collecte complète: {e}")
        raise
