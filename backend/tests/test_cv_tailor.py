import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models import (
    TailoredCVSchema,
    TailoredExperienceItem,
    TailoredSkillGroup,
    TailoredLanguage,
    TailoredEducationItem,
)
from app.services.cv_tailor import generate_tailored_cv_content


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

SAMPLE_EVALUATION = {
    "bloc_b": {
        "requirements_matched": [
            {"requirement": "Python", "candidate_evidence": "Tech Corp senior backend"},
            {"requirement": "FastAPI", "candidate_evidence": "Tech Corp API development"},
            {"requirement": "Docker", "candidate_evidence": "Profile skill"},
            {"requirement": "PostgreSQL", "candidate_evidence": "Startup Studio"},
        ],
        "missing_requirements": [
            {"requirement": "Kubernetes", "importance": "high"}
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


@pytest.mark.asyncio
async def test_generate_tailored_cv_content_success():
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content=f"```json\n{json.dumps(VALID_LLM_OUTPUT)}\n```"))
    ]
    mock_resp.usage = MagicMock(prompt_tokens=800, completion_tokens=450)

    with patch("app.services.cv_tailor.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_resp

        result = await generate_tailored_cv_content(
            profile=SAMPLE_PROFILE,
            offer=SAMPLE_OFFER,
            evaluation=SAMPLE_EVALUATION
        )

        assert isinstance(result, TailoredCVSchema)
        assert result.target_role_title == "Lead Python Developer"
        assert len(result.experiences) == 2
        assert result.experiences[0].company == "Tech Corp"
        assert len(result.prioritized_skills) == 2

        # Verify acompletion call was made with prompt containing target role & Bloc B
        mock_acompletion.assert_called_once()
        call_kwargs = mock_acompletion.call_args.kwargs
        messages = call_kwargs["messages"]
        prompt_content = messages[0]["content"]
        assert "Fintech Solutions" in prompt_content
        assert "Lead Python Developer" in prompt_content
        assert "Python" in prompt_content


@pytest.mark.asyncio
async def test_generate_tailored_cv_content_flags_hallucinations():
    hallucinated_output = dict(VALID_LLM_OUTPUT)
    hallucinated_output["experiences"] = [
        {
            "title": "CTO",
            "company": "Fake Phantom Corp",
            "location": "Paris",
            "start_date": "2023",
            "end_date": "Présent",
            "bullet_points": ["Invented bullet point"],
            "relevant_technologies": ["QuantumComputing"]
        }
    ]

    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps(hallucinated_output)))
    ]

    with patch("app.services.cv_tailor.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_resp

        with pytest.raises(ValueError, match="CV honesty verification failed"):
            await generate_tailored_cv_content(
                profile=SAMPLE_PROFILE,
                offer=SAMPLE_OFFER,
                evaluation=SAMPLE_EVALUATION
            )


def test_load_tailor_prompt_french_job_offer_fields():
    from app.services.cv_tailor import load_tailor_prompt

    french_offer = {
        "poste": "Ingénieure / Ingénieur IA",
        "entreprise": "DeepTech France",
        "localisation": "Paris (Télétravail)",
        "description": "Poste orienté frameworks d'agents et LLM.",
    }
    prompt = load_tailor_prompt(SAMPLE_PROFILE, french_offer)

    assert "DeepTech France" in prompt
    assert "Ingénieure / Ingénieur IA" in prompt
    assert "Paris (Télétravail)" in prompt
    assert "Poste visé" not in prompt
    assert "L'entreprise cible" not in prompt
