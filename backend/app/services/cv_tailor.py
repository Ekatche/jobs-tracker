import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

from litellm import acompletion

from app.models import TailoredCVSchema, TailoredExperienceItem
from app.services.cv_guards import verify_cv_honesty
from app.services.cv_templates import _cumulative_career_years, _most_recent_first

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "llm" / "prompts"
DEFAULT_CV_MODEL = os.getenv("CV_TAILOR_MODEL", os.getenv("EVALUATION_MODEL", "gemini/gemini-3.8-flash"))


class CVHonestyError(ValueError):
    """Raised when the generated CV still contains unsupported claims after the retry."""

    def __init__(self, violations: List[str]) -> None:
        self.violations = violations
        super().__init__(f"CV honesty verification failed: {'; '.join(violations)}")



def _clean_json_output(raw_text: str) -> Dict[str, Any]:
    """Strip markdown code block fences and parse JSON."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


def load_tailor_prompt(
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
    budget: Optional["PageBudget"] = None,
) -> str:
    """Format and load the CV tailor prompt template."""
    budget = budget or compute_page_budget(profile)
    prompt_file = PROMPTS_DIR / "cv" / "tailor_prompt.md"
    template = prompt_file.read_text(encoding="utf-8")

    eval_context_lines = []
    if evaluation and "bloc_b" in evaluation:
        bloc_b = evaluation["bloc_b"]
        matched = bloc_b.get("matched_requirements") or []
        if matched:
            eval_context_lines.append("Compétences et exigences validées du candidat [poids de l'exigence dans l'offre] :")
            for m in matched:
                req = m.get("requirement", "")
                evidence = m.get("candidate_evidence", "")
                tags = [m.get("weight", "")]
                if m.get("status") == "partial_match":
                    tags.append("couverture partielle")
                tags_str = ", ".join(t for t in tags if t)
                eval_context_lines.append(f"- {req} [{tags_str}] (Preuve: {evidence})")

        missing = bloc_b.get("missing_requirements") or []
        if missing:
            eval_context_lines.append("\nCompétences manquantes (ATTENTION : NE PAS INVENTER, NE PAS PRÉTENDRE LES AVOIR) :")
            for miss in missing:
                req = miss.get("requirement", "")
                weight = miss.get("weight", "")
                reason = miss.get("reason", "")
                eval_context_lines.append(f"- {req} [{weight}] (Écart: {reason})")

    eval_context_str = "\n".join(eval_context_lines) if eval_context_lines else "Aucune analyse Bloc B préalable disponible."

    # Serialize profile for prompt (excluding internal ids and cache state)
    profile_for_prompt = {
        k: v for k, v in profile.items()
        if k not in ["_id", "id", "user_id", "created_at", "updated_at", "suggested_roles_cache"]
    }

    target_company = offer.get("entreprise") or offer.get("company") or "L'entreprise cible"
    target_role = offer.get("poste") or offer.get("title") or "Poste visé"
    job_location = offer.get("localisation") or offer.get("location") or "Non spécifié"
    offer_desc = offer.get("description") or offer.get("job_description") or ""

    career_years = _cumulative_career_years(profile)
    seniority_phrase = format_career_seniority_phrase(career_years)

    return template.format(
        candidate_profile=json.dumps(profile_for_prompt, ensure_ascii=False, indent=2, default=str),
        target_company=target_company,
        target_role=target_role,
        job_location=job_location,
        offer_description=offer_desc,
        evaluation_context=eval_context_str,
        page_limit="Deux pages A4" if budget.pages == 2 else "Une page A4",
        bullet_budget=budget.bullets,
        max_projects=budget.projects,
        career_seniority_phrase=seniority_phrase,
    )


class PageBudget(NamedTuple):
    pages: int
    bullets: int
    projects: int


PAGE_BUDGETS = {1: PageBudget(1, 10, 2), 2: PageBudget(2, 22, 3)}
TWO_PAGES_FROM_YEARS = 5


def compute_page_budget(profile: Dict[str, Any]) -> PageBudget:
    """1 page sous TWO_PAGES_FROM_YEARS ans d'expérience cumulée, 2 pages au-delà, quel que soit le niveau de l'offre."""
    if _cumulative_career_years(profile) >= TWO_PAGES_FROM_YEARS:
        return PAGE_BUDGETS[2]
    return PAGE_BUDGETS[1]


def format_career_seniority_phrase(years: float) -> str:
    """Amorce de la première phrase de l'accroche. Arrondi par défaut : 7,9 ans s'écrit « 7 ans », jamais « 8 »."""
    whole_years = int(years)
    if whole_years >= 2:
        return f"avec {whole_years} ans d'expérience dans"
    if whole_years == 1:
        return "avec 1 an d'expérience dans"
    return "avec une expérience dans"


MAX_TECHNOLOGIES = 6
MAX_SKILL_GROUPS = 4
MAX_SKILLS_PER_GROUP = 8
MAX_PRINCIPAL_BULLETS = 5
MAX_SECONDARY_BULLETS = 2
MIN_PRINCIPAL_BULLETS = 2


def _is_principal(exp: TailoredExperienceItem) -> bool:
    return (exp.relevance or "").strip().casefold() == "principale"


def _is_protected(bullet: str, terms: List[str]) -> bool:
    """Vrai si la puce cite une exigence de l'offre (mot entier, casse ignorée)."""
    text = bullet.casefold()
    return any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) for term in terms)


