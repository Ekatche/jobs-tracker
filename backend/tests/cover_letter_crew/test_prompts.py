from unittest.mock import patch, MagicMock
import pytest

from tests.cover_letter_crew.fixtures import fake_response
import cover_letter_crew

@pytest.mark.asyncio
async def test_writer_prompt_includes_voice_style_when_present():
    mock_choice = MagicMock()
    mock_choice.message.content = "Lettre générée"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp, \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "openai/gpt-5.6-terra"
        mock_llm.return_value.api_key = "fake_key"

        analyst_json = {
            "candidate_name": "Alice",
            "candidate_headline": "ML Engineer",
            "missions": ["Mission 1"],
            "selected_experiences": [],
            "stacks": ["Python"],
            "projects": [],
        }

        await cover_letter_crew._call_writer(
            analyst_json=analyst_json,
            company_name="Acme",
            voice_style="Direct, phrases courtes, pas de jargon marketing.",
        )

        assert mock_comp.called
        sent_messages = mock_comp.call_args[1]["messages"]
        sent_prompt = sent_messages[0]["content"]
        assert "Direct, phrases courtes, pas de jargon marketing." in sent_prompt


@pytest.mark.asyncio
async def test_writer_prompt_includes_writing_samples_when_present():
    mock_choice = MagicMock()
    mock_choice.message.content = "Lettre générée"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp, \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "openai/gpt-5.6-terra"
        mock_llm.return_value.api_key = "fake_key"

        await cover_letter_crew._call_writer(
            analyst_json={"candidate_name": "Alice", "missions": [], "stacks": [], "projects": []},
            company_name="Acme",
            writing_samples="Je travaille depuis deux ans sur des outils internes.",
        )

        sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
        assert "<exemples_du_candidat>" in sent_prompt
        assert "Je travaille depuis deux ans sur des outils internes." in sent_prompt


def test_voice_style_block_truncates_long_samples():
    block = cover_letter_crew._build_voice_style_block("", "a" * 10000)
    assert "a" * cover_letter_crew.WRITING_SAMPLES_MAX_CHARS in block
    assert "a" * (cover_letter_crew.WRITING_SAMPLES_MAX_CHARS + 1) not in block


def test_voice_style_block_empty_when_nothing_provided():
    assert cover_letter_crew._build_voice_style_block("", "") == ""


@pytest.mark.asyncio
async def test_reviser_prompt_includes_letter_and_analysis_data():
    mock_choice = MagicMock()
    mock_choice.message.content = "Lettre révisée"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp, \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "openai/gpt-5.6-terra"
        mock_llm.return_value.api_key = "fake_key"

        letter_text = "Madame, Monsieur, voici ma candidature chez Acme..."
        analyst_json = {
            "missions": ["Optimiser les pipelines BigQuery"],
            "selected_experiences": [{"company": "DataCorp"}],
        }
        critic_flaws = ["Accroche trop générique"]
        guard_report = {"violations": ["Point d'exclamation interdit"]}

        revised = await cover_letter_crew._call_reviser(
            letter_text=letter_text,
            analyst_json=analyst_json,
            critic_flaws=critic_flaws,
            guard_report=guard_report,
        )

        assert revised == "Lettre révisée"
        assert mock_comp.called
        sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
        assert "Madame, Monsieur, voici ma candidature chez Acme..." in sent_prompt
        assert "Optimiser les pipelines BigQuery" in sent_prompt
        assert "Accroche trop générique" in sent_prompt
        assert "Point d'exclamation interdit" in sent_prompt


@pytest.mark.asyncio
async def test_writer_prompt_includes_job_title_and_offer_terms():
    mock_choice = MagicMock()
    mock_choice.message.content = "Lettre générée"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp, \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "openai/gpt-5.6-terra"
        mock_llm.return_value.api_key = "fake_key"

        await cover_letter_crew._call_writer(
            analyst_json={
                "job_title": "Ingénieur Data & IA",
                "offer_terms": ["LIMS", "historian"],
                "missions": [],
                "selected_experiences": [],
                "stacks": [],
                "projects": [],
            },
            company_name="Acme",
        )

    sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
    assert "Intitulé du poste visé : Ingénieur Data & IA" in sent_prompt
    assert "LIMS, historian" in sent_prompt


