from datetime import datetime, timedelta, timezone
from typing import List, Optional
import pymongo
from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, status, BackgroundTasks
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
import logging

from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
    Token,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from .database import get_database
from .models import (
    JobApplicationCreate,
    JobApplicationResponse,
    JobApplicationUpdate,
    UserCreate,
    UserModel,
    UserResponse,
)
from .utils import (
    capitalize_words,
    serialize_mongodb_doc,
)

from .llm.utils import fetch_documents, split_documents, summarize_chunks

# Configure logger
logger = logging.getLogger(__name__)


# Ajoutez cette classe pour le body de la requête
class RefreshTokenRequest(BaseModel):
    refresh_token: str


# Création des routeurs
auth_router = APIRouter(prefix="/auth", tags=["authentication"])
user_router = APIRouter(prefix="/users", tags=["users"])
job_router = APIRouter(prefix="/applications", tags=["applications"])

# ============ Routes d'authentification ============


@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_database)
):
    # Recherche de l'utilisateur par nom d'utilisateur ou email
    user = await db["users"].find_one(
        {
            "$or": [
                {"username": form_data.username},
                {
                    "email": form_data.username
                },  # Permet de se connecter avec email ou username
            ]
        }
    )

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Vérifier si le compte est désactivé
    if user.get("disabled", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte désactivé",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Créer le jeton d'accès avec une date d'expiration
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["_id"])}, expires_delta=access_token_expires
    )

    # Créer le refresh token avec une date d'expiration plus longue
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        data={"sub": str(user["_id"])}, expires_delta=refresh_token_expires
    )

    # Mettre à jour la dernière connexion de l'utilisateur
    await db["users"].update_one(
        {"_id": user["_id"]}, {"$set": {"last_login": datetime.now(timezone.utc)}}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@auth_router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(user: UserCreate = Body(...), db=Depends(get_database)):
    # Cette route est un alias pour create_user, mais dans le namespace auth
    return await create_user(user, db)


@auth_router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: UserModel = Depends(get_current_user)):
    # Convertir l'objet UserModel en dictionnaire puis sérialiser les ObjectId
    user_dict = current_user.model_dump(by_alias=True)
    return serialize_mongodb_doc(user_dict)


