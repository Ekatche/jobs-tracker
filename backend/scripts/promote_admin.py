# backend/scripts/promote_admin.py
"""Attribue le rôle administrateur à un utilisateur par son adresse email ou nom d'utilisateur.

Usage:
    docker exec jobtracker-backend python scripts/promote_admin.py atchokatche@gmail.com
    .venv/bin/python scripts/promote_admin.py atchokatche@gmail.com
"""

import argparse
import asyncio
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.models import utcnow_with_timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def promote_user(identifier: str) -> None:
    db = await get_database()

    # Recherche par email insensible à la casse ou par nom d'utilisateur
    user = await db["users"].find_one({
        "$or": [
            {"email": {"$regex": f"^{identifier.strip()}$", "$options": "i"}},
            {"username": identifier.strip()},
        ]
    })

    if not user:
        logger.error(f"❌ Aucun utilisateur trouvé avec l'identifiant: {identifier}")
        sys.exit(1)

    user_id = user["_id"]
    current_role = user.get("role", "user")

    if current_role == "admin":
        logger.info(f"ℹ️ L'utilisateur {user.get('email')} est déjà administrateur.")
        return

    now = utcnow_with_timezone()
    await db["users"].update_one(
        {"_id": user_id},
        {"$set": {"role": "admin", "updated_at": now}}
    )

    logger.info(f"✅ Utilisateur {user.get('email')} ({user.get('username')}) promu au rôle ADMIN avec succès !")


def main():
    parser = argparse.ArgumentParser(description="Promeut un compte utilisateur au rôle administrateur.")
    parser.add_argument("identifier", help="Email ou nom d'utilisateur du compte à promouvoir")
    args = parser.parse_args()

    asyncio.run(promote_user(args.identifier))


if __name__ == "__main__":
    main()
