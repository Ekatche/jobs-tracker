import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.tasks.verify_job_offers import (
    check_url_http_fast,
    detect_closure_in_text,
    extract_json_ld_valid_through,
    extract_visible_text,
    is_redirected_to_generic_listing,
    verify_job_offers_workflow,
    verify_single_offer,
)


def test_detect_closure_in_text():
    """Test text pattern matching for closed/expired job indicators."""
    assert detect_closure_in_text("Cette offre n'est plus disponible actuellement.") is not None
    assert detect_closure_in_text("Ce poste a été pourvu.") is not None
    assert detect_closure_in_text("Attention: candidatures closes.") is not None
    assert detect_closure_in_text("This job is no longer available.") is not None
    assert detect_closure_in_text("Position has been filled.") is not None

    # Valid job description should NOT trigger closure
    assert (
        detect_closure_in_text(
            "Nous recherchons un Data Scientist senior en CDI à Lyon. Postulez dès maintenant !"
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Cette offre d'emploi chez Leo Lagrange Animation n'est plus disponible",
        "Cette offre d'emploi chez Orange a expiré",
        "This job has expired",
        "Job has expired",
        "No longer accepting applications",
        "Oups, cette offre n'est plus en ligne.",
        "Cette offre a été dépubliée par l'entreprise.",
        "L'offre que vous recherchez n'existe plus ou n'est plus disponible.",
        "Cette offre n'est plus consultable.",
        "Désolé, cette offre n'est plus disponible.",
        "L'offre recherchée est introuvable.",
        "Ce poste n'est plus à pourvoir.",
        "Ce poste a été attribué.",
    ],
)
def test_detect_closure_in_text_real_world_platform_variants(text):
    """Formulations réelles observées chez Indeed, LinkedIn, Welcome to the Jungle,
    Apec, France Travail et HelloWork — captées après l'élargissement des patterns."""
    assert detect_closure_in_text(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "Rejoignez notre offre chez Google, une entreprise innovante, pour développer vos compétences.",
        "Cette offre exceptionnelle chez notre partenaire vous permettra de développer vos compétences en marketing digital et en gestion de projet sur le long terme",
        "Poste Data Scientist chez Acme. Vous ne trouvez pas votre page ? Page introuvable ? Contactez le support.",
    ],
)
def test_detect_closure_in_text_no_false_positive_on_active_listing(text):
    """L'élargissement des patterns (ex: 'chez [Entreprise]') ne doit pas créer
    de faux positif sur une offre active qui mentionne juste l'entreprise, ni sur
    un widget footer générique ('page introuvable') présent sur une page active."""
    assert detect_closure_in_text(text) is None


def test_extract_json_ld_valid_through_expired():
    """JSON-LD JobPosting avec validThrough dans le passé -> date extraite."""
    html = """<script type="application/ld+json">
    {"@context":"https://schema.org/","@type":"JobPosting","title":"Dev","validThrough":"2020-01-01T00:00:00+00:00"}
    </script>"""
    result = extract_json_ld_valid_through(html)
    assert result is not None
    assert result.year == 2020


def test_extract_json_ld_valid_through_future():
    """JSON-LD JobPosting avec validThrough dans le futur -> date extraite quand même
    (c'est à l'appelant de comparer à now())."""
    html = """<script type="application/ld+json">
    {"@type":"JobPosting","validThrough":"2099-01-01T00:00:00Z"}
    </script>"""
    result = extract_json_ld_valid_through(html)
    assert result is not None
    assert result.year == 2099


def test_extract_json_ld_valid_through_graph_wrapped():
    """JobPosting imbriqué dans un @graph (pattern courant sur les grandes plateformes)."""
    html = """<script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
        {"@type":"Organization","name":"Acme"},
        {"@type":"JobPosting","validThrough":"2019-06-15"}
    ]}
    </script>"""
    result = extract_json_ld_valid_through(html)
    assert result is not None
    assert result.year == 2019


