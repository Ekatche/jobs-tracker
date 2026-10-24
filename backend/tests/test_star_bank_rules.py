from app.models import BankStory, StoryExperience, StoryOrigin
from app.services.star_bank_rules import (
    _mask_invented_numbers,
    _story_facts_sources,
    experience_label,
    find_duplicate_pairs,
    guess_experience,
    match_profile_experience,
)

PROFILE_EXPS = [
    {"company": "Alpha Corp", "role": "Data Engineer", "start": "2022-01"},
    {"company": "Beta SAS", "role": "Data Analyst", "start": "2020-01"},
]


def test_guess_experience_single_company_found():
    exp = guess_experience("Chez alpha corp, le pipeline était lent.", PROFILE_EXPS)
    assert exp == StoryExperience(company="Alpha Corp", role="Data Engineer", start="2022-01")


def test_guess_experience_two_companies_is_none():
    assert guess_experience("Entre Alpha Corp et Beta SAS…", PROFILE_EXPS) is None


def test_guess_experience_no_company_is_none():
    assert guess_experience("Un pipeline lent.", PROFILE_EXPS) is None


def test_match_profile_experience_normalizes_company_and_role():
    assert match_profile_experience(StoryExperience(company="ALPHA CORP", role="data engineer"), PROFILE_EXPS) == 0
    assert match_profile_experience(StoryExperience(company="Gamma"), PROFILE_EXPS) is None
    assert match_profile_experience(None, PROFILE_EXPS) is None


def test_experience_label_with_role():
    assert experience_label(StoryExperience(company="Alpha Corp", role="Data Engineer")) == "Data Engineer · Alpha Corp"


def test_experience_label_without_role():
    assert experience_label(StoryExperience(company="Alpha Corp")) == "Alpha Corp"


def _story(id, title, result, company=None, not_dup=()):
    return BankStory(
        id=id,
        user_id="u1",
        title=title,
        theme="Général",
        situation="S",
        task="T",
        action="A",
        result=result,
        reflection="",
        key_tags=[],
        experience=StoryExperience(company=company) if company else None,
        origin=StoryOrigin(kind="manual"),
        discarded_versions=[],
        not_duplicate_of=list(not_dup),
    )


def test_close_titles_same_company_is_pair():
    a = _story("a", "[Scalabilité] Migration du pipeline de facturation", "−45 %", "Alpha Corp")
    b = _story("b", "Migration pipeline facturation", "−60 %", "ALPHA CORP")
    assert find_duplicate_pairs([a, b]) == [("a", "b")]


def test_shared_result_number_is_pair():
    a = _story("a", "Refonte du batch nocturne", "−60 % de temps")
    b = _story("b", "Accélérer la facturation", "temps réduit de 60 %")
    assert find_duplicate_pairs([a, b]) == [("a", "b")]


def test_different_companies_never_pair():
    assert find_duplicate_pairs(
        [_story("a", "Migration pipeline", "x", "Alpha"), _story("b", "Migration pipeline", "x", "Beta")]
    ) == []


def test_unrelated_stories_not_pair():
    assert (
        find_duplicate_pairs([_story("a", "Incident de production du lundi", "45 min"), _story("b", "Migration du pipeline", "−6 %")])
        == []
    )


def test_not_duplicate_of_excludes_pair():
    a = _story("a", "Migration pipeline facturation", "x", not_dup=["b"])
    assert find_duplicate_pairs([a, _story("b", "Migration pipeline facturation", "y")]) == []


def test_mask_invented_numbers_against_story_facts():
    """Un nombre de l'angle absent des faits de l'histoire est masqué ; 1,5 et 1.5 sont le même nombre."""
    story = _story("a", "Migration sur 1,5 an", "Coûts réduits de 35 %")
    angle = "Insister sur les 35 % gagnés en 1.5 an, pas sur les 40 % visés"
    assert _mask_invented_numbers(angle, _story_facts_sources(story)) == (
        "Insister sur les 35 % gagnés en 1.5 an, pas sur les [à chiffrer] % visés"
    )
