import re
from typing import Any, Dict, List

from app.services.cv_guards import (
    _AMBIGUOUS_TERMS,
    _ClaimContext,
    _clean_str,
    _collect_strings,
    _extract_metrics,
    _short_term_in,
    _stack_terms,
)
from app.services.profile.periods import company_slug as _normalize_entity

from .rules import _ENTITY_PATTERN, _SENTENCE_START_STOPWORDS


def _project_text(project: Dict[str, Any]) -> str:
    """Faits d'un projet transmis à l'analyste : nom, description, points forts."""
    parts = [
        project.get("name", ""),
        project.get("description", ""),
        *(project.get("highlights") or []),
    ]
    return " ".join(part for part in parts if part)


def _education_text(education: Dict[str, Any]) -> str:
    """Faits d'une formation ou certification : école, diplôme, organisme, sujets."""
    parts = [
        education.get("school", ""),
        education.get("degree", ""),
        education.get("name", ""),
        education.get("issuer", ""),
        *(education.get("topics") or []),
    ]
    return " ".join(part for part in parts if part)


def _allowed_entities(analyst_data: Dict[str, Any]) -> set[str]:
    allowed = {
        _normalize_entity(value)
        for value in (
            list(analyst_data.get("companies") or [])
            + list(analyst_data.get("stacks") or [])
            + list(analyst_data.get("projects") or [])
            + list(analyst_data.get("offer_terms") or [])
            + [analyst_data.get("job_title") or ""]
            + [analyst_data.get("company_name") or ""]
            + [analyst_data.get("candidate_name") or ""]
            + [analyst_data.get("candidate_headline") or ""]
        )
        if value
    }
    allowed |= {
        _normalize_entity(re.sub(r"[(),|]", " ", _project_text(project)))
        for project in analyst_data.get("selected_projects") or []
    }
    allowed |= {
        _normalize_entity(re.sub(r"[(),|]", " ", _education_text(education)))
        for education in analyst_data.get("selected_education") or []
    }
    return {entity for entity in allowed if entity}


def _check_entities(
    letter_text: str, offer_description: str, analyst_data: Dict[str, Any]
) -> List[str]:
    """Toute entité nommée doit venir des faits fournis à l'analyste."""
    allowed = _allowed_entities(analyst_data)
    violations: List[str] = []
    seen: set = set()
    for paragraph in re.split(r"\n\s*\n", letter_text):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip()):
            sentence = sentence.strip()
            if not sentence:
                continue
            for match in _ENTITY_PATTERN.finditer(sentence):
                words = match.group(0).split()
                while words and words[0] in _SENTENCE_START_STOPWORDS:
                    words.pop(0)
                if not words:
                    continue
                candidate = " ".join(words)
                normalized = _normalize_entity(candidate)
                if not normalized:
                    continue
                candidate_tokens = set(normalized.split())
                if candidate_tokens and any(
                    candidate_tokens <= set(entity.split()) for entity in allowed
                ):
                    continue
                if candidate not in seen:
                    seen.add(candidate)
                    violations.append(
                        f"Entité non autorisée citée dans la lettre : '{candidate}'"
                    )
    return violations


def _whole_word_in(needle: str, haystack: str) -> bool:
    return bool(needle) and re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack) is not None


def _attribution_sources(analyst_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Postes et projets du candidat, regroupés par nom en excluant le destinataire."""
    target = (analyst_data.get("company_name") or "").strip().casefold()
    groups: Dict[str, List[Any]] = {}
    for items, key, is_project in (
        (analyst_data.get("selected_experiences") or [], "company", False),
        (analyst_data.get("selected_projects") or [], "name", True),
    ):
        for item in items:
            name = str(item.get(key) or "").strip() if isinstance(item, dict) else ""
            folded = name.casefold()
            if not name or (
                target and (_whole_word_in(folded, target) or _whole_word_in(target, folded))
            ):
                continue
            group = groups.setdefault(folded, [name, [], is_project])
            group[1].append(item)
            group[2] = group[2] and is_project

    known_tech = {_clean_str(str(t)) for t in analyst_data.get("stacks") or []}
    for _, items, _ in groups.values():
        for item in items:
            known_tech.update(_stack_terms(item))

    sources: Dict[str, Dict[str, Any]] = {}
    for label, items, is_project in groups.values():
        sources[label] = {
            "project": is_project,
            "citable": not (
                is_project
                and (_clean_str(label) in known_tech or re.fullmatch(r"[a-zà-ÿ]+", label))
            ),
            "context": _ClaimContext.from_strings(
                [s for item in items for s in _collect_strings(item)],
                tuple(
                    s
                    for item in items
                    for k in ("stack", "technologies")
                    for s in _collect_strings(item.get(k))
                ),
            ),
            "terms": {t: raw for item in items for t, raw in _stack_terms(item).items()},
        }
    return sources


def _check_sentence_attribution(
    sentence: str,
    sources: Dict[str, Dict[str, Any]],
    target: str,
    offer_clean: str,
    seen: set,
) -> List[str]:
    named = [
        name
        for name, data in sources.items()
        if re.search(
            r"(?<!\w)" + re.escape(name) + r"(?!\w)",
            sentence,
            0 if data["project"] else re.IGNORECASE,
        )
        or (
            data["project"]
            and len(name) >= 5
            and re.search(r"(?<!\w)" + re.escape(name.upper()) + r"(?!\w)", sentence)
        )
    ]
    cited = [name for name in named if sources[name]["citable"]]
    if len(cited) != 1:
        return []

    muted = {n for n in named if not sources[n]["citable"]}
    transfer = bool(target) and bool(
        re.search(r"(?<!\w)" + re.escape(target) + r"(?!\w)", sentence, re.IGNORECASE)
    )
    name, own = cited[0], sources[cited[0]]["context"]
    others = [(other, data) for other, data in sources.items() if other != name]

    found: List[tuple] = []
    for metric in _extract_metrics(sentence):
        if own.has_metric(metric) or any(sources[m]["context"].has_canon(metric) for m in muted):
            continue
        origin = next((other for other, data in others if data["context"].has_canon(metric)), None)
        if origin:
            found.append((metric.raw, origin))

    clean_sentence = _clean_str(sentence)
    for other, data in others:
        for term, raw in data["terms"].items():
            if term in _AMBIGUOUS_TERMS or any(sources[m]["context"].supports(raw) for m in muted):
                continue
            pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
            if transfer and re.search(pattern, offer_clean):
                continue
            hit = (
                not own.supports(raw) and _short_term_in(raw, sentence)
                if len(term) <= 3
                else not own.supports(raw) and bool(re.search(pattern, clean_sentence))
            )
            if hit:
                found.append((raw, other))

    violations: List[str] = []
    for element, origin in found:
        if origin not in muted and (element, name, origin) not in seen:
            seen.add((element, name, origin))
            violations.append(
                f"Attribution erronée : « {element} » rattaché à {name} mais issu de {origin}"
            )
    return violations


def _check_attribution(
    letter_text: str, analyst_data: Dict[str, Any], offer_description: str = ""
) -> List[str]:
    """Une phrase qui cite exactement une source ne lui attribue rien qui vienne d'une autre."""
    sources = _attribution_sources(analyst_data)
    if len(sources) < 2:
        return []
    target = (analyst_data.get("company_name") or "").strip()
    offer_clean = _clean_str(offer_description or "")
    violations: List[str] = []
    seen: set = set()
    for sentence in re.split(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÖØ-Þ«\"“])|\n+", letter_text):
        violations.extend(
            _check_sentence_attribution(sentence, sources, target, offer_clean, seen)
        )
    return violations
