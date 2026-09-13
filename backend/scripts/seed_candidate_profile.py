import json
import os
import pathlib
from typing import Dict, Any, List, Tuple

def merge_profile_sources(cv_data: Dict[str, Any], site_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    conflicts: List[Dict[str, Any]] = []
    merged_experiences: List[Dict[str, Any]] = []
    provenance: List[Dict[str, str]] = []

    cv_exps = cv_data.get("experiences", [])
    site_exps = site_data.get("experiences", [])

    site_exp_map = {
        (e["company"].lower().strip(), str(e.get("start", "")), str(e.get("end", ""))): e
        for e in site_exps
    }

    for cv_e in cv_exps:
        key = (cv_e["company"].lower().strip(), str(cv_e.get("start", "")), str(cv_e.get("end", "")))
        if key in site_exp_map:
            site_e = site_exp_map.pop(key)
            # Comparer les stacks et missions pour déceler les conflits
            cv_stack = set(cv_e.get("stack", []))
            site_stack = set(site_e.get("stack", []))
            if cv_stack != site_stack:
                conflicts.append({
                    "company": cv_e["company"],
                    "field": "stack",
                    "cv_stack": list(cv_stack),
                    "site_stack": list(site_stack),
                })
            # Fusion union
            unified_exp = dict(cv_e)
            unified_exp["stack"] = list(cv_stack.union(site_stack))
            unified_exp["missions"] = list(set(cv_e.get("missions", []) + site_e.get("missions", [])))
            merged_experiences.append(unified_exp)
            provenance.append({"field_path": f"experiences.{cv_e['company']}", "source": "cv+site"})
        else:
            merged_experiences.append(cv_e)
            provenance.append({"field_path": f"experiences.{cv_e['company']}", "source": "cv"})

    # Expériences restantes du site (absentes du CV)
    for site_e in site_exp_map.values():
        merged_experiences.append(site_e)
        provenance.append({"field_path": f"experiences.{site_e['company']}", "source": "site"})

    merged_profile = {
        "headline": cv_data.get("headline") or site_data.get("headline", ""),
        "summary": cv_data.get("summary") or site_data.get("summary", ""),
        "experiences": merged_experiences,
        "projects": site_data.get("projects", cv_data.get("projects", [])),
        "education": cv_data.get("education", site_data.get("education", [])),
        "certifications": site_data.get("certifications", cv_data.get("certifications", [])),
        "languages": cv_data.get("languages", site_data.get("languages", [])),
        "skills": site_data.get("skills", cv_data.get("skills", {})),
        "provenance": provenance,
    }

    return merged_profile, conflicts

if __name__ == "__main__":
    print("Script d'amorçage de profil prêt.")
