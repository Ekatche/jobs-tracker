import json
import logging
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models import (
    TailoredCVSchema,
    TailoredExperienceItem,
    TailoredSkillGroup,
    TailoredLanguage,
    TailoredEducationItem,
    TailoredProjectItem,
)
from app.services.cv_tailor import (
    PAGE_BUDGETS,
    PageBudget,
    compute_page_budget,
    generate_tailored_cv_content,
    enforce_page_budget,
    MAX_TECHNOLOGIES,
    MAX_SKILL_GROUPS,
    MAX_SKILLS_PER_GROUP,
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
    assert "antichronologique" in prompt
    assert "CACES" in prompt
    budget = compute_page_budget(SAMPLE_PROFILE)
    assert f"Budget total : {budget.bullets} puces" in prompt
    assert f"0 à {budget.projects} projets" in prompt
    assert ("Deux pages A4" if budget.pages == 2 else "Une page A4") in prompt
    assert "{page_limit}" not in prompt
    assert '"relevance": "principale ou secondaire"' in prompt


def test_load_tailor_prompt_renders_one_and_two_page_budgets():
    from app.services.cv_tailor import load_tailor_prompt

    junior = {**SAMPLE_PROFILE, "experiences": [{"title": "Dev", "company": "A", "start_date": "2019-01", "end_date": "2022-01"}]}
    prompt = load_tailor_prompt(junior, SAMPLE_OFFER)

    assert "Une page A4" in prompt
    assert "0 à 2 projets" in prompt
    assert f"Budget total : {PAGE_BUDGETS[1].bullets} puces" in prompt

    experienced = {**SAMPLE_PROFILE, "experiences": [{"title": "Dev", "company": "A", "start_date": "2016-01", "end_date": "2021-01"}]}
    prompt = load_tailor_prompt(experienced, SAMPLE_OFFER)

    assert "Deux pages A4" in prompt
    assert "0 à 3 projets" in prompt
    assert f"Budget total : {PAGE_BUDGETS[2].bullets} puces" in prompt


def test_load_tailor_prompt_asks_for_short_sober_summary():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION)

    assert "expert mondial" not in prompt
    assert "percutante" not in prompt
    assert "proposition de valeur" not in prompt
    assert "45 mots" not in prompt
    assert prompt.count("70 mots") >= 2
    assert "expérience éprouvée" in prompt
    assert "habitué à" in prompt
    assert "Ne cite aucun nom d'employeur" in prompt


def test_load_tailor_prompt_grounds_summary_in_profile_experiences():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION)

    assert "guident la première phrase" not in prompt
    assert "Positionne le candidat" not in prompt
    assert "N'emprunte à l'offre aucun terme" in prompt
    assert "doit se retrouver dans le profil" in prompt
    assert "livrable ou public" in prompt
    assert "Reste général" in prompt
    assert "Scientist spécialisé" not in prompt
    assert "d'expérience dans" in prompt
    assert "Avec Python" not in prompt
    assert prompt.count("principalement en") >= 2


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


# Dates de fin explicites : le budget ne doit pas dépendre de la date du jour.
@pytest.mark.parametrize(
    "experiences, pages",
    [
        ([{"start": "2018-01", "end": "2022-01"}], 1),
        ([{"start": "2017-02", "end": "2022-01"}], 1),
        ([{"start": "2017-01", "end": "2022-01"}], 2),
        ([{"start": "2010-01", "end": "2015-06"}, {"start_date": "2015-07", "end_date": "2021-01"}], 2),
        ([{"start": None, "end": None}], 1),
    ],
)
def test_page_budget_by_career_years(experiences, pages):
    budget = compute_page_budget({"experiences": experiences})

    assert budget == PAGE_BUDGETS[pages]


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


