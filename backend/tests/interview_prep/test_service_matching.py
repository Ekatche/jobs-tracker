"""Tests unitaires pour la sélection d'exigences et le matching de la banque d'histoires."""

from unittest.mock import AsyncMock, patch
import pytest

from app.models import StorySlot
from app.services.interview_prep_service import (
    RequirementPick,
    build_story_slots,
    carry_over_edited_angles,
    format_bank_summary,
    format_requirements_block,
    match_bank_stories,
    select_requirements,
)
from tests.interview_prep.conftest import (
    TEST_BANK_STORY_1,
    TEST_OFFER,
    make_practice_llm_response,
)

EVAL_DATA = {
    "bloc_b": {
        "matched_requirements": [
            {"requirement": "SQL", "weight": "meaningful"},
            {"requirement": "Piloter une équipe", "weight": "critical"},
        ],
        "missing_requirements": [
            {"requirement": "GCP", "weight": "critical"},
            {"requirement": "Airflow", "weight": "high"},
        ],
    }
}


def test_select_requirements_orders_by_weight_then_bloc_b_order():
    assert [(p.requirement, p.covered) for p in select_requirements(EVAL_DATA)] == [
        ("Piloter une équipe", True),
        ("GCP", False),
        ("Airflow", False),
        ("SQL", True),
    ]


def test_select_requirements_caps_at_limit():
    assert len(select_requirements(EVAL_DATA, limit=2)) == 2


@pytest.mark.parametrize(
    "eval_input,expected",
    [
        (None, []),
        ({"bloc_b": {}}, []),
        ({"bloc_b": {"matched_requirements": [{"requirement": "", "weight": "critical"}]}}, []),
    ],
)
def test_select_requirements_empty_or_invalid_cases(eval_input, expected):
    assert select_requirements(eval_input) == expected


def test_format_requirements_block_without_picks_asks_to_extract():
    text = format_requirements_block(None)
    assert "5" in text and "exigences" in text.lower()


def test_format_requirements_block_numbers_from_one():
    picks = [RequirementPick(requirement="SQL"), RequirementPick(requirement="GCP")]
    assert format_requirements_block(picks) == "1. SQL\n2. GCP"


def test_format_bank_summary_formats_one_line_per_story():
    text = format_bank_summary([TEST_BANK_STORY_1])
    assert text == (
        "[s1] Fiabilisation du pipeline nocturne | sans expérience | "
        "−60 % de temps de traitement et zéro incident depuis 3 mois. | data, fiabilité"
    )


@pytest.mark.asyncio
async def test_match_maps_by_index_and_masks_invented_numbers():
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "Gain de 75 % et −60 %"}]}
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(pick, slot)] = await match_bank_stories(
            None, "u", TEST_OFFER, [RequirementPick(requirement="Fiabiliser", covered=True)], [TEST_BANK_STORY_1]
        )
    assert (slot.story_id, slot.fit, slot.requirement) == ("s1", "strong", "Fiabiliser")
    assert "75" not in slot.angle and "[à chiffrer]" in slot.angle and "60" in slot.angle


@pytest.mark.asyncio
async def test_match_ignores_story_id_outside_bank():
    payload = {"matches": [{"requirement_index": 1, "story_id": "story-of-someone-else", "fit": "strong", "angle": "x"}]}
    pick = RequirementPick(requirement="Fiabiliser", covered=True)
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await match_bank_stories(None, "u", TEST_OFFER, [pick], [TEST_BANK_STORY_1])
    assert result[0][1] is None


@pytest.mark.asyncio
async def test_match_uncovered_requirement_is_transferable():
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "Pont AWS vers GCP"}]}
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await match_bank_stories(
            None, "u", TEST_OFFER, [RequirementPick(requirement="GCP", covered=False)], [TEST_BANK_STORY_1]
        )
    assert result[0][1].fit == "transferable"


@pytest.mark.asyncio
async def test_match_unmatched_requirement_stays_none():
    payload = {"matches": []}
    pick = RequirementPick(requirement="Fiabiliser", covered=True)
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(returned_pick, slot)] = await match_bank_stories(None, "u", TEST_OFFER, [pick], [TEST_BANK_STORY_1])
    assert returned_pick is pick and slot is None


@pytest.mark.asyncio
async def test_match_without_picks_builds_from_ai_requirements_capped_at_five():
    payload = {
        "matches": [
            {"requirement_index": i, "requirement": f"Exigence {i}", "story_id": None, "fit": "partial", "angle": "a"}
            for i in range(1, 7)
        ]
    }
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await match_bank_stories(None, "u", TEST_OFFER, None, [TEST_BANK_STORY_1])
    assert len(result) == 5
    assert [p.requirement for p, _ in result] == [f"Exigence {i}" for i in range(1, 6)]
    assert all(p.covered is None for p, _ in result)


@pytest.mark.asyncio
async def test_match_records_story_match_usage():
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "x"}]}
    pick = RequirementPick(requirement="Fiabiliser", covered=True)
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock) as mock_usage:
        await match_bank_stories(None, "u", TEST_OFFER, [pick], [TEST_BANK_STORY_1])
    assert mock_usage.call_args.kwargs["metadata"]["sub_action"] == "story_match"


def test_carry_over_keeps_edited_angle_for_same_pair():
    old = StorySlot(requirement="Piloter une équipe", story_id="s1", angle="Mon angle", angle_edited=True)
    [kept] = carry_over_edited_angles([old], [StorySlot(requirement="piloter une équipe", story_id="s1", angle="IA")])
    assert (kept.angle, kept.angle_edited) == ("Mon angle", True)


def test_carry_over_drops_angle_when_story_changes():
    old = StorySlot(requirement="Piloter une équipe", story_id="s1", angle="Mon angle", angle_edited=True)
    [new] = carry_over_edited_angles([old], [StorySlot(requirement="Piloter une équipe", story_id="s2", angle="IA")])
    assert (new.angle, new.angle_edited) == ("IA", False)


@pytest.mark.asyncio
async def test_build_with_empty_bank_skips_match_call():
    payload = {"items": []}
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)) as mock_llm, \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock) as mock_usage:
        slots, new_stories = await build_story_slots(None, "u", {}, TEST_OFFER, None, [], [])
    assert mock_llm.call_count == 1
    assert mock_usage.call_args.kwargs["metadata"]["sub_action"] == "stories"
    assert slots == [] and new_stories == []


@pytest.mark.asyncio
async def test_build_with_no_gap_skips_writer_call():
    evaluation = {"bloc_b": {"matched_requirements": [{"requirement": "Fiabiliser", "weight": "critical"}]}}
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "x"}]}
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)) as mock_llm, \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock) as mock_usage:
        slots, new_stories = await build_story_slots(None, "u", {}, TEST_OFFER, evaluation, [TEST_BANK_STORY_1], [])
    assert mock_llm.call_count == 1
    assert mock_usage.call_args.kwargs["metadata"]["sub_action"] == "story_match"
    assert new_stories == []
    assert len(slots) == 1 and slots[0].fit == "strong" and slots[0].story_id == "s1"

