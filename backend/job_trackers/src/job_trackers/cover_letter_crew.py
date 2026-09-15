import json
import logging
from pathlib import Path
from typing import Dict, Any
from app.services.letter_guards import evaluate_letter_guards, LETTER_RULES
from letter_llm import get_letter_llm, validate_cross_provider

import litellm
from litellm import completion

# Drop unsupported params automatically across providers
litellm.drop_params = True

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "app" / "llm" / "prompts" / "cover_letter"

# Fenêtre de longueur ciblée par le rédacteur (resserrée par rapport à la
# fenêtre d'acceptation plus large des garde-fous côté letter_guards.py).
MIN_WORDS = 270
MAX_WORDS = 330


def load_prompt(name: str, **context: object) -> str:
    """Charge un prompt depuis son fichier et y substitue le contexte.

    Une seule source de vérité pour les prompts : le fichier. Le code ne
    reformule pas les règles, il les interpole.
    """
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return template.format(**context)

def _call_analyst(offer_description: str, candidate_profile: Dict[str, Any], candidate_name: str = "") -> Dict[str, Any]:
    llm = get_letter_llm("offer_analyst")
    exps = candidate_profile.get("experiences", [])
    selected_exps = exps[:3] if exps else []
    companies = [e.get("company", "") for e in selected_exps if e.get("company")]
    projects = [p.get("name", "") for p in candidate_profile.get("projects", []) if p.get("name")]
    
    candidate_stacks = set()
    for e in exps:
        for s in e.get("stack", []):
            candidate_stacks.add(s)
    if candidate_profile.get("skills"):
        for cat_skills in candidate_profile["skills"].values():
            for s in cat_skills:
                candidate_stacks.add(s)

    prompt = f"""Tu es un analyste d'offres de recrutement technique.
À partir de l'offre d'emploi ci-dessous, identifie 2 à 4 missions clés recherchées par l'employeur.
Associe-les aux expériences du candidat : {json.dumps(selected_exps, ensure_ascii=False)}

Offre d'emploi :
{offer_description[:3000]}

Réponds UNIQUEMENT par un objet JSON valide avec cette structure :
{{
    "missions": ["Mission 1", "Mission 2", "Mission 3"],
    "summary": "synthèse de correspondance"
}}"""

    try:
        resp = completion(
            model=llm.model,
            api_key=llm.api_key,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_completion_tokens=600,
            response_format={"type": "json_object"} if "gpt" in llm.model else None,
        )
        data = json.loads(resp.choices[0].message.content.strip())
        missions = data.get("missions", ["Conception de pipelines de données", "Industrialisation de modèles ML/IA"])
    except Exception as e:
        logger.warning(f"Fallback analyste: {e}")
        missions = ["Conception et déploiement de modèles IA / LLM", "Architecture et gouvernance des flux de données"]

    return {
        "missions": missions,
        "selected_experiences": selected_exps,
        "stacks": list(candidate_stacks),
        "companies": companies,
        "projects": projects,
        "candidate_name": candidate_name or (candidate_profile.get("contact") or {}).get("email", ""),
        "candidate_headline": candidate_profile.get("headline", ""),
    }

def _call_writer(analyst_json: Dict[str, Any], company_name: str) -> str:
    llm = get_letter_llm("writer")

    capped_repetitions = ", ".join(
        f'"{term}" (max {n})' for term, n in LETTER_RULES["capped_repetitions"].items()
    )

    prompt = load_prompt(
        "02_style",
        candidate_name=analyst_json.get("candidate_name", ""),
        candidate_headline=analyst_json.get("candidate_headline", ""),
        company_name=company_name,
        min_words=MIN_WORDS,
        max_words=MAX_WORDS,
        missions=json.dumps(analyst_json.get("missions", []), ensure_ascii=False),
        experiences=json.dumps(analyst_json.get("selected_experiences", []), ensure_ascii=False),
        stacks=", ".join(analyst_json.get("stacks", [])[:15]),
        projects=", ".join(analyst_json.get("projects", [])),
        capped_repetitions=capped_repetitions,
    )

    resp = completion(
        model=llm.model,
        api_key=llm.api_key,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_completion_tokens=900,
    )
    content = resp.choices[0].message.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join([l for l in lines if not l.startswith("```")]).strip()
    return content

