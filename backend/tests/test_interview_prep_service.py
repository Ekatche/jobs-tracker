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
    BankStory,
    StoryExperience,
    StoryOrigin,
    StorySlot,
)
from app.services.interview_prep_service import (
    _clean_json_output,
    generate_audience_packs,
    generate_anticipated_questions,
    generate_reverse_questions,
    export_interview_prep_markdown,
    evaluate_practice_answer,
    _mask_invented_numbers,
    select_requirements,
    format_requirements_block,
    format_bank_summary,
    match_bank_stories,
    write_stories_for_requirements,
    carry_over_edited_angles,
    build_story_slots,
    RequirementPick,
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
async def test_writer_builds_story_and_slot_mocked():
    payload = {"items": [
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
    ]}

    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content=json.dumps(payload)))
    ]
    mock_resp.usage = AsyncMock(prompt_tokens=100, completion_tokens=200, total_tokens=300)

    profile = {"skills": ["Python", "Kafka"], "experiences": [{"company": "Tech Corp", "role": "Backend Engineer", "start": "2020-01"}]}
    offer = {"_id": ObjectId(), "title": "Senior Backend", "company": "ScaleUp", "description": "Need Kafka"}
    pick = RequirementPick(requirement="Expérience Kafka", covered=True)

    with patch("app.services.interview_prep_service.acompletion", return_value=mock_resp):
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
    """Chaque ligne du kit rend l'exigence, l'adéquation en français, l'angle, puis les
    faits de l'histoire de la banque ; une ligne sans histoire a un libellé dédié."""
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
async def test_writer_prompt_uses_job_offer_poste_and_entreprise():
    mock_resp = AsyncMock()
    mock_resp.choices = [AsyncMock(message=AsyncMock(content=json.dumps({"items": []})))]
    mock_resp.usage = AsyncMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    offer = {"_id": ObjectId(), "poste": "Animateur périscolaire", "entreprise": "Mairie de Bourgoin", "description": "..."}

    with patch("app.services.interview_prep_service.acompletion", return_value=mock_resp) as mock_llm:
        with patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
            await write_stories_for_requirements(db=None, user_id="u", profile={}, offer=offer, evaluation=None, picks=None)

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
    offer = {"_id": ObjectId(), "poste": "Dev", "entreprise": "Co", "description": "D"}

    with patch.object(ips, "DEFAULT_INTERVIEW_MODEL", model), \
         patch("app.services.interview_prep_service.acompletion", return_value=mock_resp) as mock_llm, \
         patch("app.services.interview_prep_service.record_api_usage", return_value=None):
        try:
            await ips.write_stories_for_requirements(
                db=None, user_id="u", profile={}, offer=offer, evaluation=None, picks=None
            )
        except ValueError:
            pass  # "[]" n'est pas un objet avec 'items' : seul l'appel LLM nous intéresse ici
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


# --- select_requirements / match_bank_stories (banque d'histoires STAR) ---

EVAL = {"bloc_b": {
    "matched_requirements": [{"requirement": "SQL", "weight": "meaningful"}, {"requirement": "Piloter une équipe", "weight": "critical"}],
    "missing_requirements": [{"requirement": "GCP", "weight": "critical"}, {"requirement": "Airflow", "weight": "high"}]}}


def test_select_requirements_orders_by_weight_then_bloc_b_order():
    assert [(p.requirement, p.covered) for p in select_requirements(EVAL)] == [
        ("Piloter une équipe", True), ("GCP", False), ("Airflow", False), ("SQL", True)]


def test_select_requirements_caps_at_limit():
    assert len(select_requirements(EVAL, limit=2)) == 2


def test_select_requirements_without_evaluation_is_empty():
    assert select_requirements(None) == [] and select_requirements({"bloc_b": {}}) == []


def test_select_requirements_skips_empty_requirement():
    evaluation = {"bloc_b": {"matched_requirements": [{"requirement": "", "weight": "critical"}]}}
    assert select_requirements(evaluation) == []


def test_format_requirements_block_without_picks_asks_to_extract():
    text = format_requirements_block(None)
    assert "5" in text and "exigences" in text.lower()


