import pytest
from app.models import (
    TailoredCVSchema,
    TailoredExperienceItem,
    TailoredSkillGroup,
    TailoredLanguage,
    TailoredEducationItem,
    TailoredProjectItem,
)
from app.services.cv_templates import CV_TEMPLATES, render_cv_html

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
    assert '<canvas class="monogram"' in html  # Monogramme dessiné, pas du texte
    assert 'data-initials="JD"' in html
    assert ">JD<" not in html


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


TEMPLATES = list(CV_TEMPLATES)


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
    assert 'data-icon="web"' not in _render(template, website_url=None)


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
    assert ">Projets<" not in html
    assert ">Projets<" in _render(template)


def test_sidebar_order_skills_certifications_languages_formation_interests():
    html = _render("sidebar_elegance", interests=["Football"])
    positions = [
        html.index(">Compétences<"),
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


import logging

from app.services.cv_templates import SECTION_TITLES


def test_accent_injects_registry_colors():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE, accent="bordeaux")
    assert "--accent: #8b1e3f" in html
    assert "--accent-tint: #f8eef1" in html
    assert "--accent-line: #d8a9b7" in html


def test_unknown_accent_falls_back_to_marine_with_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.cv_templates"):
        html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE, accent="fluo")
    assert "--accent: #1e3a8a" in html
    assert "fluo" in caplog.text


def test_missing_template_and_accent_fall_back_to_defaults():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE, template_name=None, accent=None)
    assert "cv-layout-sidebar" in html
    assert "--accent: #1e3a8a" in html


def test_base_css_is_not_html_escaped():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE)
    assert "@import url('https://fonts.googleapis.com" in html
    assert "&#39;Inter&#39;" not in html


def test_accent_block_follows_font_import():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE)
    assert html.index("@import") < html.index("--accent: #")


@pytest.mark.parametrize("template", TEMPLATES)
def test_section_titles_come_from_registry(template):
    html = _render(template)
    assert f">{SECTION_TITLES['experience']}<" in html
    assert "Expérience Professionnelle" not in html
    assert "Projets Clés" not in html
    assert "Compétences Clés" not in html


from app.services.cv_templates import _jinja_env


def _macro(call, **context):
    return _jinja_env.from_string('{% import "_macros.html" as m %}' + call).render(**context)


def test_inline_list_separated_by_visible_dot():
    assert _macro('{{ m.inline_list(["Python", "FastAPI"]) }}') == 'Python<span class="dot"> · </span>FastAPI'


def test_inline_list_escapes_content():
    assert "&lt;b&gt;" in _macro('{{ m.inline_list(["<b>"]) }}')


def test_tools_line_is_plain_text():
    assert _macro('{{ m.tools_line(["SAP", "Excel"]) }}') == '<div class="tools">SAP · Excel</div>'


def test_contacts_use_svg_icons_and_real_text():
    html = _macro("{{ m.contacts(candidate) }}", candidate={"email": "jean@x.fr", "website_url": "https://jean.fr"})
    assert 'data-icon="mail"' in html
    assert 'data-icon="web"' in html
    assert ">jean@x.fr<" in html
    assert 'data-icon="phone"' not in html
    assert "<text" not in html


def test_mobility_line_only_when_filled():
    both = _macro("{{ m.mobility_line(candidate) }}", candidate={"mobility": "Permis B", "availability": "2x8"})
    assert both == '<div class="cv-mobility">Permis B · 2x8</div>'
    assert _macro("{{ m.mobility_line(candidate) }}", candidate={}) == ""


def test_monogram_is_canvas_not_text():
    html = _macro('{{ m.monogram("JD") }}')
    assert '<canvas class="monogram"' in html
    assert 'data-initials="JD"' in html
    assert ">JD<" not in html


def test_base_css_disables_ligatures_and_aliases_accent():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE)
    assert "font-variant-ligatures: none" in html
    assert "--color-primary: var(--accent)" in html
    assert "small-caps" not in html


import re

EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿-]")
ATS_SAFE_TEMPLATES = TEMPLATES


@pytest.mark.parametrize("template", ATS_SAFE_TEMPLATES)
def test_no_emoji_in_html(template):
    html = _render(template, website_url="https://jeandupont.fr", interests=["Football"])
    assert not EMOJI_RE.search(html)


@pytest.mark.parametrize("template", ATS_SAFE_TEMPLATES)
def test_contacts_use_svg_icons(template):
    html = _render(template)
    assert 'data-icon="mail"' in html
    assert 'data-icon="pin"' in html


def test_sidebar_main_precedes_aside():
    html = _render("sidebar_elegance")
    assert html.index("<main") < html.index("<aside")


def test_sidebar_skills_render_as_plain_text():
    html = _render("sidebar_elegance")
    assert '<div class="skill-list">Python<span class="dot"> · </span>FastAPI' in html
    assert 'class="chip' not in html
    assert 'class="badge' not in html


def test_executive_footer_titles_followed_by_their_content():
    html = _render("executive_minimalist", interests=["Randonnée"])
    positions = [
        html.index(">Formation<"),
        html.index("Master Informatique"),
        html.index(">Langues<"),
        html.index("C1 - Professionnel courant"),
        html.index(">Centres d'intérêt<"),
        html.index("Randonnée"),
    ]
    assert positions == sorted(positions)