@auth_router.post("/change-password", response_model=UserResponse)
async def change_password(
    current_password: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    # Vérifier le mot de passe actuel
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect",
        )

    # Hasher le nouveau mot de passe
    hashed_password = get_password_hash(new_password)

    # Mettre à jour le mot de passe
    await db["users"].update_one(
        {"_id": ObjectId(current_user.id)},
        {
            "$set": {
                "hashed_password": hashed_password,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    # Récupérer l'utilisateur mis à jour
    updated_user = await db["users"].find_one({"_id": ObjectId(current_user.id)})

    return updated_user


@auth_router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_data: RefreshTokenRequest, db=Depends(get_database)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Décoder le refresh token
        payload = jwt.decode(
            refresh_data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("token_type")

        # Vérifier que c'est bien un refresh token
        if user_id is None or token_type != "refresh":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Vérifier que l'utilisateur existe
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception

    # Générer un nouveau access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["_id"])}, expires_delta=access_token_expires
    )

    # Générer un nouveau refresh token (rotation des refresh tokens)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        data={"sub": str(user["_id"])}, expires_delta=refresh_token_expires
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ============ Routes utilisateur ============


@user_router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate = Body(...), db=Depends(get_database)):
    # Vérifier si l'utilisateur existe déjà
    if await db["users"].find_one(
        {"$or": [{"email": user.email}, {"username": user.username}]}
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un utilisateur avec cet email ou ce nom d'utilisateur existe déjà",
        )

    # Hasher le mot de passe
    hashed_password = get_password_hash(user.password)

    # Créer le nouvel utilisateur
    user_data = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_password,
        "full_name": user.full_name,
        "disabled": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }

    # Insérer dans la base de données
    result = await db["users"].insert_one(user_data)

    # Récupérer l'utilisateur créé
    created_user = await db["users"].find_one({"_id": result.inserted_id})

    # Sérialiser le document pour la réponse
    return serialize_mongodb_doc(created_user)


@user_router.get("/", response_model=List[UserResponse])
async def get_users(
    db=Depends(get_database), current_user: UserModel = Depends(get_current_user)
):
    # Vérifier si l'utilisateur est un administrateur (à implémenter)
    users = await db["users"].find().to_list(length=100)

    # Sérialiser chaque document pour convertir les ObjectId en chaînes
    serialized_users = [serialize_mongodb_doc(user) for user in users]

    return serialized_users


@user_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    # Vérifier si l'utilisateur consulte son propre profil ou est un administrateur
    if str(current_user.id) != user_id:
        # Vérifier si l'utilisateur est administrateur (à implémenter)
        pass

    # Récupérer l'utilisateur
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
    # Vérifier que l'utilisateur modifie son propre profil ou est administrateur
    if str(current_user.id) != user_id:
        # Vérifier si l'utilisateur est administrateur (à implémenter)
        pass

    # Préparer les données à mettre à jour
    update_data = {k: v for k, v in user_data.items() if v is not None}

    # Empêcher la modification du mot de passe via cette route
    if "password" in update_data:
        raise HTTPException(
            status_code=400,
            detail="Utilisez la route dédiée pour changer le mot de passe",
        )

    # Ajouter la date de mise à jour
    update_data["updated_at"] = datetime.now(timezone.utc)

    # Mettre à jour l'utilisateur
    result = await db["users"].update_one(
        {"_id": ObjectId(user_id)}, {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    # Récupérer l'utilisateur mis à jour
    updated_user = await db["users"].find_one({"_id": ObjectId(user_id)})

    return updated_user


@user_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    # Vérifier que l'utilisateur supprime son propre profil ou est administrateur
    if str(current_user.id) != user_id:
        # Vérifier si l'utilisateur est administrateur (à implémenter)
        pass

    # Supprimer l'utilisateur
    result = await db["users"].delete_one({"_id": ObjectId(user_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    # Supprimer également toutes les candidatures de l'utilisateur
    await db["applications"].delete_many({"user_id": ObjectId(user_id)})

    return None


# ============ Routes candidatures ============


@job_router.post(
    "/", response_model=JobApplicationResponse, status_code=status.HTTP_201_CREATED
)
async def create_application(
    background_tasks: BackgroundTasks,
    application: JobApplicationCreate = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    raw_data = jsonable_encoder(application)
    app_data = {
        k: v
        for k, v in raw_data.items()
        if v is not None and (not isinstance(v, str) or v.strip() != "")
    }
    app_data["user_id"] = current_user.id
    app_data["created_at"] = datetime.now(timezone.utc)
    if not app_data.get("application_date"):
        app_data["application_date"] = app_data["created_at"]

    result = await db["applications"].insert_one(app_data)
    created = await db["applications"].find_one({"_id": result.inserted_id})

    # Corrigeons le problème de génération de description
    url_exists = "url" in app_data and app_data["url"]
    description_missing = "description" not in app_data or not app_data["description"]
    if url_exists and description_missing:
        try:
            url = app_data.get("url")
            logger.info(f"[create_application] URL: {url!r}, ID: {result.inserted_id}")
            # Assurons-nous que l'ID est un ObjectId
            app_id = result.inserted_id
            logger.info(f"[create_application] Type ID: {type(app_id)}")

            # Programmation explicite de la tâche
            background_tasks.add_task(_generate_description_bg, app_id, url.strip(), db)
            logger.info(f"[create_application] Tâche planifiée pour URL: {url}")
        except Exception as e:
            logger.error(f"[create_application] Erreur: {str(e)}")
    else:
        logger.warning(f"[create_application] URL manquante/invalide: {url!r}")

    return serialize_mongodb_doc(created)


@job_router.get("/", response_model=List[JobApplicationResponse])
async def get_applications(
    status: Optional[str] = None,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    # Préparer la requête pour filtrer par utilisateur
    query = {"user_id": current_user.id}

    # Ajouter le filtre de statut si fourni
    if status:
        query["status"] = status

    # Récupérer les candidatures (triées par date de candidature descendante)
    applications = (
        await db["applications"]
        .find(query)
        .sort("application_date", pymongo.DESCENDING)
        .to_list(length=100)
    )

    # Sérialiser chaque document pour convertir les ObjectId en chaînes
    # et s'assurer que tous les champs sont présents
    serialized_applications = []
    for app in applications:
        serialized_app = serialize_mongodb_doc(app)
        # S'assurer explicitement que location est présent
        if "location" not in serialized_app:
            serialized_app["location"] = None  # ou '' pour une chaîne vide
        serialized_applications.append(serialized_app)

    return serialized_applications


@job_router.get("/{application_id}", response_model=JobApplicationResponse)
async def get_application(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    # Récupérer la candidature
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})

    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    # Vérifier que l'utilisateur est propriétaire de la candidature
    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé à cette candidature"
        )

    # Sérialiser le document pour convertir les ObjectId en chaînes
    return serialize_mongodb_doc(application)


@job_router.put("/{application_id}", response_model=JobApplicationResponse)
async def update_application(
    background_tasks: BackgroundTasks,
    application_id: str,
    application_data: JobApplicationUpdate = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    # Vérifier que la candidature existe et appartient à l'utilisateur
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})

    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé à cette candidature"
        )

    # Préparer les données à mettre à jour
    raw_data = jsonable_encoder(application_data)
    update_data = {
        k: v
        for k, v in raw_data.items()
        if v is not None and (not isinstance(v, str) or v.strip() != "")
    }

    # Standardiser l'entreprise et le poste avec capitalisation
    if "company" in update_data and update_data["company"]:
        update_data["company"] = capitalize_words(update_data["company"])

    if "position" in update_data and update_data["position"]:
        update_data["position"] = capitalize_words(update_data["position"])

    # Vérifier si une URL est fournie et s'il n'y a pas de description existante
    # OU si l'URL est mise à jour et que la description actuelle est vide

    # Check if URL exists and is not empty
    url_provided = "url" in update_data and update_data["url"]

    # Check if URL has been changed from previous value
    url_changed = url_provided and update_data["url"] != application.get("url", "")

    # Check if description exists and is not empty
    description_provided = "description" in update_data and update_data["description"]

    # Update timestamp and save changes to database
    update_data["updated_at"] = datetime.now(timezone.utc)
    await db["applications"].update_one(
        {"_id": ObjectId(application_id)}, {"$set": update_data}
    )

    # Generate description in background if URL changed or URL exists but description is missing
    if url_changed or (url_provided and not description_provided):
        try:
            background_tasks.add_task(
                _generate_description_bg,
                ObjectId(application_id),
                update_data["url"],
                db,
            )
        except Exception as e:
            logger.error(f"Failed to schedule description generation: {e}")

    updated_application = await db["applications"].find_one(
        {"_id": ObjectId(application_id)}
    )
    return serialize_mongodb_doc(updated_application)


@job_router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    # Vérifier que la candidature existe et appartient à l'utilisateur
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})

    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé à cette candidature"
        )

    # Supprimer la candidature
    await db["applications"].delete_one({"_id": ObjectId(application_id)})

    return None


# Route pour ajouter une note à une candidature
@job_router.post("/{application_id}/notes", response_model=JobApplicationResponse)
async def add_note(
    application_id: str,
    note: str = Body(..., embed=True),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    # Vérifier que la candidature existe et appartient à l'utilisateur
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})

    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé à cette candidature"
        )

    # Ajouter la note
    _ = await db["applications"].update_one(
        {"_id": ObjectId(application_id)},
        {"$push": {"notes": note}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )

    # Récupérer la candidature mise à jour
    updated_application = await db["applications"].find_one(
        {"_id": ObjectId(application_id)}
    )

    return serialize_mongodb_doc(updated_application)


# Ajoutez cette fonction en haut du fichier, avant les routes
async def _generate_description_bg(application_id: ObjectId, url: str, db):
    logger.info(f"[description_bg] Démarrage pour ID={application_id}, URL={url}")
    try:
        docs = await fetch_documents(url)
        if not docs:
            logger.warning(f"[description_bg] Aucun document récupéré pour {url}")
            return

        logger.info(f"[description_bg] {len(docs)} documents récupérés")
        chunks = split_documents(docs)
        description = await summarize_chunks(chunks)

        if description:
            logger.info(
                f"[description_bg] Description générée ({len(description)} chars)"
            )
            await db["applications"].update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "description": description,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        else:
            logger.warning("[description_bg] Échec de génération de description")
    except Exception as e:
        logger.error(f"[description_bg] Erreur: {str(e)}")
