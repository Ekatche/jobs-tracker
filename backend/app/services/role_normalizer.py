import json
import math
import logging
import os
import re
from typing import Any, Optional
from app.database import get_database

logger = logging.getLogger(__name__)

ROLE_SIMILARITY_THRESHOLD = 0.85
EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_ROLE_SUGGESTION_MODEL = os.getenv("ROLE_SUGGESTION_MODEL", "openai/gpt-4o-mini")


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Calcule la similarité cosinus en Python pur entre deux vecteurs."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


async def ensure_role_aliases_indexes(db=None) -> None:
    """Crée les index nécessaires sur la collection role_aliases de manière idempotente."""
    try:
        if db is None:
            db = await get_database()
        collection = db["role_aliases"]
        await collection.create_index("variants")
        await collection.create_index("canonical", unique=True)
    except Exception as e:
        logger.warning(f"⚠️ Erreur lors de la création des index role_aliases: {e}")


async def normalize_role(role: str, db=None) -> str:
    """Normalise un intitulé de poste vers sa forme canonique.

    Stratégie:
    1. Fast path: lookup exact insensible à la casse sur `variants` dans MongoDB (0 coût token).
    2. Slow path: calcul d'embedding (text-embedding-3-small), comparaison cosinus avec les
       rôles existants. Si similarité >= 0.85, rattache la variante au rôle canonique.
       Sinon, enregistre un nouveau rôle canonique.
    3. Fallback: en cas d'erreur (Mongo, OpenAI, litellm), renvoie le rôle d'origine nettoyé.
    """
    role_clean = role.strip() if role else ""
    if not role_clean:
        return ""

    role_variant = role_clean.lower()

    try:
        if db is None:
            db = await get_database()
        collection = db["role_aliases"]

        # 1. Fast path : recherche directe dans les variantes connues
        existing = await collection.find_one({"variants": role_variant})
        if existing and existing.get("canonical"):
            return existing["canonical"]

        # 2. Slow path : calcul de l'embedding pour recherche sémantique
        from litellm import aembedding

        resp = await aembedding(model=EMBEDDING_MODEL, input=[role_clean])
        item = resp.data[0] if hasattr(resp, "data") else resp["data"][0]
        embedding = (
            item.get("embedding")
            if isinstance(item, dict)
            else getattr(item, "embedding", item["embedding"])
        )

        # Récupère tous les rôles canoniques existants (scan complet: un plafond
        # arbitraire ici tronquerait la recherche à un sous-ensemble non
        # représentatif de la collection, faussant le meilleur match)
        aliases = await collection.find({}).to_list(length=None)

        best_alias: Optional[dict] = None
        best_score = -1.0

        for alias in aliases:
            cand_emb = alias.get("embedding")
            if not cand_emb:
                continue
            score = cosine_similarity(embedding, cand_emb)
            if score > best_score:
                best_score = score
                best_alias = alias

        # 3. Match trouvé si similarité >= seuil
        if best_alias is not None and best_score >= ROLE_SIMILARITY_THRESHOLD:
            canonical_role = best_alias.get("canonical", role_clean)
            await collection.update_one(
                {"_id": best_alias["_id"]},
                {"$addToSet": {"variants": role_variant}},
            )
            logger.info(
                f"🎯 Rôle '{role_clean}' normalisé en '{canonical_role}' (similarité: {best_score:.3f})"
            )
            return canonical_role

        # 4. Nouveau rôle canonique à insérer
        new_entry = {
            "canonical": role_clean,
            "embedding": embedding,
            "variants": [role_variant],
        }
        await collection.insert_one(new_entry)
        logger.info(f"✨ Nouveau rôle canonique enregistré: '{role_clean}'")
        return role_clean

    except Exception as e:
        logger.warning(
            f"⚠️ Erreur lors de la normalisation du rôle '{role_clean}': {e}, fallback sur le rôle brut"
        )
        return role_clean


