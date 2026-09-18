import json
import pytest
from unittest.mock import AsyncMock, patch
from bson import ObjectId

from app.models import (
    StarRStory,
    AudiencePackRecruiter,
    AudiencePackHiringManager,
    AudiencePackTechPanel,
    AnticipatedQuestion,
    ReverseQuestion,
    InterviewPrep,
)
from app.services.interview_prep_service import (
    _clean_json_output,
    generate_star_stories,
    generate_audience_packs,
    generate_anticipated_questions,
    generate_reverse_questions,
    export_interview_prep_markdown,
)


def test_clean_json_output():
    raw_with_fence = "```json\n[{\"title\": \"Test\"}]\n```"
    res = _clean_json_output(raw_with_fence)
    assert isinstance(res, list)
    assert res[0]["title"] == "Test"

    raw_text_prefix = "Voici le JSON:\n{\"status\": \"ok\"}\nMerci."
    res2 = _clean_json_output(raw_text_prefix)
    assert isinstance(res2, dict)
    assert res2["status"] == "ok"


@pytest.mark.asyncio
async def test_generate_star_stories_mocked():
    mock_stories = [
        {
            "title": "[Scalabilité] Pipeline Kafka",
            "theme": "Architecture",
            "target_requirement": "Expérience Kafka",
            "situation": "Trafic de 50k req/s",
            "task": "Concevoir l'ingestion",
            "action": "Partitionnement et consumer groups",
            "result": "Latence diminuée de 40%",
            "reflection": "Gérer les rebalances plus tôt",
            "key_tags": ["kafka", "python"],
        }
    ]

    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content=json.dumps(mock_stories)))
    ]
    mock_resp.usage = AsyncMock(prompt_tokens=100, completion_tokens=200, total_tokens=300)

    profile = {"skills": ["Python", "Kafka"], "experiences": [{"company": "Tech Corp"}]}
    offer = {"title": "Senior Backend", "company": "ScaleUp", "description": "Need Kafka"}
    evaluation = {"bloc_b": {"matched_requirements": [{"requirement": "Kafka", "candidate_evidence": "Used at Tech Corp"}]}}

    with patch("app.services.interview_prep_service.acompletion", return_value=mock_resp):
        with patch("app.services.interview_prep_service.record_api_usage", return_value=None):
            stories = await generate_star_stories(
                user_id=ObjectId(),
                profile=profile,
                offer=offer,
                evaluation=evaluation,
            )

    assert len(stories) == 1
    assert isinstance(stories[0], StarRStory)
    assert stories[0].title == "[Scalabilité] Pipeline Kafka"
    assert stories[0].action == "Partitionnement et consumer groups"


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

    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content=json.dumps(mock_data)))
    ]
    mock_resp.usage = AsyncMock(prompt_tokens=150, completion_tokens=250, total_tokens=400)

    with patch("app.services.interview_prep_service.acompletion", return_value=mock_resp):
        with patch("app.services.interview_prep_service.record_api_usage", return_value=None):
            recruiter, hm, tech = await generate_audience_packs(
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

    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content=json.dumps(mock_questions)))
    ]
    mock_resp.usage = AsyncMock(prompt_tokens=120, completion_tokens=180, total_tokens=300)

    with patch("app.services.interview_prep_service.acompletion", return_value=mock_resp):
        with patch("app.services.interview_prep_service.record_api_usage", return_value=None):
            questions = await generate_anticipated_questions(
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

    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content=json.dumps(mock_reverse)))
    ]
    mock_resp.usage = AsyncMock(prompt_tokens=100, completion_tokens=100, total_tokens=200)

    with patch("app.services.interview_prep_service.acompletion", return_value=mock_resp):
        with patch("app.services.interview_prep_service.record_api_usage", return_value=None):
            rev_questions = await generate_reverse_questions(
                user_id=ObjectId(),
                offer={"title": "Dev", "company": "Co", "description": "D"},
                evaluation={},
            )

    assert len(rev_questions) == 1
    assert isinstance(rev_questions[0], ReverseQuestion)
    assert rev_questions[0].category == "Dette Technique"


def test_export_interview_prep_markdown():
    story = StarRStory(
        title="[Scalabilité] Pipeline Kafka",
        theme="Architecture",
        target_requirement="Expérience Kafka",
        situation="50k req/s",
        task="Conception",
        action="Partitions",
        result="-40% latence",
        reflection="Rebalances",
        key_tags=["kafka"],
    )
    prep = InterviewPrep(
        offer_id=ObjectId(),
        user_id=ObjectId(),
        stories=[story],
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

    md = export_interview_prep_markdown(prep, offer)
    assert "# Kit de Préparation d'Entretien : Lead Backend @ TechCorp" in md
    assert "## 1. Histoires STAR+R" in md
    assert "[Scalabilité] Pipeline Kafka" in md
    assert "## 2. Packs d'Audience" in md
    assert "### Pack Recruteur / RH" in md
    assert "## 3. Questions Anticipées" in md
    assert "## 4. Questions Inversées (Anti Red-Flags)" in md
