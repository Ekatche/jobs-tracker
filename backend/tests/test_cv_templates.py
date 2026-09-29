import pytest
from app.models import (
    TailoredCVSchema,
    TailoredExperienceItem,
    TailoredSkillGroup,
    TailoredLanguage,
    TailoredEducationItem,
    TailoredProjectItem,
)
from app.services.cv_templates import render_cv_html

SAMPLE_CANDIDATE = {
    "full_name": "Jean Dupont",
    "email": "jean.dupont@email.com",
    "phone": "+33 6 12 34 56 78",
    "location": "Lyon, France",
    "linkedin_url": "https://linkedin.com/in/jeandupont",
    "github_url": "https://github.com/jeandupont",
}

SAMPLE_CV = TailoredCVSchema(
    target_role_title="Senior Backend Engineer",
    professional_summary="Ingénieur logiciel spécialisé dans les architectures distribuées et microservices haute disponibilité.",
    prioritized_skills=[
        TailoredSkillGroup(category="Backend", skills=["Python", "FastAPI", "Go"]),
        TailoredSkillGroup(category="DevOps", skills=["Docker", "Kubernetes", "AWS"]),
    ],
    experiences=[
        TailoredExperienceItem(
            title="Senior Backend Developer",
            company="Tech Corp",
            location="Lyon",
            start_date="2022",
            end_date="Présent",
            bullet_points=[
                "Conception d'APIs microservices servant 5M+ requêtes/jour.",
                "Optimisation du temps de réponse P99 de 420ms à 85ms."
            ],
            relevant_technologies=["Python", "FastAPI", "PostgreSQL"]
        )
    ],
    featured_projects=[
        TailoredProjectItem(
            name="Cloud Sync Engine",
            description="Moteur de synchronisation temps réel basé sur WebSockets et Redis.",
            technologies=["Python", "Redis", "Docker"],
            url="https://github.com/example/sync"
        )
    ],
    education=[
        TailoredEducationItem(
            degree="Master Informatique",
            institution="INSA Lyon",
            year="2020",
            details="Mention Très Bien"
        )
    ],
    languages=[
        TailoredLanguage(language="Français", level="Natif"),
        TailoredLanguage(language="Anglais", level="C1 - Professionnel courant")
    ],
    certifications=["AWS Certified Solutions Architect"]
)


def test_render_sidebar_elegance():
    html = render_cv_html(
        cv=SAMPLE_CV,
        candidate=SAMPLE_CANDIDATE,
        template_name="sidebar_elegance",
        with_photo=False
    )

    assert "<!DOCTYPE html>" in html
    assert "Jean Dupont" in html
    assert "Senior Backend Engineer" in html
    assert "Tech Corp" in html
    assert "sidebar" in html.lower()
    assert "Français" in html
    assert "C1 - Professionnel courant" in html
    assert "@page" in html
    assert "JD" in html  # Monogram initials when with_photo is False


def test_render_sidebar_elegance_with_photo():
    photo_url = "https://example.com/avatar.jpg"
    html = render_cv_html(
        cv=SAMPLE_CV,
        candidate=SAMPLE_CANDIDATE,
        template_name="sidebar_elegance",
        with_photo=True,
        photo_url=photo_url
    )

    assert photo_url in html
    assert "<img" in html


def test_render_executive_minimalist():
    html = render_cv_html(
        cv=SAMPLE_CV,
        candidate=SAMPLE_CANDIDATE,
        template_name="executive_minimalist",
        with_photo=False
    )

    assert "<!DOCTYPE html>" in html
    assert "Jean Dupont" in html
    assert "Senior Backend Engineer" in html
    assert "Tech Corp" in html
    assert "Cloud Sync Engine" in html
    assert "executive" in html.lower() or "minimalist" in html.lower()


def test_render_invalid_template_defaults_gracefully():
    # If an unknown template is requested, it falls back to sidebar_elegance
    html = render_cv_html(
        cv=SAMPLE_CV,
        candidate=SAMPLE_CANDIDATE,
        template_name="unknown_fancy_template"
    )
    assert "<!DOCTYPE html>" in html
    assert "Jean Dupont" in html


TEMPLATES = ["sidebar_elegance", "executive_minimalist"]


def _render(template, cv=SAMPLE_CV, **candidate_overrides):
    return render_cv_html(
        cv=cv,
        candidate={**SAMPLE_CANDIDATE, **candidate_overrides},
        template_name=template,
    )


@pytest.mark.parametrize("template", TEMPLATES)
def test_skills_title_is_trade_neutral(template):
    assert "Compétences Techniques" not in _render(template)


@pytest.mark.parametrize("template", TEMPLATES)
def test_interests_section_shown_only_when_filled(template):
    html = _render(template, interests=["Football", "Randonnée"])
    assert "Centres d'intérêt" in html
    assert "Randonnée" in html
    assert "Centres d'intérêt" not in _render(template, interests=[])
    assert "Centres d'intérêt" not in _render(template)


@pytest.mark.parametrize("template", TEMPLATES)
def test_portfolio_link_shown_only_when_set(template):
    assert "https://jeandupont.fr" in _render(template, website_url="https://jeandupont.fr")
    assert "🌐" not in _render(template, website_url=None)


@pytest.mark.parametrize("template", TEMPLATES)
def test_mobility_line_joins_filled_values(template):
    both = _render(template, mobility="Permis B, véhiculé", availability="2x8, nuit")
    assert "Permis B, véhiculé · 2x8, nuit" in both
    only_one = _render(template, mobility=None, availability="Disponible immédiatement")
    assert 'class="cv-mobility"' in only_one
    assert "· Disponible immédiatement" not in only_one
    assert 'class="cv-mobility"' not in _render(template, mobility=None, availability=None)


@pytest.mark.parametrize("template", TEMPLATES)
def test_certifications_section_before_formation(template):
    html = _render(template)
    assert "AWS Certified Solutions Architect" in html
    assert html.index(">Certifications & habilitations<") < html.index(">Formation<")


@pytest.mark.parametrize("template", TEMPLATES)
def test_certifications_section_hidden_when_empty(template):
    html = _render(template, cv=SAMPLE_CV.model_copy(update={"certifications": []}))
    assert "Certifications & habilitations" not in html


@pytest.mark.parametrize("template", TEMPLATES)
def test_projects_section_hidden_when_empty(template):
    html = _render(template, cv=SAMPLE_CV.model_copy(update={"featured_projects": []}))
    assert ">Projets Clés & Réalisations<" not in html
    assert ">Projets Clés & Réalisations<" in _render(template)


def test_sidebar_order_skills_certifications_languages_formation_interests():
    html = _render("sidebar_elegance", interests=["Football"])
    positions = [
        html.index(">Compétences Clés<"),
        html.index(">Certifications & habilitations<"),
        html.index(">Langues<"),
        html.index(">Formation<"),
        html.index(">Centres d'intérêt<"),
    ]
    assert positions == sorted(positions)


def test_executive_certifications_follow_skills_and_languages_stay_last():
    html = _render("executive_minimalist")
    assert html.index(">Compétences<") < html.index(">Certifications & habilitations<")
    assert html.index(">Certifications & habilitations<") < html.index(">Langues<")
    assert "Langues & Certifications" not in html
