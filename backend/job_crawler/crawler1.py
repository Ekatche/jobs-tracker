import asyncio
import os
import tempfile
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig
from crawl4ai.async_configs import BrowserConfig, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from crawl4ai.content_filter_strategy import LLMContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

logger = logging.getLogger(__name__)


class JobOffer(BaseModel):
    id: int
    poste: str
    entreprise: str
    localisation: str
    date: str
    url: str


# ✅ Configurations globales réutilisables
_browser_config = None
_crawl_config = None
_api_key_cache = None


def get_shared_browser_config() -> BrowserConfig:
    """Configuration navigateur partagée et réutilisable"""
    global _browser_config

    if _browser_config is None:
        # logger.info("🌐 Création configuration navigateur partagée")

        user_data_dir = tempfile.mkdtemp()
        _browser_config = BrowserConfig(
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport_width=1920,
            viewport_height=1080,
            verbose=False,
            user_data_dir=user_data_dir,
        )
        # logger.debug("✅ Configuration navigateur partagée créée")

    return _browser_config


def get_shared_crawl_config(api_key: str) -> CrawlerRunConfig:
    """Configuration crawl partagée et réutilisable"""
    global _crawl_config, _api_key_cache

    # ✅ Réutiliser la config si même clé API
    if _crawl_config is None or _api_key_cache != api_key:
        # logger.info("⚙️ Création configuration crawl partagée")

        _api_key_cache = api_key

        # Content filter
        content_filter = LLMContentFilter(
            llm_config=LLMConfig(provider="openai/gpt-4o-mini", api_token=api_key),
            instruction="""
Concentre-toi sur l'extraction des blocs HTML contenant des informations d'offres d'emploi :
- Titre de poste
- Nom de l'entreprise
- Les informations sur le poste (si disponibles)
- Description du poste (si disponible)
- Localisation
- Date ou lien de l'offre

Ignore et supprime tout le reste (menus, filtres, publicités, suggestions, pied de page, etc.).
Retourne uniquement le HTML minimal des offres détectées.
""",
            chunk_token_threshold=4096,
            verbose=False,
        )

        # Markdown generator
        md_generator = DefaultMarkdownGenerator(
            content_filter=content_filter,
            options={
                "ignore_links": False,
                "body_width": 0,
                "unicode_snob": True,
                "escape_all": False,
            },
        )

        # Extraction strategy
        extraction_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(provider="openai/gpt-4o-mini", api_token=api_key),
            schema=json.dumps(JobOffer.model_json_schema()),
            extraction_type="schema",
            instruction="""
Extrait toutes les offres d'emploi de cette page web.
Pour chaque offre, identifie et extrait :
- id : génère un ID unique (numéro séquentiel)
- poste : le titre du poste/métier
- entreprise : nom de l'entreprise qui recrute
- localisation : ville, région ou lieu de travail
- date : date de publication ou depuis quand l'offre est en ligne
- url : lien vers l'offre complète (si disponible)
Ignore tout contenu qui n'est pas une offre d'emploi (menus, publicités, etc.).
Si une information manque, utilise "Non spécifié" ou "" selon le cas.
Retourne une liste d'offres au format JSON.
""",
            Verbose=False,
            apply_chunking=True,
            input_format="markdown",
            extra_args={
                "temperature": 0.1,
                "max_tokens": 4000,
            },
        )

        _crawl_config = CrawlerRunConfig(
            word_count_threshold=50,
            cache_mode=CacheMode.BYPASS,
            screenshot=False,
            verbose=False,
            stream=True,
            locale="fr-FR",
            timezone_id="Europe/Paris",
            prettiify=True,
            remove_overlay_elements=True,
            extraction_strategy=extraction_strategy,
            markdown_generator=md_generator,
        )

        # logger.debug("✅ Configuration crawl partagée créée")

    return _crawl_config


