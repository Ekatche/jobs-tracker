from unittest.mock import patch, MagicMock
import pytest

from tests.cover_letter_crew.fixtures import fake_response  # noqa: F401  (insère job_trackers dans sys.path)
from cover_letter_crew import run_letter_pipeline_async

@pytest.mark.asyncio
async def test_pipeline_executes_revision_when_critic_requests():
    mock_analyst = {
        "missions": ["Lead data pipelines"],
        "selected_experiences": [{"company": "Sanofi", "missions": ["Nextflow"]}],
        "stacks": ["Nextflow", "Kafka"],
        "companies": ["Sanofi", "Biomérieux"],
        "projects": []
    }
    mock_writer_letter = "Première version de la lettre Madame, Monsieur..."
    mock_critic_verdict = {"verdict": "revise", "flaws": ["Ton trop convenu"]}
    mock_revised_letter = "Version révisée et corrigée..."

    with patch("cover_letter_crew._call_analyst", return_value=mock_analyst), \
         patch("cover_letter_crew._call_writer", return_value=mock_writer_letter), \
         patch("cover_letter_crew._call_critic", return_value=mock_critic_verdict), \
         patch("cover_letter_crew._call_reviser", return_value=mock_revised_letter), \
         patch("cover_letter_crew._get_cached_or_research_company", return_value=""), \
         patch("cover_letter_crew.validate_cross_provider"):

        result = await run_letter_pipeline_async(
            offer_description="Offre Biomérieux Lead Data",
            candidate_profile={"headline": "Data Engineer"},
            company_name="Biomérieux",
            job_title="Lead Data Engineer",
        )

        assert result["body"] == mock_revised_letter
        assert result["revised"] is True
        assert result["critic_verdict"]["verdict"] == "revise"
        context = result["guard_context"]["analyst_data"]
        assert context["stacks"] == ["Nextflow", "Kafka"]
        assert context["company_name"] == "Biomérieux"
        assert context["job_title"] == "Lead Data Engineer"


@pytest.mark.asyncio
async def test_pipeline_triggers_revision_and_reports_provider_failure_on_critic_error():
    mock_analyst = {
        "missions": ["Lead data pipelines"],
        "selected_experiences": [],
        "stacks": [],
        "companies": [],
        "projects": [],
    }
    mock_writer_letter = "Lettre rédigée normalement..."
    mock_critic_error = {
        "verdict": "error",
        "flaws": [],
        "provider": "google",
        "role": "critic",
        "detail": "quota dépassé",
    }
    mock_revised_letter = "Lettre révisée après panne du critique..."

    with patch("cover_letter_crew._call_analyst", return_value=mock_analyst), \
         patch("cover_letter_crew._call_writer", return_value=mock_writer_letter), \
         patch("cover_letter_crew._call_critic", return_value=mock_critic_error), \
         patch("cover_letter_crew._call_reviser", return_value=mock_revised_letter) as mock_reviser, \
         patch("cover_letter_crew._get_cached_or_research_company", return_value=""), \
         patch("cover_letter_crew.validate_cross_provider"):

        result = await run_letter_pipeline_async(
            offer_description="Offre Acme",
            candidate_profile={"headline": "Data Engineer"},
            company_name="Acme",
        )

    assert mock_reviser.called
    assert result["revised"] is True
    assert result["body"] == mock_revised_letter
    assert result["provider_failures"] == [
        {"provider": "google", "role": "critic", "detail": "quota dépassé"}
    ]


