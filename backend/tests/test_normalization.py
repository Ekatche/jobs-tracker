import pytest
from app.services.normalization import (
    normalize_city,
    normalize_company,
    normalize_position,
    extract_domain,
    compute_unique_key,
    extract_company_from_url,
    optimize_crawl_url,
    restore_canonical_job_url,
    clean_html_entities_and_tags,
    clean_job_title_syntax,
    normalize_offer_fields,
)


def test_normalize_city():
    assert normalize_city("44000 Nantes") == "Nantes"
    assert normalize_city("Lyon - 01") == "Lyon"
    assert normalize_city("Paris (75)") == "Paris"
    assert normalize_city("LYON 03") == "Lyon"
    assert normalize_city(None) == "Non spécifié"
    assert normalize_city("") == "Non spécifié"


def test_normalize_company():
    assert normalize_company("Acme SAS") == "ACME"
    assert normalize_company("Google LLC") == "GOOGLE"
    assert normalize_company("Tech Solutions SARL") == "TECH SOLUTIONS"
    assert normalize_company(None) == "Non spécifié"


def test_normalize_position():
    assert normalize_position("Data Scientist (H/F)") == "DATA SCIENTIST"
    assert normalize_position("Ingénieur Devops / Cloud H/F") == "CLOUD DEVOPS INGÉNIEUR"
    assert normalize_position(None) == "Non spécifié"


def test_compute_unique_key():
    key1 = compute_unique_key("Acme SAS", "Data Scientist (H/F)", "Lyon - 01")
    key2 = compute_unique_key("Acme", "Data Scientist", "44000 Lyon")
    assert key1 == key2

    key_url1 = compute_unique_key("Acme", "Data Scientist", url="https://acme.com/jobs/123/")
    key_url2 = compute_unique_key("Acme SAS", "Data Scientist H/F", url="https://acme.com/jobs/123")
    assert key_url1 == key_url2

    # Cross-source URLs (WTTJ vs LinkedIn) for same company and role
    key_wttj = compute_unique_key(
        "Deloitte", "Ai Engineer / Scientist Confirmé F/h", "Lyon",
        url="https://www.welcometothejungle.com/fr/companies/deloitte/jobs/ai-engineer-scientist-confirme-f-h_lyon"
    )
    key_linkedin = compute_unique_key(
        "Deloitte", "AI Engineer / Scientist confirmé", "Lyon",
        url="https://fr.linkedin.com/jobs/view/ai-engineer-scientist-confirm%C3%A9-f-h-at-deloitte-4463883002"
    )
    assert key_wttj == key_linkedin
    assert key_wttj == "deloitte|ai confirmé engineer scientist|lyon"


def test_extract_company_from_url():
    # ATS URLs
    assert (
        extract_company_from_url(
            "https://galderma.wd3.myworkdayjobs.com/fr-FR/External/job/Alby/Data-Analyst_JR014026-1"
        )
        == "Galderma"
    )
    assert extract_company_from_url("https://boards.greenhouse.io/stripe/jobs/123") == "Stripe"
    assert extract_company_from_url("https://jobs.lever.co/datadog/456") == "Datadog"
    assert extract_company_from_url("https://jobs.smartrecruiters.com/boschgroup/789") == "Boschgroup"
    assert (
        extract_company_from_url("https://www.welcometothejungle.com/fr/companies/alan/jobs/123")
        == "Alan"
    )
    assert extract_company_from_url("https://swile.recruitee.com/o/lead-dev") == "Swile"
    assert extract_company_from_url("https://carrieres.totalenergies.com/offres/123") == "Totalenergies"

    # New global and generalist ATS platforms
    assert extract_company_from_url("https://jobs.ashbyhq.com/openai/12345") == "Openai"
    assert extract_company_from_url("https://acme.bamboohr.com/careers/123") == "Acme"
    assert extract_company_from_url("https://apply.workable.com/qonto/j/ABC123/") == "Qonto"
    assert extract_company_from_url("https://qonto.workable.com/j/ABC123") == "Qonto"
    assert extract_company_from_url("https://alan.jobs.personio.de/job/987") == "Alan"
    assert extract_company_from_url("https://jobs.personio.de/alan/job/987") == "Alan"
    assert extract_company_from_url("https://danone.jobs2web.com/job/123") == "Danone"
    assert extract_company_from_url("https://airbus.taleo.net/careersection/jobdetail.ftl?job=123") == "Airbus"
    assert extract_company_from_url("https://careers-totalenergies.icims.com/jobs/123") == "Totalenergies"
    assert extract_company_from_url("https://swile.teamtailor.com/jobs/123") == "Swile"

    # Aggregator URLs must return None
    assert extract_company_from_url("https://candidat.francetravail.fr/offres/recherche/detail/184ABCD") is None
    assert extract_company_from_url("https://www.linkedin.com/jobs/view/12345") is None
    assert extract_company_from_url("https://www.apec.fr/candidat/detail-offre/123") is None
    assert extract_company_from_url("https://fr.indeed.com/viewjob?jk=123") is None

    # Empty or invalid URLs
    assert extract_company_from_url(None) is None
    assert extract_company_from_url("") is None


