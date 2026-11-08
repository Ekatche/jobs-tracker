from app.services.profile.merge import build_profile_from_sources
from tests.profile_merge.fixtures import CV


def test_education_entry_only_in_one_source_survives_merge():
    cv_education = {"education": [{"school": "Ecole X", "degree": "Master"}]}
    website_education = {"education": [{"school": "Ecole Y", "degree": "Licence"}]}
    profile, _ = build_profile_from_sources(
        {"cv": cv_education, "website": website_education}
    )
    schools = {e["school"] for e in profile["education"]}
    assert schools == {"Ecole X", "Ecole Y"}


def test_certification_entry_only_in_one_source_survives_merge():
    cv_certifications = {"certifications": [{"name": "AWS Certified"}]}
    website_certifications = {"certifications": [{"name": "Azure Fundamentals"}]}
    profile, _ = build_profile_from_sources(
        {"cv": cv_certifications, "website": website_certifications}
    )
    names = {c["name"] for c in profile["certifications"]}
    assert names == {"AWS Certified", "Azure Fundamentals"}


def test_education_merges_with_institution_and_dates_keys():
    """Vérifie que les formations avec 'institution' et 'dates' (CV) sont bien intégrées et normalisées."""
    cv_payload = {
        "education": [
            {
                "degree": "Spécialisation en Intelligence Artificielle",
                "institution": "CNAM Lyon",
                "dates": "2024 - 2025",
                "details": "Outils mathématiques pour l'optimisation numérique, IA avancée, IA pour données multimédias.",
            },
            {
                "degree": "Master Data Science",
                "institution": "Nexa Digital School Lyon",
                "dates": "2022",
                "details": "Algèbre linéaire, statistiques, machine learning, NLP, computer vision, big data.",
            },
        ]
    }
    profile, _ = build_profile_from_sources({"cv": cv_payload})
    assert len(profile["education"]) == 2
    cnam = next(e for e in profile["education"] if "cnam" in e["school"].lower())
    assert cnam["school"] == "CNAM Lyon"
    assert cnam["degree"] == "Spécialisation en Intelligence Artificielle"
    assert cnam["years"] == "2024 - 2025"
    assert any("optimisation numérique" in t for t in cnam["topics"])

    nexa = next(e for e in profile["education"] if "nexa" in e["school"].lower())
    assert nexa["school"] == "Nexa Digital School Lyon"
    assert nexa["years"] == "2022"
    assert any("machine learning" in t for t in nexa["topics"])


def test_education_deduplicates_and_merges_across_sources():
    """Une même école/diplôme présent dans plusieurs sources fusionne les informations sans doublon."""
    cv_payload = {
        "education": [
            {
                "institution": "CNAM Lyon",
                "degree": "Spécialisation IA",
                "dates": "2024 - 2025",
                "details": "IA avancée",
            }
        ]
    }
    website_payload = {
        "education": [
            {
                "school": "CNAM Lyon",
                "degree": "Spécialisation IA",
                "topics": ["Deep Learning", "Vision par ordinateur"],
            }
        ]
    }
    profile, _ = build_profile_from_sources({"cv": cv_payload, "website": website_payload})
    assert len(profile["education"]) == 1
    item = profile["education"][0]
    assert item["school"] == "CNAM Lyon"
    assert item["years"] == "2024 - 2025"
    assert "IA avancée" in item["topics"]
    assert "Deep Learning" in item["topics"]


def test_education_merges_with_loose_school_names_and_degree_enrichment():
    """Vérifie que les variations de nom d'école et de diplôme fusionnent en une seule entrée enrichie."""
    cv_payload = {
        "education": [
            {
                "school": "Université Claude Bernard Lyon 1",
                "degree": "Master Informatique",
                "years": "2023 - 2025",
                "topics": ["Bases de données"],
            }
        ]
    }
    website_payload = {
        "education": [
            {
                "school": "Université Lyon 1",
                "degree": "Master en Informatique / Data Science & IA",
                "years": "2025",
                "topics": ["Machine Learning", "Deep Learning"],
            }
        ]
    }
    profile, _ = build_profile_from_sources({"cv": cv_payload, "website": website_payload})
    assert len(profile["education"]) == 1
    edu = profile["education"][0]
    # L'école la plus complète est retenue
    assert edu["school"] == "Université Claude Bernard Lyon 1"
    # Le diplôme le plus descriptif et riche est retenu
    assert edu["degree"] == "Master en Informatique / Data Science & IA"
    # La période complète (intervalle) est retenue
    assert edu["years"] == "2023 - 2025"
    # Les compétences / sujets sont combinés sans doublon
    assert "Bases de données" in edu["topics"]
    assert "Machine Learning" in edu["topics"]
    assert "Deep Learning" in edu["topics"]


def test_education_does_not_merge_different_levels_same_school():
    """Deux niveaux de diplômes différents (Licence vs Master) à la même école ne doivent pas être fusionnés."""
    cv_payload = {
        "education": [
            {
                "school": "Université Lyon 1",
                "degree": "Licence Mathématiques & Informatique",
                "years": "2020 - 2023",
            }
        ]
    }
    website_payload = {
        "education": [
            {
                "school": "Université Lyon 1",
                "degree": "Master Data Science",
                "years": "2023 - 2025",
            }
        ]
    }
    profile, _ = build_profile_from_sources({"cv": cv_payload, "website": website_payload})
    assert len(profile["education"]) == 2
    degrees = {e["degree"] for e in profile["education"]}
    assert "Licence Mathématiques & Informatique" in degrees
    assert "Master Data Science" in degrees


def test_education_does_not_merge_distinct_diplomas_from_same_source():
    """Deux diplômes listés dans la même source ne doivent jamais fusionner entre eux."""
    cv_payload = {
        "education": [
            {"school": "CNAM", "degree": "Spécialisation IA", "years": "2024"},
            {"school": "CNAM", "degree": "Spécialisation Data", "years": "2025"},
        ]
    }
    profile, _ = build_profile_from_sources({"cv": cv_payload})
    assert len(profile["education"]) == 2


def test_education_tracks_conflicts_for_divergent_degrees():
    """Une divergence notable entre deux sources sur un même diplôme est tracée dans conflicts."""
    cv_payload = {
        "education": [
            {
                "school": "CNAM Lyon",
                "degree": "Diplôme d'Ingénieur en Informatique",
                "years": "2022 - 2025",
            }
        ]
    }
    website_payload = {
        "education": [
            {
                "school": "CNAM",
                "degree": "Diplôme d'Ingénieur Big Data",
                "years": "2022 - 2025",
            }
        ]
    }
    profile, conflicts = build_profile_from_sources({"cv": cv_payload, "website": website_payload})
    assert len(profile["education"]) == 1
    degree_conflicts = [c for c in conflicts if c.get("field") == "degree"]
    assert len(degree_conflicts) >= 1
    assert degree_conflicts[0]["kept"] == "Diplôme d'Ingénieur en Informatique"
    assert degree_conflicts[0]["discarded"] == "Diplôme d'Ingénieur Big Data"
