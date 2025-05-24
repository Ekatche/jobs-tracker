from fastapi import APIRouter, Body, Depends, status, HTTPException
from typing import List
from bson import ObjectId
from datetime import datetime, timezone

from ..models import Task, TaskCreate, TaskUpdate, UserModel
from ..database import get_database
from ..utils import serialize_mongodb_doc
from ..auth import get_current_user

task_router = APIRouter(prefix="/tasks", tags=["tasks"])


@task_router.get("/", response_model=List[Task])
async def get_tasks(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    tasks = await db["tasks"].find({"user_id": current_user.id}).to_list(length=100)

    for task in tasks:
        if "status" in task:
            status_lower = (
                task["status"].lower() if isinstance(task["status"], str) else ""
            )
            if status_lower == "à faire" or status_lower == "a faire":
                task["status"] = "À faire"
            elif status_lower == "en cours":
                task["status"] = "En cours"
            elif status_lower == "terminée" or status_lower == "terminee":
                task["status"] = "Terminée"

    return [serialize_mongodb_doc(task) for task in tasks]


@task_router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    task = await db["tasks"].find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    if str(task["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette tâche")
    return serialize_mongodb_doc(task)


@task_router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    task_data = task.model_dump()
    task_data["user_id"] = current_user.id
    task_data["created_at"] = datetime.now(timezone.utc)
    task_data["updated_at"] = datetime.now(timezone.utc)

    result = await db["tasks"].insert_one(task_data)
    created_task = await db["tasks"].find_one({"_id": result.inserted_id})

    return serialize_mongodb_doc(created_task)


@task_router.put("/{task_id}", response_model=Task)
async def update_task(
    task_id: str,
    task_update: TaskUpdate = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    task = await db["tasks"].find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    if str(task["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette tâche")

    update_dict = task_update.model_dump(exclude_unset=True)
    update_data = {k: v for k, v in update_dict.items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)

    await db["tasks"].update_one({"_id": ObjectId(task_id)}, {"$set": update_data})
    updated_task = await db["tasks"].find_one({"_id": ObjectId(task_id)})
    return serialize_mongodb_doc(updated_task)


@task_router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    task = await db["tasks"].find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    if str(task["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette tâche")
    await db["tasks"].delete_one({"_id": ObjectId(task_id)})
    return None
