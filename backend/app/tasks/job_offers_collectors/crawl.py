"""Step 1 & 2 of collection: URL search, zero-token ATS crawl, Crawl4AI fallback, LLM summary."""

import asyncio
import os
import sys
from typing import Any

from app.tasks.job_offers_collectors.config import SUMMARY_CONCURRENCY


def _pkg() -> Any:
    return sys.modules["app.tasks.job_offers_collectors"]


async def get_urls_for_query(query: str) -> list:
    """Étape 1: Récupération des URLs."""
    pkg = _pkg()
    pkg.logger.info(f"🔍 Recherche d'URLs pour: {query}")

    required_env_vars = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Variables manquantes: {', '.join(missing_vars)}")

    try:
        urls = await pkg.get_urls(query)
        pkg.logger.info(f"✅ {len(urls)} URLs trouvées")

        if pkg.RELEVANCE_FILTER_ENABLED:
            kept_urls = []
            rejected_count = 0
            for url in urls:
                if pkg.is_off_domain_url(url):
                    pkg.logger.warning(f"🚫 URL hors-domaine écartée: {url} (requête: '{query}')")
                    rejected_count += 1
                else:
                    kept_urls.append(url)
            pkg.logger.info(f"🚫 {rejected_count} URLs hors-domaine écartées, {len(kept_urls)} conservées")
            urls = kept_urls

        return urls
    except Exception as e:
        pkg.logger.error(f"💥 Erreur récupération URLs: {e}")
        raise


async def summarize_ats_offer_description(
    raw_description: str,
    poste: str = "",
    entreprise: str = "",
) -> str:
    """Génère une synthèse structurée en 5 sections pour une offre extraite via Zero-Token."""
    from app.services.ats.router import clean_html_to_text

    pkg = _pkg()
    cleaned_desc = clean_html_to_text(raw_description)
    if not cleaned_desc or cleaned_desc == "Non spécifié" or len(cleaned_desc) < 120:
        return cleaned_desc

    model_name = os.getenv("SUMMARY_MODEL", "gpt-5-nano")
    prompt = f"""Tu es un expert en recrutement et analyse d'offres d'emploi.
À partir de la description brute ci-dessous pour le poste "{poste}" chez "{entreprise}", génère une synthèse structurée, riche et directement exploitable rédigée en français avec des puces Markdown, organisée en sections claires :

• Contexte & Enjeux : 1 à 2 phrases sur l'entreprise, l'équipe et la mission générale.
• Missions principales : 3 à 5 puces concrètes décrivant les responsabilités quotidiennes et les livrables attendus.
• Profil recherché : niveau d'expérience requis, formation et critères indispensables.
• Stack & Outils : technologies, frameworks, cloud et méthodologies utilisés.
• Avantages & Modalités : politique de télétravail, salaire ou package si mentionnés (sinon omettre ce point).

Règles impératives :
- N'inclus aucune balise HTML (ni <p>, ni <br>, ni <em>). Utilise uniquement du Markdown propre.
- Reste factuel et fidèle au texte d'origine. Ne spécule pas sur des technologies ou avantages non mentionnés.
- Si une section n'est pas mentionnée dans l'offre, omettre ou indiquer "Non spécifié".

Description brute :
{cleaned_desc[:4000]}
"""
    try:
        from litellm import acompletion

        extra_kwargs: dict[str, Any] = {"drop_params": True}
        short = model_name.split("/")[-1].lower()
        if not any(short.startswith(p) for p in ("o1", "o3", "gpt-5", "gpt-o")):
            extra_kwargs["temperature"] = 0.2

        resp = await acompletion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            **extra_kwargs,
        )
        content = (resp.choices[0].message.content or "").strip()
        return content if content else cleaned_desc
    except Exception as e:
        pkg.logger.warning(f"Repli sur description brute (échec résumé LLM pour '{poste} - {entreprise}'): {e}")
        return cleaned_desc


async def summarize_offers(offers: list[dict]) -> list[dict]:
    """Remplace la description brute de chaque offre par sa synthèse LLM (concurrence bornée)."""
    semaphore = asyncio.Semaphore(SUMMARY_CONCURRENCY)
    pkg = _pkg()

    async def _summarize_single(offer: dict) -> dict:
        async with semaphore:
            offer["description"] = await pkg.summarize_ats_offer_description(
                offer.get("description", ""), poste=offer.get("poste", ""), entreprise=offer.get("entreprise", "")
            )
        return offer

    return list(await asyncio.gather(*[_summarize_single(o) for o in offers]))


async def crawl_urls_for_offers(urls: list) -> list:
    """Étape 2: Crawling des URLs pour extraire les offres (Zero-Token ATS/JSON-LD prioritaire)."""
    pkg = _pkg()
    pkg.logger.info(f"🕷️ Traitement de {len(urls)} URLs")
    if not urls:
        pkg.logger.warning("⚠️ Aucune URL à crawler")
        return []

    try:
        from app.services.ats.router import ExpiredOfferError, extract_ats_or_jsonld_offer
        import httpx

        ats_offers: list[dict] = []
        remaining_urls: list[str] = []

        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            for url in urls:
                try:
                    direct_offer = await extract_ats_or_jsonld_offer(url, client=client)
                    if direct_offer:
                        ats_offers.append(direct_offer)
                    else:
                        remaining_urls.append(url)
                except ExpiredOfferError:
                    pkg.logger.warning(f"🛑 Offre retirée selon l'API ATS, URL écartée: {url}")
                except Exception as e:
                    pkg.logger.debug(f"Erreur extraction directe pour {url}: {e}")
                    remaining_urls.append(url)

        if ats_offers:
            pkg.logger.info(f"⚡ {len(ats_offers)} offres extraites via Zero-Token ATS / JSON-LD (0 token LLM)")
            pkg.logger.info(f"✨ Structuration et résumé LLM pour {len(ats_offers)} offres Zero-Token...")
            ats_offers = await pkg.summarize_offers(ats_offers)

        crawled_offers: list[dict] = []
        if remaining_urls:
            pkg.logger.info(f"🕷️ Crawling de repli (Crawl4AI + LLM) pour {len(remaining_urls)} URLs restantes")
            raw_crawled = await pkg.get_job_offers_from_query(remaining_urls)
            if isinstance(raw_crawled, list):
                crawled_offers = raw_crawled

            jsonld_offers = [o for o in crawled_offers if o.get("ats_platform")]
            if jsonld_offers:
                pkg.logger.info(f"✨ Résumé LLM pour {len(jsonld_offers)} offres du repli JSON-LD du crawler...")
                llm_offers = [o for o in crawled_offers if not o.get("ats_platform")]
                crawled_offers = llm_offers + await pkg.summarize_offers(jsonld_offers)

        total_offers = ats_offers + crawled_offers
        pkg.logger.info(
            f"📊 {len(total_offers)} offres brutes au total ({len(ats_offers)} Zero-Token, {len(crawled_offers)} Crawl4AI)"
        )
        return total_offers
    except Exception as e:
        pkg.logger.error(f"💥 Erreur crawling: {e}")
        raise
