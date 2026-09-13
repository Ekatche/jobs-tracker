import asyncio
from html.parser import HTMLParser
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.database import get_database

logger = logging.getLogger(__name__)

# User agent standard pour les requêtes HTTP
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Expressions régulières indiquant qu'une offre est close ou inexistante
# Note: '404 not found' est volontairement retiré du chemin HTML statique
# pour éviter les faux positifs sur les snippets d'erreur ou JSON inline.
CLOSED_TEXT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"cette offre (n'est plus disponible|a expiré|a été pourvue|est clôturée|est fermée)",
        r"l'offre (d'emploi )?(n'est plus|a été supprimée|a expiré)",
        r"candidatures? (closes?|fermées?|terminées?)",
        r"poste (pourvu|fermé|clôturé)",
        r"cette annonce n'est plus (active|disponible)",
        r"ce poste a été pourvu",
        r"offre expirée",
        r"offre introuvable",
        r"l'annonce demandée n'existe plus",
        r"job (is )?(no longer available|expired|closed|has been filled)",
        r"position (has been )?filled",
        r"posting has expired",
        r"this job (has expired|is no longer available|is closed)",
        r"this vacancy has been closed",
        r"the job you are looking for is no longer active",
        r"page introuvable",
    ]
]


class VisibleTextParser(HTMLParser):
    """Parseur HTML qui ignore les balises script, style, noscript, svg et aside (sidebars d'offres similaires)."""

    def __init__(self) -> None:
        super().__init__()
        self._ignore_level = 0
        self._text_chunks: List[str] = []
        self._ignore_tags = {"script", "style", "noscript", "svg", "aside"}

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag.lower() in self._ignore_tags:
            self._ignore_level += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._ignore_tags and self._ignore_level > 0:
            self._ignore_level -= 1

    def handle_data(self, data: str) -> None:
        if self._ignore_level == 0:
            stripped = data.strip()
            if stripped:
                self._text_chunks.append(stripped)


