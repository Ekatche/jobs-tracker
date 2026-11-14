from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ats.router import (
    ExpiredOfferError,
    check_smartrecruiters_board_status,
    detect_non_content_marker,
    extract_ashby_job,
    extract_ats_or_jsonld_offer,
    extract_smartrecruiters_job,
    extract_workday_job,
)


def _mock_response(status_code: int, payload: object = None, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = text
    return resp


def _mock_client(resp: MagicMock) -> MagicMock:
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    return client


@pytest.mark.parametrize(
    ("html_text", "expected_category"),
    [
        ("<html><body><h1>404 Not Found</h1><p>This job is no longer open.</p></body></html>", "404-shell"),
        ("<html><body><p>Offre n’existe plus sur notre portail.</p></body></html>", "404-shell"),
        ("<html><body><p>Please sign in to apply to this position.</p></body></html>", "login-wall"),
        ("<html><body><p>Connexion requise pour accéder à cette annonce.</p></body></html>", "login-wall"),
        ("<html><body><p>Subscribe to read the full listing.</p></body></html>", "paywall"),
        ("<html><body><p>You need to enable JavaScript to view this page.</p></body></html>", "js-required"),
        (
            "<html><body><nav>Sign in</nav><main><h2>Missions</h2><p>" + ("Python backend " * 95) + "</p></main></body></html>",
            None,
        ),
        ("", None),
    ],
)
def test_detect_non_content_marker(html_text: str, expected_category: str | None):
    result = detect_non_content_marker(html_text)
    if expected_category is None:
        assert result is None
    else:
        assert result is not None and result["category"] == expected_category


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"totalFound": 0, "content": []}, "not_found"),
        ({"totalFound": 3, "content": []}, "not_found"),
        ({"totalFound": 0, "content": [{"id": "1"}]}, "not_found"),
        (None, "not_found"),
        ({"totalFound": 1, "content": [{"id": "1"}]}, "active"),
    ],
)
def test_smartrecruiters_board_status_fix_4215(payload: object, expected_status: str):
    assert check_smartrecruiters_board_status(payload) == expected_status


@pytest.mark.asyncio
async def test_smartrecruiters_empty_description_returns_none():
    payload = {"name": "Backend Engineer", "company": {"name": "Acme"}, "jobAd": {"sections": {}}}
    client = _mock_client(_mock_response(200, payload))
    res = await extract_smartrecruiters_job("https://jobs.smartrecruiters.com/Acme/12345-eng", client)
    assert res is None


@pytest.mark.asyncio
async def test_extract_ashby_job_success_workplace_priority():
    payload = {
        "organization": {"name": "Linear"},
        "jobs": [
            {
                "id": "job-123",
                "title": "Staff Backend Engineer",
                "isListed": True,
                "workplaceType": "Hybrid",
                "isRemote": True,
                "location": "Paris / Europe",
                "employmentType": "FullTime",
                "publishedAt": "2026-11-01",
                "descriptionHtml": "<p>Build fast APIs in Python.</p>",
                "compensation": {"compensationTierSummary": "€110k - €130k"},
            }
        ],
    }
    client = _mock_client(_mock_response(200, payload))
    res = await extract_ashby_job("https://jobs.ashbyhq.com/linear/job-123/application", client)
    assert res is not None
    assert res["poste"] == "Staff Backend Engineer"
    assert res["entreprise"] == "Linear"
    assert res["politique_teletravail"] == "Hybride"
    assert res["salaire"] == "€110k - €130k"
    assert res["type_contrat"] == "CDI"
    assert res["ats_platform"] == "ashby"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "payload"),
    [
        (404, {}),
        (200, {"jobs": [{"id": "job-123", "isListed": False, "title": "Old"}]}),
        (200, {"jobs": []}),
    ],
)
async def test_extract_ashby_job_expired(status_code: int, payload: dict):
    client = _mock_client(_mock_response(status_code, payload))
    with pytest.raises(ExpiredOfferError):
        await extract_ashby_job("https://jobs.ashbyhq.com/linear/job-123", client)


@pytest.mark.asyncio
async def test_extract_workday_job_success():
    payload = {
        "jobPostingInfo": {
            "title": "Principal Data Engineer",
            "jobDescription": "<ul><li>Architect ETL pipelines</li></ul>",
            "location": "Lyon",
            "timeType": "Full time",
            "remoteType": "Remote",
            "startDate": "2026-11-05",
            "canApply": True,
        }
    }
    client = _mock_client(_mock_response(200, payload))
    res = await extract_workday_job(
        "https://acme.wd5.myworkdayjobs.com/en-US/Careers/job/Lyon/Principal-Data-Engineer_R42",
        client,
    )
    called_url = client.get.call_args.args[0]
    assert called_url == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/Careers/job/Lyon/Principal-Data-Engineer_R42"
    assert res is not None
    assert res["poste"] == "Principal Data Engineer"
    assert res["politique_teletravail"] == "Full Remote"
    assert res["type_contrat"] == "CDI"
    assert res["ats_platform"] == "workday"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "payload"),
    [
        (404, {}),
        (200, {"jobPostingInfo": {"title": "Closed", "jobDescription": "", "canApply": False}}),
    ],
)
async def test_extract_workday_job_expired(status_code: int, payload: dict):
    client = _mock_client(_mock_response(status_code, payload))
    with pytest.raises(ExpiredOfferError):
        await extract_workday_job("https://acme.wd5.myworkdayjobs.com/Careers/job/Lyon/Role_R9", client)


@pytest.mark.asyncio
async def test_extract_ats_router_dispatch_and_non_content_gates():
    ashby_payload = {
        "jobs": [{"id": "j1", "title": "ML Eng", "isListed": True, "descriptionPlain": "ML systems"}]
    }
    res_ashby = await extract_ats_or_jsonld_offer(
        "https://jobs.ashbyhq.com/co/j1",
        client=_mock_client(_mock_response(200, ashby_payload)),
    )
    assert res_ashby is not None and res_ashby["ats_platform"] == "ashby"

    wd_payload = {
        "jobPostingInfo": {"title": "Cloud Eng", "jobDescription": "<p>Cloud infra</p>", "canApply": True}
    }
    res_wd = await extract_ats_or_jsonld_offer(
        "https://beta.wd3.myworkdayjobs.com/Ext/job/Cloud-Eng_R1",
        client=_mock_client(_mock_response(200, wd_payload)),
    )
    assert res_wd is not None and res_wd["ats_platform"] == "workday"

    res_login = await extract_ats_or_jsonld_offer(
        "https://example.com/jobs/1",
        client=_mock_client(_mock_response(200, text="<html><body>Sign in to view job</body></html>")),
    )
    assert res_login is None

    with pytest.raises(ExpiredOfferError):
        await extract_ats_or_jsonld_offer(
            "https://example.com/jobs/2",
            client=_mock_client(_mock_response(200, text="<html><body>This job is no longer open</body></html>")),
        )
