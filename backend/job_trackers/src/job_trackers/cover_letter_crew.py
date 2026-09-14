import json
import logging
from typing import Dict, Any
from app.services.letter_guards import evaluate_letter_guards
from letter_llm import get_letter_llm, validate_cross_provider

import litellm
from litellm import completion

# Drop unsupported params automatically across providers
litellm.drop_params = True

logger = logging.getLogger(__name__)

def _call_analyst(offer_description: str, candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
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
    }

def _call_writer(analyst_json: Dict[str, Any], company_name: str) -> str:
    llm = get_letter_llm("writer")

    prompt = f"""Tu es Eliel Katche, Ingénieur Data & IA, et tu rédiges ta lettre de motivation pour postuler chez {company_name}.
Ton écriture est professionnelle, sobre, directe, précise, sans fioritures et sans clichés d'IA.

RÈGLES DE FORME TRÈS STRICTES :
1. Longueur : Entre 270 et 330 mots (TRÈS IMPORTANT, écris au moins 280 mots pour respecter les critères de recrutement).
2. Structure : EXACTEMENT 3 ou 4 paragraphes au total, séparés par UNE ligne vide :
   - Paragraphe 1 : Accroche personnalisée pour {company_name} (ex: "Votre recherche d'un profil... retient toute mon attention.")
     INTERDICTION FORMELLE de commencer par "Je vous adresse ma candidature" ou "Actuellement à la recherche" ou "C'est avec grand intérêt".
   - Paragraphe 2 : Réalisations concrètes en rapport avec l'offre (mentionne tes missions chez Agence Nile, Centre Léon Bérard ou Bimedoc en citant les stacks réelles).
   - Paragraphe 3 : Ta méthode de travail en production (MLOps, gouvernance, architectures de données) et ce que tu apportes concrètement aux équipes de {company_name}.
   - Paragraphe 4 : Formule de politesse sobre et signature :
     "Je serais ravi d'échanger prochainement sur vos enjeux lors d'un entretien.
     Cordialement,
     Eliel Katche"
3. GARDE-FOUS STRICTS (zéro tolérance) :
   - AUCUN point d'exclamation (!)
   - AUCUN point de suspension (...)
   - AUCUN tiret cadratin (—)
   - AUCUNE parenthèse (remplace par des virgules)
   - Au maximum UN seul point-virgule (;)
   - Répétitions : utilise l'expression "mon parcours" au plus 1 fois, "mon expérience" au plus 1 fois, et "mes compétences" au plus 1 fois.
   - AUCUN mot banni : pas de "forte appétence", pas de "passionné par", pas de "dynamique", pas de "rigoureux", pas de "solide expertise", pas de "force de proposition", pas de "polyvalent", pas de "vivement intéressé".
   - AUCUN compliment générique : pas de "entreprise leader", pas d'"acteur majeur", pas d'"excellence".
   - N'invente AUCUNE entreprise non listée dans les faits fournis ci-dessous.

FAITS DU CANDIDAT :
Missions visées : {json.dumps(analyst_json.get('missions', []), ensure_ascii=False)}
Expériences réelles : {json.dumps(analyst_json.get('selected_experiences', []), ensure_ascii=False)}
Technologies : {', '.join(analyst_json.get('stacks', [])[:15])}
Projets : {', '.join(analyst_json.get('projects', []))}

Rédige directement le corps de la lettre en commençant par "Madame, Monsieur," sans en-tête d'adresse."""

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
) -> Dict[str, Any]:
    # Validation fournisseur croisé au démarrage
    validate_cross_provider(
        get_letter_llm("writer").model,
        get_letter_llm("critic").model
    )

    # 1. Analyse de l'offre et sélection d'expériences (le profil complet s'arrête ici)
    analyst_output = _call_analyst(offer_description, candidate_profile)

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
