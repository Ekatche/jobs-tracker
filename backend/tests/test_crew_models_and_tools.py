import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../job_trackers/src/job_trackers")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import OptimizedQueries, JobUrlItem, FilteredJobOffersResult
from tools.custom_tool import TavilyJobBoardSearchTool, TavilySearchInput
from app.services.job_offers import extract_urls_from_crew


class TestCrewModels:
    def test_optimized_queries_valid(self):
        query_data = {
            "primary_query": "offres emploi Data Scientist Lyon CDI",
            "alternative_queries": [
                "recrutement Data Scientist Lyon",
                "Machine Learning Engineer Lyon",
            ],
            "extracted_job_title": "Data Scientist",
            "extracted_location": "Lyon",
            "contract_type": "CDI",
        }
        model = OptimizedQueries(**query_data)
        assert model.primary_query == "offres emploi Data Scientist Lyon CDI"
        assert len(model.alternative_queries) == 2
        assert model.extracted_job_title == "Data Scientist"
        assert model.extracted_location == "Lyon"
        assert model.contract_type == "CDI"

    def test_filtered_job_offers_result_valid(self):
        item1 = JobUrlItem(
            url="https://www.welcometothejungle.com/fr/companies/abc/jobs/data-scientist",
            source_platform="Welcome to the Jungle",
            is_direct_job_offer=True,
            relevance_score=9,
            notes="Offre directe récente",
        )
        item2 = JobUrlItem(
            url="https://candidat.francetravail.fr/offres/recherche/detail/12345",
            source_platform="France Travail",
            is_direct_job_offer=True,
            relevance_score=8,
        )
        result = FilteredJobOffersResult(
            urls=[item1.url, item2.url],
            items=[item1, item2],
        )
        assert len(result.urls) == 2
        assert len(result.items) == 2
        assert result.items[0].source_platform == "Welcome to the Jungle"


class TestTavilyTool:
    def test_tool_instantiation_and_schema(self):
        tool = TavilyJobBoardSearchTool()
        assert tool.name == "Recherche d'offres d'emploi sur job boards"
        assert tool.args_schema == TavilySearchInput

    def test_invalid_query_returns_empty_list(self):
        tool = TavilyJobBoardSearchTool()
        result = tool._run(query="")
        assert result == []
        result_none = tool._run()
        assert result_none == []

    def test_board_pass_prefers_listed_sites_without_restricting_the_web(self):
        from unittest.mock import MagicMock
        tool = TavilyJobBoardSearchTool()
        mock_client = MagicMock()

        def mock_search(query, **kwargs):
            inc_domains = kwargs.get("include_domains") or []
            if "welcometothejungle.com" in inc_domains:
                # Passe 1 : job boards préférés, le reste du web peut remonter
                return {
                    "results": [
                        {"url": "https://www.welcometothejungle.com/fr/jobs/1", "score": 0.81},
                        {"url": "https://fr.jooble.org/spam-listing", "score": 0.5},
                        {"url": "https://candidat.francetravail.fr/offres/recherche/detail/123", "score": 0.7},
                        {"url": "https://www.mairie-exemple.fr/offre-animateur-jeunesse", "score": 0.62},
                    ]
                }
            elif "greenhouse.io" in inc_domains:
                # Passe 2 : ATS d'entreprises
                return {
                    "results": [
                        {"url": "https://boards.greenhouse.io/acme/jobs/123"},
                        {"url": "https://www.welcometothejungle.com/fr/jobs/1"},  # doublon
                    ]
                }
            return {"results": []}

        mock_client.search.side_effect = mock_search
        tool.client = mock_client

        results = tool._run(query="Animateur socioculturel Bourgoin-Jallieu")

        calls = [c.kwargs for c in mock_client.search.call_args_list]
        [board] = [c for c in calls if "greenhouse.io" not in c["include_domains"]]
        [ats] = [c for c in calls if "greenhouse.io" in c["include_domains"]]
        # Un seul appel job boards : en `restrict`, chaque site renvoyait ses pages même hors sujet.
        assert board["include_domains_mode"] == "prefer"
        assert board["country"] == "france"
        assert "choisirleservicepublic.gouv.fr" in board["include_domains"]
        # Indeed, LinkedIn, HelloWork (jobspy) et France Travail (abandonné) ne coûtent aucun crédit.
        for domain in ("indeed.com", "linkedin.com", "hellowork.com", "francetravail.fr"):
            assert domain in board["exclude_domains"]
        # Les ATS restent un filtre dur.
        assert ats.get("include_domains_mode", "restrict") == "restrict"
        assert mock_client.search.call_count == 2
        # Jooble et France Travail écartés même si Tavily les renvoie, WTTJ dédoublonné
        assert results == [
            "https://www.welcometothejungle.com/fr/jobs/1",
            "https://www.mairie-exemple.fr/offre-animateur-jeunesse",
            "https://boards.greenhouse.io/acme/jobs/123",
        ]

    def test_funnel_handles_partial_pass_failure(self):
        from unittest.mock import MagicMock
        tool = TavilyJobBoardSearchTool()
        mock_client = MagicMock()

        # Pass 1 fails, but Pass 2 (ATS) succeeds
        def mock_search(query, **kwargs):
            inc_domains = kwargs.get("include_domains") or []
            if "welcometothejungle.com" in inc_domains:
                raise RuntimeError("Pass 1 API timeout")
            elif "greenhouse.io" in inc_domains:
                return {
                    "results": [
                        {"url": "https://jobs.lever.co/corp/789"},
                    ]
                }
            return {"results": []}

        mock_client.search.side_effect = mock_search
        tool.client = mock_client

        results = tool._run(query="DevOps Paris")
        assert len(results) == 1
        assert results[0] == "https://jobs.lever.co/corp/789"


