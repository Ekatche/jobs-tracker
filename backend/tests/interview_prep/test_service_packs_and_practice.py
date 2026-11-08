"""Tests unitaires pour la génération des packs d'audience, questions et évaluation du mode practice."""

from unittest.mock import AsyncMock, patch
from bson import ObjectId
import pytest

from app.models import (
    AnticipatedQuestion,
    AudiencePackHiringManager,
    AudiencePackRecruiter,
    AudiencePackTechPanel,
    BankStory,
    InterviewPrep,
    ReverseQuestion,
    StoryOrigin,
    StorySlot,
)
from app.services.interview_prep_service import (
    _mask_invented_numbers,
    evaluate_practice_answer,
    export_interview_prep_markdown,
    generate_anticipated_questions,
    generate_audience_packs,
    generate_reverse_questions,
)
from tests.interview_prep.conftest import (
    TEST_PRACTICE_QUESTION,
    TEST_PRACTICE_STORY,
    make_practice_llm_response,
)


@pytest.mark.asyncio
async def test_generate_audience_packs_mocked():
    mock_data = {
        "recruiter_pack": {
            "pitch_30s": "Ingénieur passionné avec 5 ans d'expérience...",
            "comp_strategy": {"volunteer": "fourchette", "avoid": "chiffre ferme"},
            "red_flags_they_screen_for": ["instabilité"],
            "key_questions_to_ask_recruiter": ["Quelle est la suite ?"],
        },
        "hm_pack": {
            "strategic_alignment": "Résout les goulots d'étranglement actuels",
            "internal_vocabulary": ["OKR", "Squad"],
            "sharp_questions": ["Quels défis à 90 jours ?"],
        },
        "tech_pack": {
            "architecture_points": ["Idempotence", "CQRS"],
            "tradeoffs_and_risks": ["Consistance éventuelle"],
            "reverse_questions": ["Quelle est la fréquence de release ?"],
        },
    }

    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(mock_data)):
        with patch("app.services.interview_prep_service.record_api_usage", return_value=None):
            recruiter, hm, tech = await generate_audience_packs(
                db=None,
                user_id=ObjectId(),
                profile={},
                offer={"title": "Lead Dev", "company": "Acme", "description": "Desc"},
                evaluation={},
            )

    assert isinstance(recruiter, AudiencePackRecruiter)
    assert isinstance(hm, AudiencePackHiringManager)
    assert isinstance(tech, AudiencePackTechPanel)
    assert recruiter.pitch_30s.startswith("Ingénieur")
    assert hm.internal_vocabulary == ["OKR", "Squad"]
    assert tech.architecture_points == ["Idempotence", "CQRS"]


@pytest.mark.asyncio
async def test_generate_anticipated_questions_mocked():
    mock_questions = [
        {
            "category": "behavioral",
            "question": "Parlez-moi d'un conflit d'architecture.",
            "why_it_will_be_asked": "Test de communication",
            "mapped_story_id": "story-123",
            "key_points_to_cover": ["Écoute", "Benchmark", "Consensus"],
        },
        {
            "category": "technical",
            "question": "Comment gérez-vous le rebalance Kafka ?",
            "why_it_will_be_asked": "[inferred from JD]",
            "mapped_story_id": None,
            "key_points_to_cover": ["Static membership", "Session timeout"],
        },
    ]

    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(mock_questions)):
        with patch("app.services.interview_prep_service.record_api_usage", return_value=None):
            questions = await generate_anticipated_questions(
                db=None,
                user_id=ObjectId(),
                profile={},
                offer={"title": "Dev", "company": "Co", "description": "D"},
                evaluation={},
                stories=[],
            )

    assert len(questions) == 2
    assert isinstance(questions[0], AnticipatedQuestion)
    assert questions[0].category == "behavioral"
    assert questions[1].why_it_will_be_asked == "[inferred from JD]"


@pytest.mark.asyncio
async def test_generate_reverse_questions_mocked():
    mock_reverse = [
        {
            "category": "Dette Technique",
            "question": "Quel pourcentage de sprint est dédié au refactoring ?",
            "probe_intent": "Tester si la qualité est tolérée",
        }
    ]

    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(mock_reverse)):
        with patch("app.services.interview_prep_service.record_api_usage", return_value=None):
            rev_questions = await generate_reverse_questions(
                db=None,
                user_id=ObjectId(),
                offer={"title": "Dev", "company": "Co", "description": "D"},
                evaluation={},
            )

    assert len(rev_questions) == 1
    assert isinstance(rev_questions[0], ReverseQuestion)
    assert rev_questions[0].category == "Dette Technique"