def test_optimize_crawl_url():
    # LinkedIn URLs: rewrite to guest API endpoint
    assert (
        optimize_crawl_url("https://fr.linkedin.com/jobs/view/4463811288")
        == "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"
    )
    assert (
        optimize_crawl_url("https://www.linkedin.com/jobs/view/data-scientist-at-klanik-4463811288?position=1")
        == "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"
    )
    # Already guest API -> unchanged
    assert (
        optimize_crawl_url("https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288")
        == "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"
    )

    # Indeed URLs: rewrite to mobile view (/m/viewjob) to bypass Cloudflare
    assert (
        optimize_crawl_url("https://fr.indeed.com/viewjob?jk=40a89e89e93a1394")
        == "https://fr.indeed.com/m/viewjob?jk=40a89e89e93a1394"
    )
    assert (
        optimize_crawl_url("https://www.indeed.com/rc/clk?jk=abc123xyz&from=vjs")
        == "https://www.indeed.com/m/viewjob?jk=abc123xyz"
    )
    # Already mobile view -> unchanged
    assert (
        optimize_crawl_url("https://fr.indeed.com/m/viewjob?jk=40a89e89e93a1394")
        == "https://fr.indeed.com/m/viewjob?jk=40a89e89e93a1394"
    )

    # Other job boards: untouched
    wttj = "https://www.welcometothejungle.com/fr/companies/alan/jobs/123"
    assert optimize_crawl_url(wttj) == wttj
    apec = "https://www.apec.fr/candidat/recherche-emploi.html/offre/123"
    assert optimize_crawl_url(apec) == apec

    # Empty / None
    assert optimize_crawl_url(None) == ""
    assert optimize_crawl_url("") == ""


def test_restore_canonical_job_url():
    # LinkedIn guest endpoint -> user-facing view URL
    assert (
        restore_canonical_job_url("https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288")
        == "https://www.linkedin.com/jobs/view/4463811288"
    )

    # Indeed mobile endpoint -> user-facing desktop viewjob
    assert (
        restore_canonical_job_url("https://fr.indeed.com/m/viewjob?jk=40a89e89e93a1394")
        == "https://fr.indeed.com/viewjob?jk=40a89e89e93a1394"
    )

    # Other URLs untouched
    wttj = "https://www.welcometothejungle.com/fr/companies/alan/jobs/123"
    assert restore_canonical_job_url(wttj) == wttj