def test_extract_json_ld_valid_through_type_as_list():
    """@type peut être une liste (ex: ["JobPosting", "Thing"])."""
    html = """<script type="application/ld+json">
    {"@type":["JobPosting","Thing"],"validThrough":"2018-03-03T00:00:00Z"}
    </script>"""
    result = extract_json_ld_valid_through(html)
    assert result is not None
    assert result.year == 2018


@pytest.mark.parametrize(
    "html",
    [
        "<html><body>rien ici</body></html>",
        '<script type="application/ld+json">{not valid json,,,}</script>',
        '<script type="application/ld+json">{"@type":"JobPosting","title":"Dev sans date"}</script>',
        '<script type="application/ld+json">{"@type":"Organization","validThrough":"2020-01-01"}</script>',
        '<script type="application/ld+json"></script>',
        "",
    ],
)
def test_extract_json_ld_valid_through_returns_none(html):
    """Pas de JSON-LD, JSON invalide, pas de JobPosting, ou pas de validThrough -> None,
    jamais d'exception (le HTML réel est souvent imparfait)."""
    assert extract_json_ld_valid_through(html) is None


def test_extract_visible_text_strips_scripts_and_asides():
    """Test that scripts, styles, noscript and aside elements are stripped to prevent false positives."""
    html = """
    <html>
      <head>
        <style>.expired { color: red; }</style>
        <script>
          const errorMsg = "job is no longer available";
          const status = "404 not found";
        </script>
      </head>
      <body>
        <main>
          <h1>Ingénieur Data IA (H/F)</h1>
          <p>Superbe opportunité en CDI à Lyon.</p>
        </main>
        <aside class="sidebar-similar">
          <h3>Offres expirées similaires</h3>
          <p>Cette offre n'est plus disponible</p>
        </aside>
      </body>
    </html>
    """
    visible = extract_visible_text(html)
    assert "errorMsg" not in visible
    assert "job is no longer available" not in visible
    assert "404 not found" not in visible
    assert "Cette offre n'est plus disponible" not in visible
    assert "Ingénieur Data IA" in visible

    # Ensure detect_closure_in_text on this visible text does NOT mark the live job as closed
    assert detect_closure_in_text(visible) is None


def test_is_redirected_to_generic_listing():
    """Test redirection detection from specific job path to root or generic jobs listing."""
    orig = "https://company.com/careers/jobs/data-engineer-12345"

    # Redirected to root
    assert is_redirected_to_generic_listing(orig, "https://company.com/") is True
    # Redirected to generic /jobs
    assert is_redirected_to_generic_listing(orig, "https://company.com/jobs") is True
    # Redirected to generic /careers
    assert is_redirected_to_generic_listing(orig, "https://company.com/careers") is True
    # Stayed on the same specific job
    assert (
        is_redirected_to_generic_listing(
            orig, "https://company.com/careers/jobs/data-engineer-12345?ref=tracker"
        )
        is False
    )


@pytest.mark.asyncio
async def test_check_url_http_fast_404():
    """Test HTTP fast check when page returns 404."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.url = "https://example.com/job/404"
    mock_client.get.return_value = mock_response

    res = await check_url_http_fast("https://example.com/job/404", client=mock_client)
    assert res["status"] == "closed"
    assert res["valid"] is False
    assert res["status_code"] == 404
    assert "http_status_404" in res["reason"]


@pytest.mark.asyncio
async def test_check_url_http_fast_static_closed_text():
    """Test HTTP fast check when page returns 200 with closure text in visible HTML."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.url = "https://example.com/job/123"
    mock_response.text = "<html><body><h1>Cette offre a expiré</h1></body></html>"
    mock_client.get.return_value = mock_response

    res = await check_url_http_fast("https://example.com/job/123", client=mock_client)
    assert res["status"] == "closed"
    assert res["valid"] is False
    assert "static_closed_text" in res["reason"]


