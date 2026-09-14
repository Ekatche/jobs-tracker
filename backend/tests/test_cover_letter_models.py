import pytest
from datetime import datetime, timezone
from app.models import (
    CandidateProfile,
    CandidateExperience,
    CandidateAchievement,
    CandidateProject,
    CoverLetter,
    CoverLetterVersion,
    CandidateConflict,
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


def test_profile_accepts_sources_and_conflicts():
    profile = CandidateProfile(
        user_id="60c72b2f9b1d8b2bad7f9999",
        sources={"cv": {"headline": "Ingénieur Data"}, "github": {"projects": []}},
        conflicts=[
            CandidateConflict(
                company="Agence Nile",
                field="role",
                kept="Data Engineer",
                kept_source="cv",
                discarded="Lead Data Engineer",
                discarded_source="website",
            )
        ],
    )
    assert set(profile.sources) == {"cv", "github"}
    assert profile.conflicts[0].field == "role"


def test_experience_carries_alternate_missions_and_sources():
    profile = CandidateProfile(
        user_id="60c72b2f9b1d8b2bad7f9999",
        experiences=[
            {
                "company": "Agence Nile",
                "role": "Data Engineer",
                "start": "2025-08",
                "missions": ["RAG Qdrant"],
                "missions_alt": ["Agents LLM"],
                "missions_source": "website",
                "sources": ["cv", "website"],
            }
        ],
    )
    assert profile.experiences[0].missions_alt == ["Agents LLM"]
    assert profile.experiences[0].sources == ["cv", "website"]


def test_provenance_accepts_every_collector():
    for source in ("cv", "github", "website", "manual"):
        profile = CandidateProfile(
            user_id="60c72b2f9b1d8b2bad7f9999",
            provenance=[{"field_path": "experiences.0", "source": source}],
        )
        assert profile.provenance[0].source == source
