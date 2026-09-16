import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tasks.job_offers_collectors import (
    DEFAULT_QUERIES,
    MAX_QUERIES_PER_PROFILE,
    MAX_TOTAL_QUERIES,
    build_search_queries,
    build_search_queries_sync,
)


def _mock_db_with_profiles(profiles: list[dict]):
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=profiles)
    mock_db = MagicMock()
    mock_db["candidate_profile"].find.return_value = mock_cursor
    return mock_db


@pytest.mark.asyncio
async def test_build_search_queries_with_roles_and_locations():
    """(a) profil avec target_roles + locations génère les combinaisons attendues."""
    profiles = [
        {
            "preferences": {
                "target_roles": ["Data Engineer", "Data Scientist"],
                "locations": ["Lyon", "Paris"],
                "contract_types": ["CDI"],
            }
        }
    ]
    mock_db = _mock_db_with_profiles(profiles)

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)):
        queries = await build_search_queries()

    assert len(queries) == MAX_QUERIES_PER_PROFILE  # Capped at 3 per profile
    assert queries[0] == "Je recherche un poste de Data Engineer proche de Lyon (CDI)"
    assert queries[1] == "Je recherche un poste de Data Engineer proche de Paris (CDI)"
    assert queries[2] == "Je recherche un poste de Data Scientist proche de Lyon (CDI)"


@pytest.mark.asyncio
async def test_build_search_queries_empty_locations_standard_remote():
    """(b) profil avec target_roles et locations vide + remote standard génère sans ville."""
    profiles = [
        {
            "preferences": {
                "target_roles": ["Machine Learning Engineer"],
                "locations": [],
                "remote_policy": "hybrid",
                "contract_types": ["CDI"],
            }
        }
    ]
    mock_db = _mock_db_with_profiles(profiles)

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)):
        queries = await build_search_queries()

    assert queries == ["Je recherche un poste de Machine Learning Engineer (CDI)"]


@pytest.mark.asyncio
async def test_build_search_queries_empty_locations_full_remote():
    """(c) profil avec target_roles et locations vide + remote_policy == full_remote génère 'en télétravail'."""
    profiles = [
        {
            "preferences": {
                "target_roles": ["Backend Developer"],
                "locations": [],
                "remote_policy": "full_remote",
                "contract_types": ["Freelance"],
            }
        }
    ]
    mock_db = _mock_db_with_profiles(profiles)

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)):
        queries = await build_search_queries()

    assert queries == ["Je recherche un poste de Backend Developer en télétravail (Freelance)"]


@pytest.mark.asyncio
async def test_build_search_queries_case_insensitive_dedup():
    """(d) déduplication insensible à la casse entre profils."""
    profiles = [
        {
            "preferences": {
                "target_roles": ["Data Engineer"],
                "locations": ["Lyon"],
            }
        },
        {
            "preferences": {
                "target_roles": ["data engineer"],
                "locations": ["lyon"],
            }
        },
    ]
    mock_db = _mock_db_with_profiles(profiles)

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)):
        queries = await build_search_queries()

    assert len(queries) == 1
    assert queries[0] == "Je recherche un poste de Data Engineer proche de Lyon"


@pytest.mark.asyncio
async def test_build_search_queries_round_robin_fairness():
    """(e) distribution équitable Round-Robin entre profils."""
    profiles = [
        {
            "preferences": {
                "target_roles": ["RoleA1", "RoleA2", "RoleA3"],
                "locations": ["CityA"],
            }
        },
        {
            "preferences": {
                "target_roles": ["RoleB1", "RoleB2", "RoleB3"],
                "locations": ["CityB"],
            }
        },
    ]
    mock_db = _mock_db_with_profiles(profiles)

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)):
        queries = await build_search_queries()

    # Round 0: RoleA1, RoleB1
    # Round 1: RoleA2, RoleB2
    # Round 2: RoleA3, RoleB3
    assert queries[0] == "Je recherche un poste de RoleA1 proche de CityA"
    assert queries[1] == "Je recherche un poste de RoleB1 proche de CityB"
    assert queries[2] == "Je recherche un poste de RoleA2 proche de CityA"
    assert queries[3] == "Je recherche un poste de RoleB2 proche de CityB"
    assert queries[4] == "Je recherche un poste de RoleA3 proche de CityA"
    assert queries[5] == "Je recherche un poste de RoleB3 proche de CityB"


