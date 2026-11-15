import re
from typing import Any, Dict, List, Tuple

SOURCE_PRIORITY: Tuple[str, ...] = ("manual", "cv", "website", "github")

_SCALAR_FIELDS = ("role", "location", "contract", "sector")
_MANUAL_CLEARABLE_CONTACT_KEYS = ("mobility", "availability")


def _ordered_sources(sources: Dict[str, Dict[str, Any]]) -> List[str]:
    known = [s for s in SOURCE_PRIORITY if sources.get(s)]
    extra = sorted(s for s in sources if s not in SOURCE_PRIORITY and sources.get(s))
    return known + extra


def _dedup_preserving_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _keys_loosely_match(a: str, b: str) -> bool:
    """Return True if `a` and `b` likely represent the same entity despite slight differences."""
    if not a or not b or a == b or len(a) < 4 or len(b) < 4:
        return False
    tokens_a = [t for t in re.split(r"[-\s]+", a) if t]
    tokens_b = [t for t in re.split(r"[-\s]+", b) if t]
    shorter, longer = (
        (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    )
    if not shorter:
        return False
    window = len(shorter)
    return any(longer[i : i + window] == shorter for i in range(len(longer) - window + 1))


def _derive_headline(
    experiences: List[Dict[str, Any]],
    summary: str,
    skills: Dict[str, List[str]],
) -> str:
    """Dérive un titre professionnel cohérent à partir du résumé ou du rôle le plus récent."""
    if summary:
        first_sentence = summary.split(".")[0].strip()
        match = re.match(
            r"^([A-ZÀ-ÖØ-öø-ÿ][a-zA-ZÀ-ÖØ-öø-ÿ0-9\s&/,\-\+]+?)"
            r"(?:\s+(?:expérimenté[e]?|senior|confirmé[e]?|avec|spécialisé[e]?|passionné[e]?|dans|ayant|\.|\,)|$)",
            first_sentence,
            re.IGNORECASE,
        )
        if match:
            candidate = match.group(1).strip()
            if 3 <= len(candidate) <= 60 and not candidate.lower().startswith(
                ("je ", "mon ", "le ", "un ")
            ):
                return re.sub(r"\s+et\s+", " & ", candidate, flags=re.IGNORECASE)

    if experiences:
        top_role = (experiences[0].get("role") or "").strip()
        if top_role:
            return top_role
    return ""


def _first_non_empty(
    field: str, contributions: List[Tuple[str, Dict[str, Any]]]
) -> Tuple[str | None, Any]:
    """Retourne (source, valeur) du premier champ renseigné dans l'ordre de priorité."""
    for source, payload in contributions:
        value = payload.get(field)
        if value:
            return source, value
    return None, None


def _excluded_keys_from(
    sources: Dict[str, Dict[str, Any]], order: List[str], field: str
) -> set[str]:
    """Clés normalisées exclues (`_normalize_key`), pour les champs à un seul critère."""
    excluded: set[str] = set()
    for source in order:
        for exc in sources[source].get(field) or []:
            if isinstance(exc, str) and exc:
                excluded.add(_normalize_key(exc))
    return excluded


def _normalize_tokens(text: str) -> set[str]:
    stopwords = {
        "de", "des", "du", "et", "en", "d", "l", "la", "le", "les", "a", "au", "aux",
        "pour", "and", "of", "the", "in", "at", "sur", "sous", "par", "with",
    }
    tokens = set(re.split(r"[^a-z0-9]+", (text or "").lower()))
    return {t for t in tokens if len(t) > 1 and t not in stopwords}