class TestExtractUrlsFromCrew:
    def test_extract_from_direct_pydantic(self):
        pydantic_res = FilteredJobOffersResult(
            urls=[
                "https://www.welcometothejungle.com/fr/companies/test/jobs/1",
                "https://www.apec.fr/offre/2",
            ],
            items=[],
        )
        extracted = extract_urls_from_crew(pydantic_res)
        assert extracted == [
            "https://www.welcometothejungle.com/fr/companies/test/jobs/1",
            "https://www.apec.fr/offre/2",
        ]

    def test_extract_from_crew_output_object(self):
        class MockCrewOutput:
            def __init__(self, pydantic_obj):
                self.pydantic = pydantic_obj

        mock_out = MockCrewOutput(
            FilteredJobOffersResult(
                urls=["https://hellowork.com/job/123"],
                items=[],
            )
        )
        extracted = extract_urls_from_crew(mock_out)
        assert extracted == ["https://hellowork.com/job/123"]

    def test_extract_from_tasks_output(self):
        class MockTaskOutput:
            def __init__(self, pydantic_obj):
                self.pydantic = pydantic_obj

        class MockCrewOutputWithTasks:
            def __init__(self, task_outputs):
                self.tasks_output = task_outputs

        mock_task = MockTaskOutput(
            FilteredJobOffersResult(
                urls=["https://linkedin.com/jobs/view/999"],
                items=[],
            )
        )
        mock_crew = MockCrewOutputWithTasks([mock_task])
        extracted = extract_urls_from_crew(mock_crew)
        assert extracted == ["https://linkedin.com/jobs/view/999"]

    def test_extract_from_markdown_json_fallback(self):
        class MockRawOutput:
            def __init__(self, raw_str):
                self.raw = raw_str

        raw_json = """```json
[
  "https://www.apec.fr/candidat/offre/123",
  "https://candidat.francetravail.fr/offres/detail/456"
]
```"""
        mock_out = MockRawOutput(raw_json)
        extracted = extract_urls_from_crew(mock_out)
        assert len(extracted) == 2
        assert "https://www.apec.fr/candidat/offre/123" in extracted

    def test_extract_from_dict_json_fallback(self):
        dict_json = """```json
{
  "urls": [
    "https://www.welcometothejungle.com/fr/companies/abc/jobs/ds"
  ]
}
```"""
        class MockRawOutput:
            def __init__(self, raw_str):
                self.raw = raw_str

        extracted = extract_urls_from_crew(MockRawOutput(dict_json))
        assert extracted == ["https://www.welcometothejungle.com/fr/companies/abc/jobs/ds"]


class TestJobTrackerLLM:
    def test_reasoning_models_neutralize_stop_and_add_drop_params(self):
        from crew import JobTrackerLLM, is_reasoning_model, _get_openai_temperature

        # Test reasoning model detection
        assert is_reasoning_model("gpt-5.6-luna") is True
        assert is_reasoning_model("openai/gpt-5-nano") is True
        assert is_reasoning_model("o1-mini") is True
        assert is_reasoning_model("o3-mini") is True
        assert is_reasoning_model("gemini/gemini-3.8-flash") is False
        assert is_reasoning_model("gpt-4o-mini") is False

        # Test temperature configuration
        assert _get_openai_temperature("o1-mini") is None
        assert _get_openai_temperature("o3-mini") is None
        assert _get_openai_temperature("gpt-5.6-luna") == 1.0
        assert _get_openai_temperature("gpt-4o-mini") == 0.1

        # Test JobTrackerLLM behavior for reasoning models
        llm_reasoning = JobTrackerLLM(model="gpt-5.6-luna", api_key="dummy")
        assert llm_reasoning.supports_stop_words() is False
        params = llm_reasoning._prepare_completion_params("hello")
        assert "stop" not in params
        assert params.get("drop_params") is True

        # Test JobTrackerLLM behavior for non-reasoning models
        llm_standard = JobTrackerLLM(model="gemini/gemini-3.8-flash", api_key="dummy")
        assert llm_standard.supports_stop_words() is True
        params_std = llm_standard._prepare_completion_params("hello")
        assert "stop" in params_std


