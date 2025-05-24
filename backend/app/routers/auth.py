from fastapi import APIRouter, Body, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from pydantic import BaseModel

from ..auth import (
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
from ..database import get_database
from ..models import UserCreate, UserResponse, UserModel
from ..utils import serialize_mongodb_doc


class RefreshTokenRequest(BaseModel):
    refresh_token: str


auth_router = APIRouter(prefix="/auth", tags=["authentication"])


@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_database)
):
    # Recherche de l'utilisateur par nom d'utilisateur ou email
    user = await db["users"].find_one(
        {
            "$or": [
                {"username": form_data.username},
                {"email": form_data.username},
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
    from .users import create_user

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

    # Sérialiser le document pour convertir les ObjectId en chaînes
    return serialize_mongodb_doc(updated_user)


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
