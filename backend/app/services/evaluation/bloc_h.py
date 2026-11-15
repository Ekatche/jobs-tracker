"""Company application history note and deterministic Block H draft builder."""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from app.models import (
    BlocA,
    BlocB,
    BlocH,
    DraftApplicationAnswer,
)

_RESPONDED_APP_STATUSES = {
    "screening",
    "interview",
    "technical_test",
    "negotiation",
    "offer",
    "offer_received",
    "accepted",
    "première sélection",
    "entretien",
    "test technique",
    "négociation",
    "offre reçue",
    "offre acceptée",
}
_SILENT_APP_STATUSES = {
    "applied",
    "relance",
    "candidature envoyée",
    "relancé",
    "en étude",
}


async def _fetch_company_applications(
    db: Any,
    user_str_id: str,
    offer_company: str,
) -> Optional[List[Dict[str, Any]]]:
    """Query prior applications to the target company for a user."""
    try:
        apps_col = db["applications"]
        user_filter: List[Any] = [user_str_id]
        if ObjectId.is_valid(user_str_id):
            user_filter.append(ObjectId(user_str_id))
        cursor = apps_col.find(
            {
                "user_id": {"$in": user_filter},
                "company": {"$regex": f"^{re.escape(offer_company)}$", "$options": "i"},
            }
        )
        if asyncio.iscoroutine(cursor):
            cursor = await cursor
        if not hasattr(cursor, "to_list"):
            return None
        docs = await cursor.to_list(length=50)
        return docs if isinstance(docs, list) and docs else None
    except Exception:
        return None


def _count_application_outcomes(docs: List[Dict[str, Any]]) -> Tuple[int, int, Optional[int]]:
    """Count responded vs silent/rejected prior applications and recency of latest silence."""
    responded = 0
    silent = 0
    latest_silent_days: Optional[int] = None
    now = datetime.now(timezone.utc)

    for doc in docs:
        if not isinstance(doc, dict):
            continue
        status_norm = str(doc.get("status") or "").strip().lower()
        if status_norm in _RESPONDED_APP_STATUSES:
            responded += 1
        elif status_norm in _SILENT_APP_STATUSES or "refus" in status_norm or "reject" in status_norm:
            silent += 1
            app_dt = doc.get("application_date") or doc.get("created_at")
            if isinstance(app_dt, datetime):
                dt_utc = app_dt if app_dt.tzinfo else app_dt.replace(tzinfo=timezone.utc)
                days = max(0, (now - dt_utc).days)
                if latest_silent_days is None or days < latest_silent_days:
                    latest_silent_days = days

    return responded, silent, latest_silent_days


async def compute_company_history_note(
    db: Any,
    user_str_id: str,
    offer_company: str,
) -> Optional[str]:
    """Summarize prior applications to the same company without altering the score."""
    if not offer_company or db is None:
        return None
    docs = await _fetch_company_applications(db, user_str_id, offer_company)
    if not docs:
        return None

    responded, silent, latest_silent_days = _count_application_outcomes(docs)
    if silent > 0 and responded == 0:
        days_txt = f" (dernière il y a {latest_silent_days}j)" if latest_silent_days is not None else ""
        return (
            f"Historique avec {offer_company} : {silent} candidature(s) sans retour positif{days_txt}. "
            "À prendre en compte pour calibrer l'effort investi (sans impact sur le score)."
        )
    if silent > 0 and responded > 0:
        return (
            f"Historique mixte avec {offer_company} : {responded} retour(s) positif(s) et "
            f"{silent} candidature(s) sans réponse."
        )
    return None


def _collect_key_achievements(profile_doc: Dict[str, Any], bloc_b: BlocB) -> List[str]:
    """Pick up to 4 grounded candidate achievements from matches or profile experiences."""
    achievements: List[str] = []
    for match in bloc_b.matched_requirements:
        ev = (match.candidate_evidence or "").strip()
        if ev and ev not in achievements:
            achievements.append(f"{match.requirement} : {ev}")
        if len(achievements) >= 4:
            return achievements

    for exp in profile_doc.get("experiences", []) or []:
        if not isinstance(exp, dict):
            continue
        for bullet in (exp.get("achievements") or exp.get("missions") or []):
            text = str(bullet).strip()
            if text and text not in achievements:
                achievements.append(text)
            if len(achievements) >= 4:
                return achievements
    return achievements


