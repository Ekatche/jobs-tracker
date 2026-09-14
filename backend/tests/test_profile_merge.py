from app.services.profile.merge import build_profile_from_sources

CV = {
    "headline": "Ingénieur Data & IA",
    "summary": "Résumé issu du CV.",
    "experiences": [
        {
            "company": "AGENCE NILE, VIE - Ile Maurice",
            "role": "Data Engineer",
            "start": "Août 2025",
            "end": "PRESENT",
            "missions": ["Agents LLM en production", "Pipelines ETL/ELT Azure"],
            "stack": ["Python", "Mistral"],
        }
    ],
    "projects": [{"name": "WideDocs", "description": "Plateforme documentaire."}],
}

WEBSITE = {
    "summary": "Résumé issu du site.",
    "experiences": [
        {
            "company": "Agence Nile(Mauritius — International Assignment (VIE))",
            "role": "Data Engineer",
            "start": "Aug. 2025",
            "end": "Aug. 2026",
            "missions": ["RAG with Qdrant", "CRM/ERP sync", "PySpark medallion pipeline"],
            "stack": ["Qdrant", "PySpark", "python"],
        },
        {
            "company": "Agence Nile(Lyon, France)",
            "role": "Data Engineer",
            "start": "Aug. 2026",
            "end": None,
            "missions": ["Industrializing production pipelines"],
            "stack": ["Microsoft Fabric"],
        },
        {
            "company": "bioMérieux",
            "role": "Supply Chain Data Analyst",
            "start": "March 2021",
            "end": "Sept. 2021",
            "missions": ["KPI modeling"],
            "stack": ["Power BI"],
        },
    ],
    "projects": [{"name": "Sentinel", "description": "Trading quantitatif."}],
}


def test_same_role_across_sources_is_merged_once():
    """Deux écritures de la même période ne doivent produire qu'une expérience."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    nile = [e for e in profile["experiences"] if "nile" in e["company"].lower()]
    assert len(nile) == 2  # le poste mauricien et le poste lyonnais, pas trois


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


def test_projects_are_unioned_not_replaced():
    """Le bug mesuré le 2026-09-14 : WideDocs disparaissait au profit de Sentinel."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    names = {p["name"] for p in profile["projects"]}
    assert names == {"WideDocs", "Sentinel"}


def test_manual_source_always_wins():
    manual = {"headline": "Lead Data Engineer"}
    profile, _ = build_profile_from_sources({"cv": CV, "manual": manual})
    assert profile["headline"] == "Lead Data Engineer"


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


def test_unknown_source_is_accepted_after_the_known_ones():
    """Ajouter une source plus tard ne doit pas casser la fusion existante."""
    extra = {"experiences": [{"company": "Agence Nile", "role": "Ingénieur", "start": "Août 2025"}]}
    profile, _ = build_profile_from_sources({"cv": CV, "annuaire": extra})
    assert profile["experiences"][0]["role"] == "Data Engineer"
    assert "annuaire" in profile["experiences"][0]["sources"]


def test_provenance_names_every_contributing_source():
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    mauritius = next(e for e in profile["experiences"] if e["start"] == "2025-08")
    assert set(mauritius["sources"]) == {"cv", "website"}


def test_merge_is_idempotent_and_deterministic():
    once, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    twice, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    assert once == twice


def test_empty_sources_yield_empty_profile():
    profile, conflicts = build_profile_from_sources({})
    assert profile["experiences"] == []
    assert conflicts == []
