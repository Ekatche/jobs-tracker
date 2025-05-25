import asyncio
import re
import logging
from datetime import datetime, timedelta, timezone
from app.database import get_database

# Configuration du logging
logger = logging.getLogger(__name__)


# ======================================================================
# FONCTIONS DE NORMALISATION
# ======================================================================

def normalize_city(city: str) -> str:
    """Normalise les noms de villes pour éviter les doublons"""
    if not city:
        return "Non spécifié"
    
    # Supprimer les codes postaux complets (ex: "44000 Nantes" -> "Nantes")
    city = re.sub(r'^\d{5}\s+', '', city)
    
    # Supprimer les codes postaux avec tiret (ex: "Nantes - 44" -> "Nantes")
    city = re.sub(r'\s*-\s*\d+.*$', '', city)
    
    # Supprimer les arrondissements avec tiret (ex: "Lyon - 01" -> "Lyon")
    city = re.sub(r'\s*-\s*\d{2}$', '', city)
    
    # Supprimer les arrondissements avec espace (ex: "LYON 01" -> "LYON")
    city = re.sub(r'\s+\d{2}$', '', city)
    
    # Supprimer les arrondissements avec "er", "ème", etc. (ex: "Lyon 1er" -> "Lyon")
    city = re.sub(r'\s+\d{1,2}(er|ème|e)?$', '', city, flags=re.IGNORECASE)
    
    # Supprimer les parenthèses et leur contenu (ex: "Lyon (Rhône)" -> "Lyon")
    city = re.sub(r'\s*\([^)]*\)', '', city)
    
    # Nettoyer les espaces multiples
    city = re.sub(r'\s+', ' ', city.strip())
    
    # Capitaliser correctement (première lettre de chaque mot en majuscule)
    return city.title() if city else "Non spécifié"


def normalize_company(company: str) -> str:
    """Normalise les noms d'entreprises pour éviter les doublons"""
    if not company:
        return "Non spécifié"
    
    # Convertir en majuscules pour comparaison
    normalized = company.upper()
    
    # Supprimer les suffixes courants
    suffixes = [' SAS', ' SA', ' SARL', ' EURL', ' SNC', ' SCOP', ' SASU', ' SCIC']
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break
    
    # Nettoyer les espaces multiples
    normalized = re.sub(r'\s+', ' ', normalized.strip())
    
    return normalized if normalized else "Non spécifié"


def extract_domain(url: str) -> str:
    """Extrait et normalise le domaine d'une URL"""
    if not url:
        return "Non spécifié"
    
    try:
        # Extraire le domaine
        if '://' in url:
            domain = url.split('://')[1].split('/')[0]
        else:
            domain = url.split('/')[0]
        
        # Supprimer www.
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain.lower()
    except Exception:
        return "Non spécifié"


# ======================================================================
# FONCTIONS DE NETTOYAGE
# ======================================================================

async def normalize_existing_data():
    """Normalise les données existantes en base"""
    logger.info("🔄 Début de la normalisation des données existantes")
    
    db = await get_database()
    collection = db["job_offers"]
    
    # Récupérer toutes les offres
    offers = await collection.find({}).to_list(length=None)
    logger.info(f"📊 {len(offers)} offres à traiter")
    
    updated_count = 0
    error_count = 0
    
    for offer in offers:
        try:
            updates = {}
            
            # Normaliser la ville
            if offer.get("localisation"):
                normalized_city = normalize_city(offer["localisation"])
                if normalized_city != offer.get("normalized_city"):
                    updates["normalized_city"] = normalized_city
            
            # Normaliser l'entreprise
            if offer.get("entreprise"):
                normalized_company = normalize_company(offer["entreprise"])
                if normalized_company != offer.get("normalized_company"):
                    updates["normalized_company"] = normalized_company
            
            # Normaliser le site web
            if offer.get("url"):
                normalized_site = extract_domain(offer["url"])
                if normalized_site != offer.get("normalized_site"):
                    updates["normalized_site"] = normalized_site
            
            # Mettre à jour si nécessaire
            if updates:
                await collection.update_one(
                    {"_id": offer["_id"]},
                    {"$set": updates}
                )
                updated_count += 1
                
        except Exception as e:
            error_count += 1
            logger.error(f"💥 Erreur normalisation offre {offer.get('_id', 'unknown')}: {e}")
    
    logger.info(f"✅ Normalisation terminée: {updated_count} offres mises à jour sur {len(offers)}")
    if error_count > 0:
        logger.warning(f"⚠️ {error_count} erreurs lors de la normalisation")
    
    return {"normalized": updated_count, "total": len(offers), "errors": error_count}


async def cleanup_old_offers(days: int = 6):
    """Supprime les offres anciennes"""
    logger.info(f"🗑️ Début du nettoyage des offres de plus de {days} jours")
    
    db = await get_database()
    collection = db["job_offers"]
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_date_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Compter d'abord les offres à supprimer
        count_to_delete = await collection.count_documents({
            "created_at": {"$lt": cutoff_date_str}
        })
        
        if count_to_delete == 0:
            logger.info("✅ Aucune offre ancienne à supprimer")
            return {"deleted": 0}
        
        # Supprimer les offres anciennes
        result = await collection.delete_many({
            "created_at": {"$lt": cutoff_date_str}
        })
        
        logger.info(f"✅ Supprimé {result.deleted_count} offres anciennes sur {count_to_delete} identifiées")
        return {"deleted": result.deleted_count}
        
    except Exception as e:
        logger.error(f"💥 Erreur lors du nettoyage: {e}")
        return {"deleted": 0, "error": str(e)}