def test_merge_multidiffusion_offers_preserves_metadata():
    from app.services.normalization import merge_multidiffusion_offers

    wttj_offer = {
        "poste": "Ai Engineer / Scientist Confirmé F/h",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://www.welcometothejungle.com/fr/companies/deloitte/jobs/ai-engineer-scientist-confirme-f-h_lyon",
        "evaluation": {"score": 5.0, "match": "Excellent"},
        "user_interaction": "saved",
        "description": "Court descriptif WTTJ",
        "competences_cles": ["Python", "PyTorch"],
    }

    linkedin_offer = {
        "poste": "AI Engineer / Scientist confirmé",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://fr.linkedin.com/jobs/view/ai-engineer-scientist-confirm%C3%A9-f-h-at-deloitte-4463883002",
        "description": "Descriptif beaucoup plus long et détaillé issu de LinkedIn avec tous les éléments du poste...",
        "competences_cles": ["Python", "MLOps", "Docker"],
    }

    merged = merge_multidiffusion_offers(wttj_offer, linkedin_offer)

    # WTTJ has priority 80 over LinkedIn 50
    assert merged["url"] == wttj_offer["url"]
    assert linkedin_offer["url"] in merged["alternative_urls"]
    # Preserves evaluation & user_interaction
    assert merged["evaluation"] == {"score": 5.0, "match": "Excellent"}
    assert merged["user_interaction"] == "saved"
    # Merges skills
    assert set(merged["competences_cles"]) == {"Python", "PyTorch", "MLOps", "Docker"}
    # Keeps longest description
    assert merged["description"] == linkedin_offer["description"]
    # Clean canonical unique_key
    assert merged["unique_key"] == "deloitte|ai confirmé engineer scientist|lyon"


def test_clean_html_entities_and_tags():
    assert clean_html_entities_and_tags("Junior Data Scientist / ML Engineer (R&amp;D)") == "Junior Data Scientist / ML Engineer (R&D)"
    assert clean_html_entities_and_tags("Ingénieur &lt;Cloud&gt; &amp; DevOps") == "Ingénieur <Cloud> & DevOps"
    assert clean_html_entities_and_tags("Lead&#39;s Team &quot;AI&quot;") == "Lead's Team \"AI\""
    assert clean_html_entities_and_tags("<strong>Data Analyst</strong>") == "Data Analyst"
    assert clean_html_entities_and_tags("Espace\u00a0insécable\u200b") == "Espace insécable"
    assert clean_html_entities_and_tags(None) == ""
    assert clean_html_entities_and_tags("") == ""


def test_clean_job_title_syntax():
    # HTML entities in title
    raw = "Junior Data Scientist / ML Engineer (R&amp;D)"
    assert clean_job_title_syntax(raw) == "Junior Data Scientist / ML Engineer (R&D)"

    # HTML tags in title
    assert clean_job_title_syntax("<h3>Data Engineer</h3> (H/F)") == "Data Engineer"

    # Residual empty brackets and parentheses
    assert clean_job_title_syntax("Data Scientist (H/F) ()") == "Data Scientist"
    assert clean_job_title_syntax("ML Engineer [ ]") == "ML Engineer"
    assert clean_job_title_syntax("Data Analyst (CDI) (Paris)") == "Data Analyst"

    # Typographic punctuation & legal mentions
    assert clean_job_title_syntax("Data Trust & AI Governance Manager (H/F/NB)") == "Data Trust & AI Governance Manager"
    assert clean_job_title_syntax("Data Scientist – Remote") == "Data Scientist"
    assert clean_job_title_syntax("Data Scientist - -") == "Data Scientist"


def test_normalize_offer_fields():
    polluted_offer = {
        "poste": "Junior Data Scientist / ML Engineer (R&amp;D) (H/F)",
        "entreprise": "Recupere Metals &amp; Co",
        "localisation": "Paris (75) &amp; Remote",
        "description": "<p>Superbe poste de <strong>Data Scientist</strong> chez Recupere Metals &amp; Co.</p>",
        "type_contrat": "CDI &amp; Plein temps",
        "salaire": "45k&euro; - 55k&euro;",
        "mode_travail": "Hybride &amp; Flexible",
        "url": "https://recuperemetals.com/jobs/1",
    }

    cleaned = normalize_offer_fields(polluted_offer)

    assert cleaned["poste"] == "Junior Data Scientist / ML Engineer (R&D)"
    assert cleaned["entreprise"] == "Recupere Metals & Co"
    assert cleaned["localisation"] == "Paris & Remote"
    assert "<p>" not in cleaned["description"]
    assert "<strong>" not in cleaned["description"]
    assert "Recupere Metals & Co" in cleaned["description"]
    assert cleaned["type_contrat"] == "CDI & Plein temps"
    assert "€" in cleaned["salaire"]
    assert cleaned["mode_travail"] == "Hybride & Flexible"
    assert cleaned["unique_key"] is not None
    assert "recupere metals & co" in cleaned["unique_key"]



