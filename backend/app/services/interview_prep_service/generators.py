"""AI generators for audience packs, anticipated/reverse questions, and practice feedback."""

from typing import Any, Dict, List, Optional, Tuple, Union

from bson import ObjectId

from app.models import (
    AnticipatedQuestion,
    AudiencePackHiringManager,
    AudiencePackRecruiter,
    AudiencePackTechPanel,
    BankStory,
    PracticeAttempt,
    PracticeCriterion,
    ReverseQuestion,
)
from app.services.interview_prep_service.context import (
    _offer_role_and_company,
    format_candidate_profile_context,
    format_evaluation_context,
)
from app.services.interview_prep_service.llm_client import call_interview_llm
from app.services.star_bank_rules import _mask_invented_numbers

PRACTICE_CRITERIA = ("structure", "quantified_result", "offer_fit", "coverage")


async def generate_audience_packs(
    db: Any,
    user_id: Union[str, ObjectId],
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
) -> Tuple[AudiencePackRecruiter, AudiencePackHiringManager, AudiencePackTechPanel]:
    """Generate 3 segmented audience packs (Recruiter, Hiring Manager, Tech Panel)."""
    role, company = _offer_role_and_company(offer)
    parsed = await call_interview_llm(
        db=db,
        user_id=user_id,
        offer=offer,
        template_name="audience_packs.md",
        sub_action="audience_packs",
        format_vars={
            "candidate_profile": format_candidate_profile_context(profile),
            "target_company": company,
            "target_role": role,
            "offer_description": offer.get("description", "")[:4000],
            "evaluation_context": format_evaluation_context(evaluation),
        },
    )
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
    db: Any,
    user_id: Union[str, ObjectId],
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
    stories: Optional[List[BankStory]] = None,
) -> List[AnticipatedQuestion]:
    """Generate behavioral and technical questions anticipated for this exact JD."""
    stories_text = "Aucune histoire enregistrée pour le moment."
    if stories:
        stories_text = "\n".join(f"- [{s.id}] {s.title} : {s.situation[:100]}..." for s in stories)

    role, company = _offer_role_and_company(offer)
    parsed = await call_interview_llm(
        db=db,
        user_id=user_id,
        offer=offer,
        template_name="anticipated_questions.md",
        sub_action="questions",
        format_vars={
            "candidate_profile": format_candidate_profile_context(profile),
            "target_company": company,
            "target_role": role,
            "offer_description": offer.get("description", "")[:4000],
            "evaluation_context": format_evaluation_context(evaluation),
            "stories_context": stories_text,
        },
    )
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON list of questions")

    return [
        AnticipatedQuestion(
            category=item.get("category", "behavioral"),
            question=item.get("question", ""),
            why_it_will_be_asked=item.get("why_it_will_be_asked", ""),
            mapped_story_id=item.get("mapped_story_id"),
            key_points_to_cover=item.get("key_points_to_cover", []),
        )
        for item in parsed
    ]


async def generate_reverse_questions(
    db: Any,
    user_id: Union[str, ObjectId],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
) -> List[ReverseQuestion]:
    """Generate tactical reverse questions to audit project health and anti red-flags."""
    role, company = _offer_role_and_company(offer)
    parsed = await call_interview_llm(
        db=db,
        user_id=user_id,
        offer=offer,
        template_name="reverse_questions.md",
        sub_action="reverse_questions",
        format_vars={
            "target_company": company,
            "target_role": role,
            "offer_description": offer.get("description", "")[:4000],
            "evaluation_context": format_evaluation_context(evaluation),
        },
    )
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON list of reverse questions")

    return [
        ReverseQuestion(
            category=item.get("category", "Culture"),
            question=item.get("question", ""),
            probe_intent=item.get("probe_intent", ""),
        )
        for item in parsed
    ]


def _format_story_context(story: Optional[BankStory]) -> str:
    if not story:
        return "Aucune histoire liée à cette question."
    return "\n".join([
        f"Titre : {story.title}",
        f"Situation : {story.situation}",
        f"Tâche : {story.task}",
        f"Action : {story.action}",
        f"Résultat : {story.result}",
        f"Enseignement : {story.reflection}",
    ])


async def evaluate_practice_answer(
    db: Any,
    user_id: Union[str, ObjectId],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]],
    question: AnticipatedQuestion,
    answer: str,
    story: Optional[BankStory] = None,
) -> PracticeAttempt:
    """Note la réponse d'entraînement du candidat et propose une version retravaillée."""
    story_context = _format_story_context(story)
    key_points = "\n".join(f"- {p}" for p in question.key_points_to_cover) or "Aucun point clé fourni."
    role, company = _offer_role_and_company(offer)

    parsed = await call_interview_llm(
        db=db,
        user_id=user_id,
        offer=offer,
        template_name="answer_feedback.md",
        sub_action="practice",
        format_vars={
            "target_company": company,
            "target_role": role,
            "offer_description": offer.get("description", "")[:4000],
            "evaluation_context": format_evaluation_context(evaluation),
            "question_category": question.category,
            "question": question.question,
            "key_points": key_points,
            "story_context": story_context,
            "answer": answer,
        },
    )
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
