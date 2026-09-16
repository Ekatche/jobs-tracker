import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.ats.router import (
    clean_html_to_text,
    extract_ats_or_jsonld_offer,
    extract_greenhouse_job,
    extract_lever_job,
    extract_workable_job,
    normalize_employment_type,
    parse_jsonld_job_posting,
)


def test_clean_html_to_text():
    raw_html = "<p>Nous recherchons un <strong>Data Scientist</strong>.</p><br><ul><li>Python</li><li>Docker</li></ul>"
    text = clean_html_to_text(raw_html)
    assert "Data Scientist" in text
    assert "• Python" in text
    assert "<p>" not in text
    assert "<strong>" not in text


def test_normalize_employment_type():
    assert normalize_employment_type("FULL_TIME") == "CDI"
    assert normalize_employment_type("permanent") == "CDI"
    assert normalize_employment_type("PART_TIME") == "Temps partiel"
    assert normalize_employment_type("CONTRACT") == "CDD"
    assert normalize_employment_type("INTERN") == "Stage"
    assert normalize_employment_type("APPRENTICESHIP") == "Alternance"
    assert normalize_employment_type("FREELANCE") == "Freelance"
    assert normalize_employment_type(None) == "Non spécifié"


@pytest.mark.asyncio
async def test_extract_greenhouse_job_success():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "title": "Senior AI Engineer",
        "company_name": "Mistral AI",
        "location": {"name": "Paris, France"},
        "content": "<p>Description du poste AI Engineer chez Mistral.</p>",
    }
    client.get = AsyncMock(return_value=mock_resp)

    url = "https://boards.greenhouse.io/mistralai/jobs/456789"
    result = await extract_greenhouse_job(url, client)

    assert result is not None
    assert result["poste"] == "Senior AI Engineer"
    assert result["entreprise"] == "Mistral AI"
    assert result["localisation"] == "Paris, France"
    assert "Description du poste" in result["description"]
    assert result["ats_platform"] == "greenhouse"


@pytest.mark.asyncio
async def test_extract_greenhouse_job_404():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    client.get = AsyncMock(return_value=mock_resp)

    url = "https://boards.greenhouse.io/mistralai/jobs/999999"
    result = await extract_greenhouse_job(url, client)
    assert result is None


@pytest.mark.asyncio
async def test_extract_lever_job_success():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "text": "Machine Learning Platform Engineer",
        "categories": {
            "location": "Lyon",
            "commitment": "Full-time",
            "team": "Data Platform",
        },
        "descriptionPlain": "Responsabilités et missions ML Platform à Lyon.",
    }
    client.get = AsyncMock(return_value=mock_resp)

    url = "https://jobs.lever.co/doctolib/1234-abcd-5678"
    result = await extract_lever_job(url, client)

    assert result is not None
    assert result["poste"] == "Machine Learning Platform Engineer"
    assert result["entreprise"] == "Doctolib"
    assert result["localisation"] == "Lyon"
    assert result["type_contrat"] == "CDI"
    assert "Responsabilités et missions" in result["description"]
    assert result["ats_platform"] == "lever"


@pytest.mark.asyncio
async def test_extract_workable_job_success():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "jobs": [
            {
                "title": "Lead Data Scientist",
                "shortcode": "ABC123XYZ",
                "city": "Paris",
                "employment_type": "Full-time",
                "description": "<p>Superbe poste Lead Data Scientist.</p>",
            }
        ]
    }
    client.get = AsyncMock(return_value=mock_resp)

    url = "https://apply.workable.com/qonto/j/ABC123XYZ/"
    result = await extract_workable_job(url, client)

    assert result is not None
    assert result["poste"] == "Lead Data Scientist"
    assert result["entreprise"] == "Qonto"
    assert result["localisation"] == "Paris"
    assert result["type_contrat"] == "CDI"
    assert "Superbe poste Lead Data Scientist." in result["description"]
    assert result["ats_platform"] == "workable"


def test_parse_jsonld_job_posting_simple():
    html_page = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org/",
            "@type": "JobPosting",
            "title": "Ingénieur MLOps (H/F)",
            "description": "<p>Rejoignez notre équipe data à Lyon.</p>",
            "hiringOrganization": {
                "@type": "Organization",
                "name": "Acme Tech"
            },
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Lyon"
                }
            },
            "employmentType": "FULL_TIME"
        }
        </script>
    </head>
    <body><h1>Offre d'emploi</h1></body>
    </html>
    """
    result = parse_jsonld_job_posting(html_page, "https://www.hellowork.com/fr-fr/emplois/123.html")
    assert result is not None
    assert result["poste"] == "Ingénieur MLOps (H/F)"
    assert result["entreprise"] == "Acme Tech"
    assert result["localisation"] == "Lyon"
    assert result["type_contrat"] == "CDI"
    assert "Rejoignez notre équipe data à Lyon." in result["description"]
    assert result["ats_platform"] == "json_ld"


def test_parse_jsonld_job_posting_graph_format():
    html_page = """
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebPage", "name": "Careers"},
            {
                "@type": "JobPosting",
                "title": "Cloud Architect",
                "description": "Designing cloud architectures on AWS/GCP.",
                "hiringOrganization": {"name": "OVHcloud"},
                "jobLocation": {"addressLocality": "Roubaix"},
                "jobLocationType": "TELECOMMUTE",
                "employmentType": "PERMANENT"
            }
        ]
    }
    </script>
    """
    result = parse_jsonld_job_posting(html_page, "https://jobs.ovhcloud.com/job/456")
    assert result is not None
    assert result["poste"] == "Cloud Architect"
    assert result["entreprise"] == "OVHcloud"
    assert result["localisation"] == "Roubaix"
    assert result["type_contrat"] == "CDI"


def test_parse_jsonld_no_job_posting():
    html_page = "<html><head><script type=\"application/ld+json\">{\"@type\": \"BreadcrumbList\"}</script></head></html>"
    result = parse_jsonld_job_posting(html_page, "https://example.com/page")
    assert result is None


@pytest.mark.asyncio
async def test_extract_ats_or_jsonld_offer_cascade():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """
    <script type="application/ld+json">
    {
        "@type": "JobPosting",
        "title": "Fullstack Developer",
        "hiringOrganization": {"name": "Swile"},
        "jobLocation": {"address": {"addressLocality": "Montpellier"}},
        "description": "Développement Next.js et FastAPI."
    }
    </script>
    """
    client.get = AsyncMock(return_value=mock_resp)

    url = "https://jobs.ashbyhq.com/swile/789"
    result = await extract_ats_or_jsonld_offer(url, client=client)

    assert result is not None
    assert result["poste"] == "Fullstack Developer"
    assert result["entreprise"] == "Swile"
    assert result["localisation"] == "Montpellier"
    assert result["ats_platform"] == "ashby"