def extract_visible_text(html: str) -> str:
    """
    Extrait le texte visible d'un document HTML en ignorant complètement
    les scripts, styles, noscripts, svg et barres latérales (aside).
    """
    if not html:
        return ""
    parser = VisibleTextParser()
    try:
        parser.feed(html)
        return " ".join(parser._text_chunks)
    except Exception:
        # Fallback de nettoyage par regex
        text = re.sub(
            r"<(script|style|noscript|svg|aside)[^>]*>.*?</\1>",
            " ",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        return re.sub(r"<[^>]+>", " ", text)


def is_redirected_to_generic_listing(original_url: str, final_url: str) -> bool:
    """
    Détecte si l'URL spécifique d'un job a été redirigée vers une page d'accueil ou liste générale,
    ce qui arrive fréquemment quand une offre n'existe plus.
    """
    if not original_url or not final_url:
        return False

    orig_parsed = urlparse(original_url)
    final_parsed = urlparse(final_url)

    orig_path = orig_parsed.path.rstrip("/")
    final_path = final_parsed.path.rstrip("/")

    # Si on quitte le chemin de l'offre pour la racine (path vide après rstrip)
    if len(orig_path.split("/")) > 2 and final_path == "":
        return True

    # Si on atterrit sur une page de listing sans identifiant alors qu'on en avait un
    generic_endings = ("/jobs", "/emplois", "/carrieres", "/careers", "/offres", "/search")
    if orig_path != final_path and any(final_path.endswith(ending) for ending in generic_endings):
        return True

    return False


def detect_closure_in_text(text: str) -> Optional[str]:
    """Recherche les motifs d'expiration dans un bloc de texte visible nettoyé."""
    if not text:
        return None
    for pattern in CLOSED_TEXT_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


async def check_url_http_fast(
    url: str,
    timeout: float = 10.0,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Niveau 1: Vérification HTTP rapide.
    - 404/410 ou redirection vers liste générale -> status: "closed", valid: False
    - 200 OK avec texte de clôture visible -> status: "closed", valid: False
    - 200 OK normal -> status: "valid", valid: True, requires_js_check: True
    - 5xx, timeouts, connection errors -> status: "unknown", valid: None (erreur transitoire, AUCUNE suppression)
    """
    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
            timeout=timeout,
        )
        should_close_client = True

    try:
        response = await client.get(url)
        final_url = str(response.url)
        status = response.status_code

        # Statuts HTTP explicites d'indisponibilité définitive
        if status in (404, 410):
            return {
                "status": "closed",
                "valid": False,
                "status_code": status,
                "final_url": final_url,
                "reason": f"http_status_{status}",
                "requires_js_check": False,
            }

        # Erreurs serveur transitoires (5xx) -> UNKNOWN, ne jamais marquer closed
        if status >= 500:
            return {
                "status": "unknown",
                "valid": None,
                "status_code": status,
                "final_url": final_url,
                "reason": f"server_error_{status}",
                "requires_js_check": False,
            }

        # Détection de redirection vers une liste générale
        if is_redirected_to_generic_listing(url, final_url):
            return {
                "status": "closed",
                "valid": False,
                "status_code": status,
                "final_url": final_url,
                "reason": "redirected_to_generic_listing",
                "requires_js_check": False,
            }

        # Analyse du texte VISIBLE uniquement (sans scripts, styles ou sidebars d'offres similaires)
        visible_text = extract_visible_text(response.text)
        matched_closure = detect_closure_in_text(visible_text)
        if matched_closure:
            return {
                "status": "closed",
                "valid": False,
                "status_code": status,
                "final_url": final_url,
                "reason": f"static_closed_text: '{matched_closure}'",
                "requires_js_check": False,
            }

        return {
            "status": "valid",
            "valid": True,
            "status_code": status,
            "final_url": final_url,
            "reason": "http_200_ok",
            "requires_js_check": True,
        }

    except httpx.ConnectError:
        return {
            "status": "unknown",
            "valid": None,
            "status_code": None,
            "final_url": url,
            "reason": "connection_error",
            "requires_js_check": False,
        }
    except httpx.TimeoutException:
        return {
            "status": "unknown",
            "valid": None,
            "status_code": None,
            "final_url": url,
            "reason": "timeout",
            "requires_js_check": False,
        }
    except Exception as e:
        logger.warning(f"⚠️ Erreur HTTP lors du check de {url}: {e}")
        return {
            "status": "unknown",
            "valid": None,
            "status_code": None,
            "final_url": url,
            "reason": f"http_error: {str(e)}",
            "requires_js_check": False,
        }
    finally:
        if should_close_client:
            await client.aclose()


async def check_url_headless_js(url: str) -> Dict[str, Any]:
    """
    Niveau 2: Rendu complet JavaScript via Crawl4AI / Playwright.
    Attend l'hydratation et analyse le DOM pour déceler les offres closes sur les SPA.
    En cas de problème technique navigateur, renvoie status 'unknown' (ne pas supprimer).
    """
    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
        from crawl4ai.async_configs import BrowserConfig, CacheMode

        browser_config = BrowserConfig(
            headless=True,
            java_script_enabled=True,
            text_mode=False,
            viewport_width=1280,
            viewport_height=800,
        )

        crawl_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_until="networkidle",
            delay_before_return_html=1.5,
            remove_overlay_elements=True,
            js_code="""
            () => {
                // Récupération sécurisée du texte visible principal (en excluant les asides)
                const clone = document.body ? document.body.cloneNode(true) : null;
                if (clone) {
                    const ignored = clone.querySelectorAll('script, style, noscript, svg, aside');
                    ignored.forEach(el => el.remove());
                    return {
                        text_sample: clone.innerText.substring(0, 5000),
                        final_url: window.location.href
                    };
                }
                return {
                    text_sample: "",
                    final_url: window.location.href
                };
            }
            """,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawl_config)

            if not result.success:
                return {
                    "status": "unknown",
                    "valid": None,
                    "reason": f"js_crawl_failed: {result.error_message}",
                    "final_url": url,
                }

            # Extraire les données renvoyées par le script JS
            js_data = result.js_execution_result if isinstance(result.js_execution_result, dict) else {}
            final_url = js_data.get("final_url") or getattr(result, "url", url)
            page_text = js_data.get("text_sample")

            if not page_text:
                # Si le retour JS n'avait pas le format attendu, filtrer le HTML propre
                page_text = extract_visible_text(result.cleaned_html or "")

            # 1. Vérification de redirection SPA
            if is_redirected_to_generic_listing(url, final_url):
                return {
                    "status": "closed",
                    "valid": False,
                    "reason": "js_spa_redirected_to_listing",
                    "final_url": final_url,
                }

            # 2. Détection de texte d'expiration dans le texte visible
            matched_closure = detect_closure_in_text(page_text)
            if matched_closure:
                return {
                    "status": "closed",
                    "valid": False,
                    "reason": f"js_dom_closed_text: '{matched_closure}'",
                    "final_url": final_url,
                }

            return {
                "status": "valid",
                "valid": True,
                "reason": "js_rendered_active",
                "final_url": final_url,
            }

    except ImportError:
        logger.warning("⚠️ Crawl4AI non disponible, maintien du statut actif")
        return {
            "status": "valid",
            "valid": True,
            "reason": "crawl4ai_not_installed_assumed_valid",
            "final_url": url,
        }
    except Exception as e:
        logger.error(f"💥 Erreur lors de l'inspection JS de {url}: {e}")
        return {
            "status": "unknown",
            "valid": None,
            "reason": f"js_eval_exception: {str(e)}",
            "final_url": url,
        }


async def verify_single_offer(
    offer: Dict[str, Any],
    semaphore: asyncio.Semaphore,
    http_client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Vérifie une seule offre avec la logique à 2 niveaux.
    Retourne:
    - is_valid: True (active)
    - is_valid: False (clôturée/invalide avec certitude)
    - is_valid: None (état inconnu / échec transitoire, PAS de suppression)
    """
    offer_id = str(offer.get("_id", ""))
    url = offer.get("url") or offer.get("source_url")

    if not url:
        return {
            "offer_id": offer_id,
            "status": "closed",
            "is_valid": False,
            "reason": "missing_url",
            "url": None,
        }

    # Niveau 1: Check HTTP rapide
    fast_result = await check_url_http_fast(url, client=http_client)

    # Si échec transitoire (5xx, timeout, connect error)
    if fast_result.get("status") == "unknown" or fast_result.get("valid") is None:
        return {
            "offer_id": offer_id,
            "status": "unknown",
            "is_valid": None,
            "reason": fast_result["reason"],
            "url": url,
        }

    # Si offre close confirmée (404, redirection, texte visible d'expiration)
    if fast_result.get("status") == "closed" or fast_result.get("valid") is False:
        return {
            "offer_id": offer_id,
            "status": "closed",
            "is_valid": False,
            "reason": fast_result["reason"],
            "url": url,
        }

    # Niveau 2: Contrôle JS si le check HTTP a réussi et le demande
    if fast_result.get("requires_js_check", True):
        async with semaphore:
            js_result = await check_url_headless_js(url)
            return {
                "offer_id": offer_id,
                "status": js_result.get("status", "valid"),
                "is_valid": js_result.get("valid"),
                "reason": js_result.get("reason", "unknown"),
                "url": url,
            }

    return {
        "offer_id": offer_id,
        "status": "valid",
        "is_valid": True,
        "reason": fast_result["reason"],
        "url": url,
    }


async def verify_job_offers_workflow(
    limit: Optional[int] = 100,
    max_concurrency: int = 5,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Workflow principal :
    1. Récupère les offres actives (non supprimées) ayant une url ou source_url.
    2. Vérifie la validité des liens en parallèle avec contrôle de concurrence.
    3. Effectue un soft delete UNIQUEMENT sur les offres closes confirmées (is_valid is False).
       Les offres avec statut 'unknown' (erreurs transitoires) ne sont JAMAIS supprimées.
    """
    logger.info("🔍 Lancement du workflow de vérification des offres d'emploi...")
    db = await get_database()
    collection = db["job_offers"]

    # Requête ciblant les offres non supprimées ayant au moins url ou source_url
    query = {
        "is_deleted": {"$ne": True},
        "$or": [
            {"url": {"$exists": True, "$nin": [None, ""]}},
            {"source_url": {"$exists": True, "$nin": [None, ""]}},
        ],
    }

    cursor = collection.find(query).sort("created_at", -1)
    if limit:
        cursor = cursor.limit(limit)

    offers = await cursor.to_list(length=limit)
    total = len(offers)
    logger.info(f"📊 {total} offres actives trouvées pour vérification.")

    if total == 0:
        return {
            "total_checked": 0,
            "valid_count": 0,
            "closed_count": 0,
            "unknown_count": 0,
            "updated_db_count": 0,
            "summary": "Aucune offre active à vérifier",
        }

    semaphore = asyncio.Semaphore(max_concurrency)

    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
        timeout=10.0,
    ) as http_client:
        tasks = [
            verify_single_offer(offer, semaphore, http_client=http_client)
            for offer in offers
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filtrer et normaliser les résultats
    processed_results: List[Dict[str, Any]] = []
    for idx, r in enumerate(raw_results):
        if isinstance(r, Exception):
            logger.error(f"💥 Exception non interceptée sur l'offre {offers[idx].get('_id')}: {r}")
            processed_results.append({
                "offer_id": str(offers[idx].get("_id", "")),
                "status": "unknown",
                "is_valid": None,
                "reason": f"gather_exception: {str(r)}",
                "url": offers[idx].get("url") or offers[idx].get("source_url"),
            })
        else:
            processed_results.append(r)

    valid_count = sum(1 for r in processed_results if r.get("is_valid") is True)
    closed_offers = [r for r in processed_results if r.get("is_valid") is False]
    closed_count = len(closed_offers)
    unknown_count = sum(1 for r in processed_results if r.get("is_valid") is None)

    logger.info(
        f"📊 Résultat vérification: {valid_count} actives, {closed_count} closes confirmées, "
        f"{unknown_count} inconnues (ignorées)"
    )

    updated_db_count = 0
    if not dry_run and closed_offers:
        now = datetime.now(timezone.utc)
        for closed in closed_offers:
            try:
                from bson import ObjectId

                obj_id = ObjectId(closed["offer_id"])
                update_res = await collection.update_one(
                    {"_id": obj_id},
                    {
                        "$set": {
                            "is_deleted": True,
                            "deleted_date": now,
                            "deletion_reason": closed["reason"],
                            "updated_at": now,
                        }
                    },
                )
                if update_res.modified_count > 0:
                    updated_db_count += 1
            except Exception as e:
                logger.error(
                    f"💥 Erreur lors du soft delete de l'offre {closed['offer_id']}: {e}"
                )

        logger.info(f"🗑️ Soft-delete appliqué à {updated_db_count} offres closes confirmées.")

    return {
        "total_checked": total,
        "valid_count": valid_count,
        "closed_count": closed_count,
        "unknown_count": unknown_count,
        "updated_db_count": updated_db_count,
        "dry_run": dry_run,
        "closed_details": closed_offers[:20],
        "summary": (
            f"Vérification terminée: {total} testées, {valid_count} valides, "
            f"{closed_count} closes, {unknown_count} inconnues/transitoires "
            f"({updated_db_count} marquées supprimées)"
        ),
    }


def verify_job_offers_sync(
    limit: Optional[int] = 100,
    max_concurrency: int = 5,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Point d'entrée synchrone pour Airflow PythonOperator."""
    return asyncio.run(
        verify_job_offers_workflow(
            limit=limit,
            max_concurrency=max_concurrency,
            dry_run=dry_run,
        )
    )


async def restore_falsely_deleted_offers(dry_run: bool = True) -> Dict[str, Any]:
    """
    Restaure en base les offres marquées à tort comme supprimées
    suite à des erreurs réseau ou serveur transitoires (5xx, timeouts, connection errors).
    """
    db = await get_database()
    collection = db["job_offers"]

    transient_regex = "^(server_error_|connection_error|timeout|http_error:)"
    query = {
        "is_deleted": True,
        "deletion_reason": {"$regex": transient_regex},
    }

    count = await collection.count_documents(query)
    restored = 0

    if not dry_run and count > 0:
        res = await collection.update_many(
            query,
            {
                "$set": {
                    "is_deleted": False,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$unset": {
                    "deleted_date": "",
                    "deletion_reason": "",
                },
            },
        )
        restored = res.modified_count

    return {
        "matched": count,
        "restored": restored,
        "dry_run": dry_run,
    }
