"""Structured Markdown export renderer for interview prep kits."""

from typing import Any, Dict, List, Optional, Tuple

from app.models import BankStory, InterviewPrep, StorySlot
from app.services.interview_prep_service.context import _offer_role_and_company

FIT_LABELS: Dict[str, str] = {
    "strong": "forte",
    "partial": "partielle",
    "transferable": "transférable",
    "gap": "manque",
    "no_experience": "pas d'expérience dans ton profil",
    "manual": "choisie",
}


def _append_story_bank_section(
    md_lines: List[str], slots: List[Tuple[StorySlot, Optional[BankStory]]]
) -> None:
    """Append STAR+R stories section to markdown output."""
    md_lines.extend(["## 1. Histoires STAR+R (Story Bank)", ""])
    if not slots:
        md_lines.append("_Aucune histoire STAR+R générée._\n")
        return

    for idx, (slot, story) in enumerate(slots, 1):
        fit_label = FIT_LABELS.get(slot.fit, slot.fit)
        md_lines.append(f"### {idx}. {slot.requirement}")
        md_lines.append(f"**Adéquation :** {fit_label}")
        if slot.angle:
            md_lines.append(f"**Angle :** {slot.angle}")
        md_lines.append("")
        if story is None:
            md_lines.extend(["Aucune histoire pour cette exigence.", ""])
            continue
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


def _append_audience_packs_section(md_lines: List[str], prep: InterviewPrep) -> None:
    """Append segmented recruiter, hiring manager, and tech panel packs."""
    md_lines.extend(["---", "", "## 2. Packs d'Audience Segmentés", ""])

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


def _append_questions_sections(md_lines: List[str], prep: InterviewPrep) -> None:
    """Append anticipated and reverse questions sections."""
    md_lines.extend(["---", "", "## 3. Questions Anticipées (Comportementales & Techniques)", ""])
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

    md_lines.extend(["---", "", "## 4. Questions Inversées (Anti Red-Flags)", ""])
    if not prep.reverse_questions:
        md_lines.append("_Aucune question inversée._\n")
    else:
        for idx, rq in enumerate(prep.reverse_questions, 1):
            md_lines.extend([
                f"### {idx}. [{rq.category}] {rq.question}",
                f"🎯 **Ce que révèle la réponse :** {rq.probe_intent}",
                "",
            ])


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
    ]
    _append_story_bank_section(md_lines, slots)
    _append_audience_packs_section(md_lines, prep)
    _append_questions_sections(md_lines, prep)
    return "\n".join(md_lines)
