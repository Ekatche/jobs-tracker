import pytest
from app.models import (
    TailoredCVSchema,
    TailoredExperienceItem,
    TailoredProjectItem,
    TailoredSkillGroup,
    TailoredEducationItem,
    TailoredLanguage,
)
from app.services.cv_guards import verify_cv_honesty


def test_verify_cv_honesty_valid():
    source_profile = {
        "experiences": [
            {"company": "Deloitte", "title": "Data Scientist", "description": "Consulting"}
        ],
        "education": [
            {"degree": "Master IA", "school": "Centrale Lyon"}
        ],
        "skills": ["Python", "PyTorch", "Docker", "SQL"],
    }
    tailored = TailoredCVSchema(
        target_role_title="Senior AI Engineer",
        professional_summary="Impact-driven AI engineer with proven track record in production LLMs.",
        prioritized_skills=[
            TailoredSkillGroup(category="AI & ML", skills=["Python", "PyTorch"]),
            TailoredSkillGroup(category="Infra", skills=["Docker"]),
        ],
        experiences=[
            TailoredExperienceItem(
                title="Data Scientist",
                company="Deloitte",
                start_date="2022",
                end_date="Présent",
                bullet_points=[
                    "Built high-throughput LLM service delivering 35% lower latency.",
                    "Coached 3 junior engineers on PyTorch best practices.",
                ],
                relevant_technologies=["Python", "PyTorch"],
            )
        ],
        featured_projects=[
            TailoredProjectItem(
                name="RAG Assistant",
                description="FastAPI + PyTorch assistant",
                technologies=["Python", "PyTorch"],
            )
        ],
        education=[
            TailoredEducationItem(
                degree="Master IA",
                institution="Centrale Lyon",
                year="2022",
            )
        ],
        languages=[
            TailoredLanguage(language="Français", level="Natif"),
            TailoredLanguage(language="Anglais", level="C1 - Professionnel"),
        ],
        certifications=[],
    )
    is_valid, violations = verify_cv_honesty(tailored, source_profile)
    assert is_valid is True
    assert len(violations) == 0


def test_verify_cv_honesty_with_missions_and_stack_extraction():
    source_profile = {
        "experiences": [
            {
                "company": "Tech Corp",
                "role": "Data Engineer",
                "stack": ["Python", "FastAPI", "Microsoft Fabric", "Power BI"],
                "missions": [
                    "Développement d'APIs REST exposant des services de données.",
                    "Création de tableaux de bord Power BI et de modèles sémantiques.",
                ],
            }
        ],
        "projects": [
            {
                "name": "DataHub",
                "stack": ["PostgreSQL", "Next.js"],
                "description": "Optimisation de pipelines multi-sources pour des analyses avancées.",
            }
        ],
        "skills": {
            "technical_skills": ["Data Modeling", "ETL/ELT"],
        },
        "education": [
            {"degree": "Ingénieur", "institution": "Polytech"}
        ],
    }
    tailored = TailoredCVSchema(
        target_role_title="Lead Data Engineer",
        professional_summary="Ingénieur data spécialisé en API et modélisation.",
        prioritized_skills=[
            TailoredSkillGroup(
                category="Backend",
                skills=["Conception d'APIs REST", "FastAPI", "Python"],
            ),
            TailoredSkillGroup(
                category="Data & BI",
                skills=["Modélisation de données", "Pipelines multi-sources", "Modèles sémantiques"],
            ),
        ],
        experiences=[
            TailoredExperienceItem(
                title="Data Engineer",
                company="Tech Corp",
                start_date="2023",
                end_date="Présent",
                bullet_points=["Built REST APIs and semantic models."],
                relevant_technologies=["Python", "FastAPI"],
            )
        ],
        featured_projects=[
            TailoredProjectItem(
                name="DataHub",
                description="Pipelines multi-sources",
                technologies=["PostgreSQL"],
            )
        ],
        education=[
            TailoredEducationItem(
                degree="Ingénieur",
                institution="Polytech",
                year="2022",
            )
        ],
        languages=[],
        certifications=[],
    )
    is_valid, violations = verify_cv_honesty(tailored, source_profile)
    assert is_valid is True
    assert len(violations) == 0


def test_verify_cv_honesty_flags_invented_company_and_skills():
    source_profile = {
        "experiences": [
            {"company": "Deloitte", "title": "Data Scientist"}
        ],
        "education": [
            {"degree": "Master IA", "school": "Centrale Lyon"}
        ],
        "skills": ["Python", "PyTorch"],
    }
    hallucinated = TailoredCVSchema(
        target_role_title="Senior AI Engineer",
        professional_summary="...",
        prioritized_skills=[
            TailoredSkillGroup(category="AI", skills=["Python", "UnknownImaginaryFramework"]),
        ],
        experiences=[
            TailoredExperienceItem(
                title="VP Engineering",
                company="Google DeepFake Labs",  # Invented company
                start_date="2020",
                end_date="2022",
                bullet_points=["Invented quantum AGI"],
            )
        ],
        featured_projects=[],
        education=[
            TailoredEducationItem(
                degree="PhD Quantum Computing",  # Invented degree
                institution="MIT Fake",
                year="2019",
            )
        ],
        languages=[],
    )
    is_valid, violations = verify_cv_honesty(hallucinated, source_profile)
    assert is_valid is False
    assert any("Google DeepFake Labs" in v for v in violations)
    assert any("UnknownImaginaryFramework" in v for v in violations)
    assert any("MIT Fake" in v or "PhD Quantum Computing" in v for v in violations)
