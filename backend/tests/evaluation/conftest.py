"""Fixtures et helpers partagés pour la suite d'évaluation d'offres."""

import json
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest

TEST_USER_ID = "507f1f77bcf86cd799439011"
TEST_OFFER_ID = "507f1f77bcf86cd799439022"


def make_llm_response(payload: dict) -> MagicMock:
    """Helper créant une réponse factice litellm."""
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    resp.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return resp


def make_eval_db(
    *,
    offer_doc: dict = None,
    profile_doc: dict = None,
    eval_upserted_id: str = "eval_123",
    user_tier: str = "free",
) -> tuple[MagicMock, dict]:
    """Helper créant un mock complet de base de données pour l'évaluateur."""
    db = MagicMock()

    job_offers_col = AsyncMock()
    job_offers_col.find_one.return_value = offer_doc or {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "Senior Fullstack Engineer",
        "entreprise": "Acme Corp",
        "localisation": "Paris, France",
        "type_contrat": "CDI",
        "mode_travail": "Hybrid",
        "description": "Nous recherchons un Senior Fullstack Engineer maîtrisant React, FastAPI et MongoDB.",
    }
    job_offers_col.update_one.return_value = MagicMock(modified_count=1)

    candidate_profile_col = AsyncMock()
    candidate_profile_col.find_one.return_value = profile_doc or {
        "user_id": TEST_USER_ID,
        "headline": "Fullstack Developer 6 YoE",
        "summary": "Passionné par FastAPI et React",
        "skills": {"languages": ["Python", "TypeScript"], "frameworks": ["FastAPI", "React"]},
        "experiences": [
            {
                "role": "Fullstack Dev",
                "company": "Tech Corp",
                "stack": ["Python", "FastAPI", "React"],
                "missions": ["Conception d'APIs", "Refonte UI"],
            }
        ],
        "preferences": {"remote": "hybrid", "locations": ["Paris"]},
    }

    offer_evaluations_col = AsyncMock()
    offer_evaluations_col.update_one.return_value = MagicMock(upserted_id=eval_upserted_id)

    users_col = AsyncMock()
    users_col.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": user_tier}

    api_usage_col = AsyncMock()

    async def empty_cursor(*args, **kwargs):
        if False:
            yield {}

    api_usage_col.aggregate = MagicMock(side_effect=lambda *a, **k: empty_cursor())
    api_usage_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

    cols = {
        "job_offers": job_offers_col,
        "candidate_profile": candidate_profile_col,
        "offer_evaluations": offer_evaluations_col,
        "users": users_col,
        "api_usage": api_usage_col,
    }

    def db_getitem(name):
        return cols.get(name, AsyncMock())

    db.__getitem__.side_effect = db_getitem
    return db, cols

