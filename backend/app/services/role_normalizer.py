import math
import logging
from typing import Optional
from app.database import get_database

logger = logging.getLogger(__name__)

ROLE_SIMILARITY_THRESHOLD = 0.85
EMBEDDING_MODEL = "text-embedding-3-small"


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

        # Récupère tous les rôles canoniques existants
        aliases = await collection.find({}).to_list(length=200)

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
