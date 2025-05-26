from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
import re

from ..models import JobOfferResponse
from ..database import get_database

job_offers_router = APIRouter(prefix="/job-offers", tags=["job-offers"])


# Fonctions utilitaires pour le formatage
def normalize_city(city: str) -> str:
    """Normalise les noms de villes pour éviter les doublons"""
    if not city:
        return "Non spécifié"

    # Supprimer les codes postaux complets (ex: "44000 Nantes" -> "Nantes")
    city = re.sub(r"^\d{5}\s+", "", city)

    # Supprimer les codes postaux avec tiret (ex: "Nantes - 44" -> "Nantes")
    city = re.sub(r"\s*-\s*\d+.*$", "", city)

    # Supprimer les arrondissements avec tiret (ex: "Lyon - 01" -> "Lyon")
    city = re.sub(r"\s*-\s*\d{2}$", "", city)

    # Supprimer les arrondissements avec espace (ex: "LYON 01" -> "LYON")
    city = re.sub(r"\s+\d{2}$", "", city)

    # Supprimer les arrondissements avec "er", "ème", etc. (ex: "Lyon 1er" -> "Lyon")
    city = re.sub(r"\s+\d{1,2}(er|ème|e)?$", "", city, flags=re.IGNORECASE)

    # Supprimer les parenthèses et leur contenu (ex: "Lyon (Rhône)" -> "Lyon")
    city = re.sub(r"\s*\([^)]*\)", "", city)

    # Nettoyer les espaces multiples
    city = re.sub(r"\s+", " ", city.strip())

    # Capitaliser correctement (première lettre de chaque mot en majuscule)
    return city.title() if city else "Non spécifié"


def normalize_company(company: str) -> str:
    """Normalise les noms d'entreprises pour éviter les doublons"""
    if not company:
        return "Non spécifié"

    # Convertir en majuscules pour comparaison
    normalized = company.upper()

    # Supprimer les suffixes courants
    suffixes = [" SAS", " SA", " SARL", " EURL", " SNC", " SCOP", " SASU", " SCIC"]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    # Nettoyer les espaces multiples
    normalized = re.sub(r"\s+", " ", normalized.strip())

    return normalized if normalized else "Non spécifié"


def extract_domain(url: str) -> str:
    """Extrait et normalise le domaine d'une URL"""
    if not url:
        return "Non spécifié"

    # Extraire le domaine
    if "://" in url:
        domain = url.split("://")[1].split("/")[0]
    else:
        domain = url.split("/")[0]

    # Supprimer www.
    if domain.startswith("www."):
        domain = domain[4:]

    return domain.lower()


@job_offers_router.get("/", response_model=List[JobOfferResponse])
async def get_job_offers(
    keywords: Optional[str] = Query(None, description="Mots-clés à rechercher"),
    location: Optional[str] = Query(None, description="Localisation"),
    company: Optional[str] = Query(None, description="Entreprise"),
    limit: int = Query(50, le=100),
    skip: int = Query(0, ge=0),
    db=Depends(get_database),
):
    """Récupère les offres d'emploi avec filtres optionnels"""
    query_filter = {}

    if keywords:
        query_filter["poste"] = {"$regex": keywords, "$options": "i"}
    if location:
        query_filter["localisation"] = {"$regex": location, "$options": "i"}
    if company:
        query_filter["entreprise"] = {"$regex": company, "$options": "i"}

    cursor = (
        db["job_offers"]
        .find(query_filter)
        .skip(skip)
        .limit(limit)
        .sort("created_at", -1)
    )
    offers = await cursor.to_list(length=limit)

    for offer in offers:
        offer["id"] = str(offer["_id"])
        del offer["_id"]

    return offers


@job_offers_router.get("/{offer_id}", response_model=JobOfferResponse)
async def get_job_offer(offer_id: str, db=Depends(get_database)):
    """Récupère une offre d'emploi par son ID"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    offer["id"] = str(offer["_id"])
    del offer["_id"]
    return offer


@job_offers_router.delete("/{offer_id}")
async def delete_job_offer(offer_id: str, db=Depends(get_database)):
    """Supprime une offre d'emploi"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    result = await db["job_offers"].delete_one({"_id": ObjectId(offer_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    return {"message": "Offre supprimée"}


