from unittest.mock import patch
import pytest

from tests.cover_letter_crew.fixtures import fake_response  # noqa: F401  (insère job_trackers dans sys.path)
from app.services.letter_guards import GuardReport
from cover_letter_crew import run_letter_pipeline_async

FIRST_CRITIC = {"verdict": "revise", "flaws": ["Défaut"], "fidelity_flaws": ["Transfert présenté comme direct"]}
PERSISTENT = {"verdict": "revise", "flaws": [], "fidelity_flaws": ["Transfert présenté comme direct"]}
RESOLVED = {"verdict": "pass", "flaws": [], "fidelity_flaws": []}
FAILED = {"verdict": "error", "flaws": [], "fidelity_flaws": [], "provider": "google", "role": "critic", "detail": "quota"}


@pytest.mark.parametrize("second_critic, violations, blocking, failures", [
    (PERSISTENT, ["Fidélité : Transfert présenté comme direct"], True, []),
    (RESOLVED, [], False, []),
    (FAILED, ["Fidélité : Transfert présenté comme direct"], True,
     [{"provider": "google", "role": "critic", "detail": "quota"}]),
])
async def test_fidelity_flaws_are_rechecked_on_final_letter(second_critic, violations, blocking, failures):
    clean = GuardReport()
    with patch("cover_letter_crew._call_analyst", return_value={"missions": []}), \
         patch("cover_letter_crew._get_cached_or_research_company", return_value=""), \
         patch("cover_letter_crew._call_writer", return_value="brouillon"), \
         patch("cover_letter_crew._call_critic", side_effect=[FIRST_CRITIC, second_critic]) as critic, \
         patch("cover_letter_crew._call_reviser", return_value="révision") as reviser, \
         patch("cover_letter_crew.evaluate_letter_guards", side_effect=[clean, clean]), \
         patch("cover_letter_crew.validate_cross_provider"):
        result = await run_letter_pipeline_async(offer_description="Offre", candidate_profile={}, company_name="Mairie")

    assert critic.call_count == 2
    assert critic.call_args_list[1].args[0] == "révision"
    assert reviser.call_args.args[2] == ["Défaut", "Transfert présenté comme direct"]
    assert result["guard_report"]["violations"] == violations
    assert result["guard_report"]["is_blocking"] is blocking
    assert result["provider_failures"] == failures