def _call_critic(letter_text: str, missions: list) -> Dict[str, Any]:
    llm = get_letter_llm("critic")
    prompt = f"""Tu es un recruteur senior intransigeant.
Évalue cette lettre de motivation au regard des missions : {json.dumps(missions, ensure_ascii=False)}

Lettre :
{letter_text}

Critères :
- La lettre est-elle crédible, concrète et sans formulations creuses d'IA ?
- Réponds UNIQUEMENT par un JSON avec :
{{
    "verdict": "pass" si la lettre est publiable, ou "revise" si elle nécessite une retouche,
    "flaws": ["défaut 1", ...]
}}"""

    try:
        resp = completion(
            model=llm.model,
            api_key=llm.api_key,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_completion_tokens=400,
        )
        clean = resp.choices[0].message.content.strip()
        if "{" in clean:
            clean = clean[clean.find("{"):clean.rfind("}")+1]
        data = json.loads(clean)
        return {
            "verdict": data.get("verdict", "pass"),
            "flaws": data.get("flaws", []),
        }
    except Exception as e:
        logger.warning(f"Erreur critique LLM: {e}")
        return {"verdict": "pass", "flaws": []}

def _call_reviser(letter_text: str, analyst_json: Dict[str, Any], critic_flaws: list, guard_report: Dict[str, Any]) -> str:
    llm = get_letter_llm("reviser")
    violations = guard_report.get("violations", [])
    if not violations and not critic_flaws:
        return letter_text

    prompt = f"""Corrige cette lettre de motivation pour résoudre strictement les défauts identifiés ci-dessous, tout en conservant la structure en 3-4 paragraphes, entre 260 et 330 mots, sans ponctuation interdite (!, ..., —, parenthèses).

Lettre originale :
{letter_text}

Défauts à corriger :
- Violations de garde-fous : {violations}
- Remarques du critique : {critic_flaws}

Renvoie uniquement le texte corrigé de la lettre."""

    try:
        resp = completion(
            model=llm.model,
            api_key=llm.api_key,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_completion_tokens=900,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join([l for l in lines if not l.startswith("```")]).strip()
        return content
    except Exception as e:
        logger.warning(f"Erreur réviseur LLM: {e}")
        return letter_text

def run_letter_pipeline_sync(
    offer_description: str,
    candidate_profile: Dict[str, Any],
    company_name: str,
    candidate_name: str = "",
) -> Dict[str, Any]:
    # Validation fournisseur croisé au démarrage
    validate_cross_provider(
        get_letter_llm("writer").model,
        get_letter_llm("critic").model
    )

    # 1. Analyse de l'offre et sélection d'expériences (le profil complet s'arrête ici)
    analyst_output = _call_analyst(offer_description, candidate_profile, candidate_name)
    analyst_output["company_name"] = company_name

    # 2. Rédaction (ne voit que le JSON d'analyst)
    draft_letter = _call_writer(analyst_output, company_name)

    # 3. Évaluation parallèle : Garde-fous en code + Critique inter-modèle
    guard_report = evaluate_letter_guards(draft_letter, offer_description, analyst_output)
    critic_verdict = _call_critic(draft_letter, analyst_output.get("missions", []))

    # 4. Passe de révision conditionnelle
    needs_revision = guard_report.is_blocking or critic_verdict.get("verdict") == "revise"
    revised = False
    final_letter = draft_letter

    if needs_revision:
        final_letter = _call_reviser(
            draft_letter,
            analyst_output,
            critic_verdict.get("flaws", []),
            guard_report.model_dump()
        )
        revised = True
        # Ré-évaluation des garde-fous pour le rapport final
        guard_report = evaluate_letter_guards(final_letter, offer_description, analyst_output)

    return {
        "body": final_letter,
        "revised": revised,
        "critic_verdict": critic_verdict,
        "guard_report": guard_report.model_dump(),
        "models": {
            "analyst": get_letter_llm("offer_analyst").model,
            "writer": get_letter_llm("writer").model,
            "critic": get_letter_llm("critic").model,
            "reviser": get_letter_llm("reviser").model,
        }
    }
