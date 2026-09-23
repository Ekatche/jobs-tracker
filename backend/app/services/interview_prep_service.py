import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from bson import ObjectId
from litellm import acompletion

from app.models import (
    ApiUsageAction,
    AnticipatedQuestion,
    AudiencePackHiringManager,
    AudiencePackRecruiter,
    AudiencePackTechPanel,
    InterviewPrep,
    ReverseQuestion,
    StarRStory,
)
from app.services.profile.context import build_candidate_context
from app.services.usage_tracker import record_api_usage

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "interview"
DEFAULT_INTERVIEW_MODEL = os.getenv(
    "INTERVIEW_PREP_MODEL", os.getenv("EVALUATION_MODEL", "gemini/gemini-3.7-flash")
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


async def generate_star_stories(
    db,
    user_id: Union[str, ObjectId],
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
) -> List[StarRStory]:
    """Generate 3 to 5 STAR+R candidate stories grounded in candidate profile."""
    prompt_file = PROMPTS_DIR / "star_stories.md"
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
        temperature=0.2,
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
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON list of STAR+R stories")

    stories = []
    for item in parsed:
        stories.append(
            StarRStory(
                title=item.get("title", "Histoire STAR+R"),
                theme=item.get("theme", "Général"),
                target_requirement=item.get("target_requirement", "Exigence clé"),
                situation=item.get("situation", ""),
                task=item.get("task", ""),
                action=item.get("action", ""),
                result=item.get("result", ""),
                reflection=item.get("reflection", ""),
                key_tags=item.get("key_tags", []),
            )
        )
    return stories


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
        temperature=0.2,
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
    stories: Optional[List[StarRStory]] = None,
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
        temperature=0.2,
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
        temperature=0.2,
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


def export_interview_prep_markdown(prep: InterviewPrep, offer: Dict[str, Any]) -> str:
    """Render the full interview prep document as a clean, structured Markdown export."""
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

    if not prep.stories:
        md_lines.append("_Aucune histoire STAR+R générée._\n")
    else:
        for idx, s in enumerate(prep.stories, 1):
            tags_str = ", ".join(s.key_tags) if s.key_tags else "général"
            md_lines.extend([
                f"### {idx}. {s.title}",
                f"**Thème :** {s.theme} | **Tags :** `{tags_str}`",
                f"**Exigence ciblée (Bloc B) :** {s.target_requirement}",
                "",
                f"- **S (Situation) :** {s.situation}",
                f"- **T (Task) :** {s.task}",
                f"- **A (Action) :** {s.action}",
                f"- **R (Result) :** {s.result}",
                f"- **+R (Reflection) :** {s.reflection}",
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
