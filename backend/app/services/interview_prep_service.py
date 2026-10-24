import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from bson import ObjectId
from litellm import acompletion
from pydantic import BaseModel

from app.models import (
    ApiUsageAction,
    AnticipatedQuestion,
    AudiencePackHiringManager,
    AudiencePackRecruiter,
    AudiencePackTechPanel,
    BankStory,
    InterviewPrep,
    PracticeAttempt,
    PracticeCriterion,
    ReverseQuestion,
    StoryExperience,
    StoryOrigin,
    StorySlot,
)
from app.services.profile.context import build_candidate_context
from app.services.star_bank_rules import (
    _mask_invented_numbers,
    _story_facts_sources,
    experience_label,
    match_profile_experience,
)
from app.services.usage_tracker import record_api_usage

# `letter_llm` vit hors du package `app` (même montage que profile/collectors/website.py).
_JOB_TRACKERS_SRC = Path(__file__).resolve().parents[2] / "job_trackers" / "src" / "job_trackers"
if str(_JOB_TRACKERS_SRC) not in sys.path:
    sys.path.insert(0, str(_JOB_TRACKERS_SRC))

# GPT-5 et Claude 5 rejettent `temperature` : build_completion_kwargs l'omet pour eux.
from letter_llm import build_completion_kwargs  # noqa: E402

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "interview"
DEFAULT_INTERVIEW_MODEL = os.getenv(
    "INTERVIEW_PREP_MODEL", os.getenv("EVALUATION_MODEL", "gemini/gemini-3.8-flash")
)


