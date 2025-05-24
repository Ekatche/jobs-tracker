import os
import logging
from typing import List
from job_trackers.src.job_trackers.main import run_crew
from job_crawler.crawler1 import (
    crawl_and_extract_jobs_optimized,
    cleanup_shared_configs,
)
import json
from difflib import SequenceMatcher
import re


logger = logging.getLogger(__name__)


def extract_urls_from_crew(crew_result) -> List[str]:
    """Extraction simple - attend un JSON array d'URLs"""

    raw = getattr(crew_result, "raw", str(crew_result))

    if isinstance(raw, list):
        return [url for url in raw if isinstance(url, str) and url.startswith("http")]

    if isinstance(raw, str):
        try:
            # Nettoyer les markdown potentiels
            clean_raw = raw.strip()
            if clean_raw.startswith("```json"):
                clean_raw = clean_raw.replace("```json", "").replace("```", "").strip()

            urls = json.loads(clean_raw)
            if isinstance(urls, list):
                return [
                    url
                    for url in urls
                    if isinstance(url, str) and url.startswith("http")
                ]

        except json.JSONDecodeError:
            logger.warning("⚠️ JSON invalide du crew, fallback regex")
            # Fallback: extraction par regex
            return re.findall(r'https?://[^\s\]\)\'"<>\n]+', raw)

    return []


async def get_job_offers_from_query(user_query: str) -> List[dict]:
    try:
        # 1. CrewAI : obtenir la liste d'URLs
        crew_result = run_crew(user_query)

        # Log seulement le type, pas le contenu complet
        # logger.debug(f"CrewAI result type: {type(crew_result)}")
        urls = extract_urls_from_crew(crew_result)
        if not urls:
            logger.error("❌ Aucune URL extraite du crew")
            raise ValueError("Aucune URL trouvée")

        clean_urls = []
        for url in urls:
            if url and len(url) > 10:  # URLs trop courtes = invalides
                clean_url = url.rstrip(".,;!?)\"'").strip()
                clean_urls.append(clean_url)

        # Dédoublonnage
        clean_urls = list(set(clean_urls))
        logger.info(f"📋 {len(clean_urls)} URLs à crawler")

        # 2. Crawler : extraire les offres
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY manquante")

        #  crawler
        crawl_result = await crawl_and_extract_jobs_optimized(
            clean_urls,
            api_key=api_key,
            max_concurrent=2,  # Réduire pour être plus gentil avec les sites
            # filter_keywords=extract_keywords_from_query(user_query)  #  Filtrage intelligent
        )

        # 3. Vérifier le résultat du crawler
        if not isinstance(crawl_result, dict):
            logger.error(f"Format inattendu du crawler: {type(crawl_result)}")
            raise ValueError(f"Format inattendu du crawler: {type(crawl_result)}")

        offers = crawl_result.get("offers", [])

        if not isinstance(offers, list):
            logger.error(f"Les offres ne sont pas une liste: {type(offers)}")
            raise ValueError(f"Les offres ne sont pas une liste: {type(offers)}")

        # Log optimisé : seulement le nombre d'offres
        logger.info(f"Extraction terminée: {len(offers)} offres trouvées")

        # 4. Nettoyage des doublons
        offers = clean_job_offer_duplicates(offers)

        # Log détaillé seulement en mode debug
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Détail des offres: {[offer.get('title', 'Sans titre') for offer in offers[:5]]}"
            )

        for offer in offers:
            if not offer.get("url") and offer.get("source_url"):
                offer["url"] = offer["source_url"]

        return offers

    except Exception as e:
        logger.error(f"Erreur dans get_job_offers_from_query: {str(e)[:200]}")
        # ✅ Nettoyer en cas d'erreur
        cleanup_shared_configs()
        raise


def similarity(a: str, b: str) -> float:
    """Calcule la similarité entre deux chaînes (0-1)"""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def clean_job_offer_duplicates(
    offers: List[dict], similarity_threshold: float = 0.80
) -> List[dict]:
    """
    Supprime les doublons basés sur la similarité entreprise + poste

    Args:
        offers: Liste des offres d'emploi
        similarity_threshold: Seuil de similarité (0.80 = 80% de similarité)

    Returns:
        Liste nettoyée sans doublons
    """
    if not offers:
        return []

    cleaned_offers = []

    for current_offer in offers:
        current_company = str(current_offer.get("entreprise", "")).strip()
        current_position = str(current_offer.get("poste", "")).strip()
        current_url = current_offer.get("url", "")

        # Vérifier si cette offre est similaire à une offre déjà ajoutée
        is_duplicate = False

        for existing_offer in cleaned_offers:
            existing_company = str(existing_offer.get("entreprise", "")).strip()
            existing_position = str(existing_offer.get("poste", "")).strip()
            existing_url = existing_offer.get("url", "")

            # ✅ Calculer similarité entreprise ET poste
            company_similarity = similarity(current_company, existing_company)
            position_similarity = similarity(current_position, existing_position)
            # print(
            #     f"Comparaison: {current_company} vs {existing_company} "
            #     f"Comparaison: {current_position} vs {existing_position} "
            #     f"(similarité entreprise={company_similarity:.2f}, poste={position_similarity:.2f})"
            # )

            # 1. Même entreprise (>85% similarité)
            # 2. Même poste (>85% similarité)
            # 3. URLs différentes (sources différentes)
            if (
                company_similarity >= similarity_threshold
                and position_similarity >= similarity_threshold
                and current_url != existing_url
                and current_url
                and existing_url
            ):

                logger.info(
                    f"🔄 Doublon détecté: {current_company} - {current_position} "
                    f"(similarité: entreprise={company_similarity:.2f}, poste={position_similarity:.2f})"
                )
                is_duplicate = True
                break

        # ✅ Ajouter seulement si ce n'est pas un doublon
        if not is_duplicate:
            cleaned_offers.append(current_offer)

    removed_count = len(offers) - len(cleaned_offers)
    if removed_count > 0:
        logger.info(
            f"🧹 Nettoyage: {removed_count} doublons supprimés ({len(cleaned_offers)} offres conservées)"
        )

    return cleaned_offers


def extract_keywords_from_query(query: str) -> List[str]:
    """Extrait des mots-clés pertinents de la requête utilisateur"""
    keywords = []
    query_lower = query.lower()

    # Mots-clés techniques courants
    tech_keywords = [
        "python",
        "java",
        "javascript",
        "react",
        "node",
        "sql",
        "docker",
        "aws",
        "data",
        "scientist",
        "développeur",
        "ingénieur",
    ]

    for keyword in tech_keywords:
        if keyword in query_lower:
            keywords.append(keyword)

    return keywords if keywords else None
