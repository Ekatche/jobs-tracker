import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig
from crawl4ai.async_configs import BrowserConfig, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

logger = logging.getLogger(__name__)


class JobOffer(BaseModel):
    poste: str
    entreprise: str
    localisation: Optional[str] = "Non spécifié"
    date: Optional[str] = "Non spécifié"
    type_contrat: Optional[str] = "Non spécifié"  # CDI, CDD, Alternance, Stage, Freelance
    salaire: Optional[str] = "Non spécifié"       # ex: 45k€ - 55k€
    mode_travail: Optional[str] = "Non spécifié"  # Télétravail, Hybride, Présentiel
    competences_cles: Optional[List[str]] = []    # ex: ["Python", "Docker", "SQL"]
    url: Optional[str] = None


# ✅ Configurations globales réutilisables
_browser_config = None
_crawl_config = None
_api_key_cache = None


def get_shared_browser_config() -> BrowserConfig:
    """Configuration navigateur robuste pour éviter EPIPE"""
    global _browser_config

    if _browser_config is None:
        _browser_config = BrowserConfig(
            browser_type="chromium",
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport_width=1920,
            viewport_height=1080,
            verbose=False,
        )

    return _browser_config


def get_shared_crawl_config(api_key: str) -> CrawlerRunConfig:
    """Configuration crawl optimisée pour stabilité et coût minimal"""
    global _crawl_config, _api_key_cache

    if _crawl_config is None or _api_key_cache != api_key:
        _api_key_cache = api_key

        # ✅ Filtre déterministe ultra-rapide (0 token consommé)
        job_content_filter = PruningContentFilter(
            threshold=0.45,
            threshold_type="fixed",
            min_word_threshold=5,
        )

        # ✅ Markdown generator avec le filtre déterministe
        md_generator = DefaultMarkdownGenerator(
            content_filter=job_content_filter,
            options={
                "ignore_links": False,
                "strip_whitespace": True,
            },
        )

        # ✅ Détection automatique du provider LLM
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            llm_provider = "gemini/gemini-flash-latest"
            llm_token = gemini_key
        else:
            llm_provider = "openai/gpt-4o-mini"
            llm_token = api_key

        # ✅ Extraction strategy avec LLM unique
        extraction_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider=llm_provider,
                api_token=llm_token,
            ),
            schema=json.dumps(JobOffer.model_json_schema()),
            extraction_type="schema",
            instruction=f"""
            Extrait toutes les offres d'emploi de cette page web.
            Pour chaque offre, identifie et extrait précisément :
            - poste : le titre du poste/métier
            - entreprise : nom de l'entreprise qui recrute
            - localisation : ville, région ou lieu de travail
            - date : convertir la date en format ISO (YYYY-MM-DD) basée sur la date actuelle {datetime.now().strftime('%Y-%m-%d')}
            - type_contrat : type de contrat si mentionné (ex: CDI, CDD, Alternance, Stage, Freelance, ou "Non spécifié")
            - salaire : rémunération ou fourchette salariale (ou "Non spécifié")
            - mode_travail : Télétravail total, Hybride, Présentiel (ou "Non spécifié")
            - competences_cles : liste des technologies, compétences ou outils demandés
            - url : lien direct vers l'offre complète (si disponible)
            
            Ignore tout contenu qui n'est pas une offre d'emploi (menus, publicités, etc.).
            Si une information manque, utilise "Non spécifié" ou [] pour les compétences.
            Retourne une liste d'offres au format JSON.
            """,
            extra_args={"temperature": 0.1, "max_tokens": 3000},
            apply_chunking=True,
            input_format="fit_markdown",
            verbose=False,
        )

        # Script JS pour faire défiler la page et charger le contenu dynamique
        scroll_js = """
        window.scrollTo(0, document.body.scrollHeight / 2);
        await new Promise(r => setTimeout(r, 600));
        window.scrollTo(0, document.body.scrollHeight);
        await new Promise(r => setTimeout(r, 600));
        """

        _crawl_config = CrawlerRunConfig(
            word_count_threshold=30,
            cache_mode=CacheMode.BYPASS,
            screenshot=False,
            verbose=False,
            ignore_body_visibility=True,
            extraction_strategy=extraction_strategy,
            markdown_generator=md_generator,
            js_code=scroll_js,
            magic=True,
            simulate_user=False,
            override_navigator=True,
            remove_overlay_elements=True,
        )
    return _crawl_config


