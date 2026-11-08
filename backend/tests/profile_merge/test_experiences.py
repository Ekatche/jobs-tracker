from app.services.profile.merge import build_profile_from_sources
from tests.profile_merge.fixtures import CV, WEBSITE


def test_same_role_across_sources_is_merged_once():
    """Deux écritures de la même période ne doivent produire qu'une expérience."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    nile = [e for e in profile["experiences"] if "nile" in e["company"].lower()]
    assert len(nile) == 2  # le poste mauricien et le poste lyonnais, pas trois


def test_experience_with_dissimilar_company_wording_is_merged_not_duplicated():
    """Bug du 2026-09-22 : le site nomme l'employeur différemment du CV, même poste."""
    cv_payload = {
        "experiences": [
            {
                "company": "Nile",
                "role": "Data Engineer",
                "start": "2025-08",
                "end": "2026-08",
                "missions": ["Agents LLM en production"],
            }
        ]
    }
    website_payload = {
        "experiences": [
            {
                "company": "Agence Nile Consulting",
                "role": "Data Engineer",
                "start": "2025-08",
                "end": "2026-08",
                "missions": ["RAG with Qdrant", "CRM/ERP sync"],
            }
        ]
    }
    profile, _ = build_profile_from_sources({"cv": cv_payload, "website": website_payload})
    nile = [e for e in profile["experiences"] if "nile" in e["company"].lower()]
    assert len(nile) == 1


def test_experience_absent_from_cv_is_added():
    """Le CV ne contient pas tout : le site apporte les postes manquants."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    companies = {e["company"] for e in profile["experiences"]}
    assert any("bioMérieux" in c or "bioMerieux" in c for c in companies)


def test_open_ended_end_date_is_replaced_by_a_real_one():
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    mauritius = next(
        e for e in profile["experiences"] if e["start"] == "2025-08"
    )
    assert mauritius["end"] == "2026-08"


def test_missions_are_not_duplicated_across_languages():
    """Le bloc le plus fourni gagne ; l'autre reste accessible mais séparé."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    mauritius = next(e for e in profile["experiences"] if e["start"] == "2025-08")
    assert len(mauritius["missions"]) == 3
    assert "Agents LLM en production" in mauritius["missions_alt"]


def test_stack_is_unioned_without_case_duplicates():
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    mauritius = next(e for e in profile["experiences"] if e["start"] == "2025-08")
    lowered = [s.lower() for s in mauritius["stack"]]
    assert lowered.count("python") == 1
    assert {"python", "mistral", "qdrant", "pyspark"} <= set(lowered)


def test_role_divergence_is_reported_as_conflict():
    variant = {
        "experiences": [
            {
                "company": "Agence Nile",
                "role": "Lead Data Engineer",
                "start": "Août 2025",
                "end": "PRESENT",
            }
        ]
    }
    profile, conflicts = build_profile_from_sources({"cv": CV, "website": variant})
    assert any(c["field"] == "role" for c in conflicts)
    assert profile["experiences"][0]["role"] == "Data Engineer"  # cv > website


def test_conflict_attributes_kept_source_correctly_when_top_priority_lacks_the_field():
    """cv is silent on `role` for this post; the value actually came from website,
    not from cv just because cv ranks first in SOURCE_PRIORITY."""
    cv_no_role = {
        "experiences": [
            {"company": "Agence Nile", "start": "Août 2025", "end": "PRESENT"}
        ]
    }
    website = {
        "experiences": [
            {
                "company": "Agence Nile",
                "role": "B",
                "start": "Août 2025",
                "end": "PRESENT",
            }
        ]
    }
    github = {
        "experiences": [
            {
                "company": "Agence Nile",
                "role": "C",
                "start": "Août 2025",
                "end": "PRESENT",
            }
        ]
    }
    profile, conflicts = build_profile_from_sources(
        {"cv": cv_no_role, "website": website, "github": github}
    )
    assert profile["experiences"][0]["role"] == "B"
    role_conflict = next(c for c in conflicts if c["field"] == "role")
    assert role_conflict["kept_source"] == "website"
    assert role_conflict["discarded_source"] == "github"


