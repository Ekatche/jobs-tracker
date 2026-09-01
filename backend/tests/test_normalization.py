import pytest
from app.services.normalization import (
    normalize_city,
    normalize_company,
    normalize_position,
    extract_domain,
    compute_unique_key,
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
