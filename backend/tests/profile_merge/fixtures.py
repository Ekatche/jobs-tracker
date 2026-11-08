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


# --- Provenance, préférences et anciens profils (tâche 2) ---

CV_TWO_JOBS_NO_RUST = {
    "experiences": [
        experience("Orion Data", "Data Engineer", "2022-03", "2024-06", stack=["Python", "Spark"]),
        experience("Helios Conseil", "Analyste", "2020-01", "2021-12", stack=["SQL"]),
    ]
}
FERRIS_PROJECT = {
    "name": "ferris-cli",
    "stack": ["Rust"],
    "description": "Outil en ligne de commande personnel.",
}

PREFS_MANUAL = {
    "target_roles": ["Data Engineer"],
    "seniority_levels": ["senior"],
    "locations": ["Lyon"],
    "remote_policy": "hybrid",
}
PREFS_WEBSITE = {
    "target_roles": ["Analyste BI"],
    "seniority_levels": ["junior"],
    "locations": ["Paris", "Lille"],
    "remote_policy": "full_remote",
}

# Documents `candidate_profile` écrits avant sources/missions_alt/achievements et
# avant les clés de préférences récentes. Les compétences y sont déjà un dict :
# le modèle n'a jamais accepté une liste plate (git log -S sur app/models.py).
LEGACY_PROFILE_V1 = {
    "headline": "Data Engineer",
    "summary": "Ancien résumé.",
    "contact": {"email": "ancien@example.com"},
    "preferences": {"target_roles": ["Data Engineer"], "locations": ["Lyon"], "remote_policy": "hybrid"},
    "experiences": [
        {
            "company": "Orion Data",
            "role": "Data Engineer",
            "start": "2022-03",
            "end": None,
            "missions": ["Pipelines ETL"],
            "stack": ["Python"],
        }
    ],
    "projects": [{"name": "WideDocs", "description": "Plateforme documentaire.", "stack": ["Python"]}],
    "education": [{"school": "INSA Lyon", "degree": "Ingénieur", "years": "2016-2019"}],
    "skills": {"languages": ["Python", "SQL"]},
}
LEGACY_PROFILE_V0 = {
    "headline": "Analyste",
    "experiences": [{"company": "Helios Conseil", "role": "Analyste", "start": "2020-01"}],
}
