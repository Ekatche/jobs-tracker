from app.models import (
    TailoredCVSchema,
    TailoredExperienceItem,
    TailoredEducationItem,
    TailoredLanguage,
)

SAMPLE_PROFILE = {
    "personal_info": {
        "full_name": "Jean Dupont",
        "email": "jean.dupont@email.com",
        "phone": "+33 6 12 34 56 78",
        "location": "Lyon, France",
    },
    "skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "React"],
    "experiences": [
        {
            "title": "Senior Backend Engineer",
            "company": "Tech Corp",
            "location": "Lyon",
            "start_date": "2022",
            "end_date": "Présent",
            "description": "Led backend API development in Python and FastAPI. Reduced latency by 30%.",
        },
        {
            "title": "Fullstack Developer",
            "company": "Startup Studio",
            "location": "Paris",
            "start_date": "2020",
            "end_date": "2022",
            "description": "Built web applications using React, Node.js and PostgreSQL.",
        },
    ],
    "education": [
        {"degree": "Master Informatique", "institution": "INSA Lyon", "year": "2020"}
    ],
    "languages": [
        {"language": "Français", "level": "Natif"},
        {"language": "Anglais", "level": "C1"}
    ],
    "projects": [
        {"name": "Job Tracker", "description": "Platform for tracking job offers", "technologies": ["FastAPI", "React"]}
    ],
}

SAMPLE_OFFER = {
    "title": "Lead Python Developer",
    "company": "Fintech Solutions",
    "location": "Lyon (Hybride)",
    "description": "Recherche un Lead Python Developer pour concevoir des microservices FastAPI hautement disponibles avec Docker et PostgreSQL.",
    "requirements": ["Python 3.11+", "FastAPI", "Docker", "PostgreSQL", "Leadership technique"],
}

# Clés alignées sur BlocB (app.models) tel que l'évaluateur le persiste.
SAMPLE_EVALUATION = {
    "bloc_b": {
        "matched_requirements": [
            {"requirement": "Python", "weight": "critical", "candidate_evidence": "Tech Corp senior backend", "status": "full_match"},
            {"requirement": "FastAPI", "weight": "high", "candidate_evidence": "Tech Corp API development", "status": "full_match"},
            {"requirement": "Docker", "weight": "meaningful", "candidate_evidence": "Profile skill", "status": "partial_match"},
            {"requirement": "PostgreSQL", "weight": "high", "candidate_evidence": "Startup Studio", "status": "full_match"},
        ],
        "missing_requirements": [
            {"requirement": "Kubernetes", "weight": "high", "reason": "Aucune mention d'orchestration de conteneurs"}
        ],
    }
}

VALID_LLM_OUTPUT = {
    "target_role_title": "Lead Python Developer",
    "professional_summary": "Lead Python Developer expérimenté avec 5+ ans d'expertise sur FastAPI, Docker et architectures microservices.",
    "prioritized_skills": [
        {"category": "Backend & Cloud", "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"]},
        {"category": "Frontend", "skills": ["React"]}
    ],
    "experiences": [
        {
            "title": "Senior Backend Engineer",
            "company": "Tech Corp",
            "location": "Lyon",
            "start_date": "2022",
            "end_date": "Présent",
            "bullet_points": [
                "Conception et optimisation d'APIs microservices critiques avec FastAPI et Docker.",
                "Amélioration des performances globales avec une réduction de 30% de la latence."
            ],
            "relevant_technologies": ["Python", "FastAPI", "Docker"]
        },
        {
            "title": "Fullstack Developer",
            "company": "Startup Studio",
            "location": "Paris",
            "start_date": "2020",
            "end_date": "2022",
            "bullet_points": [
                "Développement complet d'applications web avec bases PostgreSQL résilientes."
            ],
            "relevant_technologies": ["React", "PostgreSQL"]
        }
    ],
    "featured_projects": [
        {
            "name": "Job Tracker",
            "description": "Plateforme SaaS de suivi de candidatures avec FastAPI.",
            "technologies": ["FastAPI", "React"],
            "url": None
        }
    ],
    "education": [
        {"degree": "Master Informatique", "institution": "INSA Lyon", "year": "2020", "details": None}
    ],
    "languages": [
        {"language": "Français", "level": "Natif"},
        {"language": "Anglais", "level": "C1"}
    ],
    "certifications": []
}

def _make_sample_cv(
    experiences=None,
    featured_projects=None,
    prioritized_skills=None,
) -> TailoredCVSchema:
    return TailoredCVSchema(
        target_role_title="Lead Developer",
        professional_summary="Résumé professionnel court et ciblé.",
        experiences=experiences or [],
        featured_projects=featured_projects or [],
        prioritized_skills=prioritized_skills or [],
        education=[TailoredEducationItem(degree="Master", institution="INSA", year="2020")],
        languages=[TailoredLanguage(language="Français", level="Natif")],
        certifications=[],
    )

def _exp(company, start, end, n_bullets, relevance=None, bullets=None):
    return TailoredExperienceItem(
        title="Role",
        company=company,
        start_date=start,
        end_date=end,
        bullet_points=bullets if bullets is not None else [f"{company} bullet {k}" for k in range(n_bullets)],
        relevant_technologies=["Tech"],
        relevance=relevance,
    )
