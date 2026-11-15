"""STAR+R story gap writing, manual angle carry-over, and slot assembly."""

from typing import Any, Dict, List, Optional, Tuple

from app.models import BankStory, StoryExperience, StoryOrigin, StorySlot
from app.services.interview_prep_service.context import (
    _offer_role_and_company,
    format_candidate_profile_context,
    format_evaluation_context,
)
from app.services.interview_prep_service.llm_client import call_interview_llm
from app.services.interview_prep_service.story_matching import (
    MAX_STORY_SLOTS,
    RequirementPick,
    format_requirements_block,
    match_bank_stories,
    select_requirements,
)
from app.services.star_bank_rules import (
    _mask_invented_numbers,
    _story_facts_sources,
    match_profile_experience,
)

_REQUIRED_STORY_FACTS = ("title", "situation", "task", "action", "result")


def _has_required_story_facts(raw_story: Any) -> bool:
    return isinstance(raw_story, dict) and all(raw_story.get(field) for field in _REQUIRED_STORY_FACTS)


def _resolve_story_experience(
    raw_experience: Any, profile_experiences: List[Dict[str, Any]]
) -> Optional[StoryExperience]:
    if not isinstance(raw_experience, dict) or not raw_experience.get("company"):
        return None
    candidate = StoryExperience(company=raw_experience["company"], role=raw_experience.get("role"))
    idx = match_profile_experience(candidate, profile_experiences)
    if idx is None:
        return None
    exp = profile_experiences[idx]
    return StoryExperience(company=exp["company"], role=exp.get("role"), start=exp.get("start"))


def _resolve_write_fit(covered: Optional[bool], ai_fit: Any) -> str:
    if covered is False:
        return "transferable"
    if ai_fit in ("strong", "partial"):
        return ai_fit
    return "strong"


def _no_story_fit(covered: Optional[bool]) -> str:
    return "gap" if covered is True else "no_experience"


def _build_written_result(
    pick: RequirementPick,
    item: Optional[Dict[str, Any]],
    offer: Dict[str, Any],
    profile_experiences: List[Dict[str, Any]],
    user_id: str,
) -> Tuple[StorySlot, Optional[BankStory]]:
    raw_story = item.get("story") if item else None
    if not _has_required_story_facts(raw_story):
        return StorySlot(requirement=pick.requirement, story_id=None, fit=_no_story_fit(pick.covered)), None

    story = BankStory(
        user_id=user_id,
        title=raw_story.get("title", ""),
        theme=raw_story.get("theme", "Général"),
        situation=raw_story.get("situation", ""),
        task=raw_story.get("task", ""),
        action=raw_story.get("action", ""),
        result=raw_story.get("result", ""),
        reflection=raw_story.get("reflection", ""),
        key_tags=raw_story.get("key_tags") or [],
        experience=_resolve_story_experience(item.get("experience"), profile_experiences),
        origin=StoryOrigin(kind="generated", offer_id=str(offer["_id"])),
    )
    angle = _mask_invented_numbers(str(item.get("angle", "")), _story_facts_sources(story))
    slot = StorySlot(
        requirement=pick.requirement,
        story_id=story.id,
        fit=_resolve_write_fit(pick.covered, item.get("fit")),
        angle=angle,
    )
    return slot, story


def _pair_written_items(
    items: List[Dict[str, Any]], picks: Optional[List[RequirementPick]]
) -> List[Tuple[RequirementPick, Optional[Dict[str, Any]]]]:
    if picks is not None:
        item_by_index: Dict[int, Dict[str, Any]] = {}
        for item in items:
            idx = item.get("requirement_index")
            if isinstance(idx, int) and not isinstance(idx, bool) and 1 <= idx <= len(picks):
                item_by_index.setdefault(idx, item)
        return [(pick, item_by_index.get(i)) for i, pick in enumerate(picks, 1)]

    # Sans sélection préalable : les exigences viennent des `requirement` renvoyés par l'IA, 5 au plus.
    pairs: List[Tuple[RequirementPick, Optional[Dict[str, Any]]]] = []
    for item in items:
        if len(pairs) >= MAX_STORY_SLOTS:
            break
        requirement = (item.get("requirement") or "").strip()
        if not requirement:
            continue
        pairs.append((RequirementPick(requirement=requirement, covered=None), item))
    return pairs