def test_export_interview_prep_markdown():
    prep = InterviewPrep(
        offer_id=ObjectId(),
        user_id=ObjectId(),
        recruiter_pack=AudiencePackRecruiter(
            pitch_30s="Mon pitch...",
            comp_strategy={"volunteer": "marché", "avoid": "chiffre"},
            red_flags_they_screen_for=["instabilité"],
            key_questions_to_ask_recruiter=["Timing ?"],
        ),
        anticipated_questions=[
            AnticipatedQuestion(
                category="technical",
                question="Architecture Kafka ?",
                why_it_will_be_asked="[inferred from JD]",
                key_points_to_cover=["Partitions"],
            )
        ],
        reverse_questions=[
            ReverseQuestion(
                category="Culture",
                question="Astreintes ?",
                probe_intent="Vérifier l'on-call",
            )
        ],
    )
    offer = {"title": "Lead Backend", "company": "TechCorp"}

    md = export_interview_prep_markdown(prep, offer, [])
    assert "# Kit de Préparation d'Entretien : Lead Backend @ TechCorp" in md
    assert "## 1. Histoires STAR+R" in md
    assert "_Aucune histoire STAR+R générée._" in md
    assert "## 2. Packs d'Audience" in md
    assert "### Pack Recruteur / RH" in md
    assert "## 3. Questions Anticipées" in md
    assert "## 4. Questions Inversées (Anti Red-Flags)" in md


def test_export_markdown_uses_slots_and_bank_facts():
    s1 = BankStory(
        user_id="u1",
        title="Migration Kafka",
        theme="Architecture",
        situation="Trafic de 50k req/s",
        task="Fiabiliser l'ingestion",
        action="Partitionnement et consumer groups",
        result="Latence réduite de −60 %",
        reflection="Automatiser le rebalance",
        key_tags=["kafka"],
        origin=StoryOrigin(kind="manual", offer_id=None),
    )
    prep = InterviewPrep(offer_id=ObjectId(), user_id=ObjectId())
    offer = {"title": "Lead Backend", "company": "TechCorp"}
    slots = [
        (StorySlot(requirement="Piloter", story_id="s1", fit="strong", angle="Coordination"), s1),
        (StorySlot(requirement="GCP", fit="no_experience"), None),
    ]

    md = export_interview_prep_markdown(prep, offer, slots)

    assert "Piloter" in md and "Coordination" in md and "−60 %" in md
    assert "pas d'expérience dans ton profil" in md
    assert "Aucune histoire pour cette exigence." in md


@pytest.mark.asyncio
async def test_practice_evaluate_scores_and_average():
    payload = {
        "criteria": {
            "coverage": {"score": 3, "comment": "Points clés partiels."},
            "structure": {"score": 0, "comment": "Pas de STAR."},
            "offer_fit": {"score": 4, "comment": "Lien explicite."},
            "quantified_result": {"score": 7, "comment": "Chiffré."},
        },
        "missing": ["Préciser le résultat"],
        "improved_answer": "J'ai migré 40 services.",
    }
    offer = {"_id": ObjectId(), "poste": "SRE", "entreprise": "Co", "description": "K8s"}

    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)) as mock_llm, \
         patch("app.services.interview_prep_service.record_api_usage", return_value=None) as mock_usage:
        attempt = await evaluate_practice_answer(
            db=None,
            user_id=ObjectId(),
            offer=offer,
            evaluation=None,
            question=TEST_PRACTICE_QUESTION,
            answer="J'ai migré le cluster en douceur.",
            story=TEST_PRACTICE_STORY,
        )

    assert [c.key for c in attempt.criteria] == ["structure", "quantified_result", "offer_fit", "coverage"]
    assert [c.score for c in attempt.criteria] == [1, 5, 4, 3]
    assert attempt.overall_score == 3.2
    assert attempt.question_id == TEST_PRACTICE_QUESTION.id
    assert attempt.question == TEST_PRACTICE_QUESTION.question
    assert attempt.missing == ["Préciser le résultat"]
    assert attempt.improved_answer == "J'ai migré 40 services."
    assert mock_usage.call_args.kwargs["metadata"]["sub_action"] == "practice"

    prompt = mock_llm.call_args.kwargs["messages"][0]["content"]
    assert "J'ai migré le cluster en douceur." in prompt
    assert "Cluster legacy de 40 services" in prompt
    assert "Gestion du risque de coupure" in prompt


@pytest.mark.asyncio
async def test_practice_evaluate_rejects_missing_criterion():
    payload = {
        "criteria": {
            "structure": {"score": 3, "comment": "c"},
            "quantified_result": {"score": 3, "comment": "c"},
            "offer_fit": {"score": 3, "comment": "c"},
        },
        "missing": [],
        "improved_answer": "R",
    }
    with patch("app.services.interview_prep_service.acompletion", return_value=make_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", return_value=None):
        with pytest.raises(ValueError, match="coverage"):
            await evaluate_practice_answer(
                db=None,
                user_id=ObjectId(),
                offer={"poste": "SRE", "entreprise": "Co", "description": "D"},
                evaluation=None,
                question=TEST_PRACTICE_QUESTION,
                answer="R",
            )


def test_practice_mask_invented_numbers():
    sources = "J'ai réduit la latence de 30 % sur 1,5 an."
    text = "Sur K8s et S3, j'ai réduit la latence de 30 % en 1.5 an pour 200 clients."
    assert _mask_invented_numbers(text, sources) == (
        "Sur K8s et S3, j'ai réduit la latence de 30 % en 1.5 an pour [à chiffrer] clients."
    )

