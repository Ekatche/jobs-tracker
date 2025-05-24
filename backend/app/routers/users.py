from fastapi import APIRouter, Body, Depends, status, HTTPException, UploadFile, File
from typing import List
from bson import ObjectId
from datetime import datetime, timezone
import os
from uuid import uuid4

from ..models import UserCreate, UserResponse, UserModel
from ..database import get_database
from ..utils import serialize_mongodb_doc
from ..auth import get_current_user, get_password_hash

UPLOAD_DIR = "app/uploads"

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.post("/upload-cv")
async def upload_cv(
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Type de fichier non autorisé")

    ext = os.path.splitext(file.filename)[1]
    filename = f"cv_{current_user.id}_{uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    url = f"/uploads/{filename}"
    await db["users"].update_one({"_id": current_user.id}, {"$set": {"cv_url": url}})

    return {"cv_url": url}


@user_router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate = Body(...), db=Depends(get_database)):
    if await db["users"].find_one(
        {"$or": [{"email": user.email}, {"username": user.username}]}
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un utilisateur avec cet email ou ce nom d'utilisateur existe déjà",
        )

    hashed_password = get_password_hash(user.password)

    user_data = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_password,
        "full_name": user.full_name,
        "disabled": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }

    result = await db["users"].insert_one(user_data)
    created_user = await db["users"].find_one({"_id": result.inserted_id})

    return serialize_mongodb_doc(created_user)


@user_router.get("/", response_model=List[UserResponse])
async def get_users(
    db=Depends(get_database), current_user: UserModel = Depends(get_current_user)
):
    users = await db["users"].find().to_list(length=100)
    serialized_users = [serialize_mongodb_doc(user) for user in users]
    return serialized_users


@user_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    if str(current_user.id) != user_id:
        pass

    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    return serialize_mongodb_doc(user)


@user_router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    if str(current_user.id) != user_id:
        pass

    update_data = {k: v for k, v in user_data.items() if v is not None}

    if "password" in update_data:
        raise HTTPException(
            status_code=400,
            detail="Utilisez la route dédiée pour changer le mot de passe",
        )

    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db["users"].update_one(
        {"_id": ObjectId(user_id)}, {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    updated_user = await db["users"].find_one({"_id": ObjectId(user_id)})
    return serialize_mongodb_doc(updated_user)


@user_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    if str(current_user.id) != user_id:
        pass

    result = await db["users"].delete_one({"_id": ObjectId(user_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    await db["applications"].delete_many({"user_id": ObjectId(user_id)})
    return None