async def write_stories_for_requirements(
    db: Any,
    user_id: str,
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]],
    picks: Optional[List[RequirementPick]],
) -> List[Tuple[StorySlot, Optional[BankStory]]]:
    """Écrit par IA une histoire pour chaque exigence sans couverture dans la banque (`sub_action="stories"`).

    Même longueur et même ordre que `picks` ; sans `picks`, les exigences sont extraites des
    `requirement` renvoyés par l'IA (5 au plus).
    """
    role, company = _offer_role_and_company(offer)
    parsed = await call_interview_llm(
        db=db,
        user_id=user_id,
        offer=offer,
        template_name="star_stories.md",
        sub_action="stories",
        format_vars={
            "candidate_profile": format_candidate_profile_context(profile),
            "target_company": company,
            "target_role": role,
            "offer_description": offer.get("description", "")[:4000],
            "evaluation_context": format_evaluation_context(evaluation),
            "requirements_block": format_requirements_block(picks),
        },
    )
    if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list):
        raise ValueError("Expected a JSON object with an 'items' list")

    profile_experiences = profile.get("experiences") or []
    pairs = _pair_written_items(parsed["items"], picks)
    return [_build_written_result(pick, item, offer, profile_experiences, user_id) for pick, item in pairs]


def carry_over_edited_angles(previous: List[StorySlot], new: List[StorySlot]) -> List[StorySlot]:
    """Reprend `angle`/`angle_edited=True` d'une ligne précédente éditée à la main.

    Condition : même exigence (comparaison `casefold`) et même `story_id` non nul.
    """
    previous_edited = {
        (slot.requirement.casefold(), slot.story_id): slot
        for slot in previous
        if slot.angle_edited and slot.story_id is not None
    }
    result = []
    for slot in new:
        old = previous_edited.get((slot.requirement.casefold(), slot.story_id)) if slot.story_id else None
        if old is not None:
            slot = slot.model_copy(update={"angle": old.angle, "angle_edited": True})
        result.append(slot)
    return result


async def build_story_slots(
    db: Any,
    user_id: str,
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]],
    bank: List[BankStory],
    previous_slots: List[StorySlot],
) -> Tuple[List[StorySlot], List[BankStory]]:
    """Assemble les lignes du kit : association banque (si non vide) puis écriture des manques.

    Le service n'écrit rien en base : il renvoie les lignes et les nouvelles histoires à insérer.
    """
    picks = select_requirements(evaluation) or None

    if not bank:
        # Banque vide : pas d'appel d'association, tout part directement à l'écriture
        # (mode extraction si `picks` est None faute d'évaluation).
        written = await write_stories_for_requirements(db, user_id, profile, offer, evaluation, picks)
        slots = [slot for slot, _ in written]
        new_stories = [story for _, story in written if story is not None]
        return carry_over_edited_angles(previous_slots, slots), new_stories

    matched = await match_bank_stories(db, user_id, offer, picks, bank)
    gaps = [pick for pick, slot in matched if slot is None]

    new_stories: List[BankStory] = []
    gap_results_iter = iter(())
    if gaps:
        written = await write_stories_for_requirements(db, user_id, profile, offer, evaluation, gaps)
        new_stories = [story for _, story in written if story is not None]
        gap_results_iter = iter(written)

    slots = [slot if slot is not None else next(gap_results_iter)[0] for _, slot in matched]
    return carry_over_edited_angles(previous_slots, slots), new_stories
