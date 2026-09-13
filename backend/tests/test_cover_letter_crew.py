import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Ensure job_trackers source is importable
job_trackers_path = Path(__file__).parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

from cover_letter_crew import run_letter_pipeline_sync

def test_pipeline_executes_revision_when_critic_requests():
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
         patch("cover_letter_crew.validate_cross_provider"):

        result = run_letter_pipeline_sync(
            offer_description="Offre Biomérieux Lead Data",
            candidate_profile={"headline": "Data Engineer"},
            company_name="Biomérieux"
        )

        assert result["body"] == mock_revised_letter
        assert result["revised"] is True
        assert result["critic_verdict"]["verdict"] == "revise"