def _clean_json_output(raw_text: str) -> Union[Dict[str, Any], List[Any]]:
    """Strip markdown code block fences and parse JSON object or array."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Tenter de trouver le premier tableau ou objet JSON valide
        match_arr = re.search(r"(\[.*\])", cleaned, flags=re.DOTALL)
        if match_arr:
            try:
                return json.loads(match_arr.group(1))
            except json.JSONDecodeError:
                pass
        match_obj = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
        if match_obj:
            try:
                return json.loads(match_obj.group(1))
            except json.JSONDecodeError:
                pass
        raise


def format_candidate_profile_context(profile: Dict[str, Any]) -> str:
    """Format candidate profile into text context for prompts (same projection as the evaluator)."""
    full_name = (profile.get("contact") or {}).get("full_name") or "Candidat"
    headline = profile.get("headline") or ""
    header = f"Candidat : {full_name} - {headline}" if headline else f"Candidat : {full_name}"
    context = json.dumps(build_candidate_context(profile), ensure_ascii=False, indent=2)
    return f"{header}\n{context}"


def format_evaluation_context(evaluation: Optional[Dict[str, Any]]) -> str:
    """Extract and format Bloc A, Bloc B, and Bloc G insights."""
    if not evaluation:
        return "Aucune évaluation préalable disponible."

    lines = []
    # Score
    score = evaluation.get("score")
    if score is not None:
        lines.append(f"Score de matching global : {score}/5.0")

    # Bloc A
    bloc_a = evaluation.get("bloc_a") or {}
    if bloc_a.get("summary"):
        lines.append(f"Synthèse de l'offre : {bloc_a.get('summary')}")
    if bloc_a.get("archetype"):
        lines.append(f"Archétype de poste identifié : {bloc_a.get('archetype')}")
    if bloc_a.get("red_flags"):
        lines.append("Drapeaux rouges détectés : " + "; ".join(bloc_a.get("red_flags")))

    # Bloc B
    bloc_b = evaluation.get("bloc_b") or {}
    matched = bloc_b.get("matched_requirements") or []
    if matched:
        lines.append("\nExigences validées (Points forts du candidat) :")
        for m in matched:
            req = m.get("requirement", "")
            ev = m.get("candidate_evidence", "")
            tags = [m.get("weight", "")]
            if m.get("status") == "partial_match":
                tags.append("couverture partielle")
            if m.get("evidence_tier") == "inferred":
                tags.append("preuve déduite, non explicite dans le profil")
            tags_str = ", ".join(t for t in tags if t)
            lines.append(f"- {req} [{tags_str}] (Preuve: {ev})")

    missing = bloc_b.get("missing_requirements") or []
    if missing:
        lines.append("\nExigences manquantes / à anticiper :")
        for mis in missing:
            req = mis.get("requirement", "")
            weight = mis.get("weight", "")
            reason = mis.get("reason", "")
            lines.append(f"- {req} [Poids: {weight}] (Écart: {reason})")

    if bloc_b.get("score_justification"):
        lines.append(f"\nJustification du score : {bloc_b.get('score_justification')}")

    # Bloc G
    bloc_g = evaluation.get("bloc_g") or {}
    if bloc_g.get("warnings"):
        lines.append("Alertes sur l'offre : " + "; ".join(bloc_g.get("warnings")))

    return "\n".join(lines)


def _offer_role_and_company(offer: Dict[str, Any]) -> Tuple[str, str]:
    """job_offers stocke poste/entreprise ; title/company gardés en repli."""
    role = offer.get("poste") or offer.get("title") or "Poste"
    company = offer.get("entreprise") or offer.get("company") or "Entreprise"
    return role, company


# --- Banque d'histoires STAR+R : sélection des exigences et association ---

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
    db,
    user_id: str,
    offer: Dict[str, Any],
    picks: Optional[List[RequirementPick]],
    bank: List[BankStory],
) -> List[Tuple[RequirementPick, Optional[StorySlot]]]:
    """Associe par IA les exigences sélectionnées (ou extraites par l'IA) aux histoires de la banque."""
    prompt_file = PROMPTS_DIR / "story_match.md"
    template = prompt_file.read_text(encoding="utf-8")

    prompt = template.format(
        target_company=_offer_role_and_company(offer)[1],
        target_role=_offer_role_and_company(offer)[0],
        offer_description=offer.get("description", "")[:4000],
        requirements_block=format_requirements_block(picks),
        bank_summary=format_bank_summary(bank),
    )

    t0 = time.time()
    response = await acompletion(
        model=DEFAULT_INTERVIEW_MODEL,
        messages=[{"role": "user", "content": prompt}],
        drop_params=True,
        **build_completion_kwargs(DEFAULT_INTERVIEW_MODEL, 0.2),
    )
    latency_ms = int((time.time() - t0) * 1000)

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    await record_api_usage(
        db=db,
        user_id=user_id,
        action=ApiUsageAction.INTERVIEW_PREP,
        models_used=[DEFAULT_INTERVIEW_MODEL],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        success=True,
        metadata={"sub_action": "story_match", "offer_id": str(offer.get("_id", ""))},
    )

    raw_content = response.choices[0].message.content
    parsed = _clean_json_output(raw_content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("matches"), list):
        raise ValueError("Expected a JSON object with a 'matches' list")
    matches = parsed["matches"]

    bank_by_id = {story.id: story for story in bank}

    if picks is not None:
        match_by_index: Dict[int, Dict[str, Any]] = {}
        for item in matches:
            idx = item.get("requirement_index")
            if not isinstance(idx, int) or isinstance(idx, bool) or not (1 <= idx <= len(picks)):
                continue
            if idx not in match_by_index:
                match_by_index[idx] = item

        pairs: List[Tuple[RequirementPick, Optional[StorySlot]]] = []
        for i, pick in enumerate(picks, 1):
            match = match_by_index.get(i)
            slot = _build_matched_slot(pick, match, bank_by_id) if match else None
            pairs.append((pick, slot))
        return pairs

    # Sans sélection préalable : les exigences viennent des `requirement` renvoyés par l'IA, 5 au plus.
    pairs = []
    for item in matches:
        if len(pairs) >= MAX_STORY_SLOTS:
            break
        requirement = (item.get("requirement") or "").strip()
        if not requirement:
            continue
        pick = RequirementPick(requirement=requirement, covered=None)
        pairs.append((pick, _build_matched_slot(pick, item, bank_by_id)))
    return pairs


# --- Banque d'histoires STAR+R : écriture des manques et assemblage des lignes ---

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


async def write_stories_for_requirements(
    db,
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
    prompt_file = PROMPTS_DIR / "star_stories.md"
    template = prompt_file.read_text(encoding="utf-8")

    prompt = template.format(
        candidate_profile=format_candidate_profile_context(profile),
        target_company=_offer_role_and_company(offer)[1],
        target_role=_offer_role_and_company(offer)[0],
        offer_description=offer.get("description", "")[:4000],
        evaluation_context=format_evaluation_context(evaluation),
        requirements_block=format_requirements_block(picks),
    )

    t0 = time.time()
    response = await acompletion(
        model=DEFAULT_INTERVIEW_MODEL,
        messages=[{"role": "user", "content": prompt}],
        drop_params=True,
        **build_completion_kwargs(DEFAULT_INTERVIEW_MODEL, 0.2),
    )
    latency_ms = int((time.time() - t0) * 1000)

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    await record_api_usage(
        db=db,
        user_id=user_id,
        action=ApiUsageAction.INTERVIEW_PREP,
        models_used=[DEFAULT_INTERVIEW_MODEL],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        success=True,
        metadata={"sub_action": "stories", "offer_id": str(offer.get("_id", ""))},
    )

    raw_content = response.choices[0].message.content
    parsed = _clean_json_output(raw_content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list):
        raise ValueError("Expected a JSON object with an 'items' list")
    items = parsed["items"]

    profile_experiences = profile.get("experiences") or []

    if picks is not None:
        item_by_index: Dict[int, Dict[str, Any]] = {}
        for item in items:
            idx = item.get("requirement_index")
            if not isinstance(idx, int) or isinstance(idx, bool) or not (1 <= idx <= len(picks)):
                continue
            if idx not in item_by_index:
                item_by_index[idx] = item
        pairs: List[Tuple[RequirementPick, Optional[Dict[str, Any]]]] = [
            (pick, item_by_index.get(i)) for i, pick in enumerate(picks, 1)
        ]
    else:
        # Sans sélection préalable : les exigences viennent des `requirement` renvoyés par l'IA, 5 au plus.
        pairs = []
        for item in items:
            if len(pairs) >= MAX_STORY_SLOTS:
                break
            requirement = (item.get("requirement") or "").strip()
            if not requirement:
                continue
            pairs.append((RequirementPick(requirement=requirement, covered=None), item))

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
    db,
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


async def generate_audience_packs(
    db,
    user_id: Union[str, ObjectId],
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
) -> Tuple[AudiencePackRecruiter, AudiencePackHiringManager, AudiencePackTechPanel]:
    """Generate 3 segmented audience packs (Recruiter, Hiring Manager, Tech Panel)."""
    prompt_file = PROMPTS_DIR / "audience_packs.md"
    template = prompt_file.read_text(encoding="utf-8")

    prompt = template.format(
        candidate_profile=format_candidate_profile_context(profile),
        target_company=_offer_role_and_company(offer)[1],
        target_role=_offer_role_and_company(offer)[0],
        offer_description=offer.get("description", "")[:4000],
        evaluation_context=format_evaluation_context(evaluation),
    )

    t0 = time.time()
    response = await acompletion(
        model=DEFAULT_INTERVIEW_MODEL,
        messages=[{"role": "user", "content": prompt}],
        drop_params=True,
        **build_completion_kwargs(DEFAULT_INTERVIEW_MODEL, 0.2),
    )
    latency_ms = int((time.time() - t0) * 1000)

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    await record_api_usage(
        db=db,
        user_id=user_id,
        action=ApiUsageAction.INTERVIEW_PREP,
        models_used=[DEFAULT_INTERVIEW_MODEL],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        success=True,
        metadata={"sub_action": "audience_packs", "offer_id": str(offer.get("_id", ""))},
    )

    raw_content = response.choices[0].message.content
    parsed = _clean_json_output(raw_content)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object with audience packs")

    recruiter_data = parsed.get("recruiter_pack") or {}
    hm_data = parsed.get("hm_pack") or {}
    tech_data = parsed.get("tech_pack") or {}

    recruiter_pack = AudiencePackRecruiter(
        pitch_30s=recruiter_data.get("pitch_30s", ""),
        comp_strategy=recruiter_data.get("comp_strategy", {}),
        red_flags_they_screen_for=recruiter_data.get("red_flags_they_screen_for", []),
        key_questions_to_ask_recruiter=recruiter_data.get("key_questions_to_ask_recruiter", []),
    )
    hm_pack = AudiencePackHiringManager(
        strategic_alignment=hm_data.get("strategic_alignment", ""),
        internal_vocabulary=hm_data.get("internal_vocabulary", []),
        sharp_questions=hm_data.get("sharp_questions", []),
    )
    tech_pack = AudiencePackTechPanel(
        architecture_points=tech_data.get("architecture_points", []),
        tradeoffs_and_risks=tech_data.get("tradeoffs_and_risks", []),
        reverse_questions=tech_data.get("reverse_questions", []),
    )
    return recruiter_pack, hm_pack, tech_pack


async def generate_anticipated_questions(
    db,
    user_id: Union[str, ObjectId],
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
    stories: Optional[List[BankStory]] = None,
) -> List[AnticipatedQuestion]:
    """Generate behavioral and technical questions anticipated for this exact JD."""
    prompt_file = PROMPTS_DIR / "anticipated_questions.md"
    template = prompt_file.read_text(encoding="utf-8")

    stories_text = "Aucune histoire enregistrée pour le moment."
    if stories:
        stories_lines = [f"- [{s.id}] {s.title} : {s.situation[:100]}..." for s in stories]
        stories_text = "\n".join(stories_lines)

    prompt = template.format(
        candidate_profile=format_candidate_profile_context(profile),
        target_company=_offer_role_and_company(offer)[1],
        target_role=_offer_role_and_company(offer)[0],
        offer_description=offer.get("description", "")[:4000],
        evaluation_context=format_evaluation_context(evaluation),
        stories_context=stories_text,
    )

    t0 = time.time()
    response = await acompletion(
        model=DEFAULT_INTERVIEW_MODEL,
        messages=[{"role": "user", "content": prompt}],
        drop_params=True,
        **build_completion_kwargs(DEFAULT_INTERVIEW_MODEL, 0.2),
    )
    latency_ms = int((time.time() - t0) * 1000)

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    await record_api_usage(
        db=db,
        user_id=user_id,
        action=ApiUsageAction.INTERVIEW_PREP,
        models_used=[DEFAULT_INTERVIEW_MODEL],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        success=True,
        metadata={"sub_action": "questions", "offer_id": str(offer.get("_id", ""))},
    )

    raw_content = response.choices[0].message.content
    parsed = _clean_json_output(raw_content)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON list of questions")

    questions = []
    for item in parsed:
        questions.append(
            AnticipatedQuestion(
                category=item.get("category", "behavioral"),
                question=item.get("question", ""),
                why_it_will_be_asked=item.get("why_it_will_be_asked", ""),
                mapped_story_id=item.get("mapped_story_id"),
                key_points_to_cover=item.get("key_points_to_cover", []),
            )
        )
    return questions


async def generate_reverse_questions(
    db,
    user_id: Union[str, ObjectId],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
) -> List[ReverseQuestion]:
    """Generate tactical reverse questions to audit project health and anti red-flags."""
    prompt_file = PROMPTS_DIR / "reverse_questions.md"
    template = prompt_file.read_text(encoding="utf-8")

    prompt = template.format(
        target_company=_offer_role_and_company(offer)[1],
        target_role=_offer_role_and_company(offer)[0],
        offer_description=offer.get("description", "")[:4000],
        evaluation_context=format_evaluation_context(evaluation),
    )

    t0 = time.time()
    response = await acompletion(
        model=DEFAULT_INTERVIEW_MODEL,
        messages=[{"role": "user", "content": prompt}],
        drop_params=True,
        **build_completion_kwargs(DEFAULT_INTERVIEW_MODEL, 0.2),
    )
    latency_ms = int((time.time() - t0) * 1000)

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    await record_api_usage(
        db=db,
        user_id=user_id,
        action=ApiUsageAction.INTERVIEW_PREP,
        models_used=[DEFAULT_INTERVIEW_MODEL],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        success=True,
        metadata={"sub_action": "reverse_questions", "offer_id": str(offer.get("_id", ""))},
    )

    raw_content = response.choices[0].message.content
    parsed = _clean_json_output(raw_content)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON list of reverse questions")

    rev_questions = []
    for item in parsed:
        rev_questions.append(
            ReverseQuestion(
                category=item.get("category", "Culture"),
                question=item.get("question", ""),
                probe_intent=item.get("probe_intent", ""),
            )
        )
    return rev_questions


PRACTICE_CRITERIA = ("structure", "quantified_result", "offer_fit", "coverage")


async def evaluate_practice_answer(
    db,
    user_id: Union[str, ObjectId],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]],
    question: AnticipatedQuestion,
    answer: str,
    story: Optional[BankStory] = None,
) -> PracticeAttempt:
    """Note la réponse d'entraînement du candidat et propose une version retravaillée."""
    prompt_file = PROMPTS_DIR / "answer_feedback.md"
    template = prompt_file.read_text(encoding="utf-8")

    if story:
        story_context = "\n".join([
            f"Titre : {story.title}",
            f"Situation : {story.situation}",
            f"Tâche : {story.task}",
            f"Action : {story.action}",
            f"Résultat : {story.result}",
            f"Enseignement : {story.reflection}",
        ])
    else:
        story_context = "Aucune histoire liée à cette question."
    key_points = "\n".join(f"- {p}" for p in question.key_points_to_cover) or "Aucun point clé fourni."

    prompt = template.format(
        target_company=_offer_role_and_company(offer)[1],
        target_role=_offer_role_and_company(offer)[0],
        offer_description=offer.get("description", "")[:4000],
        evaluation_context=format_evaluation_context(evaluation),
        question_category=question.category,
        question=question.question,
        key_points=key_points,
        story_context=story_context,
        answer=answer,
    )

    t0 = time.time()
    response = await acompletion(
        model=DEFAULT_INTERVIEW_MODEL,
        messages=[{"role": "user", "content": prompt}],
        drop_params=True,
        **build_completion_kwargs(DEFAULT_INTERVIEW_MODEL, 0.2),
    )
    latency_ms = int((time.time() - t0) * 1000)

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    await record_api_usage(
        db=db,
        user_id=user_id,
        action=ApiUsageAction.INTERVIEW_PREP,
        models_used=[DEFAULT_INTERVIEW_MODEL],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        success=True,
        metadata={"sub_action": "practice", "offer_id": str(offer.get("_id", ""))},
    )

    raw_content = response.choices[0].message.content
    parsed = _clean_json_output(raw_content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("criteria"), dict):
        raise ValueError("Expected a JSON object with practice criteria")

    criteria = []
    for key in PRACTICE_CRITERIA:
        item = parsed["criteria"].get(key)
        if not isinstance(item, dict):
            raise ValueError(f"Missing practice criterion: {key}")
        score = max(1, min(5, int(round(float(item.get("score", 1))))))
        criteria.append(PracticeCriterion(key=key, score=score, comment=str(item.get("comment", ""))))

    return PracticeAttempt(
        question_id=question.id,
        question=question.question,
        answer=answer,
        criteria=criteria,
        overall_score=round(sum(c.score for c in criteria) / len(criteria), 1),
        missing=parsed.get("missing") or [],
        improved_answer=_mask_invented_numbers(
            str(parsed.get("improved_answer", "")), sources=f"{answer}\n{story_context}"
        ),
    )


