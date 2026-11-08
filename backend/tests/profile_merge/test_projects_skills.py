from app.services.profile.merge import build_profile_from_sources
from tests.profile_merge.fixtures import CV, WEBSITE


def test_projects_are_unioned_not_replaced():
    """Le bug mesuré le 2026-09-14 : WideDocs disparaissait au profit de Sentinel."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    names = {p["name"] for p in profile["projects"]}
    assert names == {"WideDocs", "Sentinel"}


def test_skills_are_unioned_by_category_across_sources():
    cv_skills = {"skills": {"languages": ["Python"]}}
    website_skills = {"skills": {"languages": ["SQL"], "tools": ["Docker"]}}
    profile, _ = build_profile_from_sources({"cv": cv_skills, "website": website_skills})
    assert profile["skills"]["languages"] == ["Python", "SQL"]
    assert profile["skills"]["tools"] == ["Docker"]


def test_projects_merge_preserves_repo_context_and_highlights():
    """Tous les attributs des projets scrappés ou manuels (repo, context, highlights) sont conservés."""
    site_payload = {
        "projects": [
            {
                "name": "WideDocs",
                "description": "Plateforme documentaire pour avocats.",
                "context": "perso",
                "stack": ["Python", "FastAPI"],
                "url": "https://widedocs.fr/",
                "repo": "https://github.com/Ekatche/widedocs",
                "highlights": ["OCR automatique", "RGPD"],
            }
        ]
    }
    manual_payload = {
        "projects": [
            {
                "name": "WideDocs",
                "description": "Plateforme complète avec IA souveraine.",
                "stack": ["PostgreSQL", "React"],
            }
        ]
    }
    profile, _ = build_profile_from_sources({"manual": manual_payload, "website": site_payload})
    assert len(profile["projects"]) == 1
    proj = profile["projects"][0]
    assert proj["name"] == "WideDocs"
    assert proj["url"] == "https://widedocs.fr/"
    assert proj["repo"] == "https://github.com/Ekatche/widedocs"
    assert proj["context"] == "perso"
    assert "OCR automatique" in proj["highlights"]
    assert "FastAPI" in proj["stack"]
    assert "PostgreSQL" in proj["stack"]


def test_languages_extracted_from_personal_info_and_normalized():
    """Les langues déclarées dans personal_info sous forme d'objets sont normalisées en liste de strings."""
    cv_payload = {
        "personal_info": {
            "languages": [
                {"language": "English", "proficiency": "Fluent"},
                {"language": "Français", "proficiency": "Natif"},
            ]
        }
    }
    profile, _ = build_profile_from_sources({"cv": cv_payload})
    assert "English (Fluent)" in profile["languages"]
    assert "Français (Natif)" in profile["languages"]


def test_projects_deduplicate_across_casing_and_separators():
    """Vérifie que 'Jobs Tracker' et 'jobs-tracker' fusionnent en conservant les métadonnées riches."""
    website_payload = {
        "projects": [
            {
                "name": "Jobs Tracker",
                "description": "Plateforme moderne de suivi des candidatures IA.",
                "context": "perso",
                "stack": ["Next.js", "FastAPI"],
            }
        ]
    }
    github_payload = {
        "projects": [
            {
                "name": "jobs-tracker",
                "description": "Backend and frontend repo",
                "stack": ["Python", "TypeScript"],
                "url": "https://github.com/Ekatche/jobs-tracker",
                "repo": "https://github.com/Ekatche/jobs-tracker",
            }
        ]
    }
    profile, _ = build_profile_from_sources({"website": website_payload, "github": github_payload})
    assert len(profile["projects"]) == 1
    proj = profile["projects"][0]
    # Doit retenir le nom le plus soigné (avec majuscules/espaces)
    assert proj["name"] == "Jobs Tracker"
    # Doit retenir la description la plus informative
    assert "Plateforme moderne" in proj["description"]
    # Doit fusionner les stacks sans doublon
    assert set(proj["stack"]) == {"Next.js", "FastAPI", "Python", "TypeScript"}
    # Doit fusionner le repo GitHub
    assert proj["repo"] == "https://github.com/Ekatche/jobs-tracker"


def test_projects_with_differently_worded_names_are_merged_not_duplicated():
    """Bug du 2026-09-22 : CV et site donnent des libellés différents pour le même projet."""
    cv_payload = {
        "projects": [
            {"name": "Sentinel", "description": "Trading quantitatif.", "stack": ["Python"]},
        ]
    }
    website_payload = {
        "projects": [
            {
                "name": "Sentinel - Plateforme de trading algorithmique",
                "description": "Système de trading automatisé en production.",
                "stack": ["Rust"],
            }
        ]
    }
    profile, _ = build_profile_from_sources({"cv": cv_payload, "website": website_payload})
    assert len(profile["projects"]) == 1
    proj = profile["projects"][0]
    assert set(proj["stack"]) == {"Python", "Rust"}
    assert "Système de trading" in proj["description"]


def test_trivial_projects_and_excluded_projects_are_filtered():
    """Les dépôts triviaux (cv, pytests) et les projets exclus manuellement sont ignorés."""
    sources = {
        "manual": {
            "excluded_projects": ["active-learning"],
        },
        "github": {
            "projects": [
                {"name": "cv", "description": "mon cv html", "stack": ["CSS"]},
                {"name": "pytests", "description": "sandbox tests", "stack": ["Python"]},
                {"name": "Active_learning", "description": "Recherche IA semi-supervisée", "stack": ["PyTorch"]},
                {"name": "WideDocs", "description": "Plateforme juridique IA", "stack": ["FastAPI"]},
            ]
        },
    }
    profile, _ = build_profile_from_sources(sources)
    names = [p["name"] for p in profile["projects"]]
    assert "cv" not in names
    assert "pytests" not in names
    assert "Active_learning" not in names  # Exclu manuellement
    assert "WideDocs" in names
