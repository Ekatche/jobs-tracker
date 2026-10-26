import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.evaluation.domain_relevance import (
    DOMAIN_RELEVANCE_THRESHOLD,
    build_candidate_identity,
    compute_domain_relevance,
    expand_title_acronyms,
)

# Import seul : keep_relevant_titles vit dans app.services.sources (fichier
# interdit en écriture pour ce chantier), on fige ici son comportement actuel
# vis-à-vis des acronymes sensibles à la casse (M12, test de caractérisation).
from app.services.sources import keep_relevant_titles


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


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Développeur Confirmé Ia", "Développeur Confirmé intelligence artificielle"),
        ("Ingénieur IA Agentique", "Ingénieur intelligence artificielle Agentique"),
        ("Animatrice périscolaire", "Animatrice périscolaire"),
        ("Aide-soignant", "Aide-soignant"),
    ],
)
def test_expand_title_acronyms(title, expected):
    assert expand_title_acronyms(title) == expected


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Senior PO", "Senior Product Owner"),
        ("ML Engineer", "Machine Learning Engineer"),
        ("Data Analyst BI", "Data Analyst Business Intelligence"),
        ("SRE / DevOps", "Site Reliability Engineer / DevOps"),
        ("QA Engineer", "Quality Assurance Engineer"),
        ("PM Data", "Product Manager Data"),
        ("DS confirmé", "Data Scientist confirmé"),
        ("DE Spark", "Data Engineer Spark"),
        ("Chef de projet", "Chef de projet"),
        ("CHEF DE PROJET DA", "CHEF DE PROJET DA"),
        ("Développeur Confirmé Ia", "Développeur Confirmé intelligence artificielle"),
    ],
)
def test_expand_title_acronyms_extended(title, expected):
    assert expand_title_acronyms(title) == expected


@pytest.mark.asyncio
async def test_compute_domain_relevance_embeds_expanded_title():
    fake_resp = MagicMock()
    fake_resp.data = [{"embedding": [1.0, 0.0]}, {"embedding": [1.0, 0.0]}]
    embed = AsyncMock(return_value=fake_resp)

    with patch("litellm.aembedding", embed):
        await compute_domain_relevance("AI Engineer", "Développeur Confirmé Ia")

    assert embed.call_args.kwargs["input"][1] == "Développeur Confirmé intelligence artificielle"


# ---------- keep_relevant_titles (M12, import seul depuis app.services.sources) ----------


@pytest.mark.asyncio
async def test_keep_relevant_titles_expands_acronym_case_sensitively():
    """Caractérisation : `keep_relevant_titles` développe l'acronyme en casse
    exacte ("PM", cf. CASE_SENSITIVE_ACRONYMS) avant l'appel d'embedding, mais
    pas sa variante minuscule ("pm") — comportement actuel figé tel quel, pas
    de RED attendu."""
    offers = [
        {"poste": "PM Senior", "url": "http://a"},
        {"poste": "pm senior", "url": "http://b"},
    ]
    fake_resp = MagicMock()
    fake_resp.data = [
        {"embedding": [1.0, 0.0]},  # rôle
        {"embedding": [1.0, 0.0]},  # "PM Senior" développé, proche du rôle
        {"embedding": [0.0, 1.0]},  # "pm senior" pas développé, loin du rôle
    ]
    embed = AsyncMock(return_value=fake_resp)

    with patch("litellm.aembedding", embed):
        kept = await keep_relevant_titles("Product Manager", offers)

    sent_titles = embed.call_args.kwargs["input"]
    assert sent_titles == ["Product Manager", "Product Manager Senior", "pm senior"]
    assert [o["poste"] for o in kept] == ["PM Senior"]