# =====================================================================
# ======== Crawl website and get filtered markdown result ============
# =====================================================================


async def get_filtered_markdown(
    url: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Récupère le markdown filtré d'une URL avec un filtre d'élagage déterministe
    pour la création de description d'offres d'emploi.
    """
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY manquante")

    try:
        browser_config = get_shared_browser_config()

        # 📋 Filtre d'élagage déterministe (0 token)
        markdown_filter = PruningContentFilter(
            threshold=0.48,
            threshold_type="fixed",
            min_word_threshold=5,
        )

        # 📄 Générateur Markdown
        md_generator = DefaultMarkdownGenerator(
            content_filter=markdown_filter,
            options={
                "ignore_links": False,
                "strip_whitespace": True,
            },
        )

        # 🕷️ Configuration du crawl avec scroll JS
        scroll_js = """
        window.scrollTo(0, document.body.scrollHeight / 2);
        await new Promise(r => setTimeout(r, 500));
        window.scrollTo(0, document.body.scrollHeight);
        """

        crawl_config = CrawlerRunConfig(
            word_count_threshold=10,
            stream=True,
            cache_mode=CacheMode.BYPASS,
            screenshot=False,
            verbose=False,
            remove_overlay_elements=True,
            markdown_generator=md_generator,
            js_code=scroll_js,
        )

        # 🔍 Lancement du crawl
        async with AsyncWebCrawler(config=browser_config) as crawler:
            logger.debug("📱 Crawler initialisé pour extraction markdown")
            result = await crawler.arun(url=url, config=crawl_config)
            logger.info(f"📊 Crawl terminé - Success: {result.success}")

            if result.success:
                # ✅ Récupération du markdown filtré (fit_markdown)
                md_obj = result.markdown
                if hasattr(md_obj, "fit_markdown") and md_obj.fit_markdown:
                    filtered_markdown = md_obj.fit_markdown
                elif hasattr(md_obj, "raw_markdown") and md_obj.raw_markdown:
                    filtered_markdown = md_obj.raw_markdown
                elif isinstance(md_obj, str):
                    filtered_markdown = md_obj
                else:
                    filtered_markdown = str(md_obj or "")

                # ✅ Vérification si filtered_markdown est vide ou None
                if not filtered_markdown or len(filtered_markdown.strip()) == 0:
                    logger.warning(
                        "⚠️ Markdown filtré vide ou None, retour de result complet"
                    )
                    return {
                        "status": "success",
                        "url": url,
                        "filtered_markdown": result,  # ✅ Retourner result complet
                        "metadata": {
                            "url": url,
                            "title": getattr(result, "title", None),
                            "timestamp": getattr(result, "timestamp", None)
                            or datetime.now(timezone.utc).isoformat(),
                            "word_count": 0,
                            "char_count": 0,
                            "fallback_used": True,  # ✅ Indicateur de fallback
                        },
                    }

                # ✅ Si markdown filtré existe, log en debug
                logger.debug(f"📄 Markdown filtré: {filtered_markdown[:200]}...")

                # Construction des métadonnées
                meta = result.metadata or {}
                metadata = {
                    "url": url,
                    "title": meta.get("title"),
                    "timestamp": meta.get("timestamp")
                    or datetime.now(timezone.utc).isoformat(),
                    "word_count": len(filtered_markdown.split()),
                    "char_count": len(filtered_markdown),
                    "fallback_used": False,
                }

                return {
                    "status": "success",
                    "url": url,
                    "filtered_markdown": filtered_markdown,
                    "metadata": metadata,
                }

            else:
                error_msg = result.error_message or "Échec du crawl"
                logger.error(f"❌ Crawl échoué pour {url}: {error_msg}")
                return {
                    "status": "failed",
                    "url": url,
                    "error": error_msg,
                    "filtered_markdown": None,
                }

    except Exception as e:
        logger.error(f"💥 Exception lors du crawl markdown de {url}: {e}")
        return {
            "status": "exception",
            "url": url,
            "error": str(e),
            "filtered_markdown": None,
        }


# ====================================
# ======== Extract job offers ========
# ====================================


async def crawl_and_extract_jobs_optimized(
    urls: List[str],
    api_key: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Version ultra-simple avec arun_many direct"""

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY manquante")

    try:
        browser_config = get_shared_browser_config()
        crawl_config = get_shared_crawl_config(api_key)

        logger.info(f"🚀 Crawl ultra-simple de {len(urls)} URLs")

        processed_results = []
        all_offers = []

        # ✅ Utilisation directe d'arun_many selon la doc
        async with AsyncWebCrawler(config=browser_config) as crawler:
            results = await crawler.arun_many(
                urls=urls,
                config=crawl_config,
            )
            for result in results:
                logger.info(f"📊 Résultat reçu pour: {result.url}")

                if result.success and result.extracted_content:
                    try:
                        offers = json.loads(result.extracted_content)

                        if isinstance(offers, dict):
                            offers = [offers]
                        elif not isinstance(offers, list):
                            offers = []

                        # Ajouter source_url
                        for offer in offers:
                            offer["source_url"] = result.url
                            all_offers.append(offer)

                        processed_results.append(
                            {
                                "url": result.url,
                                "status": "success",
                                "offers_count": len(offers),
                            }
                        )

                        logger.info(f"✅ {len(offers)} offres de {result.url}")

                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Erreur JSON pour {result.url}: {e}")
                        processed_results.append(
                            {"url": result.url, "status": "json_error", "error": str(e)}
                        )
                else:
                    error_msg = result.error_message or "Aucun contenu"
                    logger.warning(f"⚠️ Échec pour {result.url}: {error_msg}")
                    processed_results.append(
                        {"url": result.url, "status": "failed", "error": error_msg}
                    )

        summary = {
            "total_urls": len(urls),
            "successful_crawls": sum(
                1 for r in processed_results if r.get("status") == "success"
            ),
            "total_offers": len(all_offers),
        }

        logger.info(f"🎯 Ultra-simple terminé: {summary}")

        return {
            "crawl_results": processed_results,
            "offers": all_offers,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"💥 Erreur pipeline ultra: {e}")
        await cleanup_shared_configs()
        raise


def filter_offers(
    offers: List[Dict[str, Any]],
    keywords: Optional[List[str]] = None,
    locations: Optional[List[str]] = None,
    companies: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Filtre les offres selon des critères"""
    if not any([keywords, locations, companies]):
        return offers

    logger.info(f"🔍 Filtrage de {len(offers)} offres")

    filtered_offers = offers.copy()

    if keywords:
        keywords_lower = [k.lower() for k in keywords]
        filtered_offers = [
            offer
            for offer in filtered_offers
            if any(
                keyword in offer.get("poste", "").lower() for keyword in keywords_lower
            )
        ]
        logger.debug(f"📋 Après filtrage mots-clés: {len(filtered_offers)} offres")

    if locations:
        locations_lower = [loc.lower() for loc in locations]
        filtered_offers = [
            offer
            for offer in filtered_offers
            if any(
                location in offer.get("localisation", "").lower()
                for location in locations_lower
            )
        ]
        logger.debug(f"📍 Après filtrage localisation: {len(filtered_offers)} offres")

    if companies:
        companies_lower = [c.lower() for c in companies]
        filtered_offers = [
            offer
            for offer in filtered_offers
            if any(
                company in offer.get("entreprise", "").lower()
                for company in companies_lower
            )
        ]
        logger.debug(f"🏢 Après filtrage entreprises: {len(filtered_offers)} offres")

    logger.info(f"✅ Filtrage terminé: {len(offers)} -> {len(filtered_offers)} offres")
    return filtered_offers


async def cleanup_shared_configs():
    """Nettoyage simplifié des configurations"""
    global _browser_config, _crawl_config, _api_key_cache

    try:
        # ✅ Reset uniquement (pas de user_data_dir dans votre config)
        _browser_config = None
        _crawl_config = None
        _api_key_cache = None

        # ✅ Forcer le garbage collection
        import gc

        gc.collect()

        logger.info("🧹 Nettoyage simplifié terminé")

    except Exception as e:
        logger.warning(f"Erreur lors du nettoyage: {e}")