class TestRunCrewSearchToolGuard:
    def _fake_crews(self, tool_calls_per_attempt):
        from unittest.mock import MagicMock
        from crew import tavily_search

        crews = []
        for called in tool_calls_per_attempt:
            agent = MagicMock()
            agent.tools_results = [{"tool_name": tavily_search.name, "result": []}] if called else []
            crew = MagicMock()
            crew.agents = [agent]
            crew.kickoff.return_value = f"result-{len(crews)}"
            crews.append(crew)
        return crews

    def test_tool_result_is_the_search_task_answer(self):
        from crew import tavily_search

        assert tavily_search.result_as_answer is True

    def test_retries_when_search_tool_not_called(self, monkeypatch):
        import job_trackers.src.job_trackers.main as main
        from unittest.mock import MagicMock

        crews = self._fake_crews([False, True])
        factory = MagicMock()
        factory.return_value.crew.side_effect = crews
        monkeypatch.setattr(main, "JobTrackers", factory)

        assert main.run_crew("data engineer lyon") == "result-1"
        assert factory.return_value.crew.call_count == 2

    def test_fails_when_search_tool_never_called(self, monkeypatch):
        import job_trackers.src.job_trackers.main as main
        import pytest
        from unittest.mock import MagicMock

        factory = MagicMock()
        factory.return_value.crew.side_effect = self._fake_crews([False, False])
        monkeypatch.setattr(main, "JobTrackers", factory)

        with pytest.raises(Exception, match="n'a pas appelé l'outil Tavily"):
            main.run_crew("data engineer lyon")


class TestAirflowCollectionPipeline:
    def test_total_failure_raises_runtime_error(self, monkeypatch):
        import pytest

        # Import the execute_collection_pipeline function
        dags_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../airflow/dags"))
        if not os.path.exists(dags_path):
            pytest.skip("Airflow DAGs not mounted in current environment")
        sys.path.append(dags_path)
        try:
            from collect_job_offers import execute_collection_pipeline
        except ImportError:
            pytest.skip("collect_job_offers DAG not importable")

        def mock_failing_collect(query, use_web_search=True):
            raise ValueError("LLM stop error")

        import app.tasks.job_offers_collectors
        monkeypatch.setattr(app.tasks.job_offers_collectors, "collect_offers_sync", mock_failing_collect)

        with pytest.raises(RuntimeError, match="Échec total du pipeline de collecte"):
            execute_collection_pipeline.function(["query 1", "query 2"])

    def test_partial_failure_returns_partial_failure_status(self, monkeypatch):
        import pytest

        dags_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../airflow/dags"))
        if not os.path.exists(dags_path):
            pytest.skip("Airflow DAGs not mounted in current environment")
        sys.path.append(dags_path)
        try:
            from collect_job_offers import execute_collection_pipeline
        except ImportError:
            pytest.skip("collect_job_offers DAG not importable")

        def mock_mixed_collect(query, use_web_search=True):
            if "query 1" in query:
                return {"saved": 2, "updated": 1}
            raise ValueError("LLM stop error")

        import app.tasks.job_offers_collectors
        monkeypatch.setattr(app.tasks.job_offers_collectors, "collect_offers_sync", mock_mixed_collect)

        summary = execute_collection_pipeline.function(["query 1", "query 2"])
        assert summary["status"] == "partial_failure"
        assert summary["total_saved"] == 2
        assert summary["total_updated"] == 1
        assert len(summary["results"]) == 2

    def test_afternoon_run_disables_web_search_for_every_query(self, monkeypatch):
        import pytest

        dags_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../airflow/dags"))
        if not os.path.exists(dags_path):
            pytest.skip("Airflow DAGs not mounted in current environment")
        sys.path.append(dags_path)
        try:
            from collect_job_offers import execute_collection_pipeline
        except ImportError:
            pytest.skip("collect_job_offers DAG not importable")

        received = []

        def mock_collect(query, use_web_search=True):
            received.append(use_web_search)
            return {"saved": 0, "updated": 0}

        import app.tasks.job_offers_collectors
        monkeypatch.setattr(app.tasks.job_offers_collectors, "collect_offers_sync", mock_collect)
        monkeypatch.setattr(app.tasks.job_offers_collectors, "is_web_search_run", lambda now: False)

        execute_collection_pipeline.function(["query 1", "query 2"])
        assert received == [False, False]

