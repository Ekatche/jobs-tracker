from app.services.profile.merge import build_profile_from_sources
from tests.profile_merge.fixtures import CV, WEBSITE


def test_manual_source_always_wins():
    manual = {"headline": "Lead Data Engineer"}
    profile, _ = build_profile_from_sources({"cv": CV, "manual": manual})
    assert profile["headline"] == "Lead Data Engineer"


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


def test_contact_field_resolves_by_source_priority():
    cv_contact = {"contact": {"email": "cv@example.com", "phone": "0102030405"}}
    website_contact = {"contact": {"email": "website@example.com"}}
    profile, _ = build_profile_from_sources(
        {"cv": cv_contact, "website": website_contact}
    )
    assert profile["contact"]["email"] == "cv@example.com"  # cv > website
    assert profile["contact"]["phone"] == "0102030405"  # only cv has it


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


def test_writing_style_propagates_from_manual_source():
    """Le style personnel d'écriture fourni dans manual se propage dans le profil fusionné."""
    sources = {
        "manual": {
            "writing_style": "Style concis et direct, voix active.",
        }
    }
    profile, _ = build_profile_from_sources(sources)
    assert profile.get("writing_style") == "Style concis et direct, voix active."


def test_writing_samples_propagate_from_manual_source():
    """Les lettres d'exemple fournies dans manual se propagent dans le profil fusionné."""
    sources = {"manual": {"writing_samples": "Madame, Monsieur,\nJe travaille sur..."}}
    profile, _ = build_profile_from_sources(sources)
    assert profile.get("writing_samples") == "Madame, Monsieur,\nJe travaille sur..."


def test_manual_empty_mobility_and_availability_clear_cv_values():
    profile, _ = build_profile_from_sources({
        "cv": {"contact": {"availability": "Disponible immédiatement", "mobility": "Permis B"}},
        "manual": {"contact": {"availability": "", "mobility": "  ", "email": "a@b.fr"}},
    })
    contact = profile.get("contact") or {}
    assert not contact.get("availability")
    assert not contact.get("mobility")


def test_manual_without_mobility_key_keeps_cv_value():
    profile, _ = build_profile_from_sources({
        "cv": {"contact": {"mobility": "Permis B"}},
        "manual": {"contact": {"email": "a@b.fr"}},
    })
    assert profile["contact"]["mobility"] == "Permis B"
