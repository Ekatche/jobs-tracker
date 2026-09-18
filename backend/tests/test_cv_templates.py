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
