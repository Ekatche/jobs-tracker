from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from app.database import get_database
from app.auth import get_current_user
from app.models import UserModel
from app.utils import serialize_mongodb_doc
from app.routers.applications import _generate_cover_letter_bg

cover_letters_router = APIRouter(tags=["cover_letters"])

@cover_letters_router.get("/applications/{application_id}/cover-letter")
async def get_cover_letter(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if not letter:
        return {"status": "none"}
    return serialize_mongodb_doc(letter)

@cover_letters_router.post("/applications/{application_id}/cover-letter/regenerate")
async def regenerate_cover_letter(
    application_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    # Supprime l'ancienne lettre pour forcer la regénération
    await db["cover_letters"].delete_one({"application_id": ObjectId(application_id)})
    background_tasks.add_task(
        _generate_cover_letter_bg,
        ObjectId(application_id),
        ObjectId(current_user.id),
        db
    )
    return {"status": "scheduled"}

@cover_letters_router.patch("/applications/{application_id}/cover-letter")
async def edit_cover_letter(
    application_id: str,
    body_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if not letter:
        raise HTTPException(status_code=404, detail="Lettre non trouvée")
    if str(letter.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    new_version_num = len(letter.get("versions", [])) + 1
    new_version = {
        "n": new_version_num,
        "body": body_data.get("body", ""),
        "origin": "edited",
        "models": {},
        "created_at": datetime.now(timezone.utc)
    }
    await db["cover_letters"].update_one(
        {"_id": letter["_id"]},
        {
            "$set": {"current_version": new_version_num, "updated_at": datetime.now(timezone.utc)},
            "$push": {"versions": new_version}
        }
    )
    updated = await db["cover_letters"].find_one({"_id": letter["_id"]})
    return serialize_mongodb_doc(updated)

@cover_letters_router.get("/profile/candidate")
async def get_candidate_profile(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    prof = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)})
    if not prof:
        raise HTTPException(status_code=404, detail="Profil non initialisé")
    return serialize_mongodb_doc(prof)

@cover_letters_router.put("/profile/candidate")
async def update_candidate_profile(
    profile_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    profile_data["user_id"] = ObjectId(current_user.id)
    profile_data["updated_at"] = datetime.now(timezone.utc)
    await db["candidate_profile"].update_one(
        {"user_id": ObjectId(current_user.id)},
        {"$set": profile_data},
        upsert=True
    )
    prof = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)})
    return serialize_mongodb_doc(prof)

@cover_letters_router.get("/profile/api-status")
async def check_api_accounts_status(
    current_user: UserModel = Depends(get_current_user),
):
    """
    Retourne le statut de configuration des clés API (OpenAI, Gemini, Mistral)
    et les informations d'accès aux soldes/crédits sur les consoles fournisseurs.
    """
    import sys
    from pathlib import Path
    job_trackers_path = Path(__file__).parent.parent.parent / "job_trackers" / "src" / "job_trackers"
    if str(job_trackers_path) not in sys.path:
        sys.path.insert(0, str(job_trackers_path))
    from letter_llm import get_api_status
    return get_api_status()

