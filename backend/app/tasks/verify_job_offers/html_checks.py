"""HTML, JSON-LD, redirect, and visible-text closure checks for job offers."""

from html.parser import HTMLParser
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional
from urllib.parse import parse_qs, urlparse

# Standard User-Agent for HTTP verification requests
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Compiled regex patterns indicating a job offer is closed or unavailable
CLOSED_TEXT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        # Formulations with or without company name / intermediate title
        r"(?:cette |l')?offre (?:d'emploi )?(?:chez [^.\n,;!?]+? )?(?:n'est plus (?:disponible|active|en ligne|accessible|consultable)|a expiré|a été (?:pourvue|supprimée|clôturée|archivée|désactivée|dépubliée)|est (?:clôturée|fermée|terminée|expirée|indisponible)|n'est plus à pourvoir)",
        r"(?:cette |l')?annonce (?:d'emploi )?(?:chez [^.\n,;!?]+? )?(?:n'est plus (?:active|disponible|accessible|en ligne|consultable)|n'existe plus|a été (?:désactivée|supprimée|archivée|dépubliée)|a expiré)",
        r"candidatures? (?:pour ce poste )?(?:sont )?(?:closes?|fermées?|terminées?|suspendues?)",
        # LinkedIn FR closed-job banner (figcaption.closed-job__flavor--closed)
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
        # 'page introuvable' / 'page not found' omitted intentionally (false positives in footers/JSON).
        # True HTTP 404s are already handled by status code check (http_status_404).
    ]
]


class VisibleTextParser(HTMLParser):
    """HTML parser ignoring script, style, noscript, svg, and aside sidebars."""

    def __init__(self) -> None:
        super().__init__()
        self._ignore_level = 0
        self._text_chunks: list[str] = []
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
    """Extract visible text from HTML while stripping scripts, styles, and sidebars."""
    if not html:
        return ""
    parser = VisibleTextParser()
    try:
        parser.feed(html)
        return " ".join(parser._text_chunks)
    except Exception:
        text = re.sub(
            r"<(script|style|noscript|svg|aside)[^>]*>.*?</\1>",
            " ",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        return re.sub(r"<[^>]+>", " ", text)


def is_redirected_to_generic_listing(original_url: str, final_url: str) -> bool:
    """Detect whether a specific job URL redirected to a homepage or generic listing."""
    if not original_url or not final_url:
        return False

    orig_parsed = urlparse(original_url)
    final_parsed = urlparse(final_url)

    # LinkedIn redirects purged jobs to a listing tagged trk=expired_jd_redirect
    if "expired_jd_redirect" in parse_qs(final_parsed.query).get("trk", []):
        return True

    orig_path = orig_parsed.path.rstrip("/")
    final_path = final_parsed.path.rstrip("/")

    if len(orig_path.split("/")) > 2 and final_path == "":
        return True

    generic_endings = ("/jobs", "/emplois", "/carrieres", "/careers", "/offres", "/search")
    if orig_path != final_path and any(final_path.endswith(ending) for ending in generic_endings):
        return True

    return False


def _iter_json_ld_nodes(data: Any) -> Iterator[Dict[str, Any]]:
    """Recursively traverse JSON-LD lists and @graph containers."""
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
    """Extract `validThrough` from the first schema.org/JobPosting JSON-LD block."""
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
    """Search for job closure phrases inside cleaned visible text."""
    if not text:
        return None
    for pattern in CLOSED_TEXT_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None
