import logging
import pytest

from app.models import (
    TailoredExperienceItem,
    TailoredSkillGroup,
    TailoredProjectItem,
)
from app.services.cv_tailor import (
    PAGE_BUDGETS,
    PageBudget,
    compute_page_budget,
    enforce_page_budget,
    MAX_TECHNOLOGIES,
    MAX_SKILL_GROUPS,
    MAX_SKILLS_PER_GROUP,
)
from tests.cv_tailor.fixtures import SAMPLE_EVALUATION, _make_sample_cv, _exp


# Dates de fin explicites : le budget ne doit pas dépendre de la date du jour.
@pytest.mark.parametrize(
    "experiences, pages",
    [
        ([{"start": "2018-01", "end": "2022-01"}], 1),
        ([{"start": "2017-03", "end": "2022-01"}], 1),
        ([{"start": "2017-02", "end": "2022-01"}], 2),
        ([{"start": "2010-01", "end": "2015-06"}, {"start_date": "2015-07", "end_date": "2021-01"}], 2),
        ([{"start": None, "end": None}], 1),
    ],
)
def test_page_budget_by_career_years(experiences, pages):
    budget = compute_page_budget({"experiences": experiences})

    assert budget == PAGE_BUDGETS[pages]


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


def test_enforce_keeps_consecutive_same_employer_stints_separate():
    # Internal promotion stays visible: one entry per stint, own title and dates
    stint_previous = TailoredExperienceItem(
        title="Animatrice Permanente 3-11 ans",
        company="Leo Lagrange",
        start_date="2018-09",
        end_date="2022-08",
        bullet_points=["Animation d'ateliers."],
    )
    stint_recent = TailoredExperienceItem(
        title="Responsable Hub Leo 11-13 ans",
        company="Leo Lagrange",
        start_date="2022-09",
        end_date="2026-09",
        bullet_points=["Pilotage du hub."],
        relevance="principale",
    )
    cv = _make_sample_cv(experiences=[stint_previous, stint_recent])
    result = enforce_page_budget(cv, PAGE_BUDGETS[1])

    assert [(e.title, e.start_date, e.end_date) for e in result.experiences] == [
        ("Responsable Hub Leo 11-13 ans", "2022-09", "2026-09"),
        ("Animatrice Permanente 3-11 ans", "2018-09", "2022-08"),
    ]
    assert [e.bullet_points for e in result.experiences] == [["Pilotage du hub."], ["Animation d'ateliers."]]


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
