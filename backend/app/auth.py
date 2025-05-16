import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from .database import get_database
from .models import UserModel

# Chargement des variables d'environnement
load_dotenv()

# Remplacer la configuration existante
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuration pour JWT
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Configuration pour le refresh token
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Configuration de OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


# Modèle pour le token d'accès
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


# Fonctions d'utilitaire pour les mots de passe
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


# Fonctions pour JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    to_encode.update({"jti": str(uuid.uuid4())})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "token_type": "refresh"})
    to_encode.update({"jti": str(uuid.uuid4())})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


# Fonction pour récupérer l'utilisateur actuel
async def get_current_user(
    token: str = Depends(oauth2_scheme), db=Depends(get_database)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants non valides",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Décoder le token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")

        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Récupérer l'utilisateur depuis la base de données
    user = await db["users"].find_one({"_id": ObjectId(user_id)})

    if user is None:
        raise credentials_exception

    # Vérifier si le compte est désactivé
    if user.get("disabled", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte désactivé",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Convertir l'ObjectId en chaîne avant de créer l'objet UserModel
    user["_id"] = str(user["_id"])

    return UserModel(**user)
