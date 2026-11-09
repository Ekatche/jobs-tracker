import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure job_trackers source is importable
job_trackers_path = Path(__file__).parents[2] / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))


def fake_response(text: str) -> MagicMock:
    mock = MagicMock()
    mock.choices = [MagicMock(message=MagicMock(content=text))]
    return mock
