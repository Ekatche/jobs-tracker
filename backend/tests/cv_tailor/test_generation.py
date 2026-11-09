import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models import (
    TailoredCVSchema,
)
from app.services.cv_tailor import (
    generate_tailored_cv_content,
)
from tests.cv_tailor.fixtures import SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION, VALID_LLM_OUTPUT


@pytest.mark.asyncio
async def test_generate_tailored_cv_content_success():
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content=f"```json\n{json.dumps(VALID_LLM_OUTPUT)}\n```"))
    ]
    mock_resp.usage = MagicMock(prompt_tokens=800, completion_tokens=450)

    with patch("app.services.cv_tailor.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_resp

        result = await generate_tailored_cv_content(
            profile=SAMPLE_PROFILE,
            offer=SAMPLE_OFFER,
            evaluation=SAMPLE_EVALUATION
        )

        assert isinstance(result, TailoredCVSchema)
        assert result.target_role_title == "Lead Python Developer"
        assert len(result.experiences) == 2
        assert result.experiences[0].company == "Tech Corp"
        assert len(result.prioritized_skills) == 2

        # Verify acompletion call was made with prompt containing target role & Bloc B
        mock_acompletion.assert_called_once()
        call_kwargs = mock_acompletion.call_args.kwargs
        messages = call_kwargs["messages"]
        prompt_content = messages[0]["content"]
        assert "Fintech Solutions" in prompt_content
        assert "Lead Python Developer" in prompt_content
        assert "Python" in prompt_content


@pytest.mark.asyncio
async def test_generate_tailored_cv_content_flags_hallucinations():
    hallucinated_output = dict(VALID_LLM_OUTPUT)
    hallucinated_output["experiences"] = [
        {
            "title": "CTO",
            "company": "Fake Phantom Corp",
            "location": "Paris",
            "start_date": "2023",
            "end_date": "Présent",
            "bullet_points": ["Invented bullet point"],
            "relevant_technologies": ["QuantumComputing"]
        }
    ]

    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps(hallucinated_output)))
    ]

    with patch("app.services.cv_tailor.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_resp

        with pytest.raises(ValueError, match="CV honesty verification failed"):
            await generate_tailored_cv_content(
                profile=SAMPLE_PROFILE,
                offer=SAMPLE_OFFER,
                evaluation=SAMPLE_EVALUATION
            )


@pytest.mark.asyncio
async def test_generate_tailored_cv_content_retries_with_violation_feedback():
    bad_output = json.loads(json.dumps(VALID_LLM_OUTPUT))
    bad_output["prioritized_skills"] = [
        {"category": "Divers", "skills": ["UnknownImaginaryFramework"]}
    ]
    bad_resp = MagicMock()
    bad_resp.choices = [MagicMock(message=MagicMock(content=json.dumps(bad_output)))]
    good_resp = MagicMock()
    good_resp.choices = [MagicMock(message=MagicMock(content=json.dumps(VALID_LLM_OUTPUT)))]

    with patch("app.services.cv_tailor.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.side_effect = [bad_resp, good_resp]

        result = await generate_tailored_cv_content(
            profile=SAMPLE_PROFILE, offer=SAMPLE_OFFER, evaluation=SAMPLE_EVALUATION
        )

    assert isinstance(result, TailoredCVSchema)
    assert mock_acompletion.call_count == 2
    second_prompt = mock_acompletion.call_args_list[1].kwargs["messages"][0]["content"]
    assert "UnknownImaginaryFramework" in second_prompt


@pytest.mark.asyncio
async def test_tailored_cv_schema_flattens_certification_dicts_from_llm():
    llm_payload = {
        **VALID_LLM_OUTPUT,
        "professional_summary": "Lead Python Developer sur FastAPI, Docker et PostgreSQL.",
        "certifications": [
            {"name": "Microsoft Certified: Azure Data Scientist", "issuer": "Microsoft", "year": None, "topics": []},
            {"name": "MLOps — Machine Learning Operations", "issuer": "Coursera", "year": "2024", "topics": []},
            {"name": "Expertise Big Data — 2021", "issuer": "", "year": "2021", "topics": []},
            {"name": "Analysis of bulk RNA-seq data", "issuer": "", "year": "2023", "topics": []},
            {"name": "", "issuer": "Ignored", "year": "2020", "topics": []},
        ],
    }
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(llm_payload)

    with patch("app.services.cv_tailor.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_response
        result = await generate_tailored_cv_content(
            profile=SAMPLE_PROFILE,
            offer=SAMPLE_OFFER,
            evaluation=SAMPLE_EVALUATION,
        )

    assert result.certifications == [
        "Microsoft Certified: Azure Data Scientist",
        "MLOps — Machine Learning Operations — Coursera (2024)",
        "Expertise Big Data — 2021",
        "Analysis of bulk RNA-seq data (2023)",
    ]
