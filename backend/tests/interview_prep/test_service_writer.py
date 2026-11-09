"""Tests unitaires pour la génération de stories (writer), le formatage de contexte et les modèles LLM."""

import json
from unittest.mock import AsyncMock, patch
from bson import ObjectId
import pytest

from app.models import (
    AnticipatedQuestion,
    BankStory,
    StoryExperience,
    StoryOrigin,
)
from app.services.interview_prep_service import (
    RequirementPick,
    _clean_json_output,
    format_candidate_profile_context,
    format_evaluation_context,
    write_stories_for_requirements,
)
from tests.interview_prep.conftest import (
    TEST_OFFER,
    TEST_PROFILE,
    TEST_RAW_STORY,
    make_practice_llm_response,
)


@pytest.mark.parametrize(
    "raw_input,expected_type,expected_key,expected_val",
    [
        ("```json\n[{\"title\": \"Test\"}]\n```", list, "title", "Test"),
        ("Voici le JSON:\n{\"status\": \"ok\"}\nMerci.", dict, "status", "ok"),
    ],
)
def test_clean_json_output(raw_input, expected_type, expected_key, expected_val):
    res = _clean_json_output(raw_input)
    assert isinstance(res, expected_type)
    target = res[0] if isinstance(res, list) else res
    assert target[expected_key] == expected_val


@pytest.mark.asyncio
async def test_writer_builds_story_and_slot_mocked():
    payload = {
        "items": [
            {
                "requirement_index": 1,
                "requirement": "Expérience Kafka",
                "fit": "strong",
                "angle": "Mets en avant la latence réduite de 40 %",
                "experience": {"company": "Tech Corp", "role": "Backend Engineer"},
                "story": {
                    "title": "[Scalabilité] Pipeline Kafka",
                    "theme": "Architecture",
                    "situation": "Trafic de 50k req/s",
                    "task": "Concevoir l'ingestion",
                    "action": "Partitionnement et consumer groups",
                    "result": "Latence diminuée de 40%",
                    "reflection": "Gérer les rebalances plus tôt",
                    "key_tags": ["kafka", "python"],
                },
            }
        ]
    }

    profile = {
        "skills": ["Python", "Kafka"],
        "experiences": [{"company": "Tech Corp", "role": "Backend Engineer", "start": "2020-01"}],
    }
    offer = {"_id": ObjectId(), "title": "Senior Backend", "company": "ScaleUp", "description": "Need Kafka"}
    pick = RequirementPick(requirement="Expérience Kafka", covered=True)

    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)):
        with patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock) as mock_usage:
            [(slot, story)] = await write_stories_for_requirements(
                db=None,
                user_id="u",
                profile=profile,
                offer=offer,
                evaluation=None,
                picks=[pick],
            )

    assert isinstance(story, BankStory)
    assert story.title == "[Scalabilité] Pipeline Kafka"
    assert story.action == "Partitionnement et consumer groups"
    assert story.origin == StoryOrigin(kind="generated", offer_id=str(offer["_id"]))
    assert story.experience == StoryExperience(company="Tech Corp", role="Backend Engineer", start="2020-01")
    assert slot.fit == "strong" and slot.story_id == story.id
    assert mock_usage.call_args.kwargs["metadata"]["sub_action"] == "stories"


def test_format_candidate_profile_context_uses_headline_and_real_fields():
    profile = {
        "headline": "Animatrice jeunesse",
        "contact": {"email": "x@y.fr"},
        "experiences": [
            {
                "company": "Centre social",
                "role": "Animatrice",
                "start": "2021-09",
                "end": "2024-06",
                "missions": ["Encadrer les 11-13 ans"],
            }
        ],
    }

    text = format_candidate_profile_context(profile)
    assert text.startswith("Candidat : Candidat - Animatrice jeunesse")
    assert "Ingénieur" not in text
    assert "Encadrer les 11-13 ans" in text
    assert "2024-06" in text


def test_format_evaluation_context_reads_weight_reason_and_warnings():
    evaluation = {
        "score": 3.2,
        "bloc_a": {"summary": "Poste d'animation périscolaire"},
        "bloc_b": {
            "matched_requirements": [
                {
                    "requirement": "BAFA",
                    "weight": "critical",
                    "candidate_evidence": "BAFA 2019",
                    "status": "partial_match",
                    "evidence_tier": "inferred",
                }
            ],
            "missing_requirements": [
                {"requirement": "Permis B", "weight": "high", "reason": "Non mentionné dans le profil"}
            ],
            "score_justification": "Bon fond, permis manquant",
        },
        "bloc_g": {"warnings": ["Offre republiée 4 fois"]},
    }

    text = format_evaluation_context(evaluation)
    assert "Synthèse de l'offre : Poste d'animation périscolaire" in text
    assert "BAFA [critical, couverture partielle, preuve déduite" in text
    assert "Permis B [Poids: high] (Écart: Non mentionné dans le profil)" in text
    assert "Justification du score : Bon fond, permis manquant" in text
    assert "Offre republiée 4 fois" in text


