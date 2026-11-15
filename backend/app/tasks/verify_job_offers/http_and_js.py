"""HTTP fast check (level 1) and headless Playwright check (level 2) for job offers."""

import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from .html_checks import (
    DEFAULT_HEADERS,
    detect_closure_in_text,
    extract_json_ld_valid_through,
    extract_visible_text,
    is_redirected_to_generic_listing,
)

_HEADLESS_JS_EXTRACT = """
() => {
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
"""


def _evaluate_http_response(url: str, response: httpx.Response) -> Dict[str, Any]:
    """Interpret an HTTP GET response into valid, closed, or unknown verification status."""
    final_url = str(response.url)
    status = response.status_code

    if status in (404, 410):
        return {
            "status": "closed",
            "valid": False,
            "status_code": status,
            "final_url": final_url,
            "reason": f"http_status_{status}",
            "requires_js_check": False,
        }
    if status >= 500:
        return {
            "status": "unknown",
            "valid": None,
            "status_code": status,
            "final_url": final_url,
            "reason": f"server_error_{status}",
            "requires_js_check": False,
        }

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
    if is_redirected_to_generic_listing(url, final_url):
        return {
            "status": "closed",
            "valid": False,
            "status_code": status,
            "final_url": final_url,
            "reason": "redirected_to_generic_listing",
            "requires_js_check": False,
        }

    matched_closure = detect_closure_in_text(extract_visible_text(response.text))
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


def _unknown_http_error(url: str, reason: str) -> Dict[str, Any]:
    return {
        "status": "unknown",
        "valid": None,
        "status_code": None,
        "final_url": url,
        "reason": reason,
        "requires_js_check": False,
    }


async def check_url_http_fast(
    url: str,
    timeout: float = 10.0,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Level 1: fast HTTP check.
    Returns valid/closed/unknown without deleting transient failures (5xx, timeout, connect error).
    """
    pkg = sys.modules["app.tasks.verify_job_offers"]
    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
            timeout=timeout,
            transport=pkg.public_only_transport(),
        )
        should_close_client = True

    try:
        response = await client.get(url)
        return _evaluate_http_response(url, response)
    except httpx.ConnectError:
        return _unknown_http_error(url, "connection_error")
    except httpx.TimeoutException:
        return _unknown_http_error(url, "timeout")
    except Exception as e:
        pkg.logger.warning(f"⚠️ Erreur HTTP lors du check de {url}: {e}")
        return _unknown_http_error(url, f"http_error: {str(e)}")
    finally:
        if should_close_client:
            await client.aclose()


def _evaluate_headless_result(url: str, result: Any) -> Dict[str, Any]:
    """Inspect a Crawl4AI result for SPA redirects or DOM closure banners."""
    if not result.success:
        return {
            "status": "unknown",
            "valid": None,
            "reason": f"js_crawl_failed: {result.error_message}",
            "final_url": url,
        }

    js_data = result.js_execution_result if isinstance(result.js_execution_result, dict) else {}
    final_url = js_data.get("final_url") or getattr(result, "url", url)
    page_text = js_data.get("text_sample") or extract_visible_text(result.cleaned_html or "")

    if is_redirected_to_generic_listing(url, final_url):
        return {
            "status": "closed",
            "valid": False,
            "reason": "js_spa_redirected_to_listing",
            "final_url": final_url,
        }

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


async def check_url_headless_js(url: str) -> Dict[str, Any]:
    """
    Level 2: full JS rendering via Crawl4AI / Playwright behind the public-only egress proxy.
    """
    pkg = sys.modules["app.tasks.verify_job_offers"]
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
            js_code=_HEADLESS_JS_EXTRACT,
        )

        async with (
            pkg.public_only_proxy() as proxy_url,
            AsyncWebCrawler(config=pkg.browser_config_behind_proxy(browser_config, proxy_url)) as crawler,
        ):
            result = await crawler.arun(url=url, config=crawl_config)
            return _evaluate_headless_result(url, result)
    except ImportError:
        pkg.logger.warning("⚠️ Crawl4AI non disponible, maintien du statut actif")
        return {
            "status": "valid",
            "valid": True,
            "reason": "crawl4ai_not_installed_assumed_valid",
            "final_url": url,
        }
    except Exception as e:
        pkg.logger.error(f"💥 Erreur lors de l'inspection JS de {url}: {e}")
        return {
            "status": "unknown",
            "valid": None,
            "reason": f"js_eval_exception: {str(e)}",
            "final_url": url,
        }