@job_offers_router.get("/stats/summary")
async def get_offers_stats(db=Depends(get_database)):
    """Récupère les statistiques des offres d'emploi"""

    # Total des offres
    total_offers = await db["job_offers"].count_documents({})

    # TOP WEBSITES - Pipeline simplifié
    website_pipeline = [
        {
            "$addFields": {
                "normalized_site": {
                    "$toLower": {
                        "$let": {
                            "vars": {
                                "domain": {
                                    "$arrayElemAt": [
                                        {
                                            "$split": [
                                                {
                                                    "$arrayElemAt": [
                                                        {"$split": ["$url", "://"]},
                                                        1,
                                                    ]
                                                },
                                                "/",
                                            ]
                                        },
                                        0,
                                    ]
                                }
                            },
                            "in": {
                                "$cond": {
                                    "if": {
                                        "$regexMatch": {
                                            "input": "$$domain",
                                            "regex": "^www\\.",
                                        }
                                    },
                                    "then": {"$substr": ["$$domain", 4, -1]},
                                    "else": "$$domain",
                                }
                            },
                        }
                    }
                }
            }
        },
        {"$match": {"normalized_site": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$normalized_site", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]

    # TOP COMPANIES - Traitement côté Python
    # Récupérer toutes les entreprises
    companies_cursor = db["job_offers"].find(
        {"entreprise": {"$exists": True, "$nin": [None, ""]}}, {"entreprise": 1}
    )
    companies_data = await companies_cursor.to_list(length=None)

    # Normaliser côté Python
    company_counts = {}
    for doc in companies_data:
        if doc.get("entreprise"):
            normalized = normalize_company(doc["entreprise"])
            company_counts[normalized] = company_counts.get(normalized, 0) + 1

    # Trier et limiter
    top_companies = [
        {"_id": company, "count": count}
        for company, count in sorted(
            company_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]
    ]

    # TOP CITIES - Traitement côté Python
    # Récupérer toutes les localisations
    cities_cursor = db["job_offers"].find(
        {"localisation": {"$exists": True, "$nin": [None, ""]}}, {"localisation": 1}
    )
    cities_data = await cities_cursor.to_list(length=None)

    # Normaliser côté Python
    city_counts = {}
    for doc in cities_data:
        if doc.get("localisation"):
            normalized = normalize_city(doc["localisation"])
            city_counts[normalized] = city_counts.get(normalized, 0) + 1

    # Trier et limiter
    top_cities = [
        {"_id": city, "count": count}
        for city, count in sorted(
            city_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]
    ]

    # Exécuter le pipeline pour les websites
    top_websites = await db["job_offers"].aggregate(website_pipeline).to_list(length=10)

    return {
        "total_offers": total_offers,
        "top_websites": top_websites,
        "top_companies": top_companies,
        "top_cities": top_cities,
    }


@job_offers_router.get("/count/")
async def count_job_offers(
    keywords: str = Query(None, description="Mots-clés de recherche"),
    location: str = Query(None, description="Localisation"),
    company: str = Query(None, description="Entreprise"),
    db=Depends(get_database),
):
    """Compter le nombre total d'offres d'emploi avec filtres"""
    try:
        filter_dict = {}

        # Construction des filtres de recherche
        if keywords:
            filter_dict["$or"] = [
                {"poste": {"$regex": keywords, "$options": "i"}},
                {"entreprise": {"$regex": keywords, "$options": "i"}},
            ]

        if location:
            filter_dict["localisation"] = {"$regex": location, "$options": "i"}

        if company:
            filter_dict["entreprise"] = {"$regex": company, "$options": "i"}

        # Compter les documents
        total = await db["job_offers"].count_documents(filter_dict)

        return {"total": total}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors du comptage: {str(e)}"
        )