FIT_LABELS: Dict[str, str] = {
    "strong": "forte",
    "partial": "partielle",
    "transferable": "transférable",
    "gap": "manque",
    "no_experience": "pas d'expérience dans ton profil",
    "manual": "choisie",
}


def export_interview_prep_markdown(
    prep: InterviewPrep,
    offer: Dict[str, Any],
    slots: List[Tuple[StorySlot, Optional[BankStory]]],
) -> str:
    """Render the full interview prep document as a clean, structured Markdown export.

    `slots` : chaque ligne du kit appariée à l'histoire de la banque qu'elle
    référence (`star_bank.slots_with_stories`), dans l'ordre des lignes.
    """
    title, company = _offer_role_and_company(offer)
    date_str = prep.updated_at.strftime("%Y-%m-%d")

    md_lines = [
        f"# Kit de Préparation d'Entretien : {title} @ {company}",
        f"*Généré le {date_str} par Job-Tracker x Career-Ops*",
        "",
        "---",
        "",
        "## 1. Histoires STAR+R (Story Bank)",
        "",
    ]

    if not slots:
        md_lines.append("_Aucune histoire STAR+R générée._\n")
    else:
        for idx, (slot, story) in enumerate(slots, 1):
            fit_label = FIT_LABELS.get(slot.fit, slot.fit)
            md_lines.append(f"### {idx}. {slot.requirement}")
            md_lines.append(f"**Adéquation :** {fit_label}")
            if slot.angle:
                md_lines.append(f"**Angle :** {slot.angle}")
            md_lines.append("")
            if story is None:
                md_lines.append("Aucune histoire pour cette exigence.")
                md_lines.append("")
            else:
                tags_str = ", ".join(story.key_tags) if story.key_tags else "général"
                md_lines.extend([
                    f"**{story.title}** | **Thème :** {story.theme} | **Tags :** `{tags_str}`",
                    "",
                    f"- **S (Situation) :** {story.situation}",
                    f"- **T (Task) :** {story.task}",
                    f"- **A (Action) :** {story.action}",
                    f"- **R (Result) :** {story.result}",
                    f"- **+R (Reflection) :** {story.reflection}",
                    "",
                ])

    md_lines.extend([
        "---",
        "",
        "## 2. Packs d'Audience Segmentés",
        "",
    ])

    if prep.recruiter_pack:
        rp = prep.recruiter_pack
        md_lines.extend([
            "### Pack Recruteur / RH",
            f"**Pitch 30s :** {rp.pitch_30s}",
            "",
            "**Stratégie de Rémunération :**",
            f"- *À valoriser :* {rp.comp_strategy.get('volunteer', '')}",
            f"- *À éviter :* {rp.comp_strategy.get('avoid', '')}",
            "",
            "**Pièges RH à surveiller :**",
            *[f"- {rf}" for rf in rp.red_flags_they_screen_for],
            "",
            "**Questions à poser au recruteur :**",
            *[f"- {q}" for q in rp.key_questions_to_ask_recruiter],
            "",
        ])

    if prep.hm_pack:
        hm = prep.hm_pack
        md_lines.extend([
            "### Pack Hiring Manager",
            f"**Alignement Stratégique :** {hm.strategic_alignment}",
            "",
            f"**Vocabulaire Interne Clé :** {', '.join(hm.internal_vocabulary)}",
            "",
            "**Questions ciblées à poser au Manager :**",
            *[f"- {q}" for q in hm.sharp_questions],
            "",
        ])

    if prep.tech_pack:
        tp = prep.tech_pack
        md_lines.extend([
            "### Pack Panel Technique / Pairs",
            "**Forces d'Architecture à mettre en avant :**",
            *[f"- {pt}" for pt in tp.architecture_points],
            "",
            "**Compromis et Risques assumés :**",
            *[f"- {tr}" for tr in tp.tradeoffs_and_risks],
            "",
            "**Questions inverses sur l'ingénierie :**",
            *[f"- {q}" for q in tp.reverse_questions],
            "",
        ])

    md_lines.extend([
        "---",
        "",
        "## 3. Questions Anticipées (Comportementales & Techniques)",
        "",
    ])

    if not prep.anticipated_questions:
        md_lines.append("_Aucune question anticipée._\n")
    else:
        for idx, q in enumerate(prep.anticipated_questions, 1):
            badge = "[Comportementale]" if q.category == "behavioral" else "[Technique]"
            md_lines.extend([
                f"### {idx}. {badge} {q.question}",
                f"*Pourquoi cette question :* {q.why_it_will_be_asked}",
            ])
            if q.mapped_story_id:
                md_lines.append(f"*Histoire STAR+R recommandée :* {q.mapped_story_id}")
            if q.key_points_to_cover:
                md_lines.append("**Points clés d'une réponse senior :**")
                md_lines.extend([f"- {kp}" for kp in q.key_points_to_cover])
            md_lines.append("")

    md_lines.extend([
        "---",
        "",
        "## 4. Questions Inversées (Anti Red-Flags)",
        "",
    ])

    if not prep.reverse_questions:
        md_lines.append("_Aucune question inversée._\n")
    else:
        for idx, rq in enumerate(prep.reverse_questions, 1):
            md_lines.extend([
                f"### {idx}. [{rq.category}] {rq.question}",
                f"🎯 **Ce que révèle la réponse :** {rq.probe_intent}",
                "",
            ])

    return "\n".join(md_lines)
