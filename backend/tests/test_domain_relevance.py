import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.evaluation.domain_relevance import (
    DOMAIN_RELEVANCE_THRESHOLD,
    build_candidate_identity,
    compute_domain_relevance,
)


def test_build_candidate_identity_joins_headline_and_roles():
    assert build_candidate_identity("Animatrice 2D", ["Animatrice 2D", "Motion designer"]) == \
        "Animatrice 2D Animatrice 2D Motion designer"


def test_build_candidate_identity_ignores_empty_parts():
    assert build_candidate_identity("", ["", "Animatrice 2D", None]) == "Animatrice 2D"


def test_build_candidate_identity_all_empty_returns_empty_string():
    assert build_candidate_identity("", []) == ""


@pytest.mark.asyncio
async def test_compute_domain_relevance_empty_input_returns_none():
    assert await compute_domain_relevance("", "Data Scientist") is None
    assert await compute_domain_relevance("Animatrice 2D", "") is None


@pytest.mark.asyncio
async def test_compute_domain_relevance_similar_roles_high_score():
    fake_resp = MagicMock()
    fake_resp.data = [{"embedding": [1.0, 0.0]}, {"embedding": [0.95, 0.05]}]

    with patch("litellm.aembedding", AsyncMock(return_value=fake_resp)):
        score = await compute_domain_relevance("Data Engineer", "Senior Data Engineer")

    assert score is not None
    assert score > DOMAIN_RELEVANCE_THRESHOLD


@pytest.mark.asyncio
async def test_compute_domain_relevance_unrelated_roles_low_score():
    fake_resp = MagicMock()
    fake_resp.data = [{"embedding": [1.0, 0.0]}, {"embedding": [0.0, 1.0]}]

    with patch("litellm.aembedding", AsyncMock(return_value=fake_resp)):
        score = await compute_domain_relevance("Animatrice 2D", "Data Scientist / Machine Learning Engineer")

    assert score is not None
    assert score < DOMAIN_RELEVANCE_THRESHOLD


@pytest.mark.asyncio
async def test_compute_domain_relevance_fails_open_on_exception():
    with patch("litellm.aembedding", AsyncMock(side_effect=Exception("quota exceeded"))):
        score = await compute_domain_relevance("Animatrice 2D", "Data Scientist")

    assert score is None
