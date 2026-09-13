import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from app.tasks.regenerate_descriptions import (
    build_dead_link_fallback_description,
    regenerate_single_offer,
    batch_regenerate,
)


def test_build_dead_link_fallback_description_complete():
    desc = build_dead_link_fallback_description(
        poste="Senior Data Scientist",
        entreprise="Partoo",
        competences=["Python", "FastAPI", "React"],
        reason="Page 404 introuvable",
    )
    assert "Partoo" in desc
    assert "Senior Data Scientist" in desc
    assert "Python, FastAPI, React" in desc
    assert "Page 404 introuvable" in desc
    assert "• Statut :" in desc
    assert "• Contexte :" in desc
    assert "• Compétences initiales :" in desc


def test_build_dead_link_fallback_description_empty_fields():
    desc = build_dead_link_fallback_description(
        poste="",
        entreprise="",
        competences=None,
    )
    assert "Entreprise non spécifiée" in desc
    assert "Poste non spécifié" in desc
    assert "Non spécifié" in desc


@pytest.mark.asyncio
async def test_regenerate_single_offer_active_success():
    fake_id = ObjectId()
    offer_doc = {
        "_id": fake_id,
        "poste": "Data Engineer",
        "entreprise": "Alan",
        "url": "https://www.welcometothejungle.com/fr/companies/alan/jobs/data-engineer",
        "description": "Ancienne description courte",
        "salaire": "Non spécifié",
        "competences_cles": ["Python"],
    }

    new_structured_desc = (
        "• Contexte & Enjeux : Alan révolutionne l'assurance santé.\n"
        "• Missions principales :\n  - Construire les pipelines de données.\n"
        "• Profil recherché : 4+ ans d'expérience.\n"
        "• Stack & Outils : Python, Snowflake, dbt.\n"
        "• Avantages & Modalités : Full remote."
    )

    mock_crawl_result = {
        "offers": [
            {
                "poste": "Data Engineer",
                "entreprise": "Alan",
                "description": new_structured_desc,
                "salaire": "65k - 80k €",
                "mode_travail": "Télétravail total",
            }
        ],
        "results": [{"url": offer_doc["url"], "status": "success"}],
    }

    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=offer_doc)
    mock_collection.update_one = AsyncMock()
    mock_db.__getitem__.return_value = mock_collection

    with patch(
        "job_crawler.crawler1.crawl_and_extract_jobs_optimized",
        new=AsyncMock(return_value=mock_crawl_result),
    ):
        res = await regenerate_single_offer(offer_doc, db=mock_db)

    assert res["success"] is True
    assert res["is_active"] is True
    assert res["status"] == "updated"
    assert res["description"] == new_structured_desc

    # Vérifier l'appel à update_one
    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"_id": fake_id}
    set_fields = call_args[0][1]["$set"]
    assert set_fields["description"] == new_structured_desc
    assert set_fields["is_active"] is True
    assert set_fields["salaire"] == "65k - 80k €"
    assert set_fields["mode_travail"] == "Télétravail total"


@pytest.mark.asyncio
async def test_regenerate_single_offer_dead_link_fallback():
    fake_id = ObjectId()
    offer_doc = {
        "_id": fake_id,
        "poste": "ML Engineer",
        "entreprise": "Inconnu Inc",
        "url": "https://fr.linkedin.com/jobs/view/old-job-12345",
        "description": "Ancienne description",
        "competences_cles": ["PyTorch", "Docker"],
    }

    mock_crawl_result = {
        "offers": [],
        "results": [
            {
                "url": offer_doc["url"],
                "status": "dead_link",
                "error": "Offre expirée ou page inexistante (404/410)",
            }
        ],
    }

    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=offer_doc)
    mock_collection.update_one = AsyncMock()
    mock_db.__getitem__.return_value = mock_collection

    with patch(
        "job_crawler.crawler1.crawl_and_extract_jobs_optimized",
        new=AsyncMock(return_value=mock_crawl_result),
    ):
        res = await regenerate_single_offer(offer_doc, db=mock_db)

    assert res["success"] is True
    assert res["is_active"] is False
    assert res["status"] == "dead_or_expired"
    assert "Cette offre n'est plus accessible en ligne" in res["description"]
    assert "Inconnu Inc" in res["description"]
    assert "PyTorch, Docker" in res["description"]

    # Vérifier que is_active=False a été enregistré dans MongoDB
    mock_collection.update_one.assert_called_once()
    set_fields = mock_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["is_active"] is False
    assert "• Statut :" in set_fields["description"]


@pytest.mark.asyncio
async def test_regenerate_single_offer_invalid_url():
    fake_id = ObjectId()
    offer_doc = {
        "_id": fake_id,
        "poste": "Dev",
        "entreprise": "BadUrl Corp",
        "url": "not-a-valid-url",
        "competences_cles": [],
    }

    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=offer_doc)
    mock_collection.update_one = AsyncMock()
    mock_db.__getitem__.return_value = mock_collection

    res = await regenerate_single_offer(offer_doc, db=mock_db)

    assert res["success"] is True
    assert res["is_active"] is False
    assert res["status"] == "invalid_url"
    assert "URL manquante ou invalide" in res["description"]


@pytest.mark.asyncio
async def test_batch_regenerate():
    doc1 = {
        "_id": ObjectId(),
        "poste": "Poste 1",
        "entreprise": "Ent 1",
        "url": "https://example.com/job1",
        "description": "Ancien",
    }
    doc2 = {
        "_id": ObjectId(),
        "poste": "Poste 2",
        "entreprise": "Ent 2",
        "url": "https://example.com/job2",
        "description": "Ancien",
    }

    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count_documents = AsyncMock(return_value=2)
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[doc1, doc2])
    mock_cursor.limit.return_value = mock_cursor
    mock_collection.find.return_value = mock_cursor
    mock_db.__getitem__.return_value = mock_collection

    # Mock regenerate_single_offer: 1 success, 1 dead link
    with patch(
        "app.tasks.regenerate_descriptions.regenerate_single_offer",
        side_effect=[
            {"success": True, "is_active": True, "description": "Desc 1"},
            {"success": True, "is_active": False, "description": "Desc 2"},
        ],
    ):
        stats = await batch_regenerate(db=mock_db, limit=2, delay_between_requests=0)

    assert stats["total"] == 2
    assert stats["updated"] == 1
    assert stats["dead_links"] == 1
    assert stats["errors"] == 0
