import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.ats.router import (
    ExpiredOfferError,
    clean_html_to_text,
    extract_ats_or_jsonld_offer,
    extract_greenhouse_job,
    extract_indeed_job,
    extract_lever_job,
    extract_smartrecruiters_job,
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
    with pytest.raises(ExpiredOfferError):
        await extract_greenhouse_job(url, client)

    # L'expiration traverse le routeur : pas de repli JSON-LD sur la page de listing.
    with pytest.raises(ExpiredOfferError):
        await extract_ats_or_jsonld_offer(url, client)
    assert client.get.await_count == 2


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


def test_clean_html_to_text_with_encoded_entities():
    # Test avec entités HTML encodées comme sur LinkedIn (&lt;p&gt;&lt;em&gt;...)
    raw_linkedin_html = "&lt;p&gt;&lt;em&gt;&lt;strong&gt;Qui sommes nous ?&lt;br&gt;&lt;br&gt;&lt;/strong&gt;&lt;/em&gt;&lt;/p&gt;&lt;p&gt;Fondé en France, Talan est un groupe international.&lt;/p&gt;"
    text = clean_html_to_text(raw_linkedin_html)
    assert "Qui sommes nous ?" in text
    assert "Fondé en France, Talan" in text
    assert "<p>" not in text
    assert "&lt;" not in text
    assert "<em>" not in text
    assert "<strong>" not in text


@pytest.mark.asyncio
async def test_summarize_ats_offer_description_success(monkeypatch):
    from app.tasks.job_offers_collectors import summarize_ats_offer_description

    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(
            message=MagicMock(
                content="• Contexte : Équipe Cloud 4 Data\n• Missions : Industrialisation plateformes AWS\n• Profil : 4+ ans exp"
            )
        )
    ]

    import litellm
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=mock_resp))

    long_raw = "<p>Qui sommes nous ?</p>" * 20
    summary = await summarize_ats_offer_description(long_raw, poste="Data Ops", entreprise="Talan")
    assert "Contexte : Équipe Cloud 4 Data" in summary
    assert "Missions : Industrialisation" in summary


@pytest.mark.asyncio
async def test_summarize_ats_offer_description_fallback_on_error(monkeypatch):
    from app.tasks.job_offers_collectors import summarize_ats_offer_description

    import litellm
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=RuntimeError("API quota exceeded")))

    long_raw = "<p>Fondé en France, Talan est un groupe international.</p>" * 10
    fallback = await summarize_ats_offer_description(long_raw, poste="Data Ops", entreprise="Talan")
    assert "Fondé en France, Talan est un groupe international." in fallback
    assert "<p>" not in fallback



def _indeed_client(job):
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"jobData": {"results": [{"job": job}] if job else []}}}
    client.post = AsyncMock(return_value=mock_resp)
    return client


@pytest.mark.asyncio
async def test_extract_indeed_job_success():
    client = _indeed_client({
        "key": "c36df2e77c64da3f",
        "title": "Ingénieur de Recherche H/F",
        "description": {"html": "<p>Le projet BrainTwin vise &agrave; d&eacute;velopper</p>"},
        "location": {"city": "Villeurbanne", "formatted": {"short": "Villeurbanne (69)"}},
        "employer": {"name": "CNRS"},
        "attributes": [{"label": "Python"}, {"label": "CDD"}],
    })
    url = "https://fr.indeed.com/viewjob?from=app-tracker-saved-appcard&hl=en&jk=c36df2e77c64da3f&tk=1k3ap"
    res = await extract_indeed_job(url, client)

    assert res["poste"] == "Ingénieur de Recherche H/F"
    assert res["entreprise"] == "CNRS"
    assert res["localisation"] == "Villeurbanne (69)"
    assert res["type_contrat"] == "CDD"
    assert "Le projet BrainTwin vise à développer" in res["description"]
    assert res["ats_platform"] == "indeed"
    sent = client.post.call_args
    assert 'jobKeys: ["c36df2e77c64da3f"]' in sent.kwargs["json"]["query"]
    assert sent.kwargs["headers"]["indeed-co"] == "FR"


@pytest.mark.asyncio
async def test_extract_indeed_job_without_key_or_result():
    client = _indeed_client(None)
    assert await extract_indeed_job("https://fr.indeed.com/emplois?q=data", client) is None
    client.post.assert_not_called()
    assert await extract_indeed_job("https://fr.indeed.com/viewjob?jk=abc123", client) is None


@pytest.mark.asyncio
async def test_extract_ats_or_jsonld_offer_routes_indeed():
    client = _indeed_client({"key": "abc123", "title": "Data Engineer", "employer": {"name": "Acme"}})
    client.get = AsyncMock()
    res = await extract_ats_or_jsonld_offer("https://fr.indeed.com/viewjob?jk=abc123", client=client)
    assert res["poste"] == "Data Engineer"
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_extract_smartrecruiters_job_success():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "name": "Ingénieur IA (H/F)",
        "company": {"name": "ASI"},
        "location": {
            "city": "Lyon",
            "fullLocation": "Lyon, Auvergne-Rhône-Alpes, France",
            "hybrid": True,
        },
        "typeOfEmployment": {"label": "Permanent"},
        "jobAd": {
            "sections": {
                "companyDescription": {"title": "Description entreprise", "text": "<p>ASI est une ESN.</p>"},
                "jobDescription": {"title": "Missions", "text": "<p>Développement de modèles GenAI.</p>"},
                "qualifications": {"title": "Profil", "text": "<ul><li>Python</li><li>LangChain</li></ul>"},
            }
        },
    }
    client.get = AsyncMock(return_value=mock_resp)

    url = "https://jobs.smartrecruiters.com/ASIFR/744000138664100-ingenieur-ia-h-f-?trid=abc"
    res = await extract_smartrecruiters_job(url, client)

    assert res is not None
    assert res["poste"] == "Ingénieur IA (H/F)"
    assert res["entreprise"] == "ASI"
    assert res["localisation"] == "Lyon, Auvergne-Rhône-Alpes, France (Hybride)"
    assert res["type_contrat"] == "CDI"
    assert res["ats_platform"] == "smartrecruiters"
    assert "### Description entreprise" in res["description"]
    assert "ASI est une ESN." in res["description"]
    assert "### Missions" in res["description"]
    assert "• Python" in res["description"]
    assert "• LangChain" in res["description"]
    client.get.assert_called_once()
    assert "api.smartrecruiters.com/v1/companies/ASIFR/postings/744000138664100" in client.get.call_args[0][0]


@pytest.mark.asyncio
async def test_extract_smartrecruiters_job_expired_404():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    client.get = AsyncMock(return_value=mock_resp)

    url = "https://jobs.smartrecruiters.com/ASIFR/999999999999999"
    with pytest.raises(ExpiredOfferError):
        await extract_smartrecruiters_job(url, client)


@pytest.mark.asyncio
async def test_extract_ats_or_jsonld_offer_routes_smartrecruiters():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "name": "Lead IA",
        "company": {"name": "Tech Corp"},
        "location": {"city": "Paris"},
        "jobAd": {"sections": {"jobDescription": {"title": "Poste", "text": "<p>Super poste.</p>"}}},
    }
    client.get = AsyncMock(return_value=mock_resp)

    url = "https://jobs.smartrecruiters.com/TechCorp/123456789"
    res = await extract_ats_or_jsonld_offer(url, client=client)

    assert res is not None
    assert res["poste"] == "Lead IA"
    assert res["entreprise"] == "Tech Corp"
    assert res["ats_platform"] == "smartrecruiters"
