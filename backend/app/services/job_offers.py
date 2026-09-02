import os
import logging
from typing import List, Dict, Any
from job_trackers.src.job_trackers.main import run_crew
from job_crawler.crawler1 import (
    crawl_and_extract_jobs_optimized,
    cleanup_shared_configs,
)
import json
from difflib import SequenceMatcher
import re
import hashlib
from functools import lru_cache

logger = logging.getLogger(__name__)


def normalize_text_for_comparison(text: str) -> str:
    """Normalise une chaîne pour comparaison rapide (minuscules, sans ponctuation, stopwords)"""
    if not text:
        return ""
    # Minuscules et suppression caractères spéciaux
    text = re.sub(r"[^\w\s]", " ", text.lower().strip())
    # Remplacement des espaces multiples
    words = [w for w in text.split() if len(w) > 1 and w not in {"de", "du", "des", "le", "la", "les", "un", "une", "en", "pour", "et", "ou"}]
    return " ".join(words)


@lru_cache(maxsize=4000)
def cached_similarity(a: str, b: str) -> float:
    """Version mise en cache du calcul de similarité"""
    if not a or not b:
        return 0.0
    norm_a = normalize_text_for_comparison(a)
    norm_b = normalize_text_for_comparison(b)
    if norm_a == norm_b:
        return 1.0
    return SequenceMatcher(None, norm_a, norm_b).ratio()


def fast_similarity_check(text1: str, text2: str, threshold: float = 0.75) -> bool:
    """Vérification rapide de similarité sans requête réseau externe"""
    if not text1 or not text2:
        return False

    # 1. Vérification exacte (le plus rapide)
    if text1.lower().strip() == text2.lower().strip():
        return True

    # 2. Différence de longueur trop importante
    len1, len2 = len(text1), len(text2)
    len_diff = abs(len1 - len2) / max(len1, len2)
    if len_diff > 0.5:  # Plus de 50% de différence de longueur
        return False

    # 3. Mots communs (Jaccard)
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if words1 and words2:
        jaccard = len(words1.intersection(words2)) / len(words1.union(words2))
        if jaccard < 0.25:  # Moins de 25% de mots communs
            return False

    # 4. Calcul de similarité
    return cached_similarity(text1, text2) >= threshold


from app.services.normalization import normalize_company, normalize_position


def create_offer_hash(company: str, position: str) -> str:
    """Crée un hash normalisé pour grouper les offres potentiellement similaires"""
    norm_c = normalize_company(company).lower()
    norm_p = normalize_position(position).lower()

    company_words = [w for w in norm_c.split() if len(w) > 1][:2]
    position_words = [w for w in norm_p.split() if len(w) > 1][:3]

    hash_string = f"{'_'.join(company_words)}|{'_'.join(position_words)}"
    return hashlib.md5(hash_string.encode()).hexdigest()[:8]


def clean_job_offer_duplicates_optimized(
    offers: List[dict],
    company_similarity_threshold: float = 0.75,
    position_similarity_threshold: float = 0.80,
) -> List[dict]:
    """
    Nettoyage optimisé des doublons 100% en local et sans appels externes
    """
    if not offers:
        return []

    logger.info(f"🧹 Nettoyage optimisé de {len(offers)} offres")

    # Étape 1: Groupement rapide par hash
    hash_groups: Dict[str, List[dict]] = {}
    for offer in offers:
        company = str(offer.get("entreprise", "")).strip()
        position = str(offer.get("poste", "")).strip()

        if not company or not position:
            continue

        offer_hash = create_offer_hash(company, position)
        if offer_hash not in hash_groups:
            hash_groups[offer_hash] = []
        hash_groups[offer_hash].append(offer)

    # Étape 2: Traitement par groupe
    cleaned_offers = []
    total_removed = 0

    for group_hash, group_offers in hash_groups.items():
        if len(group_offers) == 1:
            cleaned_offers.extend(group_offers)
            continue

        group_cleaned = []

        for current_offer in group_offers:
            current_company = str(current_offer.get("entreprise", "")).strip()
            current_position = str(current_offer.get("poste", "")).strip()
            current_url = current_offer.get("url", "")

            is_duplicate = False

            for existing_offer in group_cleaned:
                existing_company = str(existing_offer.get("entreprise", "")).strip()
                existing_position = str(existing_offer.get("poste", "")).strip()
                existing_url = existing_offer.get("url", "")

                # 1. URLs identiques
                if current_url and existing_url and current_url == existing_url:
                    is_duplicate = True
                    break

                # 2. Similarité entreprise + poste
                if fast_similarity_check(current_company, existing_company, company_similarity_threshold):
                    if fast_similarity_check(current_position, existing_position, position_similarity_threshold):
                        logger.debug(f"🔄 Doublon détecté: {current_company[:25]} - {current_position[:25]}")
                        is_duplicate = True
                        break

            if not is_duplicate:
                group_cleaned.append(current_offer)
            else:
                total_removed += 1

        cleaned_offers.extend(group_cleaned)

    logger.info(
        f"✅ Nettoyage terminé: {total_removed} doublons supprimés, {len(cleaned_offers)} conservées"
    )
    return cleaned_offers