@pytest.mark.asyncio
async def test_writer_prompt_uses_job_offer_poste_and_entreprise():
    offer = {
        "_id": ObjectId(),
        "poste": "Animateur périscolaire",
        "entreprise": "Mairie de Bourgoin",
        "description": "...",
    }

    with patch(
        "app.services.interview_prep_service.acompletion",
        return_value=make_practice_llm_response({"items": []}),
    ) as mock_llm:
        with patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
            await write_stories_for_requirements(
                db=None, user_id="u", profile={}, offer=offer, evaluation=None, picks=None
            )

    prompt = mock_llm.call_args.kwargs["messages"][0]["content"]
    assert "Animateur périscolaire" in prompt
    assert "Mairie de Bourgoin" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model,expected_temperature",
    [
        ("openai/gpt-5.6-terra", None),
        ("anthropic/claude-opus-5-5", None),
        ("gemini/gemini-3.8-flash", 0.2),
    ],
)
async def test_generators_omit_temperature_for_models_that_reject_it(model, expected_temperature):
    from app.services import interview_prep_service as ips

    mock_resp = AsyncMock()
    mock_resp.choices = [AsyncMock(message=AsyncMock(content="[]"))]
    mock_resp.usage = AsyncMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    offer = {"_id": ObjectId(), "poste": "Dev", "entreprise": "Co", "description": "D"}

    with patch.object(ips, "DEFAULT_INTERVIEW_MODEL", model), \
         patch("app.services.interview_prep_service.acompletion", return_value=mock_resp) as mock_llm, \
         patch("app.services.interview_prep_service.record_api_usage", return_value=None):
        try:
            await ips.write_stories_for_requirements(
                db=None, user_id="u", profile={}, offer=offer, evaluation=None, picks=None
            )
        except ValueError:
            pass
        await ips.generate_anticipated_questions(db=None, user_id=ObjectId(), profile={}, offer=offer)
        await ips.generate_reverse_questions(db=None, user_id=ObjectId(), offer=offer)
        try:
            await ips.generate_audience_packs(db=None, user_id=ObjectId(), profile={}, offer=offer)
        except Exception:
            pass
        question = AnticipatedQuestion(category="behavioral", question="Q ?", why_it_will_be_asked="W")
        try:
            await ips.evaluate_practice_answer(
                db=None, user_id=ObjectId(), offer=offer, evaluation=None, question=question, answer="R"
            )
        except ValueError:
            pass

    assert mock_llm.call_count == 5
    for call in mock_llm.call_args_list:
        assert call.kwargs["model"] == model
        assert call.kwargs.get("temperature") == expected_temperature
        assert call.kwargs["drop_params"] is True


@pytest.mark.asyncio
async def test_writer_uncovered_without_neighbor_gives_no_experience():
    payload = {"items": [{"requirement_index": 1, "story": None, "experience": None, "fit": "strong", "angle": ""}]}
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(slot, story)] = await write_stories_for_requirements(
            None, "u", TEST_PROFILE, TEST_OFFER, None, [RequirementPick(requirement="GCP", covered=False)]
        )
    assert (slot.fit, slot.story_id, story) == ("no_experience", None, None)


@pytest.mark.asyncio
async def test_writer_uncovered_with_neighbor_gives_transferable():
    payload = {
        "items": [
            {
                "requirement_index": 1,
                "story": TEST_RAW_STORY,
                "experience": {"company": "Alpha Corp", "role": "Data Engineer"},
                "fit": "strong",
                "angle": "",
            }
        ]
    }
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(slot, story)] = await write_stories_for_requirements(
            None, "u", TEST_PROFILE, TEST_OFFER, None, [RequirementPick(requirement="GCP", covered=False)]
        )
    assert slot.fit == "transferable" and story.origin.kind == "generated" and slot.story_id == story.id


@pytest.mark.asyncio
async def test_writer_fewer_items_than_requirements():
    payload = {
        "items": [
            {"requirement_index": 1, "story": TEST_RAW_STORY, "experience": None, "fit": "strong", "angle": ""},
        ]
    }
    picks = [RequirementPick(requirement="SQL", covered=True), RequirementPick(requirement="GCP", covered=False)]
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await write_stories_for_requirements(None, "u", TEST_PROFILE, TEST_OFFER, None, picks)
    assert [s.fit for s, _ in result] == ["strong", "no_experience"]


@pytest.mark.asyncio
async def test_writer_drops_experience_not_in_profile():
    payload = {
        "items": [
            {
                "requirement_index": 1,
                "story": TEST_RAW_STORY,
                "experience": {"company": "Inconnue SA"},
                "fit": "strong",
                "angle": "",
            },
            {
                "requirement_index": 2,
                "story": TEST_RAW_STORY,
                "experience": {"company": "alpha corp"},
                "fit": "strong",
                "angle": "",
            },
        ]
    }
    picks = [RequirementPick(requirement="R1", covered=True), RequirementPick(requirement="R2", covered=True)]
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await write_stories_for_requirements(None, "u", TEST_PROFILE, TEST_OFFER, None, picks)
    assert result[0][1].experience is None
    assert result[1][1].experience == StoryExperience(company="Alpha Corp", role="Data Engineer", start="2022-01")


@pytest.mark.asyncio
async def test_writer_masks_numbers_absent_from_new_story():
    payload = {
        "items": [
            {
                "requirement_index": 1,
                "story": TEST_RAW_STORY,
                "experience": None,
                "fit": "strong",
                "angle": "Gain de −90 %",
            }
        ]
    }
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(slot, story)] = await write_stories_for_requirements(
            None, "u", TEST_PROFILE, TEST_OFFER, None, [RequirementPick(requirement="X", covered=True)]
        )
    assert "90" not in slot.angle and "[à chiffrer]" in slot.angle