@pytest.mark.asyncio
async def test_check_url_http_fast_valid():
    """Test HTTP fast check when page is 200 OK without closure indicators."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.url = "https://example.com/job/123"
    mock_response.text = "<html><body><h1>Poste Data Scientist</h1><button>Postuler</button></body></html>"
    mock_client.get.return_value = mock_response

    res = await check_url_http_fast("https://example.com/job/123", client=mock_client)
    assert res["status"] == "valid"
    assert res["valid"] is True
    assert res["requires_js_check"] is True


@pytest.mark.asyncio
async def test_check_url_http_fast_jsonld_expired():
    """Test HTTP fast check when page is 200 OK but JSON-LD JobPosting.validThrough is in the past
    (data structurée exposée pour le SEO, plus fiable qu'une détection par regex sur texte visible)."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.url = "https://example.com/job/123"
    mock_response.text = """
    <html><body>
    <h1>Poste Data Scientist</h1>
    <script type="application/ld+json">
    {"@context":"https://schema.org/","@type":"JobPosting","title":"Data Scientist","validThrough":"2020-01-01T00:00:00Z"}
    </script>
    </body></html>
    """
    mock_client.get.return_value = mock_response

    res = await check_url_http_fast("https://example.com/job/123", client=mock_client)
    assert res["status"] == "closed"
    assert res["valid"] is False
    assert "jsonld_valid_through_expired" in res["reason"]


@pytest.mark.asyncio
async def test_check_url_http_fast_jsonld_future_stays_valid():
    """JSON-LD JobPosting avec validThrough dans le futur ne doit pas marquer l'offre comme close."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.url = "https://example.com/job/123"
    mock_response.text = """
    <html><body>
    <h1>Poste Data Scientist</h1>
    <script type="application/ld+json">
    {"@type":"JobPosting","validThrough":"2099-01-01T00:00:00Z"}
    </script>
    </body></html>
    """
    mock_client.get.return_value = mock_response

    res = await check_url_http_fast("https://example.com/job/123", client=mock_client)
    assert res["status"] == "valid"
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_check_url_http_fast_transient_failures_return_unknown():
    """Assert that 5xx, ConnectError, Timeout, and generic errors return status 'unknown' and valid=None."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # 1. 503 Service Unavailable
    mock_503 = MagicMock(spec=httpx.Response)
    mock_503.status_code = 503
    mock_503.url = "https://example.com/job/503"
    mock_client.get.return_value = mock_503
    res_503 = await check_url_http_fast("https://example.com/job/503", client=mock_client)
    assert res_503["status"] == "unknown"
    assert res_503["valid"] is None
    assert "server_error_503" in res_503["reason"]

    # 2. ConnectError
    mock_client.get.side_effect = httpx.ConnectError("Network unreachable")
    res_conn = await check_url_http_fast("https://example.com/job/conn", client=mock_client)
    assert res_conn["status"] == "unknown"
    assert res_conn["valid"] is None
    assert res_conn["reason"] == "connection_error"

    # 3. TimeoutException
    mock_client.get.side_effect = httpx.TimeoutException("Read timed out")
    res_timeout = await check_url_http_fast("https://example.com/job/timeout", client=mock_client)
    assert res_timeout["status"] == "unknown"
    assert res_timeout["valid"] is None
    assert res_timeout["reason"] == "timeout"

    # 4. Generic Exception
    mock_client.get.side_effect = RuntimeError("DNS lookup failure")
    res_err = await check_url_http_fast("https://example.com/job/err", client=mock_client)
    assert res_err["status"] == "unknown"
    assert res_err["valid"] is None
    assert "http_error:" in res_err["reason"]


@pytest.mark.asyncio
async def test_verify_single_offer_no_deletion_on_transient():
    """Assert that verify_single_offer produces is_valid=None on transient network/server failures."""
    sem = asyncio.Semaphore(5)
    offer = {"_id": "offer-transient", "url": "https://example.com/job/503"}

    with patch("app.tasks.verify_job_offers.check_url_http_fast", new_callable=AsyncMock) as mock_http:
        mock_http.return_value = {
            "status": "unknown",
            "valid": None,
            "reason": "server_error_503",
        }
        res = await verify_single_offer(offer, sem)
        assert res["status"] == "unknown"
        assert res["is_valid"] is None
        assert res["reason"] == "server_error_503"


@pytest.mark.asyncio
async def test_verify_single_offer_tier2_js_closed():
    """Test verify_single_offer when tier 1 succeeds but tier 2 JS detects closure."""
    sem = asyncio.Semaphore(5)
    offer = {"_id": "offer-abc", "url": "https://example.com/job/spa-closed"}

    with patch(
        "app.tasks.verify_job_offers.check_url_http_fast",
        new_callable=AsyncMock,
    ) as mock_http, patch(
        "app.tasks.verify_job_offers.check_url_headless_js",
        new_callable=AsyncMock,
    ) as mock_js:
        mock_http.return_value = {
            "status": "valid",
            "valid": True,
            "status_code": 200,
            "final_url": "https://example.com/job/spa-closed",
            "reason": "http_200_ok",
            "requires_js_check": True,
        }
        mock_js.return_value = {
            "status": "closed",
            "valid": False,
            "reason": "js_dom_closed_text: 'cette offre a été pourvue'",
            "final_url": "https://example.com/job/spa-closed",
        }

        res = await verify_single_offer(offer, sem)
        assert res["status"] == "closed"
        assert res["is_valid"] is False
        assert "cette offre a été pourvue" in res["reason"]


@pytest.mark.asyncio
async def test_verify_job_offers_workflow_dry_run_and_execution():
    """
    Test workflow:
    - dry_run=True: asserts 0 writes made to MongoDB
    - dry_run=False: asserts soft-delete writes happen ONLY on genuine closures, never on transient/unknowns.
    """
    from bson import ObjectId

    valid_id = ObjectId()
    closed_id = ObjectId()
    transient_id = ObjectId()

    sample_offers = [
        {"_id": valid_id, "url": "https://example.com/valid"},
        {"_id": closed_id, "url": "https://example.com/closed-404"},
        {"_id": transient_id, "url": "https://example.com/transient-500"},
    ]

    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=sample_offers)
    mock_collection.find.return_value = mock_cursor

    mock_update_res = MagicMock()
    mock_update_res.modified_count = 1
    mock_collection.update_one = AsyncMock(return_value=mock_update_res)

    async def fake_verify_single_offer(offer, sem, http_client=None):
        url = offer["url"]
        if "valid" in url:
            return {"offer_id": str(offer["_id"]), "status": "valid", "is_valid": True, "reason": "ok"}
        elif "closed" in url:
            return {"offer_id": str(offer["_id"]), "status": "closed", "is_valid": False, "reason": "http_status_404"}
        else:
            return {"offer_id": str(offer["_id"]), "status": "unknown", "is_valid": None, "reason": "server_error_500"}

    with patch("app.tasks.verify_job_offers.get_database", AsyncMock(return_value=mock_db)), patch(
        "app.tasks.verify_job_offers.verify_single_offer", side_effect=fake_verify_single_offer
    ):
        # 1. DRY RUN PASS
        res_dry = await verify_job_offers_workflow(dry_run=True)
        assert res_dry["valid_count"] == 1
        assert res_dry["closed_count"] == 1
        assert res_dry["unknown_count"] == 1
        assert res_dry["updated_db_count"] == 0
        mock_collection.update_one.assert_not_called()

        # 2. REAL EXECUTION PASS
        res_exec = await verify_job_offers_workflow(dry_run=False)
        assert res_exec["valid_count"] == 1
        assert res_exec["closed_count"] == 1
        assert res_exec["unknown_count"] == 1
        assert res_exec["updated_db_count"] == 1

        # Assert update_one was called ONLY for closed_id
        assert mock_collection.update_one.call_count == 1
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"_id": closed_id}
        assert call_args[0][1]["$set"]["is_deleted"] is True
        assert call_args[0][1]["$set"]["deletion_reason"] == "http_status_404"