def test_enforce_sorts_like_renderer():
    exp_old = TailoredExperienceItem(
        title="Junior Dev",
        company="Old Corp",
        location="Paris",
        start_date="2018",
        end_date="2020",
        bullet_points=["Worked on legacy apps."],
        relevant_technologies=["PHP"],
    )
    exp_current = TailoredExperienceItem(
        title="Staff Engineer",
        company="Current Corp",
        location="Lyon",
        start_date="2022",
        end_date="Présent",
        bullet_points=["Architecting systems."],
        relevant_technologies=["Python"],
    )
    exp_mid = TailoredExperienceItem(
        title="Senior Dev",
        company="Mid Corp",
        location="Lyon",
        start_date="2020",
        end_date="2022",
        bullet_points=["Scaling microservices."],
        relevant_technologies=["FastAPI"],
    )

    cv = _make_sample_cv(experiences=[exp_old, exp_current, exp_mid])
    result = enforce_page_budget(cv, PAGE_BUDGETS[1])

    assert [e.company for e in result.experiences] == ["Current Corp", "Mid Corp", "Old Corp"]


def test_enforce_merges_consecutive_same_employer():
    stint_recent = TailoredExperienceItem(
        title="Engineering Lead",
        company="Tech Corp",
        location="Lyon",
        start_date="2022",
        end_date="Présent",
        bullet_points=["Led team of 8.", "Designed cloud architecture."],
        relevant_technologies=["Python", "FastAPI"],
    )
    stint_previous = TailoredExperienceItem(
        title="Senior Developer",
        company="tech corp  ",
        location="Paris",
        start_date="2020",
        end_date="2022",
        bullet_points=["Built microservices."],
        relevant_technologies=["python", "Docker", "PostgreSQL"],
        relevance="principale",
    )
    cv = _make_sample_cv(experiences=[stint_recent, stint_previous])
    result = enforce_page_budget(cv, PAGE_BUDGETS[1])

    assert len(result.experiences) == 1
    merged = result.experiences[0]
    assert merged.company == "Tech Corp"
    assert merged.title == "Engineering Lead"
    assert merged.location == "Lyon"
    assert merged.end_date == "Présent"
    assert merged.start_date == "2020"
    assert merged.bullet_points == [
        "Led team of 8.",
        "Designed cloud architecture.",
        "Built microservices.",
    ]
    assert merged.relevant_technologies == ["Python", "FastAPI", "Docker", "PostgreSQL"]
    assert merged.relevance == "principale"


def test_enforce_keeps_non_consecutive_same_employer():
    stint_1 = TailoredExperienceItem(
        title="Lead Dev",
        company="Acme Corp",
        start_date="2024",
        end_date="Présent",
        bullet_points=["Leadership."],
    )
    stint_2 = TailoredExperienceItem(
        title="Consultant",
        company="Other Agency",
        start_date="2022",
        end_date="2024",
        bullet_points=["Consulting."],
    )
    stint_3 = TailoredExperienceItem(
        title="Junior Dev",
        company="Acme Corp",
        start_date="2020",
        end_date="2022",
        bullet_points=["Junior tasks."],
    )
    cv = _make_sample_cv(experiences=[stint_1, stint_2, stint_3])
    result = enforce_page_budget(cv, PAGE_BUDGETS[1])

    assert len(result.experiences) == 3
    assert [e.company for e in result.experiences] == ["Acme Corp", "Other Agency", "Acme Corp"]


def test_enforce_caps_projects_skills_technologies():
    projects = [
        TailoredProjectItem(name=f"Project {i}", description=f"Desc {i}", technologies=["Tech"])
        for i in range(4)
    ]
    skill_groups = [
        TailoredSkillGroup(category=f"Category {i}", skills=[f"Skill {k}" for k in range(12)])
        for i in range(6)
    ]
    exp = TailoredExperienceItem(
        title="Developer",
        company="Solo Corp",
        start_date="2022",
        end_date="Présent",
        bullet_points=["B1", "B2"],
        relevant_technologies=[f"Tech {k}" for k in range(10)],
    )

    cv = _make_sample_cv(
        experiences=[exp],
        featured_projects=projects,
        prioritized_skills=skill_groups,
    )
    result = enforce_page_budget(cv, PAGE_BUDGETS[1])

    assert len(result.featured_projects) == PAGE_BUDGETS[1].projects
    assert [p.name for p in result.featured_projects] == ["Project 0", "Project 1"]

    assert len(result.prioritized_skills) == MAX_SKILL_GROUPS
    for group in result.prioritized_skills:
        assert len(group.skills) == MAX_SKILLS_PER_GROUP

    assert len(result.experiences[0].relevant_technologies) == MAX_TECHNOLOGIES


