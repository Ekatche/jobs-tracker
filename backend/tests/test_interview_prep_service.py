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
    evaluate_practice_answer,
    _mask_invented_numbers,
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
                db=None,
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

    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content=json.dumps(mock_questions)))
    ]
    mock_resp.usage = AsyncMock(prompt_tokens=120, completion_tokens=180, total_tokens=300)

    with patch("app.services.interview_prep_service.acompletion", return_value=mock_resp):
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

    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content=json.dumps(mock_reverse)))
    ]
    mock_resp.usage = AsyncMock(prompt_tokens=100, completion_tokens=100, total_tokens=200)

    with patch("app.services.interview_prep_service.acompletion", return_value=mock_resp):
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


def test_format_candidate_profile_context_uses_headline_and_real_fields():
    from app.services.interview_prep_service import format_candidate_profile_context

    profile = {
        "headline": "Animatrice jeunesse",
        "contact": {"email": "x@y.fr"},
        "experiences": [
            {"company": "Centre social", "role": "Animatrice", "start": "2021-09", "end": "2024-06",
             "missions": ["Encadrer les 11-13 ans"]}
        ],
    }

    text = format_candidate_profile_context(profile)

    assert text.startswith("Candidat : Candidat - Animatrice jeunesse")
    assert "Ingénieur" not in text
    assert "Encadrer les 11-13 ans" in text
    assert "2024-06" in text


def test_format_evaluation_context_reads_weight_reason_and_warnings():
    from app.services.interview_prep_service import format_evaluation_context

    evaluation = {
        "score": 3.2,
        "bloc_a": {"summary": "Poste d'animation périscolaire"},
        "bloc_b": {
            "matched_requirements": [
                {"requirement": "BAFA", "weight": "critical", "candidate_evidence": "BAFA 2019",
                 "status": "partial_match", "evidence_tier": "inferred"}
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
async def test_star_stories_prompt_uses_job_offer_poste_and_entreprise():
    mock_resp = AsyncMock()
    mock_resp.choices = [AsyncMock(message=AsyncMock(content="[]"))]
    mock_resp.usage = AsyncMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    offer = {"poste": "Animateur périscolaire", "entreprise": "Mairie de Bourgoin", "description": "..."}

    with patch("app.services.interview_prep_service.acompletion", return_value=mock_resp) as mock_llm:
        with patch("app.services.interview_prep_service.record_api_usage", return_value=None):
            await generate_star_stories(db=None, user_id=ObjectId(), profile={}, offer=offer)

    prompt = mock_llm.call_args.kwargs["messages"][0]["content"]
    assert "Animateur périscolaire" in prompt
    assert "Mairie de Bourgoin" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("model,expected_temperature", [
    ("openai/gpt-5.6-terra", None),
    ("anthropic/claude-opus-5-5", None),
    ("gemini/gemini-3.8-flash", 0.2),
])
async def test_generators_omit_temperature_for_models_that_reject_it(model, expected_temperature):
    # GPT-5 et Claude 5 rejettent `temperature` : un appel qui l'envoie échoue en production.
    from app.services import interview_prep_service as ips

    mock_resp = AsyncMock()
    mock_resp.choices = [AsyncMock(message=AsyncMock(content="[]"))]
    mock_resp.usage = AsyncMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    offer = {"poste": "Dev", "entreprise": "Co", "description": "D"}

    with patch.object(ips, "DEFAULT_INTERVIEW_MODEL", model), \
         patch("app.services.interview_prep_service.acompletion", return_value=mock_resp) as mock_llm, \
         patch("app.services.interview_prep_service.record_api_usage", return_value=None):
        await ips.generate_star_stories(db=None, user_id=ObjectId(), profile={}, offer=offer)
        await ips.generate_anticipated_questions(db=None, user_id=ObjectId(), profile={}, offer=offer)
        await ips.generate_reverse_questions(db=None, user_id=ObjectId(), offer=offer)
        try:
            await ips.generate_audience_packs(db=None, user_id=ObjectId(), profile={}, offer=offer)
        except Exception:
            pass  # "[]" n'est pas un objet de packs : seul l'appel LLM nous intéresse ici
        question = AnticipatedQuestion(category="behavioral", question="Q ?", why_it_will_be_asked="W")
        try:
            await ips.evaluate_practice_answer(
                db=None, user_id=ObjectId(), offer=offer, evaluation=None, question=question, answer="R"
            )
        except ValueError:
            pass  # "[]" n'est pas un objet de retour : seul l'appel LLM nous intéresse ici

    assert mock_llm.call_count == 5
    for call in mock_llm.call_args_list:
        assert call.kwargs["model"] == model
        assert call.kwargs.get("temperature") == expected_temperature
        assert call.kwargs["drop_params"] is True


def _practice_llm_response(payload):
    mock_resp = AsyncMock()
    mock_resp.choices = [AsyncMock(message=AsyncMock(content=json.dumps(payload)))]
    mock_resp.usage = AsyncMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    return mock_resp


_PRACTICE_QUESTION = AnticipatedQuestion(
    category="behavioral",
    question="Parlez-moi d'une migration difficile.",
    why_it_will_be_asked="Exigence Kubernetes",
    key_points_to_cover=["Gestion du risque de coupure"],
)
_PRACTICE_STORY = StarRStory(
    title="Migration K8s",
    theme="Architecture",
    target_requirement="Kubernetes",
    situation="Cluster legacy de 40 services",
    task="Migrer sans coupure",
    action="Bascule progressive",
    result="Zéro incident",
    reflection="Automatiser plus tôt",
)


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

    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)) as mock_llm, \
         patch("app.services.interview_prep_service.record_api_usage", return_value=None) as mock_usage:
        attempt = await evaluate_practice_answer(
            db=None,
            user_id=ObjectId(),
            offer=offer,
            evaluation=None,
            question=_PRACTICE_QUESTION,
            answer="J'ai migré le cluster en douceur.",
            story=_PRACTICE_STORY,
        )

    assert [c.key for c in attempt.criteria] == ["structure", "quantified_result", "offer_fit", "coverage"]
    assert [c.score for c in attempt.criteria] == [1, 5, 4, 3]
    assert attempt.overall_score == 3.2
    assert attempt.question_id == _PRACTICE_QUESTION.id
    assert attempt.question == _PRACTICE_QUESTION.question
    assert attempt.missing == ["Préciser le résultat"]
    assert attempt.improved_answer == "J'ai migré 40 services."  # 40 vient de l'histoire liée
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
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", return_value=None):
        with pytest.raises(ValueError, match="coverage"):
            await evaluate_practice_answer(
                db=None,
                user_id=ObjectId(),
                offer={"poste": "SRE", "entreprise": "Co", "description": "D"},
                evaluation=None,
                question=_PRACTICE_QUESTION,
                answer="R",
            )


def test_practice_mask_invented_numbers():
    sources = "J'ai réduit la latence de 30 % sur 1,5 an."
    text = "Sur K8s et S3, j'ai réduit la latence de 30 % en 1.5 an pour 200 clients."
    assert _mask_invented_numbers(text, sources) == (
        "Sur K8s et S3, j'ai réduit la latence de 30 % en 1.5 an pour [à chiffrer] clients."
    )
