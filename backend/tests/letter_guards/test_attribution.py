import pytest

from app.services.letter_guards import evaluate_letter_guards
from tests.letter_guards.fixtures import ATTRIBUTION_ANALYST, ATTRIBUTION_CASES


@pytest.mark.parametrize("sentence, expected", ATTRIBUTION_CASES)
def test_attribution(sentence, expected):
    report = evaluate_letter_guards(sentence, "", ATTRIBUTION_ANALYST)
    found = [v for v in report.violations if v.startswith("Attribution erronée")]
    assert found == ([f"Attribution erronée : {expected}"] if expected else [])
