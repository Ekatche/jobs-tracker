"""Remplit `star_stories` à partir des histoires héritées de `interview_preps.stories`.

Rattrape les kits créés avant l'introduction de la banque d'histoires STAR+R
partagée entre kits. Simulation par défaut : compte sans rien écrire.
`--apply` migre chaque kit sans `story_slots` (via `ensure_prep_migrated`) puis
vérifie l'invariant de remplissage sans perte sur les seuls kits migrés par ce
run.
"""
import asyncio
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_database
from app.services.star_bank import (
    INTERVIEW_PREPS_COLLECTION,
    ensure_prep_migrated,
    get_bank_story,
    load_bank,
    user_filter,
)
from app.services.star_bank_rules import find_duplicate_pairs


class MigrationInvariantError(RuntimeError):
    """Levée quand un kit migré n'a pas autant de lignes que d'histoires héritées,
    ou qu'une ligne pointe vers une histoire absente de la banque de son utilisateur."""


async def check_invariant(db, preps: List[Dict[str, Any]]) -> None:
    """Pour chaque kit : `len(story_slots) == len(stories)` et, à chaque position,
    l'histoire héritée existe dans la banque de son utilisateur. Sinon
    `MigrationInvariantError`.

    L'id vérifié est celui de l'histoire héritée (`stories[i]["id"]`) quand elle
    en a un, jamais celui de la ligne migrée (`story_slots[i]["story_id"]`) : les
    deux viennent de la même variable dans `ensure_prep_migrated`
    (`story_id = legacy.get("id") or str(uuid.uuid4())`), donc comparer la ligne
    à elle-même serait tautologique et ne détecterait jamais un `mapped_story_id`
    de question anticipée devenu orphelin si cette variable cessait un jour de
    conserver l'id hérité. Seules les histoires héritées sans `id` (uuid créé au
    remplissage, jamais réécrit dans la copie de sûreté) retombent sur le
    `story_id` de la ligne de même position, faute d'autre référence.
    """
    for prep in preps:
        user_id = str(prep.get("user_id"))
        legacy_stories = prep.get("stories") or []
        story_slots = prep.get("story_slots") or []

        if len(story_slots) != len(legacy_stories):
            raise MigrationInvariantError(
                f"kit {prep.get('_id')} : {len(story_slots)} ligne(s) pour "
                f"{len(legacy_stories)} histoire(s) héritée(s)"
            )

        for legacy, slot in zip(legacy_stories, story_slots):
            story_id = legacy.get("id") or slot.get("story_id")
            if await get_bank_story(db, user_id, story_id) is None:
                raise MigrationInvariantError(
                    f"kit {prep.get('_id')} : histoire {story_id!r} absente de la "
                    f"banque de l'utilisateur {user_id}"
                )


async def migrate(db, apply: bool) -> Dict[str, Dict[str, int]]:
    """Rapport par `user_id` : `kit_stories` (histoires héritées de tous ses kits),
    `kits_to_migrate` (kits sans `story_slots` au début du run), puis, lus en fin
    de run, `bank_stories`, `kits_with_slots` et `possible_duplicates` (0 jusqu'à
    ce qu'une tâche ultérieure le branche sur la détection de doublons).

    En simulation (`apply=False`), aucun appel d'écriture : on compte seulement.
    En mode `apply`, chaque kit sans `story_slots` est migré via
    `ensure_prep_migrated`, puis l'invariant de remplissage sans perte est
    vérifié sur ces seuls kits (une fusion ou une suppression ultérieure retire
    légitimement des histoires de la banque, sans que ça invalide un run passé).

    `possible_duplicates` compte les paires détectées par `find_duplicate_pairs`
    sur la banque finale de l'utilisateur (après migration en mode `apply`).
    """
    report: Dict[str, Dict[str, int]] = {}
    to_migrate: Dict[str, List[Dict[str, Any]]] = {}

    cursor = db[INTERVIEW_PREPS_COLLECTION].find({})
    async for prep in cursor:
        user_id = str(prep.get("user_id"))
        entry = report.setdefault(user_id, {"kit_stories": 0, "kits_to_migrate": 0})
        entry["kit_stories"] += len(prep.get("stories") or [])
        if "story_slots" not in prep:
            entry["kits_to_migrate"] += 1
            to_migrate.setdefault(user_id, []).append(prep)

    if apply:
        for user_id, preps in to_migrate.items():
            migrated_preps = [await ensure_prep_migrated(db, prep) for prep in preps]
            await check_invariant(db, migrated_preps)

    for user_id, entry in report.items():
        bank = await load_bank(db, user_id)
        kits_with_slots = await db[INTERVIEW_PREPS_COLLECTION].count_documents(
            {**user_filter(user_id), "story_slots": {"$exists": True}}
        )
        entry["bank_stories"] = len(bank)
        entry["kits_with_slots"] = kits_with_slots
        entry["possible_duplicates"] = len(find_duplicate_pairs(bank))

    return report


async def main():
    apply = "--apply" in sys.argv[1:]
    db = await get_database()
    report = await migrate(db, apply=apply)

    print(f"Mode : {'APPLY' if apply else 'simulation (aucune écriture)'}")
    print(f"Utilisateurs concernés : {len(report)}")
    for user_id, counts in report.items():
        print(f"  {user_id} : {counts}")


if __name__ == "__main__":
    asyncio.run(main())
