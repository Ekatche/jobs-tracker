import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from bson import ObjectId

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("regenerate_descriptions")


def build_dead_link_fallback_description(
    poste: str,
    entreprise: str,
    competences: Any = None,
    reason: str = "Lien expiré ou annonce retirée par le recruteur",
) -> str:
    """Génère une description de secours structurée et propre pour un lien mort ou expiré."""
    comps_str = "Non spécifié"
    if isinstance(competences, list) and competences:
        valid_items = [str(c).strip() for c in competences if c and str(c).strip()]
        if valid_items:
            comps_str = ", ".join(valid_items)
    elif isinstance(competences, str) and competences.strip():
        comps_str = competences.strip()

    company_label = (entreprise or "").strip() or "Entreprise non spécifiée"
    job_label = (poste or "").strip() or "Poste non spécifié"

    return (
        f"• Statut : Cette offre n'est plus accessible en ligne ({reason}).\n"
        f"• Contexte : Opportunité archivée chez {company_label} pour le poste de {job_label}.\n"
        f"• Compétences initiales : {comps_str}\n"
        f"• Note : Les candidatures sur ce lien d'origine sont probablement closes."
    )


async def regenerate_single_offer(
    offer_id_or_doc: Any,
    db: Optional[Any] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Régénère la description d'une offre d'emploi stockée en base.
    - Si l'offre est accessible et active : extrait la description structurée en 5 sections Markdown.
    - Si le lien est mort/expiré/introuvable : marque l'offre avec is_active=False et
      génère une description de secours synthétique propre basée sur les métadonnées existantes.
    """
    from app.database import get_database
    from job_crawler.crawler1 import crawl_and_extract_jobs_optimized

    if db is None:
        db = await get_database()

    collection = db["job_offers"]

    # 1. Résolution de l'offre
    if isinstance(offer_id_or_doc, (str, ObjectId)):
        oid = ObjectId(offer_id_or_doc) if isinstance(offer_id_or_doc, str) else offer_id_or_doc
        offer_doc = await collection.find_one({"_id": oid})
        if not offer_doc:
            return {"success": False, "error": f"Offre {oid} introuvable"}
    elif isinstance(offer_id_or_doc, dict):
        offer_doc = offer_id_or_doc
    else:
        return {"success": False, "error": "Type d'offre invalide"}

    offer_id = str(offer_doc["_id"])
    url = offer_doc.get("url") or offer_doc.get("source_url")
    poste = offer_doc.get("poste", "")
    entreprise = offer_doc.get("entreprise", "")
    competences = offer_doc.get("competences_cles")

    if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        logger.warning(f"Offre {offer_id}: URL manquante ou invalide: {url}")
        fallback_desc = build_dead_link_fallback_description(
            poste=poste,
            entreprise=entreprise,
            competences=competences,
            reason="URL manquante ou invalide",
        )
        update_fields = {
            "description": fallback_desc,
            "is_active": False,
            "description_updated_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await collection.update_one({"_id": ObjectId(offer_id)}, {"$set": update_fields})
        return {
            "success": True,
            "offer_id": offer_id,
            "is_active": False,
            "status": "invalid_url",
            "description": fallback_desc,
        }

    logger.info(f"🔄 Début régénération pour [{entreprise}] {poste} ({url})")

    # 2. Crawl et extraction
    crawl_res = await crawl_and_extract_jobs_optimized([url], api_key=api_key)
    extracted_offers = crawl_res.get("offers", [])
    results_meta = crawl_res.get("results", [])

    is_dead = False
    failure_reason = "Lien mort ou contenu indisponible"
    if results_meta:
        meta_first = results_meta[0]
        st = meta_first.get("status")
        if st in ("dead_link", "empty_content", "no_extraction"):
            is_dead = True
            failure_reason = meta_first.get("error") or failure_reason

    # 3. Traitement selon succès ou échec
    if is_dead or not extracted_offers:
        logger.warning(f"🛑 Lien mort ou offre indisponible pour {url} ({failure_reason})")
        fallback_desc = build_dead_link_fallback_description(
            poste=poste,
            entreprise=entreprise,
            competences=competences,
            reason=failure_reason,
        )
        update_fields = {
            "description": fallback_desc,
            "is_active": False,
            "description_updated_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await collection.update_one({"_id": ObjectId(offer_id)}, {"$set": update_fields})
        return {
            "success": True,
            "offer_id": offer_id,
            "is_active": False,
            "status": "dead_or_expired",
            "description": fallback_desc,
        }

    # Offre extraite avec succès
    best_offer = extracted_offers[0]
    new_desc = (best_offer.get("description") or "").strip()

    if not new_desc or new_desc.lower() in ("non spécifié", "non disponible"):
        # Le LLM a renvoyé une coquille vide
        fallback_desc = build_dead_link_fallback_description(
            poste=poste,
            entreprise=entreprise,
            competences=competences,
            reason="Aucune description exploitable sur la page",
        )
        update_fields = {
            "description": fallback_desc,
            "is_active": False,
            "description_updated_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await collection.update_one({"_id": ObjectId(offer_id)}, {"$set": update_fields})
        return {
            "success": True,
            "offer_id": offer_id,
            "is_active": False,
            "status": "empty_description",
            "description": fallback_desc,
        }

    # Mise à jour avec la description structurée
    update_fields = {
        "description": new_desc,
        "is_active": True,
        "description_updated_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    # Enrichir d'autres champs manquants s'ils ont été découverts
    for field in ("type_contrat", "salaire", "mode_travail", "competences_cles"):
        val = best_offer.get(field)
        if val and val not in ("Non spécifié", None, []) and (not offer_doc.get(field) or offer_doc.get(field) == "Non spécifié"):
            update_fields[field] = val

    await collection.update_one({"_id": ObjectId(offer_id)}, {"$set": update_fields})
    logger.info(f"✅ Offre {offer_id} régénérée avec succès ({len(new_desc)} caractères)")

    return {
        "success": True,
        "offer_id": offer_id,
        "is_active": True,
        "status": "updated",
        "description": new_desc,
    }


async def batch_regenerate(
    db: Optional[Any] = None,
    query_filter: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    missing_only: bool = False,
    delay_between_requests: float = 1.0,
) -> Dict[str, Any]:
    """
    Régénère les descriptions d'un lot d'offres en base.
    """
    from app.database import get_database

    if db is None:
        db = await get_database()

    collection = db["job_offers"]

    match_query: Dict[str, Any] = {
        "$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]
    }

    if query_filter:
        match_query.update(query_filter)

    if missing_only:
        # Cible les descriptions vides, "Non spécifié", ou n'ayant pas encore les puces de sections
        match_query["$and"] = match_query.get("$and", [])
        match_query["$and"].append(
            {
                "$or": [
                    {"description": {"$exists": False}},
                    {"description": None},
                    {"description": ""},
                    {"description": "Non spécifié"},
                    {"description": {"$not": {"$regex": "• Contexte"}}},
                ]
            }
        )

    total_matching = await collection.count_documents(match_query)
    logger.info(f"📋 Offres éligibles à la régénération : {total_matching}")

    cursor = collection.find(match_query)
    if limit and limit > 0:
        cursor = cursor.limit(limit)

    offers_to_process = await cursor.to_list(length=limit or None)
    logger.info(f"🚀 Début du traitement par lot pour {len(offers_to_process)} offres")

    stats = {
        "total": len(offers_to_process),
        "updated": 0,
        "dead_links": 0,
        "errors": 0,
    }

    for i, doc in enumerate(offers_to_process, 1):
        offer_id = str(doc["_id"])
        logger.info(f"[{i}/{len(offers_to_process)}] Traitement offre {offer_id} ({doc.get('poste')})")

        try:
            res = await regenerate_single_offer(doc, db=db)
            if res.get("success"):
                if res.get("is_active"):
                    stats["updated"] += 1
                else:
                    stats["dead_links"] += 1
            else:
                stats["errors"] += 1
        except Exception as e:
            logger.error(f"Erreur inattendue sur offre {offer_id}: {e}")
            stats["errors"] += 1

        if delay_between_requests > 0 and i < len(offers_to_process):
            await asyncio.sleep(delay_between_requests)

    logger.info(
        f"🏁 Lot terminé : {stats['updated']} mises à jour, "
        f"{stats['dead_links']} liens morts/inactifs, {stats['errors']} erreurs."
    )
    return stats


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Régénération des descriptions des offres d'emploi dans MongoDB"
    )
    parser.add_argument(
        "--offer-id",
        type=str,
        help="ID MongoDB d'une offre spécifique à régénérer",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximum d'offres à traiter",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Traiter uniquement les offres sans description structurée",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Traiter toutes les offres non supprimées",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Délai en secondes entre deux requêtes (défaut: 1.0s)",
    )
    return parser.parse_args()


async def main():
    args = parse_cli_args()

    if args.offer_id:
        res = await regenerate_single_offer(args.offer_id)
        print(json.dumps(res, indent=2, default=str))
    else:
        missing_only = args.missing_only or (not args.all)
        stats = await batch_regenerate(
            limit=args.limit,
            missing_only=missing_only,
            delay_between_requests=args.delay,
        )
        print("\n--- STATISTIQUES FINALES ---")
        print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
