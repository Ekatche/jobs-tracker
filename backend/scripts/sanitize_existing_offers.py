"""Script de nettoyage et déséchappement rétroactif des offres existantes en base MongoDB.

Ce script applique:
1. Le décodage des entités HTML (&amp; -> &, &quot; -> ", etc.) et la suppression des balises résiduelles
2. Le nettoyage syntaxique avancé des intitulés de poste (parenthèses orphelines, typographie)
3. La conversion propre HTML -> texte des descriptions polluées
4. La normalisation des villes et métadonnées
5. La régénération des clés d'unicité (unique_key) si nécessaire

Usage:
    docker exec jobtracker-backend python scripts/sanitize_existing_offers.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Assure que le dossier backend est dans le PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.services.normalization import (
    clean_html_entities_and_tags,
    clean_job_title_syntax,
    normalize_city,
    compute_unique_key,
)
from app.services.ats.router import clean_html_to_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def sanitize_all_offers():
    db = await get_database()
    collection = db["job_offers"]

    total_count = await collection.count_documents({})
    logger.info(f"🔍 Analyse de {total_count} offres d'emploi en base...")

    cursor = collection.find({})
    modified_count = 0
    title_fixed_count = 0
    desc_fixed_count = 0

    async for doc in cursor:
        doc_id = doc.get("_id")
        updates = {}

        # 1. Nettoyage de l'intitulé de poste
        raw_poste = doc.get("poste", "")
        clean_poste = clean_job_title_syntax(raw_poste)
        if clean_poste != raw_poste:
            updates["poste"] = clean_poste
            title_fixed_count += 1
            logger.info(f"✏️ Titre nettoyé [{doc_id}]: '{raw_poste}' -> '{clean_poste}'")

        # 2. Nettoyage de l'entreprise
        raw_ent = doc.get("entreprise", "")
        clean_ent = clean_html_entities_and_tags(raw_ent)
        if clean_ent != raw_ent:
            updates["entreprise"] = clean_ent
            logger.info(f"🏢 Entreprise nettoyée [{doc_id}]: '{raw_ent}' -> '{clean_ent}'")

        # 3. Nettoyage de la localisation
        raw_loc = doc.get("localisation", "")
        clean_loc = clean_html_entities_and_tags(raw_loc)
        if clean_loc and clean_loc.lower() not in {"non spécifié", "inconnu", "none", "null"}:
            clean_loc = normalize_city(clean_loc)
        if clean_loc != raw_loc:
            updates["localisation"] = clean_loc

        # 4. Nettoyage des métadonnées (type_contrat, salaire, mode_travail)
        for field in ("type_contrat", "salaire", "mode_travail"):
            raw_val = doc.get(field, "")
            if raw_val and isinstance(raw_val, str):
                clean_val = clean_html_entities_and_tags(raw_val)
                if clean_val != raw_val:
                    updates[field] = clean_val

        # 5. Nettoyage de la description
        raw_desc = doc.get("description", "")
        if raw_desc and isinstance(raw_desc, str) and ("<" in raw_desc or "&" in raw_desc):
            clean_desc = clean_html_to_text(raw_desc)
            if clean_desc != raw_desc:
                updates["description"] = clean_desc
                desc_fixed_count += 1
                logger.info(f"📄 Description nettoyée pour [{doc_id}] ({len(raw_desc)} -> {len(clean_desc)} caractères)")

        # 6. Recalcul de la clé unique si des champs clés ont changé
        final_company = updates.get("entreprise", doc.get("entreprise", ""))
        final_poste = updates.get("poste", doc.get("poste", ""))
        final_loc = updates.get("localisation", doc.get("localisation", ""))
        final_url = doc.get("url")

        new_key = compute_unique_key(
            company=final_company,
            position=final_poste,
            location=final_loc,
            url=final_url,
        )
        if new_key != doc.get("unique_key"):
            updates["unique_key"] = new_key

        # Sauvegarde si modifications
        if updates:
            await collection.update_one({"_id": doc_id}, {"$set": updates})
            modified_count += 1

    logger.info(
        f"✅ Nettoyage terminé avec succès !\n"
        f"  - Total d'offres analysées : {total_count}\n"
        f"  - Offres modifiées : {modified_count}\n"
        f"  - Titres corrigés : {title_fixed_count}\n"
        f"  - Descriptions assainies : {desc_fixed_count}"
    )


if __name__ == "__main__":
    asyncio.run(sanitize_all_offers())
