import json
import re
import unicodedata
from typing import Any, Dict, List, Optional

from .constants import CV_OUTPUT_KEYS, CVResponseError

_EMPTINESS_FIELDS = (
    "experiences", "projects", "education", "certifications", "languages", "skills",
)
_LIST_SECTIONS = ("experiences", "projects", "education", "certifications", "languages", "interests")
_IDENTITY_FIELDS = {
    "experiences": ("company", "role", "start"),
    "projects": ("name",),
    "education": ("school", "degree"),
    "certifications": ("name",),
}


def _flatten_contact_value(v: Any) -> Optional[str]:
    """Flattens nested dict or list into a clean ' · '-separated string."""
    if v is None:
        return None
    if isinstance(v, str):
        cleaned = v.strip()
        return cleaned if cleaned else None
    if isinstance(v, (list, tuple, set)):
        valid = [p for item in v if (p := _flatten_contact_value(item))]
        return " · ".join(valid) if valid else None
    if isinstance(v, dict):
        parts = []
        for key, val in v.items():
            flattened = _flatten_contact_value(val)
            if not flattened:
                continue
            key_text = str(key).casefold()
            if ("permis" in key_text or "licen" in key_text) and "permis" not in flattened.casefold():
                flattened = f"Permis {flattened}"
            parts.append(flattened)
        return " · ".join(parts) if parts else None
    s = str(v).strip()
    return s if s else None


def _clean_list_field(raw: Any) -> List[str]:
    if isinstance(raw, list):
        return [str(i).strip() for i in raw if str(i).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _clean_parsed_cv(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data

    raw_contact = data.get("contact")
    if isinstance(raw_contact, dict):
        data["contact"] = {
            k: flat
            for k, v in raw_contact.items()
            if (flat := _flatten_contact_value(v))
        }
    elif "contact" in data:
        data.pop("contact")

    data["interests"] = _clean_list_field(data.get("interests"))
    data["languages"] = _clean_list_field(data.get("languages"))

    raw_skills = data.get("skills")
    if isinstance(raw_skills, list):
        raw_skills = {"general": raw_skills}
    if isinstance(raw_skills, dict):
        data["skills"] = {
            category: items
            for category, items in raw_skills.items()
            if isinstance(items, list) and any(str(i).strip() for i in items)
        }
    else:
        data.pop("skills", None)

    for key in [k for k in data if k not in CV_OUTPUT_KEYS]:
        del data[key]
    return data


def _read_json_response(response: Any, model: str) -> tuple:
    """Décode la réponse JSON d'un modèle et renvoie (données, usage facturé)."""
    usage_obj = getattr(response, "usage", None)
    usage = {
        "model": model,
        "input_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
    }
    try:
        raw_content = response.choices[0].message.content.strip()
        clean_json = re.sub(r"^```(?:json)?|```$", "", raw_content, flags=re.MULTILINE).strip()
        data = json.loads(clean_json)
    except (ValueError, AttributeError, IndexError, TypeError) as exc:
        raise CVResponseError(f"Réponse du modèle {model} non exploitable : {exc}", [usage]) from exc
    if not isinstance(data, dict):
        raise CVResponseError(f"Réponse du modèle {model} : objet JSON attendu", [usage])
    return data, usage


def _is_filled(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_is_filled(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_is_filled(v) for v in value)
    return bool(value)


def is_empty_extraction(payload: Any) -> bool:
    """Vrai si aucun fait n'a été extrait (un CV de formations seules reste exploitable)."""
    if not isinstance(payload, dict):
        return True
    return not any(_is_filled(payload.get(field)) for field in _EMPTINESS_FIELDS)


def _has_usable_content(data: Any) -> bool:
    return not is_empty_extraction(data)


def _start_year(value: Any) -> str:
    match = re.search(r"\d{4}", str(value or ""))
    return match.group(0) if match else ""


def _item_key(section: str, item: Any) -> str:
    if isinstance(item, dict):
        fields = _IDENTITY_FIELDS.get(section) or tuple(sorted(item))
        values = [
            _start_year(item.get(f))
            if (section, f) == ("experiences", "start")
            else str(item.get(f) or "").strip().casefold()
            for f in fields
        ]
        return "|".join(values)
    return str(item).strip().casefold()


def _merge_cv_complement(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Complète `base` avec `extra` sans jamais écraser une valeur déjà présente."""
    for section in _LIST_SECTIONS:
        current = list(base.get(section) or [])
        seen = {_item_key(section, item) for item in current}
        for item in extra.get(section) or []:
            key = _item_key(section, item)
            if key not in seen:
                seen.add(key)
                current.append(item)
        if current:
            base[section] = current

    skills = {cat: list(items) for cat, items in (base.get("skills") or {}).items()}
    for category, items in (extra.get("skills") or {}).items():
        merged = skills.setdefault(category, [])
        known = {str(i).strip().casefold() for i in merged}
        for item in items:
            if str(item).strip().casefold() not in known:
                known.add(str(item).strip().casefold())
                merged.append(item)
    if skills:
        base["skills"] = skills

    contact = dict(base.get("contact") or {})
    for key, value in (extra.get("contact") or {}).items():
        if not contact.get(key):
            contact[key] = value
    if contact:
        base["contact"] = contact

    for key, value in extra.items():
        if key not in _LIST_SECTIONS and key not in ("skills", "contact", "_usage"):
            if not base.get(key) and value:
                base[key] = value
    return base


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.casefold().split())


def _find_excerpt(page_text: str, needle: str) -> Optional[str]:
    if len(needle) < 3:
        return None
    pattern = re.compile(rf"(?<!\w){re.escape(needle)}(?!\w)")
    if not pattern.search(_normalize(page_text)):
        return None
    for line in page_text.splitlines():
        if pattern.search(_normalize(line)):
            return line.strip()[:160]
    return None


def _locate_evidence(payload: Dict[str, Any], page_texts: List[str]) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    wanted = (("experiences", ("company",)), ("education", ("degree", "school")))
    for section, fields in wanted:
        for index, item in enumerate(payload.get(section) or []):
            if not isinstance(item, dict):
                continue
            value = next((item.get(f) for f in fields if _normalize(item.get(f))), None)
            needle = _normalize(value)
            if not needle:
                continue
            for page, text in enumerate(page_texts, start=1):
                excerpt = _find_excerpt(text, needle)
                if excerpt is not None:
                    evidence.append({"section": section, "index": index, "page": page, "excerpt": excerpt})
                    break
    return evidence


def _build_import_report(
    total_pages: int,
    vlm_pages: List[int],
    text_pages: List[int],
    fallback_used: bool,
    errors: List[str],
    evidence: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    covered = set(vlm_pages) | set(text_pages)
    return {
        "total_pages": total_pages,
        "pages_by_method": {"vlm": sorted(vlm_pages), "text": sorted(text_pages)},
        "skipped_pages": [n for n in range(1, total_pages + 1) if n not in covered],
        "fallback_used": fallback_used,
        "errors": errors,
        "evidence": evidence or [],
    }


def _pages_with_text(page_texts: List[str], first_page: int = 1) -> List[int]:
    return [n for n, text in enumerate(page_texts, start=1) if n >= first_page and text.strip()]