async def crawl_single_job_url_optimized(
    url: str, crawler: AsyncWebCrawler, config: CrawlerRunConfig
) -> Dict[str, Any]:
    """Version optimisée qui réutilise un crawler et une config existants"""
    # logger.debug(f"🕷️ Crawl optimisé de: {url}")

    try:
        result = await crawler.arun(url=url, config=config)

        logger.debug(f"📊 Crawl terminé - Success: {result.success}")

        if result.success and result.extracted_content:
            logger.debug("✅ Contenu extrait, parsing JSON...")

            try:
                offers = json.loads(result.extracted_content)

                if isinstance(offers, dict):
                    offers = [offers]
                elif not isinstance(offers, list):
                    offers = []

                logger.info(f"🎯 {len(offers)} offres extraites de {url}")

                return {
                    "url": url,
                    "status": "success",
                    "offers_count": len(offers),
                    "offers": offers,
                }

            except json.JSONDecodeError as e:
                logger.error(f"❌ Erreur JSON pour {url}: {e}")
                return {
                    "url": url,
                    "status": "json_error",
                    "error": str(e),
                    "raw_content": result.extracted_content[:200] + "...",
                }
        else:
            error_msg = result.error_message or "Aucun contenu extrait"
            logger.warning(f"⚠️ Crawl de {url} sans succès: {error_msg}")
            return {
                "url": url,
                "status": "failed",
                "error": error_msg,
            }

    except Exception as e:
        logger.error(f"💥 Exception lors du crawl de {url}: {e}")
        return {"url": url, "status": "exception", "error": str(e)}


# =====================================================================
# ======== Crawl wensite and get fit markdown result ==================
# =====================================================================


async def get_filtered_markdown(
    url: str, api_key: Optional[str] = None, include_raw_markdown: bool = False
) -> Dict[str, Any]:
    """
    Récupère le markdown filtré d'une URL avec le filtre LLM

    Args:
        url: URL à crawler
        api_key: Clé API OpenAI (optionnelle)
        include_raw_markdown: Inclure aussi le markdown non filtré

    Returns:
        Dict contenant le markdown filtré et les métadonnées
    """
    # logger.info(f"📄 Récupération markdown filtré pour: {url}")

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY manquante")

    try:
        # ✅ Configurations
        browser_config = get_shared_browser_config()

        # ✅ Content filter spécialisé pour le markdown
        content_filter = LLMContentFilter(
            llm_config=LLMConfig(provider="openai/gpt-4o-mini", api_token=api_key),
            instruction="""
            Filtre cette page web pour ne garder que le contenu pertinent lié aux offres d'emploi.

            GARDE:
            - Titres de postes
            - Noms d'entreprises
            - Informations sur les postes (salaire, type de contrat, etc.)
            - Descriptions de postes
            - Localisations/lieux de travail
            - Dates de publication
            - Liens vers les offres détaillées
            - Critères de candidature/compétences requises

            SUPPRIME:
            - Menus de navigation
            - Barres latérales
            - Publicités
            - Pied de page
            - Formulaires de recherche/filtres
            - Contenus promotionnels
            - Widgets sociaux
            - Cookies/RGPD banners

            Retourne uniquement le HTML nettoyé focalisé sur les offres d'emploi.
            """,
            chunk_token_threshold=6000,  # Plus large pour le markdown
            verbose=False,
        )

        #  Markdown generator avec filtre
        md_generator = DefaultMarkdownGenerator(
            content_filter=content_filter,
            options={
                "ignore_links": False,  # Garder les liens
                "body_width": 0,  # Pas de limite de largeur
                "unicode_snob": True,
                "escape_all": False,
                "mark_code": True,  # Marquer le code
                "wrap_links": False,
                "protect_links": True,
                "strip_whitespace": True,
            },
        )

        # Configuration crawl pour markdown uniquement
        crawl_config = CrawlerRunConfig(
            word_count_threshold=10,
            cache_mode=CacheMode.BYPASS,
            screenshot=False,
            verbose=True,
            locale="fr-FR",
            timezone_id="Europe/Paris",
            prettiify=True,
            remove_overlay_elements=True,
            markdown_generator=md_generator,
        )

        # ✅ Crawler
        async with AsyncWebCrawler(config=browser_config) as crawler:
            logger.debug("📱 Crawler initialisé pour extraction markdown")
            result = await crawler.arun(url=url, config=crawl_config)
            logger.info(f"📊 Crawl terminé - Success: {result.success}")

            if result.success:
                filtered_markdown = result.markdown

                # Métadonnées
                metadata = {
                    "url": url,
                    "title": getattr(result, "title", None),
                    "timestamp": getattr(result, "timestamp", None),
                    "word_count": (
                        len(filtered_markdown.split()) if filtered_markdown else 0
                    ),
                    "char_count": len(filtered_markdown) if filtered_markdown else 0,
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
                    "url": url,
                    "status": "failed",
                    "error": error_msg,
                    "fit_markdown": None,
                }
    except Exception as e:
        logger.error(f"💥 Exception lors du crawl markdown de {url}: {e}")

        return {
            "url": url,
            "status": "exception",
            "error": str(e),
            "fit_markdown": None,
        }


