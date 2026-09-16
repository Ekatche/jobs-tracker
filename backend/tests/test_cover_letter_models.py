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
from app.services.profile.merge import build_profile_from_sources

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


def test_merge_producer_output_validates_with_missing_fields():
    """Test that the merge producer's output is accepted by CandidateProfile.

    Covers critical cases:
    - Experience where no source supplies 'role' → merge outputs None
    - Project with empty description from one source, non-empty from another
    - Round-trip: model_dump() preserves all keys the merge produced
    """
    sources = {
        "cv": {
            "headline": "Senior Data Engineer",
            "experiences": [
                {
                    "company": "TechCorp",
                    "start": "2023-01",
                    "location": "Paris",
                    "missions": ["Build pipelines"],
                    "stack": ["Python", "Airflow"],
                }
                # Note: no 'role' in CV
            ],
            "projects": [
                {
                    "name": "DataLake",
                    "description": "Central data repository",
                    "stack": ["Spark"],
                }
            ],
            "education": [],
            "certifications": [],
        },
        "website": {
            "headline": "Data Expert",
            "experiences": [
                {
                    "company": "TechCorp",
                    "start": "2023-01",  # Same as CV so they merge
                    # Note: no 'role' in website either — merge will emit role=None
                    "missions": ["Design infrastructure"],
                    "stack": ["AWS"],
                }
            ],
            "projects": [
                {
                    "name": "DataLake",
                    "description": "",  # empty description (will prefer CV's)
                    "stack": ["Kubernetes"],
                }
            ],
            "education": [],
            "certifications": [],
        },
    }

    # Call real producer
    profile_dict, conflicts = build_profile_from_sources(sources)

    # This is where the bug was: model_validate would fail if role: str = ""
    # because merge outputs role: None when no source supplies it
    profile = CandidateProfile.model_validate({
        "user_id": "60c72b2f9b1d8b2bad7f9999",
        **profile_dict
    })

    # Verify critical fields exist and validate type
    assert profile.experiences, "Should have merged experience"
    exp = profile.experiences[0]
    assert exp.company == "TechCorp"
    assert exp.role is None, "Role should be None when no source supplies it (CV didn't have it)"
    assert exp.start == "2023-01"
    assert exp.location == "Paris"
    assert "Build pipelines" in exp.missions
    assert exp.missions_source == "cv"
    assert set(exp.sources) == {"cv", "website"}

    # Verify project merged from both sources
    assert profile.projects, "Should have merged projects"
    proj = profile.projects[0]
    assert proj.name == "DataLake"
    assert proj.description, "Should use non-empty description from cv"
    assert set(proj.sources) == {"cv", "website"}

    # Critical: round-trip preservation - all keys that merge produced are still there
    dumped = profile.model_dump()
    assert dumped["headline"] == "Senior Data Engineer"
    assert dumped["experiences"][0]["company"] == "TechCorp"
    assert dumped["experiences"][0]["role"] is None, "role must be None, not absent"
    assert dumped["experiences"][0]["missions_source"] is not None
    assert dumped["experiences"][0]["sources"] == ["cv", "website"]
    assert dumped["projects"][0]["sources"] == ["cv", "website"]


def test_provenance_accepts_every_collector():
    for source in ("cv", "github", "website", "manual"):
        profile = CandidateProfile(
            user_id="60c72b2f9b1d8b2bad7f9999",
            provenance=[{"field_path": "experiences.0", "source": source}],
        )
        assert profile.provenance[0].source == source
