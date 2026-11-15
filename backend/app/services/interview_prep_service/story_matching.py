"""STAR+R bank requirement selection and AI matching."""

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from app.models import BankStory, StorySlot
from app.services.interview_prep_service.context import _offer_role_and_company
from app.services.interview_prep_service.llm_client import call_interview_llm
from app.services.star_bank_rules import (
    _mask_invented_numbers,
    _story_facts_sources,
    experience_label,
)

WEIGHT_RANK = {"critical": 0, "high": 1, "meaningful": 2}
MAX_STORY_SLOTS = 5
BANK_SUMMARY_LIMIT = 60


class RequirementPick(BaseModel):
    requirement: str
    weight: str = "high"
    covered: Optional[bool] = None


def select_requirements(
    evaluation: Optional[Dict[str, Any]], limit: int = MAX_STORY_SLOTS
) -> List[RequirementPick]:
    """Agrège `bloc_b.matched_requirements` puis `missing_requirements`, triés par poids (stable, inconnu en dernier)."""
    if not evaluation:
        return []
    bloc_b = evaluation.get("bloc_b") or {}
    picks: List[RequirementPick] = []
    for items, covered in (
        (bloc_b.get("matched_requirements") or [], True),
        (bloc_b.get("missing_requirements") or [], False),
    ):
        for entry in items:
            requirement = (entry.get("requirement") or "").strip()
            if not requirement:
                continue
            picks.append(
                RequirementPick(requirement=requirement, weight=entry.get("weight", "high"), covered=covered)
            )
    picks.sort(key=lambda p: WEIGHT_RANK.get(p.weight, len(WEIGHT_RANK)))
    return picks[:limit]


def format_requirements_block(picks: Optional[List[RequirementPick]]) -> str:
    """Numérote les exigences choisies ; sans sélection, demande à l'IA d'en extraire au plus 5 de la description."""
    if picks is None:
        return "Extrais toi-même au plus 5 exigences clés de la description de poste ci-dessus."
    return "\n".join(f"{i}. {pick.requirement}" for i, pick in enumerate(picks, 1))


def format_bank_summary(bank: List[BankStory], limit: int = BANK_SUMMARY_LIMIT) -> str:
    """Une ligne par histoire de la banque : id, titre, expérience, résultat tronqué, tags."""
    lines = []
    for story in bank[:limit]:
        label = experience_label(story.experience) if story.experience else "sans expérience"
        lines.append(
            f"[{story.id}] {story.title} | {label} | {story.result[:160]} | {', '.join(story.key_tags)}"
        )
    return "\n".join(lines)


def _resolve_match_fit(covered: Optional[bool], ai_fit: Any) -> str:
    if covered is False:
        return "transferable"
    if ai_fit in ("strong", "partial"):
        return ai_fit
    if ai_fit == "transferable" and covered is None:
        return "transferable"
    return "partial"


def _build_matched_slot(
    pick: RequirementPick, match: Dict[str, Any], bank_by_id: Dict[str, BankStory]
) -> Optional[StorySlot]:
    story_id = match.get("story_id")
    story = bank_by_id.get(story_id) if story_id else None
    if story is None:
        return None
    angle = _mask_invented_numbers(str(match.get("angle", "")), _story_facts_sources(story))
    return StorySlot(
        requirement=pick.requirement,
        story_id=story.id,
        fit=_resolve_match_fit(pick.covered, match.get("fit")),
        angle=angle,
    )


async def match_bank_stories(
    db: Any,
    user_id: str,
    offer: Dict[str, Any],
    picks: Optional[List[RequirementPick]],
    bank: List[BankStory],
) -> List[Tuple[RequirementPick, Optional[StorySlot]]]:
    """Associe par IA les exigences sélectionnées (ou extraites par l'IA) aux histoires de la banque."""
    role, company = _offer_role_and_company(offer)
    parsed = await call_interview_llm(
        db=db,
        user_id=user_id,
        offer=offer,
        template_name="story_match.md",
        sub_action="story_match",
        format_vars={
            "target_company": company,
            "target_role": role,
            "offer_description": offer.get("description", "")[:4000],
            "requirements_block": format_requirements_block(picks),
            "bank_summary": format_bank_summary(bank),
        },
    )
    if not isinstance(parsed, dict) or not isinstance(parsed.get("matches"), list):
        raise ValueError("Expected a JSON object with a 'matches' list")
    matches = parsed["matches"]
    bank_by_id = {story.id: story for story in bank}

    if picks is not None:
        match_by_index: Dict[int, Dict[str, Any]] = {}
        for item in matches:
            idx = item.get("requirement_index")
            if isinstance(idx, int) and not isinstance(idx, bool) and 1 <= idx <= len(picks):
                match_by_index.setdefault(idx, item)
        return [
            (pick, _build_matched_slot(pick, match_by_index[i], bank_by_id) if i in match_by_index else None)
            for i, pick in enumerate(picks, 1)
        ]

    # Sans sélection préalable : les exigences viennent des `requirement` renvoyés par l'IA, 5 au plus.
    pairs: List[Tuple[RequirementPick, Optional[StorySlot]]] = []
    for item in matches:
        if len(pairs) >= MAX_STORY_SLOTS:
            break
        requirement = (item.get("requirement") or "").strip()
        if not requirement:
            continue
        pick = RequirementPick(requirement=requirement, covered=None)
        pairs.append((pick, _build_matched_slot(pick, item, bank_by_id)))
    return pairs