def _collect_jd_keywords(offer_doc: Dict[str, Any], bloc_b: BlocB) -> List[str]:
    """Extract up to 15 unique keywords from offer skills and evaluated requirements."""
    keywords: List[str] = []
    for kw in (offer_doc.get("competences_cles") or []):
        s = str(kw).strip()
        if s and s not in keywords:
            keywords.append(s)
    for m in bloc_b.matched_requirements + bloc_b.missing_requirements:
        req = (m.requirement or "").strip()
        if req and req not in keywords and len(req) <= 60:
            keywords.append(req)
    return keywords[:15]


def _build_draft_answers(
    offer_doc: Dict[str, Any],
    profile_doc: Dict[str, Any],
    bloc_a: BlocA,
    bloc_b: BlocB,
    key_achievements: List[str],
) -> List[DraftApplicationAnswer]:
    """Build standard deterministic draft answers for high-fit applications."""
    company = (offer_doc.get("entreprise") or offer_doc.get("company") or "l'entreprise").strip()
    role = (offer_doc.get("poste") or offer_doc.get("title") or bloc_a.archetype or "ce poste").strip()
    summary_line = (bloc_a.summary or "").strip()
    top_proofs = "; ".join(key_achievements[:2]) if key_achievements else (profile_doc.get("headline") or "mon parcours")
    availability = (
        (profile_doc.get("personal_info") or {}).get("availability")
        or (profile_doc.get("contact") or {}).get("availability")
        or "selon préavis convenu"
    )
    location = (offer_doc.get("localisation") or "").strip()
    practical = f"Basé à proximité / disponible pour {location}" if location else "Disponible"

    return [
        DraftApplicationAnswer(
            question=f"Pourquoi ce rôle de {role} chez {company} ?",
            answer=(
                f"Votre besoin autour de {role}"
                + (f" ({summary_line})" if summary_line else "")
                + f" correspond directement à mes réalisations récentes, notamment : {top_proofs}."
            ),
        ),
        DraftApplicationAnswer(
            question="Pertinence du profil et réalisations clés",
            answer=(
                "Exigences clés couvertes : "
                + (", ".join(m.requirement for m in bloc_b.matched_requirements[:4]) or "profil aligné")
                + "."
            ),
        ),
        DraftApplicationAnswer(
            question="Disponibilité et adéquation pratique",
            answer=f"{practical} — disponibilité : {availability}.",
        ),
    ]


def build_bloc_h_draft(
    offer_doc: Dict[str, Any],
    profile_doc: Dict[str, Any],
    bloc_a: BlocA,
    bloc_b: BlocB,
    final_score: float,
) -> BlocH:
    """Build deterministic Block H draft application answers when score >= 4.0."""
    if final_score < 4.0:
        return BlocH(eligible=False)

    key_achievements = _collect_key_achievements(profile_doc, bloc_b)
    gaps_flagged: List[str] = [
        f"{m.requirement} ({m.weight})"
        for m in bloc_b.missing_requirements
        if m.weight in ("critical", "high")
    ]
    for pref in bloc_a.preference_mismatches:
        gaps_flagged.append(f"Préférence {pref.criterion} : offre={pref.offer_value} vs souhait={pref.expected}")
    if bloc_a.domain_coherence == "partial":
        gaps_flagged.append("Cohérence domaine partielle : mettre en avant les réalisations transférables.")

    return BlocH(
        eligible=True,
        answers=_build_draft_answers(offer_doc, profile_doc, bloc_a, bloc_b, key_achievements),
        key_achievements=key_achievements[:4],
        gaps_flagged=gaps_flagged,
        jd_keywords=_collect_jd_keywords(offer_doc, bloc_b),
    )
