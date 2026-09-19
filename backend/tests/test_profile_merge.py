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


def test_contact_field_resolves_by_source_priority():
    cv_contact = {"contact": {"email": "cv@example.com", "phone": "0102030405"}}
    website_contact = {"contact": {"email": "website@example.com"}}
    profile, _ = build_profile_from_sources(
        {"cv": cv_contact, "website": website_contact}
    )
    assert profile["contact"]["email"] == "cv@example.com"  # cv > website
    assert profile["contact"]["phone"] == "0102030405"  # only cv has it


def test_skills_are_unioned_by_category_across_sources():
    cv_skills = {"skills": {"languages": ["Python"]}}
    website_skills = {"skills": {"languages": ["SQL"], "tools": ["Docker"]}}
    profile, _ = build_profile_from_sources({"cv": cv_skills, "website": website_skills})
    assert profile["skills"]["languages"] == ["Python", "SQL"]
    assert profile["skills"]["tools"] == ["Docker"]


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


def test_headline_derived_automatically_when_missing():
    """Un titre cohérent est dérivé depuis le résumé ou les expériences si non fourni."""
    sources_with_summary = {
        "cv": {
            "summary": "Data Scientist et AI Engineer expérimenté dans la conception de solutions...",
            "experiences": [{"company": "A", "role": "Data Engineer", "start": "2025-01"}],
        }
    }
    profile1, _ = build_profile_from_sources(sources_with_summary)
    assert profile1["headline"] == "Data Scientist & AI Engineer"

    sources_with_role_only = {
        "cv": {
            "experiences": [{"company": "A", "role": "Data Engineer", "start": "2025-01"}],
            "skills": {"ia": ["RAG", "Machine Learning"]},
        }
    }
    profile2, _ = build_profile_from_sources(sources_with_role_only)
    assert profile2["headline"] == "Data Engineer"


def test_headline_fallback_is_empty_string_without_summary_or_experience():
    """Sans résumé ni expérience, le fallback ne doit plus être un intitulé tech codé en dur."""
    profile, _ = build_profile_from_sources({"manual": {"skills": {}}})
    assert profile["headline"] == ""


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


def test_writing_style_propagates_from_manual_source():
    """Le style personnel d'écriture fourni dans manual se propage dans le profil fusionné."""
    sources = {
        "manual": {
            "writing_style": "Style concis et direct, voix active.",
        }
    }
    profile, _ = build_profile_from_sources(sources)
    assert profile.get("writing_style") == "Style concis et direct, voix active."


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





