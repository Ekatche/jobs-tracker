import json
import os
import pathlib
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from bson import ObjectId

def merge_profile_sources(cv_data: Dict[str, Any], site_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    conflicts: List[Dict[str, Any]] = []
    merged_experiences: List[Dict[str, Any]] = []
    provenance: List[Dict[str, str]] = []

    cv_exps = cv_data.get("experiences", [])
    site_exps = site_data.get("experiences", [])

    site_exp_map = {
        (e["company"].lower().strip(), str(e.get("start", "")), str(e.get("end", ""))): e
        for e in site_exps
    }

    for cv_e in cv_exps:
        key = (cv_e["company"].lower().strip(), str(cv_e.get("start", "")), str(cv_e.get("end", "")))
        if key in site_exp_map:
            site_e = site_exp_map.pop(key)
            # Comparer les stacks et missions pour déceler les conflits
            cv_stack = set(cv_e.get("stack", []))
            site_stack = set(site_e.get("stack", []))
            if cv_stack != site_stack:
                conflicts.append({
                    "company": cv_e["company"],
                    "field": "stack",
                    "cv_stack": list(cv_stack),
                    "site_stack": list(site_stack),
                })
            # Fusion union
            unified_exp = dict(cv_e)
            unified_exp["stack"] = list(cv_stack.union(site_stack))
            unified_exp["missions"] = list(set(cv_e.get("missions", []) + site_e.get("missions", [])))
            merged_experiences.append(unified_exp)
            provenance.append({"field_path": f"experiences.{cv_e['company']}", "source": "cv+site"})
        else:
            merged_experiences.append(cv_e)
            provenance.append({"field_path": f"experiences.{cv_e['company']}", "source": "cv"})

    # Expériences restantes du site (absentes du CV)
    for site_e in site_exp_map.values():
        merged_experiences.append(site_e)
        provenance.append({"field_path": f"experiences.{site_e['company']}", "source": "site"})

    merged_profile = {
        "headline": cv_data.get("headline") or site_data.get("headline", ""),
        "summary": cv_data.get("summary") or site_data.get("summary", ""),
        "experiences": merged_experiences,
        "projects": site_data.get("projects", cv_data.get("projects", [])),
        "education": cv_data.get("education", site_data.get("education", [])),
        "certifications": site_data.get("certifications", cv_data.get("certifications", [])),
        "languages": cv_data.get("languages", site_data.get("languages", [])),
        "skills": site_data.get("skills", cv_data.get("skills", {})),
        "provenance": provenance,
    }

    return merged_profile, conflicts


def get_default_candidate_data() -> Dict[str, Any]:
    """Retourne les informations structurées issues du CV d'Eliel Katche."""
    return {
        "headline": "Ingénieur Data & IA",
        "summary": (
            "Ingénieur Data & IA, j'allie ingénierie des données (pipelines ETL/ELT cloud, "
            "data warehouses, qualité et gouvernance) et industrialisation de l'IA (modèles ML "
            "et agents IA en production, MLOps). Expérience développée dans des environnements "
            "exigeants (santé, biopharma, industrie)."
        ),
        "contact": {
            "email": "atchokatche@gmail.com",
            "phone": "(+33) 6 50 34 48 18",
            "github": "https://github.com/Ekatche",
            "website": "https://github.com/Ekatche",
            "linkedin": "",
        },
        "experiences": [
            {
                "company": "Agence Nile",
                "role": "Data Engineer",
                "location": "Ile Maurice (VIE)",
                "contract": "VIE",
                "start": "2025",
                "end": None,
                "sector": "Conseil & Digital",
                "missions": [
                    "Conception et mise en production d'agents LLM pour automatiser des processus métier (support, traitement documentaire)",
                    "Développement de solutions RAG avec prompt engineering et utilisation de LLMs (Mistral) pour fiabiliser les réponses métier",
                    "Industrialisation de pipelines ETL/ELT (Microsoft Fabric, Azure Data Lake, Azure SQL) alimentant des dashboards Power BI",
                    "Orchestration et automatisation de workflows (Python, cron) pour synchroniser les données (HubSpot, Sage X3, Odoo)",
                ],
                "achievements": [
                    {"text": "Mise en production d'agents IA et pipelines Fabric en architecture Medallion", "metric": None}
                ],
                "stack": ["Python", "Azure", "Microsoft Fabric", "Mistral", "RAG", "LLM", "Power BI", "SQL"],
            },
            {
                "company": "Centre Léon Bérard",
                "role": "Data Scientist",
                "location": "Lyon",
                "contract": "CDI",
                "start": "2023",
                "end": "2024",
                "sector": "Santé / Recherche oncologique",
                "missions": [
                    "Automatisation des flux de traitement des données patients en RCP Moléculaire (~10 patients/semaine)",
                    "Extraction de données PDF et conciliation de sources hétérogènes ; gestion base NoSQL",
                    "Développement d'un POC de RAG (Mistral + ChromaDB) pour l'aide au matching d'essais cliniques",
                    "Pilotage de l'implémentation de l'outil CGI Clinics présenté au consortium européen",
                ],
                "achievements": [
                    {"text": "Traitement automatisé de dossiers médicaux pour RCP Moléculaire", "metric": "~10 patients/semaine"}
                ],
                "stack": ["Python", "Mistral", "ChromaDB", "RAG", "NoSQL", "OCR", "NLP"],
            },
            {
                "company": "Nodya Group",
                "role": "Data Scientist / Engineer Consultant",
                "location": "Lyon",
                "contract": "Consultant",
                "start": "2022",
                "end": "2023",
                "sector": "Conseil Data",
                "missions": [
                    "Structuration de bases de données et optimisation des processus ETL multi-sources",
                ],
                "achievements": [],
                "stack": ["Python", "ETL", "SQL"],
            },
            {
                "company": "Bimedoc",
                "role": "Data Scientist",
                "location": "Lyon",
                "contract": "CDI",
                "start": "2021",
                "end": "2022",
                "sector": "Santé numérique",
                "missions": [
                    "Développement et maintenance de flux d'intégration de données sur AWS (S3, Glue, Athena)",
                    "Amélioration de l'extraction d'information depuis des documents PDF (OCR)",
                    "Optimisation d'un modèle de reconnaissance d'entités nommées (NER spaCy) spécialisé sur les médicaments",
                ],
                "achievements": [],
                "stack": ["AWS", "S3", "Glue", "Athena", "Python", "spaCy", "OCR", "NER"],
            },
        ],
        "projects": [
            {
                "name": "Sentinel",
                "description": "Architecture de streaming et analyse de données à haute cadence avec traitement temps réel.",
                "stack": ["Python", "FastAPI", "MongoDB", "Docker"],
                "url": "https://github.com/Ekatche",
                "year": "2025",
                "context": "perso",
            }
        ],
        "education": [
            {"school": "CNAM Lyon", "degree": "Spécialisation en Intelligence Artificielle", "years": "2024 - 2025", "topics": ["Optimisation", "IA avancée", "Deep Learning"]},
            {"school": "Nexa Digital School Lyon", "degree": "Master Data Science", "years": "2022", "topics": ["Machine Learning", "NLP", "Big Data"]},
            {"school": "IAE Lyon School of Management", "degree": "Master Supply Chain Management", "years": "2020", "topics": ["Management", "Logistique"]},
            {"school": "IAE Lyon School of Management", "degree": "Licence de Gestion Technique Quantitative", "years": "2017", "topics": ["Gestion quantitative", "Windsor University"]},
        ],
        "certifications": [
            {"name": "Azure Data Scientist Associate (DP-100)", "issuer": "Microsoft", "year": "2026", "topics": ["Azure ML", "Cloud"]},
            {"name": "MLOps Machine Learning Operations Specialization", "issuer": "Duke University (Coursera)", "year": "2024", "topics": ["MLOps", "CI/CD"]},
        ],
        "languages": ["Français (Natif)", "Anglais (Courant)"],
        "skills": {
            "langages": ["Python", "JavaScript", "Bash", "SQL"],
            "cloud": ["Microsoft Fabric", "Azure", "AWS (S3, Glue, Athena)"],
            "bases": ["MongoDB", "Azure SQL", "MySQL", "PostgreSQL", "ChromaDB"],
            "mlops": ["Docker", "Git", "CI/CD", "MLflow", "Hugging Face"],
            "frameworks": ["FastAPI", "Django", "Streamlit", "LangChain"],
            "data_eng": ["ETL / ELT", "Architecture Medallion", "PySpark", "Power BI"],
        },
        "provenance": [{"field_path": "cv", "source": "cv.md"}],
    }


async def seed_mongo_profile(user_id_str: str = None):
    """Insère ou met à jour le profil candidat dans MongoDB."""
    import sys
    from pathlib import Path
    app_path = Path(__file__).parent.parent
    if str(app_path) not in sys.path:
        sys.path.insert(0, str(app_path))
    from app.database import get_database

    db = await get_database()
    users_coll = db["users"]
    if user_id_str:
        user = await users_coll.find_one({"_id": ObjectId(user_id_str)})
    else:
        user = await users_coll.find_one()

    if not user:
        print("❌ Aucun utilisateur trouvé pour associer le profil.")
        return False

    user_id = user["_id"]
    profile_data = get_default_candidate_data()
    profile_data["user_id"] = ObjectId(user_id)
    profile_data["updated_at"] = datetime.now(timezone.utc)

    await db["candidate_profile"].update_one(
        {"user_id": ObjectId(user_id)},
        {"$set": profile_data},
        upsert=True
    )
    print(f"✅ Profil candidat amorcé avec succès pour l'utilisateur {user.get('username')} ({user_id}) !")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default=None, help="User ID to seed profile for")
    args = parser.parse_args()
    asyncio.run(seed_mongo_profile(args.user_id))

