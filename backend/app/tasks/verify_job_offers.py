import asyncio
from html.parser import HTMLParser
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import parse_qs, urlparse

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
CLOSED_TEXT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        # Formulations avec ou sans nom d'entreprise / intitulé intermédiaire (ex: 'Cette offre d'emploi chez Leo Lagrange Animation n'est plus disponible')
        r"(?:cette |l')?offre (?:d'emploi )?(?:chez [^.\n,;!?]+? )?(?:n'est plus (?:disponible|active|en ligne|accessible|consultable)|a expiré|a été (?:pourvue|supprimée|clôturée|archivée|désactivée|dépubliée)|est (?:clôturée|fermée|terminée|expirée|indisponible)|n'est plus à pourvoir)",
        r"(?:cette |l')?annonce (?:d'emploi )?(?:chez [^.\n,;!?]+? )?(?:n'est plus (?:active|disponible|accessible|en ligne|consultable)|n'existe plus|a été (?:désactivée|supprimée|archivée|dépubliée)|a expiré)",
        r"candidatures? (?:pour ce poste )?(?:sont )?(?:closes?|fermées?|terminées?|suspendues?)",
        # Bandeau LinkedIn FR d'une offre close (figcaption.closed-job__flavor--closed)
        r"candidatures ne sont plus acceptées",
        r"(?:ce |le )?poste (?:a été |est )?(?:pourvu|fermé|clôturé|comblé|attribué)",
        r"(?:ce |le )?poste n'est plus à pourvoir",
        r"offre (?:d'emploi )?(?:expirée|introuvable|désactivée|clôturée|supprimée)",
        r"l'annonce demandée (?:n'existe plus|est introuvable)",
        r"(?:l')?offre (?:demandée|recherchée) (?:n'existe plus|est introuvable)",
        r"l'offre (?:que vous (?:cherchez|recherchez|souhaitez afficher) )?(?:n'est plus (?:disponible|en ligne|active|consultable)|n'existe plus|est introuvable)",
        r"ce recrutement est (?:terminé|clôturé|fermé)",
        r"le lien que vous avez suivi est (?:expiré|invalide|mort)",
        r"job (?:posting )?(?:is |has )?(?:no longer (?:available|active|open)|expired|closed|has been filled|archived)",
        r"position (?:has been |is )?filled",
        r"posting (?:has expired|is closed|is no longer available)",
        r"this (?:job|vacancy|position|role) (?:has expired|is no longer available|is closed|has been filled|is archived)",
        r"the job you are looking for is no longer (?:active|available|open)",
        r"no longer accepting applications",
        # Note: 'page introuvable' / 'page not found' sont volontairement absents du
        # texte statique — trop génériques (snippet d'erreur, widget footer, JSON
        # inline) présents sur des pages d'offre pourtant actives. Les vrais 404
        # HTTP sont déjà couverts par le status code (http_status_404).
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

    # LinkedIn redirige une offre purgée vers un listing marqué trk=expired_jd_redirect
    if "expired_jd_redirect" in parse_qs(final_parsed.query).get("trk", []):
        return True

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


