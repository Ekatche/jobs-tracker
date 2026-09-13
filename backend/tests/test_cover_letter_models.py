import pytest
from datetime import datetime, timezone
from app.models import (
    CandidateProfile,
    CandidateExperience,
    CandidateAchievement,
    CandidateProject,
    CoverLetter,
    CoverLetterVersion,
)

def test_candidate_profile_schema_valid():
    prof = CandidateProfile(
        user_id="60c72b2f9b1d8b2bad7f9999",
        headline="Senior Data Engineer",
        summary="Spécialiste pipelines MLOps et data streaming",
        experiences=[
            CandidateExperience(
                company="Biomérieux",
                role="Data Engineer",
                contract="CDI",
                start="2022",
                end=None,
                sector="biopharma",
                missions=["Conception pipelines Nextflow"],
                achievements=[CandidateAchievement(text="Réduction temps de calcul", metric="50%")],
                stack=["Nextflow", "Python", "Docker"]
            )
        ],
        projects=[
            CandidateProject(
                name="Sentinel",
                description="Moteur de détection",
                stack=["Rust", "DuckDB"],
                context="perso"
            )
        ]
    )
    assert prof.experiences[0].end is None
    assert prof.experiences[0].achievements[0].metric == "50%"
    assert prof.projects[0].context == "perso"

def test_cover_letter_version_and_document_schema():
    version = CoverLetterVersion(
        n=1,
        body="Madame, Monsieur...",
        origin="generated",
        models={"analyst": "gemini-3.8-flash", "writer": "gpt-5.6-sol", "critic": "mistral-large-3-0"},
        prompt_version="2026-09-13.v1",
        guard_report={"is_blocking": False, "violations": []},
        critic_verdict={"verdict": "pass", "flaws": []},
        revised=False,
    )
    doc = CoverLetter(
        user_id="60c72b2f9b1d8b2bad7f9999",
        application_id="60c72b2f9b1d8b2bad7f8888",
        status="ready",
        versions=[version],
        current_version=1,
    )
    assert doc.status == "ready"
    assert len(doc.versions) == 1
    assert doc.versions[0].origin == "generated"