def test_experience_start_and_end_date_keys_are_normalized():
    """Vérifie que les clés 'start_date' et 'end_date' du CV sont bien prises en compte et normalisées."""
    cv_payload = {
        "experiences": [
            {
                "company": "Agence Nile",
                "role": "Data Engineer",
                "start_date": "August 2025",
                "end_date": "2026",
            },
            {
                "company": "Centre Léon Bérard",
                "role": "Data Scientist",
                "start_date": "Fev 2023",
                "end_date": "June 2024",
            },
        ]
    }
    profile, _ = build_profile_from_sources({"cv": cv_payload})
    assert len(profile["experiences"]) == 2
    nile = next(e for e in profile["experiences"] if "nile" in e["company"].lower())
    assert nile["start"] == "2025-08"
    assert nile["end"] == "2026"

    clb = next(e for e in profile["experiences"] if "bérard" in e["company"].lower() or "berard" in e["company"].lower())
    assert clb["start"] == "2023-02"
    assert clb["end"] == "2024-06"


def test_experience_reconciliation_fills_missing_start_from_other_source():
    """Si une entrée manuelle a start: None, la source CV fournit la date réelle sans créer de doublon."""
    manual_payload = {
        "experiences": [
            {
                "company": "Agence Nile",
                "role": "Lead Data Engineer",
                "start": None,
                "end": None,
            }
        ]
    }
    cv_payload = {
        "experiences": [
            {
                "company": "Agence Nile",
                "role": "Data Engineer",
                "start_date": "August 2025",
                "end_date": "2026",
            }
        ]
    }
    profile, _ = build_profile_from_sources({"manual": manual_payload, "cv": cv_payload})
    assert len(profile["experiences"]) == 1
    exp = profile["experiences"][0]
    assert exp["role"] == "Lead Data Engineer"  # manual > cv
    assert exp["start"] == "2025-08"            # cv supplied missing start
    assert exp["end"] == "2026"                 # cv supplied missing end
    assert set(exp["sources"]) == {"manual", "cv"}


def test_full_eight_experiences_from_portfolio_are_preserved():
    """Toutes les expériences du portfolio (tech et non-tech, anciennes) sont conservées lors du merge."""
    sources = {
        "cv": {
            "experiences": [
                {"company": "Agence Nile (VIE)", "role": "Data Engineer", "start": "2025-08", "end": "2026-08"},
                {"company": "Centre Léon Bérard", "role": "Data Scientist", "start": "2023-02", "end": "2024-06"},
            ]
        },
        "website": {
            "experiences": [
                {"company": "Agence Nile (CDI)", "role": "Data Engineer", "start": "2026-08", "end": None},
                {"company": "Agence Nile (VIE)", "role": "Data Engineer", "start": "2025-08", "end": "2026-08"},
                {"company": "Centre Léon Bérard", "role": "Data Scientist", "start": "2023-02", "end": "2024-06"},
                {"company": "Nodya Group", "role": "Data Scientist / Consultant", "start": "2022-10", "end": "2023-02"},
                {"company": "Bimedoc", "role": "Data Scientist / Data Engineer", "start": "2021-09", "end": "2022"},
                {"company": "bioMérieux", "role": "Data Analyst Supply Chain", "start": "2021-03", "end": "2021-09"},
                {"company": "Sanofi Aventis Group", "role": "Assistant Achats Globaux", "start": "2019", "end": "2020"},
                {"company": "Framatome", "role": "Acheteur Équipements", "start": "2018", "end": "2019"},
            ]
        }
    }
    profile, _ = build_profile_from_sources(sources)
    assert len(profile["experiences"]) == 8
    companies = [e["company"] for e in profile["experiences"]]
    assert any("Sanofi" in c for c in companies)
    assert any("Framatome" in c for c in companies)
    assert any("bioMérieux" in c or "bioMerieux" in c for c in companies)
    assert any("Bimedoc" in c for c in companies)
    nile_exps = [e for e in profile["experiences"] if "nile" in e["company"].lower()]
    assert len(nile_exps) == 2


def test_multiple_roles_at_same_company_same_source_not_collapsed():
    """Deux rôles au sein de la même entreprise dans une même source ne doivent jamais être fusionnés."""
    sources = {
        "website": {
            "experiences": [
                {"company": "Entreprise X", "role": "Junior Engineer", "start": "2020-01", "end": "2021-01"},
                {"company": "Entreprise X", "role": "Senior Engineer", "start": "2021-01", "end": None},
            ]
        }
    }
    profile, _ = build_profile_from_sources(sources)
    assert len(profile["experiences"]) == 2
    roles = {e["role"] for e in profile["experiences"]}
    assert roles == {"Junior Engineer", "Senior Engineer"}