def enforce_page_budget(
    cv: TailoredCVSchema,
    budget: PageBudget,
    evaluation: Optional[Dict[str, Any]] = None,
) -> TailoredCVSchema:
    """Fait tenir le CV adapté dans son budget de pages sans retirer aucune expérience.

    1. Tri antichronologique du rendu (_most_recent_first) ; chaque poste garde son entrée, même chez un
       employeur déjà cité, pour que la progression interne reste visible.
    2. Plafonds : MAX_PRINCIPAL_BULLETS par expérience principale, MAX_SECONDARY_BULLETS par secondaire ;
       si le LLM n'a désigné aucune principale, la plus récente l'est.
    3. Au-delà de budget.bullets : coupe la dernière puce des secondaires, de la plus ancienne à la plus
       récente, puis des principales sans descendre sous MIN_PRINCIPAL_BULLETS. Une puce qui cite une
       exigence critical ou high de Bloc B n'est jamais coupée.
    4. Une entrée sans puce perd ses technologies ; projets plafonnés à budget.projects, compétences à
       MAX_SKILL_GROUPS groupes de MAX_SKILLS_PER_GROUP.
    """
    experiences = [TailoredExperienceItem(**d) for d in _most_recent_first([e.model_dump() for e in cv.experiences])]

    principal = [_is_principal(exp) for exp in experiences]
    if experiences and not any(principal):
        principal[0] = True

    matched = ((evaluation or {}).get("bloc_b") or {}).get("matched_requirements") or []
    terms = [
        m["requirement"].strip().casefold()
        for m in matched
        if m.get("weight") in ("critical", "high") and (m.get("requirement") or "").strip()
    ]
    bullets = [list(exp.bullet_points) for exp in experiences]

    def drop_last_unprotected(i: int) -> bool:
        for j in range(len(bullets[i]) - 1, -1, -1):
            if not _is_protected(bullets[i][j], terms):
                removed = bullets[i].pop(j)
                logger.info(f"Page budget: bullet removed from {experiences[i].company}: {removed[:60]}")
                return True
        return False

    for i in range(len(experiences)):
        cap = MAX_PRINCIPAL_BULLETS if principal[i] else MAX_SECONDARY_BULLETS
        while len(bullets[i]) > cap and drop_last_unprotected(i):
            pass

    oldest_first = range(len(experiences) - 1, -1, -1)
    trim_order = [i for i in oldest_first if not principal[i]] + [i for i in oldest_first if principal[i]]
    for i in trim_order:
        floor = MIN_PRINCIPAL_BULLETS if principal[i] else 0
        while sum(map(len, bullets)) > budget.bullets and len(bullets[i]) > floor and drop_last_unprotected(i):
            pass

    total = sum(map(len, bullets))
    if total > budget.bullets:
        logger.warning(f"Page budget exceeded: {total} bullets kept for a budget of {budget.bullets}")

    capped_exps = [
        exp.model_copy(
            update={
                "bullet_points": kept,
                "relevant_technologies": (exp.relevant_technologies or [])[:MAX_TECHNOLOGIES] if kept else [],
            }
        )
        for exp, kept in zip(experiences, bullets)
    ]

    capped_skills = []
    for group in cv.prioritized_skills[:MAX_SKILL_GROUPS]:
        capped_skills.append(
            group.model_copy(
                update={"skills": group.skills[:MAX_SKILLS_PER_GROUP]}
            )
        )

    return cv.model_copy(
        update={
            "experiences": capped_exps,
            "featured_projects": cv.featured_projects[: budget.projects],
            "prioritized_skills": capped_skills,
        }
    )


async def generate_tailored_cv_content(
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> TailoredCVSchema:
    """
    Generate tailored CV content aligned to job offer and Bloc B evaluation,
    validated by strict anti-hallucination guardrails.
    """
    budget = compute_page_budget(profile)
    prompt = load_tailor_prompt(profile, offer, evaluation, budget)
    chosen_model = model or DEFAULT_CV_MODEL

    log_role = offer.get("poste") or offer.get("title") or "Poste"
    log_company = offer.get("entreprise") or offer.get("company") or "Entreprise"
    logger.info(f"Generating tailored CV for {log_role} at {log_company} with model {chosen_model}")

    max_attempts = 2
    violations: List[str] = []
    for attempt in range(max_attempts):
        attempt_prompt = prompt
        if violations:
            attempt_prompt += (
                "\n\n## CORRECTION REQUISE\n"
                "Ta réponse précédente a été rejetée car elle contenait des éléments absents du profil candidat :\n"
                + "\n".join(f"- {v}" for v in violations)
                + "\nRetire ces éléments (ou remplace-les par des compétences présentes mot pour mot dans le profil) "
                "et renvoie le JSON complet corrigé."
            )

        try:
            response = await acompletion(
                model=chosen_model,
                messages=[{"role": "user", "content": attempt_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
                drop_params=True,
            )

            content_text = response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling LLM for CV tailoring: {e}", exc_info=True)
            raise

        raw_json = _clean_json_output(content_text)
        tailored_cv = TailoredCVSchema(**raw_json)

        # Anti-hallucination guardrail validation
        is_valid, violations = verify_cv_honesty(tailored_cv, profile)
        if is_valid:
            return enforce_page_budget(tailored_cv, budget, evaluation)

        logger.warning(f"CV honesty verification failed (attempt {attempt + 1}/{max_attempts}): {'; '.join(violations)}")

    raise CVHonestyError(violations)

