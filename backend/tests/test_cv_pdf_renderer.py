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