@pytest.mark.asyncio
async def test_company_researcher_discards_truncated_summary():
    mock_choice = MagicMock()
    mock_choice.message.content = "Spécialisée dans la chimie verte, Acme produit sept"
    mock_choice.finish_reason = "length"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp), \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "gemini/gemini-3.8-flash"
        mock_llm.return_value.api_key = "fake_key"

        context = await cover_letter_crew._call_company_researcher("Acme", ["extrait"])

    assert context == ""


@pytest.mark.asyncio
async def test_call_analyst_sees_project_details():
    from cover_letter_crew import _call_analyst

    profile = {
        "experiences": [{"company": "Initech", "stack": ["Docker"]}],
        "projects": [{
            "name": "Survie multi-omique",
            "description": "Autoencodeur et perte de Cox sur profils génomiques",
            "stack": ["PyTorch"],
            "context": "recherche",
            "repo": "https://example.com/repo",
            "sources": ["github"],
        }],
    }

    with patch("cover_letter_crew.acompletion", return_value=fake_response('{"missions": ["M1"]}')) as mock_comp:
        result = await _call_analyst("Description", profile)

    sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
    assert "perte de Cox" in sent_prompt
    assert "PyTorch" in result["stacks"]
    assert result["projects"] == ["Survie multi-omique"]
    assert result["selected_projects"] == [{
        "name": "Survie multi-omique",
        "context": "recherche",
        "description": "Autoencodeur et perte de Cox sur profils génomiques",
        "stack": ["PyTorch"],
    }]


@pytest.mark.asyncio
async def test_writer_prompt_includes_project_details():
    mock_choice = MagicMock()
    mock_choice.message.content = "Lettre générée"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp, \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "openai/gpt-5.6-terra"
        mock_llm.return_value.api_key = "fake_key"

        await cover_letter_crew._call_writer(
            analyst_json={
                "missions": [],
                "selected_experiences": [],
                "stacks": [],
                "projects": ["Lecteur PDF"],
                "selected_projects": [{
                    "name": "Lecteur PDF",
                    "description": "OCR et NER sur rapports oncologiques",
                    "context": "client",
                }],
            },
            company_name="Acme",
        )

    sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
    assert "OCR et NER sur rapports oncologiques" in sent_prompt


@pytest.mark.asyncio
async def test_call_analyst_sees_education():
    from cover_letter_crew import _call_analyst

    profile = {
        "experiences": [],
        "projects": [],
        "education": [{
            "school": "Université de Lyon",
            "degree": "Master bio-informatique",
            "years": "",
            "topics": ["analyse multi-omique"],
        }],
        "certifications": [{"name": "Deep Learning Specialization", "issuer": "", "year": "2023", "topics": []}],
    }

    with patch("cover_letter_crew.acompletion", return_value=fake_response('{"missions": ["M1"]}')) as mock_comp:
        result = await _call_analyst("Description", profile)

    sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
    assert "analyse multi-omique" in sent_prompt
    assert result["selected_education"] == [
        {"school": "Université de Lyon", "degree": "Master bio-informatique", "topics": ["analyse multi-omique"]},
        {"name": "Deep Learning Specialization", "year": "2023"},
    ]


@pytest.mark.asyncio
async def test_analyst_prompt_requires_grounded_thesis():
    from cover_letter_crew import _call_analyst

    with patch("cover_letter_crew.acompletion", return_value=fake_response('{"missions": ["M1"]}')) as mock_comp:
        await _call_analyst("Description", {"experiences": [], "projects": []})

    sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
    assert "recouvrement" in sent_prompt
    assert "nomme" in sent_prompt
    assert "Synthèse thématique liant le parcours" not in sent_prompt


@pytest.mark.asyncio
async def test_writer_prompt_includes_education():
    mock_choice = MagicMock()
    mock_choice.message.content = "Lettre générée"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp, \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "openai/gpt-5.6-terra"
        mock_llm.return_value.api_key = "fake_key"

        await cover_letter_crew._call_writer(
            analyst_json={
                "missions": [],
                "selected_experiences": [],
                "stacks": [],
                "projects": [],
                "selected_projects": [],
                "selected_education": [{"degree": "Master bio-informatique", "topics": ["analyse multi-omique"]}],
            },
            company_name="Acme",
        )

    sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
    assert "Master bio-informatique" in sent_prompt
