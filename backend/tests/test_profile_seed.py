import pytest
from scripts.seed_candidate_profile import merge_profile_sources

def test_merge_profile_union_and_conflicts():
    cv_data = {
        "experiences": [
            {
                "company": "Bimedoc",
                "role": "Data Engineer",
                "start": "2021",
                "end": "2022",
                "stack": ["Odoo", "Python"],
                "missions": ["ERP integration"]
            }
        ]
    }
    site_data = {
        "experiences": [
            {
                "company": "Bimedoc",
                "role": "Data Engineer",
                "start": "2021",
                "end": "2022",
                "stack": ["Sylob", "Python"],
                "missions": ["ERP migration"]
            },
            {
                "company": "bioMérieux",
                "role": "Bioinformatician",
                "start": "2019",
                "end": "2020",
                "stack": ["Nextflow"],
                "missions": ["Genomics analysis"]
            }
        ]
    }

    merged, conflicts = merge_profile_sources(cv_data, site_data)

    # 1. Union : bioMérieux présent bien qu'absent du CV
    companies = [e["company"] for e in merged["experiences"]]
    assert "bioMérieux" in companies
    assert "Bimedoc" in companies

    # 2. Conflit détecté sur Bimedoc (Odoo vs Sylob)
    assert len(conflicts) > 0
    bimedoc_conflict = next(c for c in conflicts if c["company"] == "Bimedoc")
    assert "Odoo" in str(bimedoc_conflict["cv_stack"])
    assert "Sylob" in str(bimedoc_conflict["site_stack"])

    # 3. Provenance conservée
    assert any(p["source"] in ("cv", "site", "cv+site") for p in merged.get("provenance", []))