def clean_job_offer_duplicates(
    offers: List[dict],
    company_similarity_threshold: float = 0.75,
    position_similarity_threshold: float = 0.80,
) -> List[dict]:
    """Wrapper pour la fonction de nettoyage optimisée"""
    return clean_job_offer_duplicates_optimized(
        offers, company_similarity_threshold, position_similarity_threshold
    )


def extract_urls_from_crew(crew_result) -> List[str]:
    """Extraction robuste des URLs d'offres d'emploi à partir du résultat CrewAI (Pydantic, dict ou string)."""
    # 1. Vérifier si l'objet Pydantic est directement accessible
    pydantic_output = getattr(crew_result, "pydantic", None)
    if pydantic_output and hasattr(pydantic_output, "urls"):
        urls = [u for u in pydantic_output.urls if isinstance(u, str) and u.startswith("http")]
        if urls:
            logger.info(f"✅ {len(urls)} URLs extraites directement depuis le modèle Pydantic du Crew")
            return urls

    # 2. Vérifier les outputs des tâches individuelles (tasks_output)
    tasks_output = getattr(crew_result, "tasks_output", None)
    if tasks_output and isinstance(tasks_output, list) and len(tasks_output) > 0:
        for task_out in reversed(tasks_output):
            t_pydantic = getattr(task_out, "pydantic", None)
            if t_pydantic and hasattr(t_pydantic, "urls"):
                urls = [u for u in t_pydantic.urls if isinstance(u, str) and u.startswith("http")]
                if urls:
                    logger.info(f"✅ {len(urls)} URLs extraites depuis task_output.pydantic")
                    return urls

    # 3. Si l'objet est directement un modèle Pydantic ou un dict
    if hasattr(crew_result, "urls"):
        urls = getattr(crew_result, "urls")
        if isinstance(urls, list):
            return [u for u in urls if isinstance(u, str) and u.startswith("http")]

    if isinstance(crew_result, dict) and "urls" in crew_result:
        urls = crew_result["urls"]
        if isinstance(urls, list):
            return [u for u in urls if isinstance(u, str) and u.startswith("http")]

    # 4. Fallback texte / JSON / Regex
    raw = getattr(crew_result, "raw", str(crew_result))

    if isinstance(raw, list):
        return [url for url in raw if isinstance(url, str) and url.startswith("http")]

    if isinstance(raw, str):
        try:
            clean_raw = raw.strip()
            if clean_raw.startswith("```json"):
                clean_raw = clean_raw.replace("```json", "").replace("```", "").strip()
            elif clean_raw.startswith("```"):
                clean_raw = clean_raw.replace("```", "").strip()

            data = json.loads(clean_raw)
            if isinstance(data, list):
                return [u for u in data if isinstance(u, str) and u.startswith("http")]
            elif isinstance(data, dict) and "urls" in data and isinstance(data["urls"], list):
                return [u for u in data["urls"] if isinstance(u, str) and u.startswith("http")]

        except (json.JSONDecodeError, Exception):
            logger.warning("⚠️ Parsing JSON impossible, utilisation du fallback Regex")
            return re.findall(r'https?://[^\s\]\)\'"<>\n]+', raw)

    return []


async def get_urls(user_query: str) -> List[str]:
    """Obtenir les URLs à partir de la requête utilisateur"""
    try:
        # 1. CrewAI : obtenir la liste d'URLs
        crew_result = run_crew(user_query)
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

        return clean_urls

    except Exception as e:
        logger.error(f"Erreur dans l'extraction des urls: {str(e)[:200]}")
        raise


async def get_job_offers_from_query(clean_urls: str) -> List[dict]:
    try:
        # 1. Vérifier les URLs
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY manquante")

        # 2. Crawler
        crawl_result = await crawl_and_extract_jobs_optimized(
            clean_urls,
            api_key=api_key,
        )

        # 3. Vérifier le résultat du crawler
        if not isinstance(crawl_result, dict):
            logger.error(f"Format inattendu du crawler: {type(crawl_result)}")
            raise ValueError(f"Format inattendu du crawler: {type(crawl_result)}")

        offers = crawl_result.get("offers", [])

        if not isinstance(offers, list):
            logger.error(f"Les offres ne sont pas une liste: {type(offers)}")
            raise ValueError(f"Les offres ne sont pas une liste: {type(offers)}")

        logger.info(f"📊 Extraction terminée: {len(offers)} offres brutes trouvées")

        # Log détaillé seulement en mode debug
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Détail des offres: {[offer.get('title', 'Sans titre') for offer in offers[:5]]}"
            )

        # ✅ Garder seulement la normalisation des URLs
        for offer in offers:
            if not offer.get("url") and offer.get("source_url"):
                offer["url"] = offer["source_url"]

        return offers

    except Exception as e:
        logger.error(f"Erreur dans get_job_offers_from_query: {str(e)[:200]}")
        await cleanup_shared_configs()
        raise


def similarity(a: str, b: str) -> float:
    """Calcule la similarité entre deux chaînes (0-1) de manière optimisée"""
    return cached_similarity(a, b)
