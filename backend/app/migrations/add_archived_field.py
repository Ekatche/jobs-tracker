import asyncio
import sys
from pathlib import Path

# Ajouter le chemin parent au sys.path pour pouvoir importer les modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.database import get_database


async def migrate_applications():
    """Ajoute le champ archived=False à toutes les candidatures existantes qui ne l'ont pas."""

    db = await get_database()

    # Compter le nombre de documents sans le champ archived
    count_before = await db["applications"].count_documents(
        {"archived": {"$exists": False}}
    )

    if count_before == 0:
        print(
            "Aucune migration nécessaire. Toutes les candidatures ont déjà le champ 'archived'."
        )
        return

    print(f"Migration de {count_before} candidatures sans champ 'archived'...")

    # Mettre à jour tous les documents qui n'ont pas le champ archived
    result = await db["applications"].update_many(
        {"archived": {"$exists": False}}, {"$set": {"archived": False}}
    )

    print(f"Migration terminée : {result.modified_count} candidatures mises à jour.")

    # Vérifier que toutes les candidatures ont maintenant le champ archived
    count_after = await db["applications"].count_documents(
        {"archived": {"$exists": False}}
    )

    if count_after == 0:
        print("Succès : Toutes les candidatures ont maintenant le champ 'archived'.")
    else:
        print(
            f"Attention : {count_after} candidatures n'ont toujours pas le champ 'archived'."
        )


if __name__ == "__main__":
    asyncio.run(migrate_applications())