def test_enforce_leaves_short_cv_unchanged():
    exp1 = TailoredExperienceItem(
        title="Lead",
        company="Firm A",
        start_date="2022",
        end_date="Présent",
        bullet_points=["Point 1", "Point 2"],
        relevant_technologies=["Python", "FastAPI"],
    )
    exp2 = TailoredExperienceItem(
        title="Dev",
        company="Firm B",
        start_date="2020",
        end_date="2022",
        bullet_points=["Point 3"],
        relevant_technologies=["Docker"],
    )
    project = TailoredProjectItem(name="App", description="Desc", technologies=["Python"])
    skill_group = TailoredSkillGroup(category="Backend", skills=["Python", "FastAPI"])

    cv = _make_sample_cv(
        experiences=[exp1, exp2],
        featured_projects=[project],
        prioritized_skills=[skill_group],
    )
    result = enforce_page_budget(cv, PAGE_BUDGETS[1])

    assert result.model_dump() == cv.model_dump()


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


def test_enforce_never_drops_experiences():
    exps = [_exp(f"Company {i}", f"{2010 + i * 2}", f"{2012 + i * 2}", 3) for i in range(8)]
    cv = _make_sample_cv(experiences=exps)

    result = enforce_page_budget(cv, PAGE_BUDGETS[1])

    assert [e.company for e in result.experiences] == [f"Company {i}" for i in range(7, -1, -1)]
    assert sum(len(e.bullet_points) for e in result.experiences) == PAGE_BUDGETS[1].bullets
    for exp in result.experiences:
        if not exp.bullet_points:
            assert exp.relevant_technologies == []


def test_enforce_trims_secondary_before_principal():
    cv = _make_sample_cv(
        experiences=[
            _exp("Recent Secondary", "2024", "Présent", 2, "secondaire"),
            _exp("Mid Principal", "2021", "2024", 5, "principale"),
            _exp("Old Secondary", "2018", "2021", 2, "secondaire"),
            _exp("Oldest Principal", "2015", "2018", 4, "Principale "),
        ]
    )

    result = enforce_page_budget(cv, PAGE_BUDGETS[1])
    # Secondaires coupées de la plus ancienne à la plus récente ; une principale ancienne garde ses puces.
    assert [len(e.bullet_points) for e in result.experiences] == [1, 5, 0, 4]

    tight = enforce_page_budget(cv, PageBudget(1, 3, 2))
    # Les principales ne descendent jamais sous 2 puces, même au-delà du budget.
    assert [len(e.bullet_points) for e in tight.experiences] == [0, 2, 0, 2]


def test_enforce_keeps_bullets_citing_critical_requirements():
    old_bullets = [
        "Migration des bases vers PostgreSQL.",
        "Animation d'ateliers Docker.",
        "Scripts d'automatisation en Python.",
    ]
    cv = _make_sample_cv(
        experiences=[
            _exp("Recent Corp", "2022", "Présent", 2),
            _exp("Old Corp", "2018", "2022", 0, bullets=old_bullets),
        ]
    )
    tight = PageBudget(1, 2, 2)

    result = enforce_page_budget(cv, tight, SAMPLE_EVALUATION)
    # PostgreSQL (high) et Python (critical) restent ; Docker (meaningful) peut partir.
    assert result.experiences[1].bullet_points == [old_bullets[0], old_bullets[2]]

    without_evaluation = enforce_page_budget(cv, tight)
    assert without_evaluation.experiences[1].bullet_points == []


