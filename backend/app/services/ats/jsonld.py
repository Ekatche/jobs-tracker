"""Schema.org JSON-LD JobPosting universal HTML parser."""

import json
import re
from typing import Any, Dict, List, Optional

from app.services.ats.common import clean_html_to_text, normalize_employment_type


def _extract_jsonld_items(data: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        if data.get("@type") == "JobPosting":
            items.append(data)
        elif "@graph" in data and isinstance(data["@graph"], list):
            items.extend(
                elem for elem in data["@graph"] if isinstance(elem, dict) and elem.get("@type") == "JobPosting"
            )
    elif isinstance(data, list):
        items.extend(
            elem for elem in data if isinstance(elem, dict) and elem.get("@type") == "JobPosting"
        )
    return items


def _extract_jsonld_location(item: Dict[str, Any]) -> str:
    location = "Non spécifié"
    job_loc = item.get("jobLocation")
    if isinstance(job_loc, dict):
        addr = job_loc.get("address")
        if isinstance(addr, dict):
            location = addr.get("addressLocality") or addr.get("addressRegion") or "Non spécifié"
        elif isinstance(addr, str):
            location = addr
        elif job_loc.get("addressLocality"):
            location = job_loc.get("addressLocality")
    elif isinstance(job_loc, list) and job_loc:
        first = job_loc[0]
        if isinstance(first, dict):
            addr = first.get("address")
            if isinstance(addr, dict):
                location = addr.get("addressLocality") or "Non spécifié"

    if item.get("jobLocationType") == "TELECOMMUTE" or "telecommute" in str(item).lower():
        if location == "Non spécifié":
            return "Télétravail"
    return str(location).strip()


def parse_jsonld_job_posting(html_content: str, url: str) -> Optional[Dict[str, Any]]:
    """Parse universel des balises Schema.org `<script type="application/ld+json">` avec `@type: JobPosting`."""
    if not html_content or "JobPosting" not in html_content:
        return None

    scripts = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    for script_text in scripts:
        try:
            data = json.loads(script_text.strip())
        except Exception:
            continue

        for item in _extract_jsonld_items(data):
            title = item.get("title") or item.get("name")
            if not title:
                continue
            org = item.get("hiringOrganization")
            if isinstance(org, dict):
                company = org.get("name") or "Non spécifié"
            elif isinstance(org, str):
                company = org
            else:
                company = "Non spécifié"

            return {
                "poste": str(title).strip(),
                "entreprise": str(company).strip(),
                "description": clean_html_to_text(item.get("description", "")),
                "localisation": _extract_jsonld_location(item),
                "type_contrat": normalize_employment_type(item.get("employmentType")),
                "url": url,
                "ats_platform": "json_ld",
                "source_record": item,
            }

    return None
