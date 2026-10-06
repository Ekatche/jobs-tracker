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


def test_load_tailor_prompt_includes_bloc_b_requirements_with_weight():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION)

    assert "Aucune analyse Bloc B préalable disponible." not in prompt
    assert "- Python [critical] (Preuve: Tech Corp senior backend)" in prompt
    assert "- Docker [meaningful, couverture partielle] (Preuve: Profile skill)" in prompt
    assert "- Kubernetes [high] (Écart: Aucune mention d'orchestration de conteneurs)" in prompt


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


def test_load_tailor_prompt_covers_non_tech_trades_and_relevance_quotas():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION)

    assert "vocabulaire technique" not in prompt
    assert "vocabulaire métier" in prompt
    assert "colis ou lignes par heure" in prompt
    assert "délai de recrutement" in prompt
    assert "4 à 5 bullet points" in prompt
    assert "1 à 2 bullet points" in prompt
    assert "0 à 3 projets" in prompt
    assert "CACES" in prompt
    assert "Une page A4" in prompt


def test_load_tailor_prompt_without_evaluation_judges_relevance_from_offer():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER)

    assert "Aucune analyse Bloc B préalable disponible." in prompt
    assert "En l'absence d'analyse Bloc B, juge la pertinence de chaque expérience d'après l'offre" in prompt


@pytest.mark.asyncio
async def test_generate_tailored_cv_content_retries_with_violation_feedback():
    bad_output = json.loads(json.dumps(VALID_LLM_OUTPUT))
    bad_output["prioritized_skills"] = [
        {"category": "Divers", "skills": ["UnknownImaginaryFramework"]}
    ]
    bad_resp = MagicMock()
    bad_resp.choices = [MagicMock(message=MagicMock(content=json.dumps(bad_output)))]
    good_resp = MagicMock()
    good_resp.choices = [MagicMock(message=MagicMock(content=json.dumps(VALID_LLM_OUTPUT)))]

    with patch("app.services.cv_tailor.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.side_effect = [bad_resp, good_resp]

        result = await generate_tailored_cv_content(
            profile=SAMPLE_PROFILE, offer=SAMPLE_OFFER, evaluation=SAMPLE_EVALUATION
        )

    assert isinstance(result, TailoredCVSchema)
    assert mock_acompletion.call_count == 2
    second_prompt = mock_acompletion.call_args_list[1].kwargs["messages"][0]["content"]
    assert "UnknownImaginaryFramework" in second_prompt