def test_format_requirements_block_numbers_from_one():
    picks = [RequirementPick(requirement="SQL"), RequirementPick(requirement="GCP")]
    assert format_requirements_block(picks) == "1. SQL\n2. GCP"


OFFER = {"_id": ObjectId(), "poste": "Lead Data", "entreprise": "Acme", "description": "Fiabiliser la plateforme data."}

s1 = BankStory(
    id="s1",
    user_id="u",
    title="Fiabilisation du pipeline nocturne",
    situation="Chez Acme, le pipeline nocturne échouait une nuit sur deux.",
    task="Fiabiliser le traitement sans régression.",
    action="J'ai ajouté des reprises idempotentes et un monitoring.",
    result="−60 % de temps de traitement et zéro incident depuis 3 mois.",
    reflection="Automatiser les tests de charge plus tôt.",
    key_tags=["data", "fiabilité"],
    origin=StoryOrigin(kind="manual"),
)


def test_format_bank_summary_formats_one_line_per_story():
    text = format_bank_summary([s1])
    assert text == "[s1] Fiabilisation du pipeline nocturne | sans expérience | −60 % de temps de traitement et zéro incident depuis 3 mois. | data, fiabilité"


@pytest.mark.asyncio
async def test_match_maps_by_index_and_masks_invented_numbers():
    # banque : histoire s1 dont le résultat est "−60 % de temps de traitement"
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "Gain de 75 % et −60 %"}]}
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(pick, slot)] = await match_bank_stories(
            None, "u", OFFER, [RequirementPick(requirement="Fiabiliser", covered=True)], [s1]
        )
    assert (slot.story_id, slot.fit, slot.requirement) == ("s1", "strong", "Fiabiliser")
    assert "75" not in slot.angle and "[à chiffrer]" in slot.angle and "60" in slot.angle


@pytest.mark.asyncio
async def test_match_ignores_story_id_outside_bank():
    payload = {"matches": [{"requirement_index": 1, "story_id": "story-of-someone-else", "fit": "strong", "angle": "x"}]}
    pick = RequirementPick(requirement="Fiabiliser", covered=True)
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await match_bank_stories(None, "u", OFFER, [pick], [s1])
    assert result[0][1] is None


@pytest.mark.asyncio
async def test_match_uncovered_requirement_is_transferable():
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "Pont AWS vers GCP"}]}
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await match_bank_stories(None, "u", OFFER, [RequirementPick(requirement="GCP", covered=False)], [s1])
    assert result[0][1].fit == "transferable"


@pytest.mark.asyncio
async def test_match_unmatched_requirement_stays_none():
    payload = {"matches": []}
    pick = RequirementPick(requirement="Fiabiliser", covered=True)
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(returned_pick, slot)] = await match_bank_stories(None, "u", OFFER, [pick], [s1])
    assert returned_pick is pick and slot is None


@pytest.mark.asyncio
async def test_match_without_picks_builds_from_ai_requirements_capped_at_five():
    payload = {"matches": [
        {"requirement_index": i, "requirement": f"Exigence {i}", "story_id": None, "fit": "partial", "angle": "a"}
        for i in range(1, 7)
    ]}
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await match_bank_stories(None, "u", OFFER, None, [s1])
    assert len(result) == 5
    assert [p.requirement for p, _ in result] == [f"Exigence {i}" for i in range(1, 6)]
    assert all(p.covered is None for p, _ in result)


@pytest.mark.asyncio
async def test_match_records_story_match_usage():
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "x"}]}
    pick = RequirementPick(requirement="Fiabiliser", covered=True)
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock) as mock_usage:
        await match_bank_stories(None, "u", OFFER, [pick], [s1])
    assert mock_usage.call_args.kwargs["metadata"]["sub_action"] == "story_match"


# --- write_stories_for_requirements / carry_over_edited_angles / build_story_slots ---

PROFILE = {"experiences": [{"company": "Alpha Corp", "role": "Data Engineer", "start": "2022-01"}]}

_RAW_STORY = {
    "title": "[Agilité] Titre percutant",
    "theme": "Architecture",
    "situation": "Situation détaillée",
    "task": "Tâche précise",
    "action": "Action concrète",
    "result": "Résultat de −60 % et zéro incident",
    "reflection": "Enseignement tiré",
    "key_tags": ["x"],
}


