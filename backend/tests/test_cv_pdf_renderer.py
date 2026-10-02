import io
import pdfplumber
import pytest

from app.models import (
    TailoredCVSchema,
    TailoredExperienceItem,
    TailoredSkillGroup,
    TailoredLanguage,
    TailoredEducationItem,
)
from app.services.cv_pdf_renderer import generate_cv_pdf
from app.services.cv_templates import render_cv_html


@pytest.mark.asyncio
async def test_generate_cv_pdf_produces_selectable_vector_pdf():
    cv = TailoredCVSchema(
        target_role_title="Senior Python Architect",
        professional_summary="Expert en architectures résilientes et microservices distribués.",
        prioritized_skills=[
            TailoredSkillGroup(category="Backend", skills=["Python", "FastAPI", "Docker"])
        ],
        experiences=[
            TailoredExperienceItem(
                title="Lead Developer",
                company="Vector Tech Europe",
                location="Paris",
                start_date="2021",
                end_date="Présent",
                bullet_points=[
                    "Développement d'un système de streaming temps réel.",
                    "Gestion d'une infrastructure conteneurisée sur AWS."
                ],
                relevant_technologies=["Python", "AWS"]
            )
        ],
        featured_projects=[],
        education=[
            TailoredEducationItem(degree="Ingénieur", institution="Polytechnique", year="2018")
        ],
        languages=[
            TailoredLanguage(language="Français", level="Natif")
        ],
        certifications=[]
    )

    candidate = {
        "full_name": "Éléonore Martin",
        "email": "eleonore.martin@tech.fr",
        "phone": "+33 6 98 76 54 32",
        "location": "Paris, France",
    }

    html = render_cv_html(
        cv=cv,
        candidate=candidate,
        template_name="sidebar_elegance",
        with_photo=False
    )

    pdf_bytes = await generate_cv_pdf(html)

    # 1. Verify standard PDF magic header
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")

    # 2. Verify vector selectable text extraction via pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        assert len(pdf.pages) >= 1
        first_page = pdf.pages[0]
        extracted_text = first_page.extract_text()

        assert "Éléonore Martin" in extracted_text or "Eleonore Martin" in extracted_text
        assert "Senior Python Architect" in extracted_text
        assert "Vector Tech Europe" in extracted_text
        assert "Français" in extracted_text


import asyncio
import re
from functools import lru_cache

import pymupdf

from app.models import TailoredProjectItem
from app.services.cv_templates import CV_TEMPLATES, SECTION_TITLES

ATS_TEMPLATES = list(CV_TEMPLATES)
EMOJI_OR_PRIVATE_USE = re.compile("[\U0001F000-\U0001FAFF☀-➿-]")
JOB_COUNT = 6

ATS_CANDIDATE = {
    "full_name": "Jean Dupont",
    "email": "jean.dupont@email.com",
    "phone": "+33 6 12 34 56 78",
    "location": "Lyon, France",
    "linkedin_url": "https://linkedin.com/in/jeandupont",
    "github_url": "https://github.com/jeandupont",
    "website_url": "https://jeandupont.fr",
    "mobility": "Permis B, véhiculé",
    "availability": "Disponible immédiatement",
    "interests": ["Football", "Randonnée", "Photographie"],
}


def _job(i):
    return TailoredExperienceItem(
        title=f"Poste numéro {i}",
        company=f"Entreprise {i}",
        location="Lyon",
        start_date=str(2010 + 2 * i),
        end_date=str(2012 + 2 * i),
        bullet_points=[
            f"Réalisation {i}.{j} : pilotage d'un chantier de modernisation avec une équipe "
            "pluridisciplinaire, suivi des indicateurs et amélioration continue des processus."
            for j in range(1, 5)
        ],
        # Outils distincts des compétences : « Python · FastAPI » ne peut venir que des pastilles.
        relevant_technologies=["SAP", "Excel"],
    )


ATS_CV = TailoredCVSchema(
    target_role_title="Responsable des opérations",
    professional_summary=(
        "Responsable des opérations, douze ans d'expérience en pilotage d'équipes et en "
        "amélioration continue, habitué aux environnements multisites."
    ),
    prioritized_skills=[
        TailoredSkillGroup(category="Technique", skills=["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL", "Redis"]),
        TailoredSkillGroup(category="Gestion", skills=["Planification", "Budget", "Recrutement", "Animation d'équipe"]),
    ],
    experiences=[_job(i) for i in range(1, JOB_COUNT + 1)],
    featured_projects=[
        TailoredProjectItem(
            name="Refonte logistique",
            description="Réorganisation des flux d'un entrepôt de 20 000 m².",
            technologies=["Airflow", "Tableau"],
        )
    ],
    education=[TailoredEducationItem(degree="Master Management", institution="IAE Lyon", year="2010")],
    languages=[
        TailoredLanguage(language="Anglais", level="C1"),
        TailoredLanguage(language="Allemand", level="B2"),
    ],
    certifications=["Auditeur certifié ISO 9001", "Sauveteur Secouriste du Travail"],
)


