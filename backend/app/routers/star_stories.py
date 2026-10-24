"""Routes de la banque d'histoires STAR+R, partagée entre tous les kits d'un utilisateur.

Isolation : toute lecture/écriture passe par les fonctions de `star_bank`,
filtrées par `user_filter`. Histoire absente ou d'un autre utilisateur → 404
sur chaque route.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.database import get_database
from app.models import StoryExperience, UserModel
from app.services.star_bank import (
    StoryNotFoundError,
    delete_bank_story,
    get_bank_story,
    load_bank,
    mark_not_duplicate,
    merge_stories,
    restore_discarded_version,
    story_usage,
    story_usage_counts,
    update_story_facts,
    user_filter,
)
from app.services.star_bank_rules import experience_label, match_profile_experience

logger = logging.getLogger(__name__)

star_stories_router = APIRouter(tags=["star-stories"])

CANDIDATE_PROFILE_COLLECTION = "candidate_profile"
UNATTACHED_GROUP_LABEL = "Sans expérience rattachée"


class UpdateStoryRequest(BaseModel):
    title: Optional[str] = None
    theme: Optional[str] = None
    situation: Optional[str] = None
    task: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    reflection: Optional[str] = None
    key_tags: Optional[List[str]] = None
    experience: Optional[StoryExperience] = None


class MergeStoryRequest(BaseModel):
    discard_id: str


class NotDuplicateRequest(BaseModel):
    other_id: str


class RestoreVersionRequest(BaseModel):
    version_id: str


def _experience_dict(exp: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return {"company": exp.get("company"), "role": exp.get("role"), "start": exp.get("start")}


def _story_with_usage(story, usage_counts: Dict[str, int]) -> Dict[str, Any]:
    data = story.model_dump()
    data["used_in_kits"] = usage_counts.get(story.id, 0)
    return data


@star_stories_router.get("/star-stories")
async def list_star_stories(
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """La banque groupée par expérience du profil, dans l'ordre du profil ; le groupe
    « Sans expérience rattachée » vient toujours en dernier."""
    user_id = str(current_user.id)
    stories = await load_bank(db, user_id)
    usage_counts = await story_usage_counts(db, user_id)

    profile = await db[CANDIDATE_PROFILE_COLLECTION].find_one(user_filter(user_id))
    experiences = (profile or {}).get("experiences") or []

    buckets: List[List[Any]] = [[] for _ in experiences]
    unattached: List[Any] = []
    for story in stories:
        idx = match_profile_experience(story.experience, experiences)
        if idx is None:
            unattached.append(story)
        else:
            buckets[idx].append(story)

    groups: List[Dict[str, Any]] = []
    for idx, exp in enumerate(experiences):
        if not buckets[idx]:
            continue
        exp_struct = StoryExperience(**_experience_dict(exp))
        groups.append(
            {
                "label": experience_label(exp_struct),
                "experience": exp_struct.model_dump(),
                "stories": [_story_with_usage(s, usage_counts) for s in buckets[idx]],
            }
        )
    if unattached:
        groups.append(
            {
                "label": UNATTACHED_GROUP_LABEL,
                "experience": None,
                "stories": [_story_with_usage(s, usage_counts) for s in unattached],
            }
        )

    return {
        "groups": groups,
        "experiences": [
            {**_experience_dict(exp), "label": experience_label(StoryExperience(**_experience_dict(exp)))}
            for exp in experiences
        ],
        "count": len(stories),
    }


@star_stories_router.patch("/star-stories/{story_id}")
async def patch_star_story(
    story_id: str,
    payload: UpdateStoryRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Modifie uniquement les champs envoyés. N'appelle jamais le LLM : la
    propagation aux autres kits se fait par simple jointure à la lecture.

    `null` explicite refusé (422) sur tout champ sauf `experience`, dont
    `null` détache l'histoire de son expérience : un fait requis à `None`
    rendrait illisible toute la banque de l'utilisateur.
    """
    user_id = str(current_user.id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if value is None and field != "experience":
            raise HTTPException(status_code=422, detail=f"Champ obligatoire : {field}.")
    updated = await update_story_facts(db, user_id, story_id, changes)
    if updated is None:
        raise HTTPException(status_code=404, detail="Histoire introuvable.")
    return updated.model_dump()


@star_stories_router.get("/star-stories/{story_id}/usage")
async def get_star_story_usage(
    story_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    user_id = str(current_user.id)
    story = await get_bank_story(db, user_id, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Histoire introuvable.")
    kits = await story_usage(db, user_id, story_id)
    return {"kits": kits}


@star_stories_router.delete("/star-stories/{story_id}")
async def delete_star_story(
    story_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    user_id = str(current_user.id)
    affected = await delete_bank_story(db, user_id, story_id)
    if affected is None:
        raise HTTPException(status_code=404, detail="Histoire introuvable.")
    return {"affected_kits": affected}


@star_stories_router.post("/star-stories/{keep_id}/merge")
async def merge_star_stories(
    keep_id: str,
    payload: MergeStoryRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Fusionne `discard_id` dans `keep_id` : historique conservé, lignes et
    questions des kits redirigées, `discard_id` supprimée de la banque."""
    if keep_id == payload.discard_id:
        raise HTTPException(status_code=400, detail="Impossible de fusionner une histoire avec elle-même.")
    user_id = str(current_user.id)
    try:
        merged = await merge_stories(db, user_id, keep_id, payload.discard_id)
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail="Histoire introuvable.")
    return merged.model_dump()


@star_stories_router.post("/star-stories/{story_id}/not-duplicate")
async def mark_star_story_not_duplicate(
    story_id: str,
    payload: NotDuplicateRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Marque `story_id` et `other_id` comme « histoires différentes » (exclues de
    la détection de doublons dans les deux sens)."""
    if story_id == payload.other_id:
        raise HTTPException(status_code=400, detail="Une histoire ne peut pas être différente d'elle-même.")
    user_id = str(current_user.id)
    try:
        updated = await mark_not_duplicate(db, user_id, story_id, payload.other_id)
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail="Histoire introuvable.")
    return updated.model_dump()


@star_stories_router.post("/star-stories/{story_id}/restore")
async def restore_star_story_version(
    story_id: str,
    payload: RestoreVersionRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Restaure une version archivée : ses faits remplacent les faits courants,
    qui deviennent eux-mêmes une nouvelle version archivée."""
    user_id = str(current_user.id)
    try:
        restored = await restore_discarded_version(db, user_id, story_id, payload.version_id)
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail="Histoire ou version introuvable.")
    return restored.model_dump()