@pytest.mark.asyncio
async def test_build_search_queries_capped_at_max_total():
    """(f) plafonnement strict à MAX_TOTAL_QUERIES."""
    # 5 profiles with 3 queries each = 15 total potential queries
    profiles = [
        {
            "preferences": {
                "target_roles": [f"Role{i}_1", f"Role{i}_2", f"Role{i}_3"],
                "locations": ["Paris"],
            }
        }
        for i in range(5)
    ]
    mock_db = _mock_db_with_profiles(profiles)

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)):
        queries = await build_search_queries()

    assert len(queries) == MAX_TOTAL_QUERIES
    assert len(queries) == 8


@pytest.mark.asyncio
async def test_build_search_queries_profile_without_roles_ignored():
    """(g) profil sans target_roles ignoré."""
    profiles = [
        {
            "preferences": {
                "target_roles": [],
                "locations": ["Lyon"],
            }
        },
        {
            "preferences": {
                "target_roles": ["DevOps Engineer"],
                "locations": ["Nantes"],
            }
        },
    ]
    mock_db = _mock_db_with_profiles(profiles)

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)):
        queries = await build_search_queries()

    assert len(queries) == 1
    assert queries[0] == "Je recherche un poste de DevOps Engineer proche de Nantes"


@pytest.mark.asyncio
async def test_build_search_queries_empty_db_fallback():
    """(h) base vide ou aucun profil exploitable → retourne DEFAULT_QUERIES."""
    mock_db = _mock_db_with_profiles([])

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)):
        queries = await build_search_queries()

    assert queries == list(DEFAULT_QUERIES)


@pytest.mark.asyncio
async def test_build_search_queries_mongo_exception_fallback():
    """(i) exception levée par MongoDB → rattrapée proprement et retourne DEFAULT_QUERIES."""
    with patch("app.tasks.job_offers_collectors.get_database", side_effect=Exception("Mongo connection refused")):
        queries = await build_search_queries()

    assert queries == list(DEFAULT_QUERIES)


def test_build_search_queries_sync_wrapper():
    """Vérifie l'exécution synchrone et son fallback sécurisé."""
    with patch("app.tasks.job_offers_collectors.build_search_queries", side_effect=Exception("Crash")):
        queries = build_search_queries_sync()

    assert queries == list(DEFAULT_QUERIES)


@pytest.mark.asyncio
async def test_build_search_queries_normalizes_and_mutualizes_roles():
    """Vérifie la mutualisation multi-utilisateurs grâce à la normalisation de rôles."""
    profiles = [
        {
            "preferences": {
                "target_roles": ["AI Engineer"],
                "locations": ["Lyon"],
            }
        },
        {
            "preferences": {
                "target_roles": ["Ingénieur IA"],
                "locations": ["Lyon"],
            }
        },
    ]
    mock_db = _mock_db_with_profiles(profiles)

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)), \
         patch("app.services.role_normalizer.normalize_role", AsyncMock(return_value="AI Engineer")) as mock_norm:
        queries = await build_search_queries()

    # Both profiles should produce the same query and be mutualized into 1
    assert len(queries) == 1
    assert queries[0] == "Je recherche un poste de AI Engineer proche de Lyon"
    assert mock_norm.call_count == 2


@pytest.mark.asyncio
async def test_build_search_queries_intra_profile_role_dedup():
    """Vérifie qu'un profil ayant deux variantes du même rôle dans son profil ne duplique pas."""
    profiles = [
        {
            "preferences": {
                "target_roles": ["AI Engineer", "Ingénieur IA"],
                "locations": ["Lyon"],
            }
        }
    ]
    mock_db = _mock_db_with_profiles(profiles)

    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=mock_db)), \
         patch("app.services.role_normalizer.normalize_role", AsyncMock(return_value="AI Engineer")):
        queries = await build_search_queries()

    # Intra-profile dedup should leave only 1 branch of queries
    assert len(queries) == 1
    assert queries[0] == "Je recherche un poste de AI Engineer proche de Lyon"