def _normalize(text):
    return " ".join(text.split())


@lru_cache(maxsize=None)
def _extract(template):
    """Texte par page : pdfplumber (ordre de lecture visuel) et pymupdf (ordre du flux, donc du DOM)."""
    html = render_cv_html(cv=ATS_CV, candidate=ATS_CANDIDATE, template_name=template)
    pdf_bytes = asyncio.run(generate_cv_pdf(html))
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = tuple(page.extract_text() or "" for page in pdf.pages)
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        flow = tuple(page.get_text(sort=False) for page in doc)
    return pages, flow


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_name_is_first_line(template):
    pages, _ = _extract(template)
    lines = [line.strip() for line in pages[0].splitlines() if line.strip()]
    assert lines[0] == "Jean Dupont"


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_profile_fills_two_pages(template):
    pages, _ = _extract(template)
    assert len(pages) >= 2


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_standard_section_titles_extracted(template):
    pages, _ = _extract(template)
    text = _normalize(" ".join(pages)).casefold()
    assert [t for t in SECTION_TITLES.values() if t.casefold() not in text] == []


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_skills_separated_in_text(template):
    pages, _ = _extract(template)
    text = _normalize(" ".join(pages))
    assert "Python · FastAPI" in text
    assert "PythonFastAPI" not in text


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_no_side_column_line_inside_a_job(template):
    _, flow = _extract(template)
    text = _normalize(" ".join(flow))
    for i in range(1, JOB_COUNT + 1):
        start = text.index(f"Poste numéro {i}")
        block = text[start:text.index(f"Réalisation {i}.4", start)]
        assert "jean.dupont@email.com" not in block
        assert "Allemand" not in block


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_no_ligature_glyph(template):
    pages, _ = _extract(template)
    text = _normalize(" ".join(pages))
    assert "ﬁ" not in text and "ﬂ" not in text
    assert "certifié" in text.casefold()


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_monogram_initials_not_extracted(template):
    pages, _ = _extract(template)
    assert "JD" not in {line.strip() for page in pages for line in page.splitlines()}


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_no_emoji_or_private_use_glyph(template):
    pages, _ = _extract(template)
    assert not EMOJI_OR_PRIVATE_USE.search(" ".join(pages))


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_job_title_and_first_bullet_on_same_page(template):
    pages, _ = _extract(template)
    flat = [_normalize(page) for page in pages]
    for i in range(1, JOB_COUNT + 1):
        title_page = next(n for n, page in enumerate(flat) if f"Poste numéro {i}" in page)
        bullet_page = next(n for n, page in enumerate(flat) if f"Réalisation {i}.1" in page)
        assert title_page == bullet_page


# (postes, puces ajoutées au dernier) : sans « break-after: avoid », « Compétences » finit la page 1.
ORPHAN_TITLE_LAYOUTS = {"executive_minimalist": (4, 5), "classique": (3, 5), "creatif": (4, 5)}


@pytest.mark.parametrize("template", ORPHAN_TITLE_LAYOUTS)
def test_section_title_never_ends_a_page(template):
    jobs, extra = ORPHAN_TITLE_LAYOUTS[template]
    last = _job(jobs)
    last = last.model_copy(update={"bullet_points": last.bullet_points + ["Ligne de remplissage."] * extra})
    cv = ATS_CV.model_copy(update={"experiences": [_job(i) for i in range(1, jobs)] + [last]})
    pdf_bytes = asyncio.run(generate_cv_pdf(render_cv_html(cv=cv, candidate=ATS_CANDIDATE, template_name=template)))
    titles = {t.casefold() for t in SECTION_TITLES.values()}
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        lines = [(n, line.strip()) for n, page in enumerate(doc)
                 for line in page.get_text(sort=False).splitlines() if line.strip()]
    orphans = [t for (p, t), (q, _) in zip(lines, lines[1:]) if t.casefold() in titles and p != q]
    assert orphans == []