def _iter_json_ld_nodes(data: Any) -> Iterator[Dict[str, Any]]:
    """Parcourt récursivement un document JSON-LD (liste, @graph) pour en extraire les noeuds."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_json_ld_nodes(item)
    elif isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _iter_json_ld_nodes(item)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def extract_json_ld_valid_through(html: str) -> Optional[datetime]:
    """
    Extrait la date `validThrough` du premier bloc JSON-LD `schema.org/JobPosting`
    trouvé dans la page. Donnée structurée exposée pour le SEO par la plupart des
    grandes plateformes (Indeed, LinkedIn, France Travail, Apec, HelloWork, WTTJ) :
    plus fiable qu'une détection par regex sur texte visible, zéro dépendance à la langue.
    """
    if not html:
        return None
    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _iter_json_ld_nodes(data):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if "JobPosting" not in types:
                continue
            parsed = _parse_iso_datetime(node.get("validThrough"))
            if parsed:
                return parsed
    return None


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

        # Vérification structurée JSON-LD (schema.org JobPosting.validThrough) - la plus fiable,
        # zéro dépendance à la langue/formulation, exposée par la plupart des grandes plateformes
        valid_through = extract_json_ld_valid_through(response.text)
        if valid_through and valid_through < datetime.now(timezone.utc):
            return {
                "status": "closed",
                "valid": False,
                "status_code": status,
                "final_url": final_url,
                "reason": f"jsonld_valid_through_expired: {valid_through.isoformat()}",
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


INDEED_GRAPHQL_URL = "https://apis.indeed.com/graphql"
INDEED_JOB_KEY_RE = re.compile(r"^[0-9a-f]{16}$")


def extract_indeed_job_key(url: str) -> Optional[str]:
    """Clé d'offre Indeed (paramètre jk) d'une URL indeed.*, ou None."""
    parsed = urlparse(url or "")
    if "indeed" not in (parsed.hostname or "").split("."):
        return None
    jk = (parse_qs(parsed.query).get("jk") or [""])[0].lower()
    return jk if INDEED_JOB_KEY_RE.match(jk) else None


async def check_indeed_jobs(
    job_keys: List[str], client: httpx.AsyncClient, batch_size: int = 50
) -> Dict[str, Dict[str, Any]]:
    """
    Statut des offres Indeed via l'API GraphQL de l'app mobile (celle de jobspy) : la page web
    répond 401 Cloudflare au VPS. Par lots, pour ne pas faire bloquer l'IP qui sert aussi à la collecte.
    Une clé absente d'une réponse valide reste inconnue ; un lot en échec ne donne aucun verdict.
    """
    if not job_keys:
        return {}
    try:
        from jobspy.indeed.constant import headers as indeed_api_headers
    except ImportError:
        logger.warning("jobspy introuvable : vérification Indeed par l'API ignorée.")
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    for start in range(0, len(job_keys), batch_size):
        batch = job_keys[start:start + batch_size]
        query = (
            f"query {{ jobData(jobKeys: {json.dumps(batch)}) "
            "{ results { job { key expired } } } }"
        )
        try:
            response = await client.post(
                INDEED_GRAPHQL_URL, json={"query": query}, headers=indeed_api_headers
            )
            payload = response.json() if response.status_code == 200 else {}
            if payload.get("errors") or "data" not in payload:
                raise ValueError(f"HTTP {response.status_code}, errors={payload.get('errors')}")
            jobs = {
                item["job"]["key"]: item["job"]
                for item in payload["data"]["jobData"]["results"]
                if item.get("job")
            }
        except Exception as e:
            logger.warning(f"⚠️ API Indeed en échec sur un lot de {len(batch)} offres : {e}")
            continue
        for key in batch:
            job = jobs.get(key)
            if job is None:
                results[key] = {"status": "unknown", "is_valid": None, "reason": "indeed_api_job_not_found"}
            elif job.get("expired"):
                results[key] = {"status": "closed", "is_valid": False, "reason": "indeed_api_expired"}
            else:
                results[key] = {"status": "valid", "is_valid": True, "reason": "indeed_api_active"}
    return results


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

    host_labels = (urlparse(url).hostname or "").split(".")

    # HelloWork rend la clôture côté serveur (« n'est plus disponible », typePage DO-Expiree) :
    # un 200 sans texte de clôture suffit, alors que le headless y expire souvent (networkidle 60 s)
    if "hellowork" in host_labels and fast_result.get("status_code") == 200:
        return {
            "offer_id": offer_id,
            "status": "valid",
            "is_valid": True,
            "reason": "static_render_domain_ok",
            "url": url,
        }

    # Indeed: 401 Cloudflare au niveau 1 puis timeout headless (~60 s) -> jamais concluant,
    # on garde les clôtures détectées en HTTP ci-dessus et on saute le navigateur
    if "indeed" in host_labels:
        return {
            "offer_id": offer_id,
            "status": "unknown",
            "is_valid": None,
            "reason": "headless_skipped_antibot_domain",
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


def _unknown_reason_key(result: Dict[str, Any]) -> str:
    """« linkedin.com js_crawl_failed » : domaine sans sous-domaine, raison sans son détail."""
    host = urlparse(result.get("url") or "").hostname or "?"
    reason = str(result.get("reason") or "unknown").split(":")[0].strip()
    return f"{'.'.join(host.split('.')[-2:])} {reason}"


async def verify_job_offers_workflow(
    limit: Optional[int] = 100,
    max_concurrency: int = 5,
    dry_run: bool = False,
    time_budget_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Workflow principal :
    1. Récupère les offres actives (non supprimées) ayant une url ou source_url :
       celles affichées à un utilisateur (matched_user_ids non vide) d'abord, puis les autres ;
       dans chaque groupe, jamais vérifiées d'abord puis last_verified_at le plus ancien (rotation).
    2. Vérifie les liens dans cet ordre, max_concurrency à la fois. Passé time_budget_seconds,
       plus aucune offre n'est lancée : les restantes, non tamponnées, passent en tête au run suivant.
    3. Écrit au fil de l'eau last_verified_at sur chaque offre vérifiée, et un soft delete
       UNIQUEMENT sur les offres closes confirmées (is_valid is False).
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

    # Offres affichées à au moins un utilisateur d'abord : sans cette priorité, le lot quotidien
    # se dilue sur toute la base et une offre close reste visible des jours.
    is_visible = {"$and": [{"$isArray": "$matched_user_ids"}, {"$gt": [{"$size": "$matched_user_ids"}, 0]}]}
    pipeline: List[Dict[str, Any]] = [
        {"$match": query},
        # Seuls les champs du tri et de la vérification : sans plafond, le tri porte sur toute la base.
        {"$project": {
            "url": 1,
            "source_url": 1,
            "last_verified_at": 1,
            "created_at": 1,
            "_visible": {"$cond": [is_visible, 1, 0]},
        }},
        {"$sort": {"_visible": -1, "last_verified_at": 1, "created_at": -1}},
    ]
    if limit:
        pipeline.append({"$limit": limit})

    offers = await collection.aggregate(pipeline).to_list(length=limit)
    found = len(offers)
    logger.info(f"📊 {found} offres actives trouvées pour vérification.")

    if found == 0:
        return {
            "total_checked": 0,
            "valid_count": 0,
            "closed_count": 0,
            "unknown_count": 0,
            "updated_db_count": 0,
            "summary": "Aucune offre active à vérifier",
        }

    semaphore = asyncio.Semaphore(max_concurrency)
    updated_db_count = 0
    indeed_verdicts: Dict[str, Dict[str, Any]] = {}

    async def verify_and_persist(
        offer: Dict[str, Any], http_client: httpx.AsyncClient
    ) -> Dict[str, Any]:
        nonlocal updated_db_count
        url = offer.get("url") or offer.get("source_url")
        try:
            verdict = indeed_verdicts.get(extract_indeed_job_key(url))
            if verdict and verdict["is_valid"] is not None:
                result = {"offer_id": str(offer.get("_id", "")), **verdict, "url": url}
            else:
                result = await verify_single_offer(offer, semaphore, http_client=http_client)
        except Exception as e:
            logger.error(f"💥 Exception non interceptée sur l'offre {offer.get('_id')}: {e}")
            result = {
                "offer_id": str(offer.get("_id", "")),
                "status": "unknown",
                "is_valid": None,
                "reason": f"gather_exception: {str(e)}",
                "url": url,
            }

        if dry_run:
            return result

        # Écriture au fil de l'eau : un run coupé par execution_timeout garde ce qu'il a vérifié.
        # last_verified_at aussi sur 'unknown', sinon ces offres resteraient en tête de rotation.
        now = datetime.now(timezone.utc)
        fields: Dict[str, Any] = {"last_verified_at": now}
        is_closed = result.get("is_valid") is False
        if is_closed:
            fields.update({
                "is_deleted": True,
                "pipeline_stage": "expired",
                "deleted_date": now,
                "deletion_reason": result["reason"],
                "updated_at": now,
            })
        try:
            update_res = await collection.update_one({"_id": offer["_id"]}, {"$set": fields})
            if is_closed and update_res.modified_count > 0:
                updated_db_count += 1
        except Exception as e:
            logger.error(f"💥 Erreur lors de l'écriture de l'offre {result['offer_id']}: {e}")
        return result

    deadline = monotonic() + time_budget_seconds if time_budget_seconds else None
    pending = iter(offers)
    processed_results: List[Dict[str, Any]] = []

    async def worker(http_client: httpx.AsyncClient) -> None:
        # Itérateur partagé : les workers prennent les offres dans l'ordre de priorité.
        for offer in pending:
            if deadline is not None and monotonic() >= deadline:
                return
            processed_results.append(await verify_and_persist(offer, http_client))

    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
        timeout=10.0,
    ) as http_client:
        # Indeed en une passe par lots avant les workers : les offres tranchées par l'API
        # ne passent ni par le check HTTP (401) ni par le headless
        indeed_keys = list(dict.fromkeys(
            key for o in offers
            if (key := extract_indeed_job_key(o.get("url") or o.get("source_url")))
        ))
        indeed_verdicts = await check_indeed_jobs(indeed_keys, http_client)
        if indeed_keys:
            decided = sum(1 for v in indeed_verdicts.values() if v["is_valid"] is not None)
            logger.info(f"🔎 API Indeed : {decided}/{len(indeed_keys)} offres tranchées.")
        await asyncio.gather(*(worker(http_client) for _ in range(max_concurrency)))

    total = len(processed_results)
    deferred_count = found - total
    if deferred_count:
        logger.info(f"⏱️ Budget de temps atteint : {deferred_count} offres reportées au prochain run.")

    valid_count = sum(1 for r in processed_results if r.get("is_valid") is True)
    closed_offers = [r for r in processed_results if r.get("is_valid") is False]
    closed_count = len(closed_offers)
    unknown_count = sum(1 for r in processed_results if r.get("is_valid") is None)
    # « site raison » -> nombre, pour savoir quelles offres restent sans verdict et pourquoi
    unknown_reasons = dict(Counter(
        _unknown_reason_key(r) for r in processed_results if r.get("is_valid") is None
    ).most_common())

    logger.info(
        f"📊 Résultat vérification: {valid_count} actives, {closed_count} closes confirmées, "
        f"{unknown_count} inconnues (ignorées)"
    )
    if unknown_reasons:
        logger.info(f"❔ Inconnues par site et raison : {unknown_reasons}")

    if not dry_run and closed_offers:
        logger.info(f"🗑️ Soft-delete appliqué à {updated_db_count} offres closes confirmées.")

    return {
        "total_checked": total,
        "valid_count": valid_count,
        "closed_count": closed_count,
        "unknown_count": unknown_count,
        "updated_db_count": updated_db_count,
        "deferred_count": deferred_count,
        "unknown_reasons": unknown_reasons,
        "dry_run": dry_run,
        "closed_details": closed_offers[:20],
        "summary": (
            f"Vérification terminée: {total} testées, {valid_count} valides, "
            f"{closed_count} closes, {unknown_count} inconnues/transitoires "
            f"({updated_db_count} marquées supprimées, {deferred_count} reportées)"
        ),
    }


def verify_job_offers_sync(
    limit: Optional[int] = 100,
    max_concurrency: int = 5,
    dry_run: bool = False,
    time_budget_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Point d'entrée synchrone pour Airflow PythonOperator."""
    return asyncio.run(
        verify_job_offers_workflow(
            limit=limit,
            max_concurrency=max_concurrency,
            dry_run=dry_run,
            time_budget_seconds=time_budget_seconds,
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
                    "pipeline_stage": "discovered",
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
