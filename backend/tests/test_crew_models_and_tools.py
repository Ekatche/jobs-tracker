import pytest
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
