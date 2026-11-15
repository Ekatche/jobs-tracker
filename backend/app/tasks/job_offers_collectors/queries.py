"""Dynamic search query generation from candidate profiles with round-robin fairness."""

import asyncio
from datetime import datetime, timezone
import os
import sys
from typing import Any

from app.services.normalization import clean_job_title_syntax
from app.tasks.job_offers_collectors.config import (
    DEFAULT_QUERIES,
    MAX_QUERIES_PER_PROFILE,
    MAX_TOTAL_QUERIES,
)


def _pkg() -> Any:
    return sys.modules["app.tasks.job_offers_collectors"]


async def _normalize_profile_roles(
    raw_roles: list[str], memo: dict[str, str], db: Any
) -> list[str]:
    from app.services.role_normalizer import normalize_role

    target_roles: list[str] = []
    seen_roles: set[str] = set()
    for raw in raw_roles:
        cleaned = clean_job_title_syntax(raw)
        if not cleaned or cleaned == "Non spécifié":
            cleaned = raw
        key = cleaned.lower()
        if key in memo:
            norm_role = memo[key]
        else:
            norm_role = await normalize_role(cleaned, db=db)
            memo[key] = norm_role

        norm_key = norm_role.lower()
        if norm_key not in seen_roles:
            seen_roles.add(norm_key)
            target_roles.append(norm_role)
    return target_roles


def _build_profile_query_strings(
    target_roles: list[str],
    locations: list[str],
    is_full_remote: bool,
    contract_types: list[str],
) -> list[str]:
    candidate_queries: list[str] = []
    for contract in contract_types or [None]:
        suffix = f" ({contract})" if contract else ""
        if target_roles:
            for role in target_roles:
                if locations:
                    candidate_queries.extend(f"Je recherche un poste de {role} proche de {loc}{suffix}" for loc in locations)
                elif is_full_remote:
                    candidate_queries.append(f"Je recherche un poste de {role} en télétravail{suffix}")
                else:
                    candidate_queries.append(f"Je recherche un poste de {role}{suffix}")
        elif locations:
            candidate_queries.extend(f"Je recherche un poste proche de {loc}{suffix}" for loc in locations)
        elif is_full_remote:
            candidate_queries.append(f"Je recherche un poste en télétravail{suffix}")
    return candidate_queries


def _round_robin_queries(profiles_queries_list: list[list[str]], rotation_day: int) -> list[str]:
    profile_offset = rotation_day % len(profiles_queries_list)
    rotated_profiles = profiles_queries_list[profile_offset:] + profiles_queries_list[:profile_offset]
    selected_queries: list[str] = []
    seen_keys: set[str] = set()
    round_idx = 0

    while len(selected_queries) < MAX_TOTAL_QUERIES:
        added_in_round = False
        for p_queries in rotated_profiles:
            if round_idx < len(p_queries):
                query = p_queries[round_idx].strip()
                dedup_key = query.lower()
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    selected_queries.append(query)
                    if len(selected_queries) >= MAX_TOTAL_QUERIES:
                        break
                added_in_round = True
        if not added_in_round:
            break
        round_idx += 1
    return selected_queries


async def build_search_queries(rotation_day: int | None = None) -> list[str]:
    """Génère dynamiquement les requêtes de recherche depuis les préférences des candidats."""
    pkg = _pkg()
    try:
        db = await pkg.get_database()
        cursor = db["candidate_profile"].find({
            "$or": [
                {"preferences.search_active": True},
                {"preferences.search_active": {"$exists": False}},
            ]
        })
        profiles = await cursor.to_list(length=100)

        memo_normalized: dict[str, str] = {}
        profiles_queries_list: list[list[str]] = []
        rotation_day = datetime.now(timezone.utc).date().toordinal() if rotation_day is None else rotation_day

        for profile in profiles:
            prefs = profile.get("preferences") or {}
            if prefs.get("search_active") is False:
                continue
            raw_roles = [r.strip() for r in (prefs.get("target_roles") or []) if isinstance(r, str) and r.strip()]
            target_roles = await _normalize_profile_roles(raw_roles, memo_normalized, db)
            locations = [loc.strip() for loc in (prefs.get("locations") or []) if isinstance(loc, str) and loc.strip()]
            is_full_remote = str(prefs.get("remote_policy")).lower() in ("full_remote", "remotepolicy.full_remote")
            candidate_queries = _build_profile_query_strings(
                target_roles, locations, is_full_remote, prefs.get("contract_types") or []
            )
            if candidate_queries:
                offset = (rotation_day * MAX_QUERIES_PER_PROFILE) % len(candidate_queries)
                rotated = candidate_queries[offset:] + candidate_queries[:offset]
                profiles_queries_list.append(rotated[:MAX_QUERIES_PER_PROFILE])

        if not profiles_queries_list:
            pkg.logger.info("ℹ️ Aucun profil candidat avec rôles cibles trouvé, utilisation de DEFAULT_QUERIES")
            return list(DEFAULT_QUERIES)

        selected_queries = _round_robin_queries(profiles_queries_list, rotation_day)
        if not selected_queries:
            return list(DEFAULT_QUERIES)

        pkg.logger.info(f"✅ {len(selected_queries)} requêtes de recherche dynamiques générées: {selected_queries}")
        return selected_queries
    except Exception as e:
        pkg.logger.warning(
            f"⚠️ Erreur lors de la génération dynamique des requêtes: {e}, utilisation du fallback DEFAULT_QUERIES"
        )
        return list(DEFAULT_QUERIES)


def build_search_queries_sync() -> list[str]:
    """Version synchrone pour Airflow avec boucle d'événements dédiée et résilience."""
    pkg = _pkg()
    os.environ.setdefault("ENVIRONMENT", "airflow")
    try:
        return asyncio.run(pkg.build_search_queries())
    except Exception as e:
        pkg.logger.warning(
            f"⚠️ Erreur execution sync build_search_queries: {e}, utilisation du fallback DEFAULT_QUERIES"
        )
        return list(DEFAULT_QUERIES)
