import sys
from pathlib import Path
from unittest.mock import patch

import pytest

job_trackers_path = Path(__file__).parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

from cover_letter_crew import run_letter_pipeline_async


@pytest.mark.asyncio
async def test_pipeline_returns_analyst_data_as_guard_context():
    analyst = {"missions": ["Pipelines"], "stacks": ["Nextflow"], "companies": ["Sanofi"]}

    with patch("cover_letter_crew._call_analyst", return_value=dict(analyst)), \
         patch("cover_letter_crew._call_writer", return_value="Lettre propre."), \
         patch("cover_letter_crew._call_critic", return_value={"verdict": "pass", "flaws": []}), \
         patch("cover_letter_crew._get_cached_or_research_company", return_value=""), \
         patch("cover_letter_crew.validate_cross_provider"):
        result = await run_letter_pipeline_async(
            offer_description="Offre", candidate_profile={}, company_name="Acme", job_title="Data Engineer"
        )

    context = result["guard_context"]["analyst_data"]
    assert context["stacks"] == ["Nextflow"]
    assert context["company_name"] == "Acme"
    assert context["job_title"] == "Data Engineer"
