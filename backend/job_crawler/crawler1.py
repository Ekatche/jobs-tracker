import asyncio
import os
import re
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

from app.services.normalization import (
    extract_company_from_url,
    optimize_crawl_url,
    restore_canonical_job_url,
)

logger = logging.getLogger(__name__)

# crawl4ai 0.6.3 ne re-soumet jamais une URL : ni sur timeout de navigation, ni
# sur page rendue vide. Un crawl vide remonte avec success=False et un
# error_message parfois vide, ou avec success=True et un markdown de quelques
# dizaines de caractères (shell SPA). Les deux cas sont traités ici comme des
# échecs à réessayer.
MIN_PAGE_TEXT_CHARS = int(os.getenv("CRAWL_MIN_PAGE_CHARS", "500"))
CRAWL_MAX_RETRIES = int(os.getenv("CRAWL_MAX_RETRIES", "2"))
CRAWL_RETRY_DELAY_S = float(os.getenv("CRAWL_RETRY_DELAY_S", "8"))


class JobOffer(BaseModel):
    poste: str
    entreprise: str
    description: Optional[str] = "Non spécifié"
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

        # ✅ Détection automatique et robuste du provider LLM
        prefer_gemini = os.getenv("PREFER_GEMINI", "").lower() in ("true", "1")
        gemini_key = os.getenv("GEMINI_API_KEY")

        # gpt-4o-mini reste le défaut ici : gpt-5-nano renvoie des champs nuls
        # sur l'extraction structurée (offres rejetées par le contrôle d'ancrage).
        openai_model = os.getenv("CRAWL_LLM_MODEL", "openai/gpt-4o-mini")

        if api_key and not prefer_gemini:
            llm_provider = openai_model
            llm_token = api_key
        elif gemini_key:
            llm_provider = "gemini/gemini-flash-latest"
            llm_token = gemini_key
        else:
            llm_provider = openai_model
            llm_token = api_key

        # Les modèles gpt-5 n'acceptent que temperature=1, et leur raisonnement
        # consommerait le budget max_tokens de l'extraction.
        if "gpt-5" in llm_provider:
            llm_extra_args = {
                "temperature": 1,
                "max_tokens": 4000,
                "reasoning_effort": "minimal",
            }
        else:
            llm_extra_args = {"temperature": 0.1, "max_tokens": 4000}

        # ✅ Extraction strategy avec LLM unique
        extraction_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider=llm_provider,
                api_token=llm_token,
            ),
            schema=json.dumps(JobOffer.model_json_schema()),
            extraction_type="schema",
            instruction=f"""
            Extrait toutes les offres d'emploi RÉELLES et ACTIVES de cette page web.

            RÈGLE CRITIQUE D'EXPIRATION :
            - Si la page indique que l'offre n'est plus disponible (ex: "L'offre que vous souhaitez afficher n'est plus disponible", "Offre expirée", "Offre introuvable", page d'erreur 404, page de connexion), NE RETOURNE AUCUNE OFFRE (tableau vide []).

            Pour chaque offre active, identifie et extrait précisément :
            - poste : le titre exact du poste/métier (ne jamais mettre "Non spécifié" si une offre est présente)
            - entreprise : le nom réel de l'entreprise ou du cabinet employeur (cherche attentivement dans l'en-tête, le titre, le texte d'introduction ou la signature)
            - description : une synthèse structurée, riche et directement exploitable rédigée en français avec des puces Markdown, organisée en sections claires :
              • Contexte & Enjeux : 1 à 2 phrases sur l'entreprise, l'équipe et la mission générale.
              • Missions principales : 3 à 5 puces concrètes décrivant les responsabilités quotidiennes et les livrables attendus.
              • Profil recherché : niveau d'expérience requis, formation et critères indispensables.
              • Stack & Outils : technologies, frameworks, cloud et méthodologies utilisés.
              • Avantages & Modalités : politique de télétravail, salaire ou package si mentionnés (sinon omettre ce point).
              Ne reste jamais vague ou générique : extrais les détails techniques et fonctionnels réels présents dans le texte.
            - localisation : ville, département ou région du poste
            - date : date de publication au format ISO (YYYY-MM-DD), basée sur la date d'aujourd'hui {datetime.now().strftime('%Y-%m-%d')}
            - type_contrat : type de contrat (CDI, CDD, Alternance, Stage, Freelance, ou "Non spécifié")
            - salaire : rémunération ou fourchette salariale indiquée (ou "Non spécifié")
            - mode_travail : Télétravail total, Hybride, Présentiel (ou "Non spécifié")
            - competences_cles : liste des technologies, outils, langages ou compétences clés exigées
            - url : lien direct vers l'offre (si disponible)

            Ignore les menus, bannières, pied de page et publicités.
            Retourne une liste d'offres au format JSON.
            """,
            extra_args=llm_extra_args,
            apply_chunking=True,
            input_format="fit_markdown",
            verbose=False,
        )


        # Script JS pour masquer les bannières cookies et faire défiler la page pour charger le contenu dynamique
        scroll_js = """
        const cookieSelectors = [
            '#tarteaucitronPersonalize2',
            '#axeptio_btn_acceptAll',
            '#onetrust-accept-btn-handler',
            'button[id*="accept"]',
            'button[class*="cookie-accept"]',
            'button[class*="consent-accept"]'
        ];
        for (const sel of cookieSelectors) {
            const btn = document.querySelector(sel);
            if (btn) { try { btn.click(); } catch(e){} break; }
        }
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
            # Les SPA (France Travail, etc.) chargent l'offre via XHR après le
            # rendu initial : attendre la fin de l'activité réseau plutôt qu'un
            # délai fixe, sinon on capture parfois un fragment générique du shell.
            wait_until="networkidle",
            page_timeout=45000,
            delay_before_return_html=2.5,
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
            threshold=0.38,
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
                # ✅ Récupération du markdown : fit_markdown en priorité, sinon raw_markdown
                md_obj = result.markdown
                filtered_markdown = ""
                if hasattr(md_obj, "fit_markdown") and md_obj.fit_markdown and len(md_obj.fit_markdown.strip()) > 100:
                    filtered_markdown = md_obj.fit_markdown.strip()
                elif hasattr(md_obj, "raw_markdown") and md_obj.raw_markdown and len(md_obj.raw_markdown.strip()) > 100:
                    filtered_markdown = md_obj.raw_markdown.strip()
                elif isinstance(md_obj, str) and len(md_obj.strip()) > 100:
                    filtered_markdown = md_obj.strip()

                # ✅ Vérification si filtered_markdown est vide ou None
                if not filtered_markdown:
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

        # Optimisation des URLs pour le scraping (bypasses LinkedIn guest et Indeed mobile)
        url_mapping: Dict[str, str] = {}
        crawl_urls: List[str] = []
        for u in urls:
            opt = optimize_crawl_url(u)
            crawl_urls.append(opt)
            url_mapping[opt] = u
            url_mapping[u] = u

        def _resolve_original_url(crawl_url: str) -> str:
            if not crawl_url:
                return ""
            if crawl_url in url_mapping:
                return url_mapping[crawl_url]
            stripped = crawl_url.rstrip("/")
            if stripped in url_mapping:
                return url_mapping[stripped]
            return restore_canonical_job_url(crawl_url)

        processed_results = []
        all_offers = []

        # ✅ Utilisation directe d'arun_many selon la doc
        async with AsyncWebCrawler(config=browser_config) as crawler:
            pending = list(crawl_urls)
            attempt = 0
            empty_counts: Dict[str, int] = {}
            actually_retried_urls: set = set()

            while pending:
                if attempt:
                    delay = CRAWL_RETRY_DELAY_S * attempt
                    logger.info(
                        f"🔁 Retry {attempt}/{CRAWL_MAX_RETRIES} sur {len(pending)} URL(s) "
                        f"vides, après {delay}s"
                    )
                    await asyncio.sleep(delay)

                results = await crawler.arun_many(
                    urls=pending,
                    config=crawl_config,
                )
                to_retry: List[str] = []

                for result in results:
                    orig_url = _resolve_original_url(result.url)
                    logger.info(f"📊 Résultat reçu pour: {result.url} (original: {orig_url})")

                    page_text = _get_page_text(result)

                    # 1. Vérification immédiate de lien mort ou offre expirée (aucun retry inutile)
                    if _is_dead_or_expired(result, page_text):
                        logger.warning(
                            f"🛑 Lien mort ou expiré pour {orig_url} "
                            f"(status={getattr(result, 'status_code', None)}) — sortie immédiate"
                        )
                        processed_results.append(
                            {
                                "url": orig_url,
                                "status": "dead_link",
                                "error": "Offre expirée ou page inexistante (404/410 ou contenu expiré)",
                                "attempts": attempt + 1,
                            }
                        )
                        continue

                    # 2. Vérification de crawl vide
                    if _is_empty_crawl(result, page_text):
                        empty_counts[result.url] = empty_counts.get(result.url, 0) + 1
                        reason = (
                            result.error_message
                            or f"contenu vide ({len(page_text.strip())} chars)"
                        )

                        # Seuls les vrais échecs réseau ou timeouts valent un retry.
                        # Une page vide après navigation réussie (ex: coquille SPA sans offre)
                        # ne changera pas au retry.
                        is_transient_network_error = (
                            not getattr(result, "success", False)
                            or bool(
                                result.error_message
                                and any(
                                    err in result.error_message.lower()
                                    for err in ("timeout", "net::err", "connection", "econnreset")
                                )
                            )
                        )

                        if is_transient_network_error and attempt < CRAWL_MAX_RETRIES:
                            logger.warning(
                                f"⚠️ Échec réseau transitoire pour {orig_url}: {reason} — à réessayer"
                            )
                            actually_retried_urls.add(result.url)
                            to_retry.append(result.url)
                        else:
                            logger.warning(
                                f"❌ Crawl vide après {attempt + 1} tentative(s) pour "
                                f"{orig_url}: {reason}"
                            )
                            processed_results.append(
                                {
                                    "url": orig_url,
                                    "status": "empty_content",
                                    "error": reason,
                                    "attempts": attempt + 1,
                                }
                            )
                        continue

                    if not result.extracted_content:
                        # Page correctement crawlée mais le LLM n'a rien extrait :
                        # un retry ne changerait pas le contenu de la page.
                        logger.warning(
                            f"⚠️ Aucune extraction pour {orig_url} "
                            f"({len(page_text.strip())} chars crawlés)"
                        )
                        processed_results.append(
                            {
                                "url": orig_url,
                                "status": "no_extraction",
                                "error": "Aucun contenu extrait par le LLM",
                                "attempts": attempt + 1,
                            }
                        )
                        continue

                    try:
                        offers = json.loads(result.extracted_content)

                        if isinstance(offers, dict):
                            offers = [offers]
                        elif not isinstance(offers, list):
                            offers = []

                        # Fallback nom d'entreprise depuis l'URL si manquant ou générique
                        for offer in offers:
                            ent = (offer.get("entreprise") or "").strip()
                            if not ent or ent.lower() in (
                                "non spécifié",
                                "non disponible",
                                "inconnu",
                                "none",
                                "null",
                                "undefined",
                            ):
                                fallback = extract_company_from_url(orig_url)
                                if fallback:
                                    logger.info(
                                        f"🏢 Entreprise enrichie depuis l'URL pour {orig_url}: '{fallback}'"
                                    )
                                    offer["entreprise"] = fallback

                        # Filet de sécurité : rejeter les offres non ancrées dans la
                        # page réellement crawlée (pages SPA mal chargées, contenu
                        # générique du shell au lieu de l'offre ciblée)
                        grounded_offers = []
                        for offer in offers:
                            if _offer_grounded_in_page(offer, page_text, orig_url):
                                grounded_offers.append(offer)
                            else:
                                logger.warning(
                                    f"⚠️ Offre rejetée (non retrouvée dans la page crawlée): "
                                    f"'{offer.get('poste')}' chez '{offer.get('entreprise')}' — {orig_url}"
                                )
                        offers = grounded_offers

                        # Ajouter source_url et url canoniques (pour l'utilisateur)
                        for offer in offers:
                            offer["source_url"] = orig_url
                            offer["url"] = orig_url
                            all_offers.append(offer)

                        processed_results.append(
                            {
                                "url": orig_url,
                                "status": "success",
                                "offers_count": len(offers),
                                "attempts": attempt + 1,
                            }
                        )

                        logger.info(f"✅ {len(offers)} offres de {orig_url}")

                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Erreur JSON pour {orig_url}: {e}")
                        processed_results.append(
                            {"url": orig_url, "status": "json_error", "error": str(e)}
                        )


                pending = to_retry
                attempt += 1

        summary = {
            "total_urls": len(urls),
            "successful_crawls": sum(
                1 for r in processed_results if r.get("status") == "success"
            ),
            "empty_crawls": sum(
                1 for r in processed_results if r.get("status") == "empty_content"
            ),
            "dead_links": sum(
                1 for r in processed_results if r.get("status") == "dead_link"
            ),
            "retried_urls": len(actually_retried_urls),
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


def _get_page_text(result) -> str:
    """Récupère le texte markdown effectivement crawlé pour une page (fit ou raw)"""
    md_obj = getattr(result, "markdown", None)
    if md_obj is None:
        return ""
    if hasattr(md_obj, "fit_markdown") and md_obj.fit_markdown:
        return md_obj.fit_markdown
    if hasattr(md_obj, "raw_markdown") and md_obj.raw_markdown:
        return md_obj.raw_markdown
    if isinstance(md_obj, str):
        return md_obj
    return ""


DEAD_OR_EXPIRED_PATTERNS = (
    "l'offre que vous souhaitez afficher n'est plus disponible",
    "cette offre n'est plus disponible",
    "offre n'est plus disponible",
    "offre expirée",
    "offre introuvable",
    "cette annonce n'est plus en ligne",
    "cette offre a été pourvue",
    "cette offre d'emploi a été supprimée",
    "offre archivée",
    "no longer accepting applications",
    "ce poste n'accepte plus de candidatures",
    "cette offre n'est plus active",
    "cette page n'existe plus",
    "page introuvable",
    "erreur 404",
    "404 not found",
    "offre non disponible",
    "detail-offre-inexistante",
)


def _is_dead_or_expired(result, page_text: str) -> bool:
    """
    Détecte si la page correspond à un lien mort ou à une offre expirée/supprimée.
    - Code HTTP 404, 410
    - URL redirigée vers une page d'erreur (404 délimité, inexistante, expired)
    - Présence de motifs textuels d'expiration dans page_text (ou raw html si page courte)
    """
    status_code = getattr(result, "status_code", None)
    if status_code in (404, 410):
        return True

    raw_redir = getattr(result, "redirected_url", None)
    redirected_url = raw_redir.lower() if isinstance(raw_redir, str) else ""
    if re.search(r"[/=_\-?]404([/?&#_\-.]|$)", redirected_url) or any(
        p in redirected_url for p in ("inexistante", "expired")
    ):
        return True

    text_to_check = page_text.lower()
    for pattern in DEAD_OR_EXPIRED_PATTERNS:
        if pattern in text_to_check:
            return True

    # Ne scanner le HTML brut que pour les pages courtes (< MIN_PAGE_TEXT_CHARS)
    # pour éviter les faux positifs issus des bundles JS embarqués sur les pages pleines
    if len(page_text.strip()) < MIN_PAGE_TEXT_CHARS:
        raw_html = getattr(result, "html", None)
        html_to_check = raw_html.lower() if isinstance(raw_html, str) else ""
        for pattern in DEAD_OR_EXPIRED_PATTERNS:
            if pattern in html_to_check:
                return True


    return False


def _is_empty_crawl(result, page_text: str) -> bool:
    """
    Un crawl est vide s'il a échoué, ou s'il a « réussi » en ne ramenant qu'un
    squelette de page. crawl4ai renvoie success=True dès que la navigation
    aboutit, même quand le rendu SPA n'a produit aucun contenu exploitable.
    """
    if not getattr(result, "success", False):
        return True
    return len(page_text.strip()) < MIN_PAGE_TEXT_CHARS


def _offer_grounded_in_page(
    offer: Dict[str, Any], page_text: str, url: Optional[str] = None
) -> bool:
    """
    Vérifie que l'offre extraite par le LLM correspond réellement au contenu
    de la page crawlée (poste ou entreprise retrouvés dans le texte ou l'URL).
    Filet de sécurité contre les pages SPA mal chargées où le LLM extrait
    des offres génériques sans rapport avec l'URL demandée.
    """
    if not page_text:
        return True  # Pas de texte à comparer : ne pas rejeter à l'aveugle

    page_text_lower = page_text.lower()
    poste = (offer.get("poste") or "").strip().lower()
    entreprise = (offer.get("entreprise") or "").strip().lower()

    poste_found = bool(poste) and poste not in ("non spécifié",) and poste in page_text_lower
    entreprise_found = (
        bool(entreprise) and entreprise not in ("non spécifié",) and entreprise in page_text_lower
    )

    # Si l'entreprise est retrouvée dans le texte du DOM : l'offre est ancrée
    if entreprise_found:
        return True

    # Si l'entreprise provient du fallback de l'URL (Workday, WTTJ, etc.),
    # le poste DOIT impérativement être retrouvé dans la page pour éviter toute hallucination.
    if url and entreprise and entreprise not in ("non spécifié",):
        fallback_comp = extract_company_from_url(url)
        if fallback_comp and fallback_comp.lower() == entreprise.lower():
            return poste_found

    return poste_found


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