def test_executive_has_no_black_rule_nor_summary_frame():
    html = _render("executive_minimalist")
    assert "2px solid var(--color-slate-900)" not in html
    assert "border-left: 3px" not in html


def test_badges_are_gone_from_base_css():
    assert ".badge" not in render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE)


def test_classique_never_renders_photo():
    html = render_cv_html(
        cv=SAMPLE_CV,
        candidate=SAMPLE_CANDIDATE,
        template_name="classique",
        with_photo=True,
        photo_url="https://example.com/avatar.jpg",
    )
    assert "<img" not in html
    assert "avatar.jpg" not in html


def test_classique_section_order():
    html = _render("classique", interests=["Football"])
    positions = [
        html.index(">Expérience professionnelle<"),
        html.index(">Projets<"),
        html.index(">Certifications & habilitations<"),
        html.index(">Compétences<"),
        html.index(">Formation<"),
        html.index(">Langues<"),
        html.index(">Centres d'intérêt<"),
    ]
    assert positions == sorted(positions)


def test_classique_skills_as_plain_text_lines():
    assert "<strong>Backend</strong> : Python · FastAPI · Go" in _render("classique")


def test_classique_uses_grey_bands_and_accent_only_on_name():
    html = _render("classique")
    assert '<h2 class="cl-band">' in html
    assert ".cl-band" in html and "var(--color-slate-100)" in html


def test_registry_lists_four_templates_in_display_order():
    assert CV_TEMPLATES == ("sidebar_elegance", "executive_minimalist", "classique", "creatif")


def test_creatif_shows_photo_or_monogram():
    with_photo = render_cv_html(
        cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE, template_name="creatif",
        with_photo=True, photo_url="https://example.com/avatar.jpg",
    )
    assert 'class="avatar-img"' in with_photo
    assert "<canvas" not in with_photo
    without = _render("creatif")
    assert "<img" not in without
    assert '<canvas class="monogram"' in without


def test_creatif_titles_sit_in_left_gutter():
    html = _render("creatif")
    assert '<h2 class="cr-title">Expérience professionnelle</h2>' in html
    assert "grid-template-columns: 31mm 1fr" in html


def test_creatif_footer_titles_followed_by_their_content():
    html = _render("creatif", interests=["Randonnée"])
    positions = [
        html.index(">Formation<"),
        html.index("Master Informatique"),
        html.index(">Langues<"),
        html.index("C1 - Professionnel courant"),
        html.index(">Centres d'intérêt<"),
        html.index("Randonnée"),
    ]
    assert positions == sorted(positions)


def _dated_job(title, start, end):
    return TailoredExperienceItem(title=title, company="Société", start_date=start, end_date=end)


@pytest.mark.parametrize("template", TEMPLATES)
def test_experiences_rendered_most_recent_first(template):
    # Ordre et formats tels que le LLM les renvoie (cf. CV stockés) : mois optionnel, séparateurs variés.
    cv = SAMPLE_CV.model_copy(update={"experiences": [
        _dated_job("Poste 2023", "2023-02", "2024-06"),
        _dated_job("Poste 2019", "2019", "2020"),
        _dated_job("Poste 2025", "08/2025", "Présent"),
        _dated_job("Poste 2021", "sept. 2021", "2022"),
        _dated_job("Poste 2022", "2022-09", "02/2023"),
    ]})
    html = _render(template, cv=cv)
    positions = [html.index(f"Poste {year}") for year in (2025, 2023, 2022, 2021, 2019)]
    assert positions == sorted(positions)


@pytest.mark.parametrize("template", TEMPLATES)
def test_experience_dates_show_years_only(template):
    cv = SAMPLE_CV.model_copy(update={"experiences": [
        _dated_job("Poste actuel", "08/2025", "Présent"),
        _dated_job("Poste passé", "2023-02", "2024-06"),
        _dated_job("Poste ancien", "sept. 2019", "mars 2021"),
    ]})
    html = _render(template, cv=cv)
    assert "2025 – Présent" in html
    assert "2023 – 2024" in html
    assert "2019 – 2021" in html
    assert "08/2025" not in html and "2023-02" not in html and "sept." not in html


def test_same_start_puts_current_job_first():
    cv = SAMPLE_CV.model_copy(update={"experiences": [
        _dated_job("Poste terminé", "2022-01", "2023-06"),
        _dated_job("Poste actuel", "2022-01", "Présent"),
    ]})
    html = _render("classique", cv=cv)
    assert html.index("Poste actuel") < html.index("Poste terminé")


def test_undated_experiences_keep_their_order_after_dated_ones():
    cv = SAMPLE_CV.model_copy(update={"experiences": [
        _dated_job("Sans date A", "", None),
        _dated_job("Poste daté", "2020", "2021"),
        _dated_job("Sans date B", "n.c.", None),
    ]})
    html = _render("classique", cv=cv)
    assert html.index("Poste daté") < html.index("Sans date A") < html.index("Sans date B")