def test_enforce_defaults_most_recent_to_principal():
    cv = _make_sample_cv(
        experiences=[
            _exp("Old Corp", "2018", "2022", 5),
            _exp("Recent Corp", "2022", "Présent", 5),
        ]
    )

    result = enforce_page_budget(cv, PAGE_BUDGETS[1])

    assert [e.company for e in result.experiences] == ["Recent Corp", "Old Corp"]
    assert [len(e.bullet_points) for e in result.experiences] == [5, 2]
    assert all(e.relevance is None for e in result.experiences)


def test_enforce_logs_each_cut(caplog):
    cv = _make_sample_cv(experiences=[_exp("Solo Corp", "2022", "Présent", 7, "principale")])

    with caplog.at_level(logging.INFO, logger="app.services.cv_tailor"):
        result = enforce_page_budget(cv, PAGE_BUDGETS[1])

    assert len(result.experiences[0].bullet_points) == 5
    cuts = [r for r in caplog.records if "Page budget: bullet removed from Solo Corp" in r.getMessage()]
    assert len(cuts) == 2


def test_cumulative_career_years_merges_overlaps_and_gaps():
    from app.services.cv_templates import _cumulative_career_years

    # Overlapping stints: should count the union, not double-count
    profile_overlap = {
        "experiences": [
            {"start": "2020-01", "end": "2022-01"},
            {"start": "2020-06", "end": "2021-06"},
        ]
    }
    assert _cumulative_career_years(profile_overlap) == 2.0

    # Stints with a 2-year gap: should NOT count the gap
    profile_gap = {
        "experiences": [
            {"start": "2018-01", "end": "2020-01"},
            {"start": "2022-01", "end": "2024-01"},
        ]
    }
    assert _cumulative_career_years(profile_gap) == 4.0

    # Single 8-year stint, exclusive month difference
    profile_single = {
        "experiences": [
            {"start": "09/2018", "end": "09/2026"}
        ]
    }
    assert _cumulative_career_years(profile_single) == 8.0


def test_format_career_seniority_phrase_rounds_down():
    from app.services.cv_tailor import format_career_seniority_phrase

    assert format_career_seniority_phrase(8.0) == "avec 8 ans d'expérience dans"
    assert format_career_seniority_phrase(8.3) == "avec 8 ans d'expérience dans"
    # Jamais d'arrondi vers le haut : 7,9 ans ne s'écrit pas « 8 ans »
    assert format_career_seniority_phrase(7.9) == "avec 7 ans d'expérience dans"
    assert format_career_seniority_phrase(1.8) == "avec 1 an d'expérience dans"
    assert format_career_seniority_phrase(1.0) == "avec 1 an d'expérience dans"
    assert format_career_seniority_phrase(0.6) == "avec une expérience dans"
    assert format_career_seniority_phrase(0.0) == "avec une expérience dans"


def test_load_tailor_prompt_injects_seniority_phrase():
    from app.services.cv_tailor import load_tailor_prompt, compute_page_budget

    profile_8yrs = {
        "full_name": "Camille Martin",
        "experiences": [{"start": "09/2018", "end": "09/2026", "title": "Éducatrice"}]
    }
    offer = {"poste": "Éducateur Spécialisé", "entreprise": "Association Horizon"}
    budget = compute_page_budget(profile_8yrs)
    prompt = load_tailor_prompt(profile_8yrs, offer, budget=budget)

    assert "avec 8 ans d'expérience dans" in prompt

    profile_junior = {
        "full_name": "Junior Dev",
        "experiences": [{"start": "01/2026", "end": "06/2026", "title": "Stagiaire"}]
    }
    budget_j = compute_page_budget(profile_junior)
    prompt_j = load_tailor_prompt(profile_junior, offer, budget=budget_j)

    assert "avec une expérience dans" in prompt_j


def test_page_budget_ignores_career_gaps():
    from app.services.cv_tailor import compute_page_budget

    # Empan 2010-2022 = 12 ans, mais 4 ans travaillés seulement : une page.
    profile = {
        "experiences": [
            {"start": "2010-01", "end": "2012-01"},
            {"start": "2020-01", "end": "2022-01"},
        ]
    }
    assert compute_page_budget(profile) == PAGE_BUDGETS[1]