async def remove_duplicates():
    """Supprime les doublons basés sur URL ou combinaison poste+entreprise+localisation"""
    logger.info("🔍 Début de la suppression des doublons")
    
    db = await get_database()
    collection = db["job_offers"]
    
    # Pipeline pour identifier les doublons par URL
    url_duplicates_pipeline = [
        {"$match": {"url": {"$nin": [None, ""]}}},
        {"$group": {
            "_id": "$url",
            "count": {"$sum": 1},
            "docs": {"$push": {"id": "$_id", "created_at": "$created_at"}}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]
    
    deleted_count = 0
    
    try:
        # Traiter les doublons par URL
        url_duplicates = await collection.aggregate(url_duplicates_pipeline).to_list(length=None)
        
        for duplicate_group in url_duplicates:
            # Garder le plus récent, supprimer les autres
            docs = sorted(duplicate_group["docs"], key=lambda x: x["created_at"], reverse=True)
            docs_to_delete = docs[1:]  # Tous sauf le premier (plus récent)
            
            for doc in docs_to_delete:
                await collection.delete_one({"_id": doc["id"]})
                deleted_count += 1
        
        logger.info(f"✅ Supprimé {deleted_count} doublons")
        return {"deleted_duplicates": deleted_count}
        
    except Exception as e:
        logger.error(f"💥 Erreur lors de la suppression des doublons: {e}")
        return {"deleted_duplicates": 0, "error": str(e)}


async def cleanup_invalid_offers():
    """Supprime les offres avec des données invalides ou incomplètes"""
    logger.info("🧹 Début du nettoyage des offres invalides")
    
    db = await get_database()
    collection = db["job_offers"]
    
    deleted_count = 0
    
    try:
        # Supprimer les offres sans poste ni entreprise
        result1 = await collection.delete_many({
            "$or": [
                {"poste": {"$in": [None, "", "Poste non spécifié"]}},
                {"entreprise": {"$in": [None, "", "Entreprise non spécifiée", "Non spécifié"]}}
            ]
        })
        deleted_count += result1.deleted_count
        
        # Supprimer les offres avec des URLs invalides
        result2 = await collection.delete_many({
            "url": {"$regex": "^(?!https?://).*"}  # URLs qui ne commencent pas par http(s)://
        })
        deleted_count += result2.deleted_count
        
        logger.info(f"✅ Supprimé {deleted_count} offres invalides")
        return {"deleted_invalid": deleted_count}
        
    except Exception as e:
        logger.error(f"💥 Erreur lors du nettoyage des invalides: {e}")
        return {"deleted_invalid": 0, "error": str(e)}


# ======================================================================
# FONCTION PRINCIPALE POUR AIRFLOW
# ======================================================================

async def cleanup_workflow(days: int = 6):
    """Fonction principale de nettoyage pour Airflow"""
    logger.info("🚀 Début du workflow de nettoyage Airflow")
    
    results = {
        "start_time": datetime.now(timezone.utc),
        "steps": {}
    }
    
    try:
        # Étape 1: Normalisation des données
        logger.info("📝 Étape 1: Normalisation des données")
        results["steps"]["normalize"] = await normalize_existing_data()
        
        # Étape 2: Suppression des doublons
        logger.info("🔍 Étape 2: Suppression des doublons")
        results["steps"]["duplicates"] = await remove_duplicates()
        
        # Étape 3: Suppression des offres invalides
        logger.info("🧹 Étape 3: Suppression des offres invalides")
        results["steps"]["invalid"] = await cleanup_invalid_offers()
        
        # Étape 4: Suppression des anciennes offres
        logger.info(f"🗑️ Étape 4: Suppression des offres > {days} jours")
        results["steps"]["old_offers"] = await cleanup_old_offers(days)
        
        # Résumé final
        results["end_time"] = datetime.now(timezone.utc)
        results["duration"] = (results["end_time"] - results["start_time"]).total_seconds()
        
        total_deleted = sum([
            results["steps"].get("duplicates", {}).get("deleted_duplicates", 0),
            results["steps"].get("invalid", {}).get("deleted_invalid", 0),
            results["steps"].get("old_offers", {}).get("deleted", 0)
        ])
        
        total_normalized = results["steps"].get("normalize", {}).get("normalized", 0)
        
        logger.info("🎯 Workflow de nettoyage terminé:")
        logger.info(f"  📊 Données normalisées: {total_normalized}")
        logger.info(f"  🗑️ Offres supprimées: {total_deleted}")
        logger.info(f"  ⏱️ Durée: {results['duration']:.2f}s")
        
        results["summary"] = {
            "total_normalized": total_normalized,
            "total_deleted": total_deleted,
            "success": True
        }
        
        return results
        
    except Exception as e:
        logger.error(f"💥 Erreur dans le workflow de nettoyage: {e}")
        results["error"] = str(e)
        results["summary"] = {"success": False}
        return results


def cleanup_workflow_sync(days: int = 6):
    """Version synchrone pour l'intégration Airflow"""
    return asyncio.run(cleanup_workflow(days))
