"""Step 3 & 4 of collection: MongoDB enrichment normalization and in-batch deduplication."""

import asyncio
from datetime import datetime, timezone
import os
import sys
from typing import Any

from app.services.normalization import (
    clean_html_entities_and_tags,
    clean_job_title_syntax,
    compute_unique_key,
    deduplicate_and_merge_offers,
    detect_contract_type,
    extract_company_from_url,
    extract_seniority,
    normalize_city,
)

_INVALID_PLACEHOLDERS = {"non spécifié", "non disponible", "inconnu", "none", "null", "undefined", ""}


def _pkg() -> Any:
    return sys.modules["app.tasks.job_offers_collectors"]


def _normalize_competences(raw_skills: Any) -> list[str]:
    if isinstance(raw_skills, str):
        return [clean_html_entities_and_tags(c.strip()) for c in raw_skills.split(",") if c.strip()]
    if isinstance(raw_skills, list):
        return [clean_html_entities_and_tags(str(c).strip()) for c in raw_skills if str(c).strip()]
    return []


async def _enrich_single_offer(offer: dict, query: str, current_time: datetime) -> dict | None:
    """Validate, clean, normalize, and shape one raw offer into MongoDB schema."""
    pkg = _pkg()
    if not all(key in offer for key in ("poste", "entreprise")):
        pkg.logger.warning(f"⚠️ Offre invalide (champs manquants): {offer}")
        return None

    poste = clean_html_entities_and_tags(str(offer.get("poste", "")).strip())
    entreprise = clean_html_entities_and_tags(str(offer.get("entreprise", "")).strip())
    raw_description = str(offer.get("description", "")).strip()
    if raw_description and ("<" in raw_description or "&" in raw_description):
        from app.services.ats.router import clean_html_to_text

        description = clean_html_to_text(raw_description) or "Non spécifié"
    else:
        description = clean_html_entities_and_tags(raw_description) or "Non spécifié"

    localisation = clean_html_entities_and_tags(str(offer.get("localisation", "")).strip())
    if localisation and localisation.lower() not in {"non spécifié", "inconnu", "none", "null"}:
        localisation = normalize_city(localisation)

    date = clean_html_entities_and_tags(str(offer.get("date", "")).strip())
    type_contrat = clean_html_entities_and_tags(str(offer.get("type_contrat", "")).strip())
    salaire = clean_html_entities_and_tags(str(offer.get("salaire", "")).strip())
    mode_travail = clean_html_entities_and_tags(str(offer.get("mode_travail", "")).strip())
    competences_cles = _normalize_competences(offer.get("competences_cles", []))

    url = str(offer.get("url", "")).strip() or None
    source_url = str(offer.get("source_url", "")).strip() or None
    ats_platform = offer.get("ats_platform")

    if (not entreprise or entreprise.lower() in _INVALID_PLACEHOLDERS) and (url or source_url):
        fallback_company = extract_company_from_url(url or source_url)
        if fallback_company:
            pkg.logger.info(f"🏢 Entreprise enrichie via fallback URL: '{fallback_company}' (était '{entreprise}')")
            entreprise = fallback_company

    if not poste or not entreprise or poste.lower() in _INVALID_PLACEHOLDERS or entreprise.lower() in _INVALID_PLACEHOLDERS:
        pkg.logger.warning(f"⚠️ Offre rejetée (poste ou entreprise invalide/non spécifié): poste='{poste}', entreprise='{entreprise}'")
        return None

    clean_poste = clean_job_title_syntax(poste)
    seniority_level = extract_seniority(poste, description)
    try:
        canonical_title = await pkg.normalize_role(clean_poste)
    except Exception:
        canonical_title = clean_poste

    return {
        "poste": clean_poste,
        "raw_poste": poste,
        "canonical_title": canonical_title,
        "seniority_level": seniority_level,
        "entreprise": entreprise,
        "description": description,
        "localisation": localisation if localisation else "Non spécifié",
        "date": date if date else "Non spécifié",
        "type_contrat": detect_contract_type(type_contrat, poste, description),
        "salaire": salaire if salaire else "Non spécifié",
        "mode_travail": mode_travail if mode_travail else "Non spécifié",
        "competences_cles": competences_cles,
        "url": url,
        "alternative_urls": offer.get("alternative_urls") or [],
        "source_url": source_url,
        "ats_platform": ats_platform,
        "unique_key": compute_unique_key(company=entreprise, position=clean_poste, location=localisation, url=url),
        "source_query": query,
        "created_at": current_time,
        "updated_at": current_time,
        "pipeline_stage": offer.get("pipeline_stage") or "discovered",
        "is_deleted": False,
        "deleted_date": None,
        "raw_data": {ats_platform or "llm_crawl": offer.get("source_record") or offer},
    }


async def enrich_offers(offers: list, query: str) -> list:
    """Étape 3: Enrichissement des offres avec métadonnées selon le modèle MongoDB."""
    pkg = _pkg()
    pkg.logger.info(f"🔧 Enrichissement de {len(offers)} offres selon le modèle de données")
    if not offers:
        pkg.logger.warning("⚠️ Aucune offre à enrichir")
        return []

    try:
        enriched_offers = []
        invalid_count = 0
        current_time = datetime.now(timezone.utc)
        for index, offer in enumerate(offers, 1):
            try:
                enriched = await _enrich_single_offer(offer, query, current_time)
                if enriched is None:
                    invalid_count += 1
                    continue
                enriched_offers.append(enriched)
                if index <= 3:
                    pkg.logger.debug(f"🔍 Offre {index} enrichie: {enriched['poste']} chez {enriched['entreprise']}")
            except Exception as e:
                pkg.logger.warning(f"⚠️ Erreur enrichissement offre {index}: {e}")
                pkg.logger.debug(f"Offre problématique: {offer}")
                invalid_count += 1

        pkg.logger.info(f"✅ {len(enriched_offers)} offres enrichies selon le modèle MongoDB ({invalid_count} invalides)")
        return enriched_offers
    except Exception as e:
        pkg.logger.error(f"💥 Erreur enrichissement: {e}")
        raise


async def clean_duplicate_offers(offers: list) -> list:
    """Étape 4: Nettoyage des doublons et fusion multi-sources (Couche 3 & 4)."""
    pkg = _pkg()
    pkg.logger.info(f"🧹 Nettoyage des doublons sur {len(offers)} offres")
    if not offers:
        pkg.logger.warning("⚠️ Aucune offre à nettoyer")
        return []

    try:
        cleaned_offers = deduplicate_and_merge_offers(offers)
        removed_count = len(offers) - len(cleaned_offers)
        pkg.logger.info(f"✅ Nettoyage terminé: {removed_count} doublons fusionnés/supprimés, {len(cleaned_offers)} offres conservées")
        return cleaned_offers
    except Exception as e:
        pkg.logger.error(f"💥 Erreur nettoyage doublons: {e}")
        raise


def enrich_offers_sync(offers: list, query: str) -> list:
    """Version sync pour Airflow - Étape 3."""
    os.environ.setdefault("ENVIRONMENT", "airflow")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(asyncio.wait_for(enrich_offers(offers, query), timeout=300))
    finally:
        loop.close()