async def match_taxonomy_role(role: str, db=None) -> Optional[str]:
    """Cherche un métier canonique existant (ROME/ESCO) pour `role`, en lecture seule.

    Contrairement à normalize_role(), n'enregistre jamais de nouveau rôle
    canonique quand aucune correspondance n'est trouvée: renvoie None plutôt
    que de fabriquer un canonical à partir du texte brut. Destiné aux cas où
    on veut uniquement des intitulés issus de la taxonomie (ex: suggestions),
    pas un identifiant de déduplication.
    """
    role_clean = role.strip() if role else ""
    if not role_clean:
        return None

    role_variant = role_clean.lower()

    try:
        if db is None:
            db = await get_database()
        collection = db["role_aliases"]

        existing = await collection.find_one({"variants": role_variant})
        if existing and existing.get("canonical"):
            return existing["canonical"]

        from litellm import aembedding

        resp = await aembedding(model=EMBEDDING_MODEL, input=[role_clean])
        item = resp.data[0] if hasattr(resp, "data") else resp["data"][0]
        embedding = (
            item.get("embedding")
            if isinstance(item, dict)
            else getattr(item, "embedding", item["embedding"])
        )

        aliases = await collection.find({}).to_list(length=None)

        best_alias: Optional[dict] = None
        best_score = -1.0
        for alias in aliases:
            cand_emb = alias.get("embedding")
            if not cand_emb:
                continue
            score = cosine_similarity(embedding, cand_emb)
            if score > best_score:
                best_score = score
                best_alias = alias

        if best_alias is not None and best_score >= ROLE_SIMILARITY_THRESHOLD:
            return best_alias.get("canonical")

        return None

    except Exception as e:
        logger.warning(f"⚠️ Erreur lors du matching taxonomie pour '{role_clean}': {e}")
        return None


async def suggest_role_titles_from_profile(
    profile: dict, model: str = DEFAULT_ROLE_SUGGESTION_MODEL
) -> dict[str, Any]:
    """Propose des intitulés de métier plausibles à partir du profil complet du candidat.

    Contrairement au matching direct headline/experiences[].role, exploite aussi
    summary et skills via un appel LLM pour capter des métiers cohérents avec le
    profil mais non formulés tels quels dans le CV. Les intitulés renvoyés sont
    du texte libre en langage naturel: c'est à l'appelant de les faire passer par
    match_taxonomy_role() pour ne garder que ceux qui correspondent à un vrai
    métier ROME/ESCO.
    """
    headline = (profile.get("headline") or "").strip()
    summary = (profile.get("summary") or "").strip()

    experience_roles = [
        (exp.get("role") or "").strip()
        for exp in (profile.get("experiences") or [])
        if (exp.get("role") or "").strip()
    ]

    skills = profile.get("skills") or {}
    skill_terms: list[str] = []
    if isinstance(skills, dict):
        for values in skills.values():
            if isinstance(values, list):
                skill_terms.extend(str(v) for v in values)
    elif isinstance(skills, list):
        skill_terms = [str(v) for v in skills]

    if not headline and not summary and not experience_roles:
        return {"roles": [], "_usage": None}

    prompt = f"""
Voici le profil d'un candidat (poste actuel, résumé, expériences passées, compétences).

Titre actuel: {headline or "non renseigné"}
Résumé: {summary or "non renseigné"}
Postes occupés précédemment: {", ".join(experience_roles) or "aucun"}
Compétences: {", ".join(skill_terms[:40]) or "aucune"}

Propose entre 3 et 5 intitulés de métier réels et plausibles pour ce candidat,
en français, tels qu'on les trouverait dans une offre d'emploi ou un référentiel
métier (ROME/ESCO). N'invente pas de métier incohérent avec le profil. Ne répète
pas nécessairement le titre actuel: explore aussi des métiers adjacents cohérents
avec les compétences et l'expérience.

Réponds en JSON strict: {{"roles": ["intitulé 1", "intitulé 2", ...]}}
"""

    try:
        from litellm import acompletion

        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            drop_params=True,
        )
        content = response.choices[0].message.content.strip()
        content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
        data = json.loads(content)
        roles = [str(r).strip() for r in (data.get("roles") or []) if str(r).strip()]

        usage = getattr(response, "usage", None)
        return {
            "roles": roles,
            "_usage": {
                "model": model,
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            },
        }
    except Exception as e:
        logger.warning(f"⚠️ Erreur lors de la suggestion de métiers via LLM: {e}")
        return {"roles": [], "_usage": None}
