from app.services.profile.context import build_candidate_context


def test_build_candidate_context_uses_candidate_profile_fields():
    profile = {
        "headline": "Animatrice jeunesse",
        "experiences": [
            {
                "company": "Centre social",
                "role": "Animatrice",
                "sector": "Animation",
                "start": "2021-09",
                "end": "2024-06",
                "missions": ["Encadrer les 11-13 ans"],
                "achievements": [{"text": "Séjour organisé", "metric": "24 jeunes"}],
            }
        ],
    }

    ctx = build_candidate_context(profile)

    assert ctx["headline"] == "Animatrice jeunesse"
    exp = ctx["experiences"][0]
    assert exp["start"] == "2021-09" and exp["end"] == "2024-06"
    assert exp["sector"] == "Animation"
    assert exp["missions"] == ["Encadrer les 11-13 ans"]
    assert exp["achievements"] == [{"text": "Séjour organisé", "metric": "24 jeunes"}]


def test_build_candidate_context_empty_profile():
    ctx = build_candidate_context({})
    assert ctx["experiences"] == [] and ctx["projects"] == [] and ctx["languages"] == []