@pytest.mark.asyncio
async def test_writer_uncovered_without_neighbor_gives_no_experience():
    payload = {"items": [{"requirement_index": 1, "story": None, "experience": None, "fit": "strong", "angle": ""}]}
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(slot, story)] = await write_stories_for_requirements(
            None, "u", PROFILE, OFFER, None, [RequirementPick(requirement="GCP", covered=False)]
        )
    assert (slot.fit, slot.story_id, story) == ("no_experience", None, None)


@pytest.mark.asyncio
async def test_writer_uncovered_with_neighbor_gives_transferable():
    payload = {"items": [{
        "requirement_index": 1,
        "story": _RAW_STORY,
        "experience": {"company": "Alpha Corp", "role": "Data Engineer"},
        "fit": "strong",
        "angle": "",
    }]}
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(slot, story)] = await write_stories_for_requirements(
            None, "u", PROFILE, OFFER, None, [RequirementPick(requirement="GCP", covered=False)]
        )
    assert slot.fit == "transferable" and story.origin.kind == "generated" and slot.story_id == story.id


@pytest.mark.asyncio
async def test_writer_fewer_items_than_requirements():
    payload = {"items": [
        {"requirement_index": 1, "story": _RAW_STORY, "experience": None, "fit": "strong", "angle": ""},
    ]}
    picks = [RequirementPick(requirement="SQL", covered=True), RequirementPick(requirement="GCP", covered=False)]
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await write_stories_for_requirements(None, "u", PROFILE, OFFER, None, picks)
    assert [s.fit for s, _ in result] == ["strong", "no_experience"]


@pytest.mark.asyncio
async def test_writer_drops_experience_not_in_profile():
    payload = {"items": [
        {"requirement_index": 1, "story": _RAW_STORY, "experience": {"company": "Inconnue SA"}, "fit": "strong", "angle": ""},
        {"requirement_index": 2, "story": _RAW_STORY, "experience": {"company": "alpha corp"}, "fit": "strong", "angle": ""},
    ]}
    picks = [RequirementPick(requirement="R1", covered=True), RequirementPick(requirement="R2", covered=True)]
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        result = await write_stories_for_requirements(None, "u", PROFILE, OFFER, None, picks)
    assert result[0][1].experience is None
    assert result[1][1].experience == StoryExperience(company="Alpha Corp", role="Data Engineer", start="2022-01")


@pytest.mark.asyncio
async def test_writer_masks_numbers_absent_from_new_story():
    payload = {"items": [{
        "requirement_index": 1,
        "story": _RAW_STORY,
        "experience": None,
        "fit": "strong",
        "angle": "Gain de −90 %",
    }]}
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)), \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock):
        [(slot, story)] = await write_stories_for_requirements(
            None, "u", PROFILE, OFFER, None, [RequirementPick(requirement="X", covered=True)]
        )
    assert "90" not in slot.angle and "[à chiffrer]" in slot.angle


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
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)) as mock_llm, \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock) as mock_usage:
        slots, new_stories = await build_story_slots(None, "u", {}, OFFER, None, [], [])
    assert mock_llm.call_count == 1
    assert mock_usage.call_args.kwargs["metadata"]["sub_action"] == "stories"
    assert slots == [] and new_stories == []


@pytest.mark.asyncio
async def test_build_with_no_gap_skips_writer_call():
    evaluation = {"bloc_b": {"matched_requirements": [{"requirement": "Fiabiliser", "weight": "critical"}]}}
    payload = {"matches": [{"requirement_index": 1, "story_id": "s1", "fit": "strong", "angle": "x"}]}
    with patch("app.services.interview_prep_service.acompletion", return_value=_practice_llm_response(payload)) as mock_llm, \
         patch("app.services.interview_prep_service.record_api_usage", new_callable=AsyncMock) as mock_usage:
        slots, new_stories = await build_story_slots(None, "u", {}, OFFER, evaluation, [s1], [])
    assert mock_llm.call_count == 1
    assert mock_usage.call_args.kwargs["metadata"]["sub_action"] == "story_match"
    assert new_stories == []
    assert len(slots) == 1 and slots[0].fit == "strong" and slots[0].story_id == "s1"
