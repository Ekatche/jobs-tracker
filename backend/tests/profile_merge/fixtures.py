"""Données partagées des tests de fusion du profil."""

CV = {
    "headline": "Ingénieur Data & IA",
    "summary": "Résumé issu du CV.",
    "experiences": [
        {
            "company": "AGENCE NILE, VIE - Ile Maurice",
            "role": "Data Engineer",
            "start": "Août 2025",
            "end": "PRESENT",
            "missions": ["Agents LLM en production", "Pipelines ETL/ELT Azure"],
            "stack": ["Python", "Mistral"],
        }
    ],
    "projects": [{"name": "WideDocs", "description": "Plateforme documentaire."}],
}

WEBSITE = {
    "summary": "Résumé issu du site.",
    "experiences": [
        {
            "company": "Agence Nile(Mauritius — International Assignment (VIE))",
            "role": "Data Engineer",
            "start": "Aug. 2025",
            "end": "Aug. 2026",
            "missions": ["RAG with Qdrant", "CRM/ERP sync", "PySpark medallion pipeline"],
            "stack": ["Qdrant", "PySpark", "python"],
        },
        {
            "company": "Agence Nile(Lyon, France)",
            "role": "Data Engineer",
            "start": "Aug. 2026",
            "end": None,
            "missions": ["Industrializing production pipelines"],
            "stack": ["Microsoft Fabric"],
        },
        {
            "company": "bioMérieux",
            "role": "Supply Chain Data Analyst",
            "start": "March 2021",
            "end": "Sept. 2021",
            "missions": ["KPI modeling"],
            "stack": ["Power BI"],
        },
    ],
    "projects": [{"name": "Sentinel", "description": "Trading quantitatif."}],
}


def experience(company, role, start, end=None, **extra):
    """Une expérience minimale ; `extra` ajoute missions, stack, etc."""
    return {"company": company, "role": role, "start": start, "end": end, **extra}


# Employeurs fictifs pour les cas de conflit et de réimport.
CV_V1_ORION = {
    "experiences": [
        experience("Orion Data SAS", "Data Engineer", "2022-03", "2024-06"),
        experience("Helios Conseil", "Analyste", "2020-01", "2021-12"),
    ]
}
MANUAL_ORION_CORRECTION = {
    "experiences": [experience("Orion Data", "Lead Data Engineer", "2022-03", "2024-06")]
}