@pytest.mark.asyncio
async def test_company_research_failure_does_not_break_pipeline():
    mock_analyst = {
        "missions": ["Lead data pipelines"],
        "selected_experiences": [],
        "stacks": [],
        "companies": [],
        "projects": [],
    }
    mock_writer_letter = "Lettre générée malgré l'erreur..."

    with patch("cover_letter_crew._call_analyst", return_value=mock_analyst), \
         patch("cover_letter_crew._search_company_web", side_effect=Exception("Tavily unreachable")), \
         patch("cover_letter_crew._call_writer", return_value=mock_writer_letter), \
         patch("cover_letter_crew._call_critic", return_value={"verdict": "pass", "flaws": []}), \
         patch("cover_letter_crew.evaluate_letter_guards") as mock_guards, \
         patch("cover_letter_crew.validate_cross_provider"):

        mock_guard_report = MagicMock()
        mock_guard_report.is_blocking = False
        mock_guards.return_value = mock_guard_report

        result = await run_letter_pipeline_async(
            offer_description="Offre Acme",
            candidate_profile={"headline": "Data Engineer"},
            company_name="Acme",
        )

    assert result.get("body") == mock_writer_letter


def _guards(*violations):
    from app.services.letter_guards import GuardReport
    return GuardReport(is_blocking=bool(violations), violations=list(violations), warnings=[], stats={})


async def _run_with_guards(guard_reports, reviser_outputs):
    with patch("cover_letter_crew._call_analyst", return_value={"missions": []}), \
         patch("cover_letter_crew._get_cached_or_research_company", return_value=""), \
         patch("cover_letter_crew._call_writer", return_value="brouillon"), \
         patch("cover_letter_crew._call_critic", return_value={"verdict": "revise", "flaws": ["Défaut"]}), \
         patch("cover_letter_crew._call_reviser", side_effect=reviser_outputs) as reviser, \
         patch("cover_letter_crew.evaluate_letter_guards", side_effect=guard_reports), \
         patch("cover_letter_crew.validate_cross_provider"):
        result = await run_letter_pipeline_async(
            offer_description="Offre", candidate_profile={}, company_name="Mairie"
        )
    return result, reviser


@pytest.mark.asyncio
async def test_second_revision_runs_when_guards_still_block():
    result, reviser = await _run_with_guards(
        [_guards("A"), _guards("Formule accordée"), _guards()],
        ["révision 1", "révision 2"],
    )
    assert reviser.call_count == 2
    second = reviser.call_args_list[1].args
    assert second[0] == "révision 1"
    assert second[2] == []
    assert second[3]["violations"] == ["Formule accordée"]
    assert result["body"] == "révision 2"
    assert result["guard_report"]["violations"] == []


@pytest.mark.asyncio
async def test_no_second_revision_when_first_revision_is_clean():
    result, reviser = await _run_with_guards([_guards("A"), _guards()], ["révision 1"])
    assert reviser.call_count == 1
    assert result["body"] == "révision 1"


@pytest.mark.asyncio
async def test_second_revision_is_discarded_when_it_is_worse():
    result, reviser = await _run_with_guards(
        [_guards("A"), _guards("B"), _guards("B", "C")],
        ["révision 1", "révision 2"],
    )
    assert reviser.call_count == 2
    assert result["body"] == "révision 1"
    assert result["guard_report"]["violations"] == ["B"]


@pytest.mark.asyncio
async def test_pipeline_passes_job_title_and_capitalized_name_to_writer():
    mock_analyst = {"missions": [], "selected_experiences": [], "stacks": [], "companies": [], "projects": []}

    with patch("cover_letter_crew._call_analyst", return_value=mock_analyst) as analyst, \
         patch("cover_letter_crew._call_writer", return_value="Lettre") as writer, \
         patch("cover_letter_crew._call_critic", return_value={"verdict": "pass", "flaws": []}), \
         patch("cover_letter_crew._get_cached_or_research_company", return_value=""), \
         patch("cover_letter_crew.evaluate_letter_guards") as guards, \
         patch("cover_letter_crew.validate_cross_provider"):
        guards.return_value.is_blocking = False
        guards.return_value.model_dump.return_value = {}

        await run_letter_pipeline_async(
            offer_description="Offre",
            candidate_profile={},
            company_name="Acme",
            candidate_name="eliel Katche",
            job_title="Ingénieur Data & IA",
        )

    assert analyst.call_args[0][2] == "Eliel Katche"
    assert writer.call_args[0][0]["job_title"] == "Ingénieur Data & IA"