# ====================================
# ======== Extract job offers ========
# ====================================


async def crawl_and_extract_jobs_optimized(
    urls: List[str],
    api_key: Optional[str] = None,
    max_concurrent: int = 3,
    filter_keywords: Optional[List[str]] = None,
    filter_locations: Optional[List[str]] = None,
    filter_companies: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Version optimisée qui réutilise les configurations"""

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY manquante")

    try:
        #  Créer les configurations une seule fois
        browser_config = get_shared_browser_config()
        crawl_config = get_shared_crawl_config(api_key)

        logger.info("📶 Lancement crawl optimisé...")

        #  Un seul crawler partagé pour toutes les URLs
        async with AsyncWebCrawler(config=browser_config) as crawler:
            # logger.debug("📱 Crawler unique initialisé")

            #  Contrôle de concurrence
            semaphore = asyncio.Semaphore(max_concurrent)

            async def crawl_with_semaphore(url: str):
                async with semaphore:
                    return await crawl_single_job_url_optimized(
                        url, crawler, crawl_config
                    )

            #  Exécution parallèle avec crawler partagé
            tasks = [crawl_with_semaphore(url) for url in urls]
            crawl_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Traitement des résultats
        processed_results = []
        all_offers = []

        for i, result in enumerate(crawl_results):
            if isinstance(result, Exception):
                logger.error(f"❌ Exception pour URL {urls[i]}: {result}")
                processed_results.append(
                    {"url": urls[i], "status": "exception", "error": str(result)}
                )
            else:
                processed_results.append(result)

                # Extraire les offres
                if result.get("status") == "success" and result.get("offers"):
                    for offer in result["offers"]:
                        offer["source_url"] = result["url"]
                        all_offers.append(offer)

        # ✅ Filtrage si nécessaire
        if filter_keywords or filter_locations or filter_companies:
            logger.info("🔍 Application des filtres...")
            all_offers = filter_offers(
                all_offers, filter_keywords, filter_locations, filter_companies
            )

        # ✅ Résumé
        summary = {
            "total_urls": len(urls),
            "successful_crawls": sum(
                1 for r in processed_results if r.get("status") == "success"
            ),
            "total_offers": len(all_offers),
        }

        logger.info("🎯 Pipeline optimisé terminé:")
        logger.info(f"  📊 URLs: {summary['total_urls']}")
        logger.info(f"  ✅ Succès: {summary['successful_crawls']}")
        logger.info(f"  📋 Offres: {summary['total_offers']}")

        return {
            "crawl_results": processed_results,
            "offers": all_offers,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"💥 Erreur pipeline optimisé: {e}")
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


#  Fonction de nettoyage pour libérer les ressources
def cleanup_shared_configs():
    """Nettoie les configurations partagées"""
    global _browser_config, _crawl_config, _api_key_cache
    _browser_config = None
    _crawl_config = None
    _api_key_cache = None
    logger.info("🧹 Configurations partagées nettoyées")
