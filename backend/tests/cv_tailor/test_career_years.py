


def test_cumulative_career_years_merges_overlaps_and_gaps():
    from app.services.cv_templates import _cumulative_career_years

    # Overlapping stints: should count the union, not double-count
    profile_overlap = {
        "experiences": [
            {"start": "2020-01", "end": "2022-01"},
            {"start": "2020-06", "end": "2021-06"},
        ]
    }
    assert _cumulative_career_years(profile_overlap) == 25 / 12

    # Stints with a 2-year gap: should NOT count the gap
    profile_gap = {
        "experiences": [
            {"start": "2018-01", "end": "2020-01"},
            {"start": "2022-01", "end": "2024-01"},
        ]
    }
    assert _cumulative_career_years(profile_gap) == 50 / 12

    # Single stint, end month counted: 97 months
    profile_single = {
        "experiences": [
            {"start": "09/2018", "end": "09/2026"}
        ]
    }
    assert _cumulative_career_years(profile_single) == 97 / 12

    # Consecutive stints from a real profile: 12 + 48 + 49 months, 9 whole years
    profile_consecutive = {
        "experiences": [
            {"start": "2017-09", "end": "2018-08"},
            {"start": "2018-09", "end": "2022-08"},
            {"start": "2022-09", "end": "2026-09"},
        ]
    }
    assert int(_cumulative_career_years(profile_consecutive)) == 9

    # Year-only dates count whole years, like _format_duration
    assert int(_cumulative_career_years({"experiences": [{"start": "2020", "end": "2022"}]})) == 2


def test_format_career_seniority_phrase_rounds_down():
    from app.services.cv_tailor import format_career_seniority_phrase

    assert format_career_seniority_phrase(8.0) == "avec 8 ans d'expérience dans"
    assert format_career_seniority_phrase(8.3) == "avec 8 ans d'expérience dans"
    # Jamais d'arrondi vers le haut : 7,9 ans ne s'écrit pas « 8 ans »
    assert format_career_seniority_phrase(7.9) == "avec 7 ans d'expérience dans"
    assert format_career_seniority_phrase(1.8) == "avec 1 an d'expérience dans"
    assert format_career_seniority_phrase(1.0) == "avec 1 an d'expérience dans"
    assert format_career_seniority_phrase(0.6) == "avec une expérience dans"
    assert format_career_seniority_phrase(0.0) == "avec une expérience dans"
