"""Fusion rétroactive des offres en doublon, y compris entre variantes d'un même nom d'entreprise.

Simulation par défaut : liste les paires sans rien écrire. `--apply` fusionne réellement.
La règle vit dans app/services/offer_dedup.py, appliquée aussi chaque nuit par cleanup_job_offers.
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_database
from app.services.offer_dedup import merge_duplicate_offers


async def main(apply: bool) -> None:
    await merge_duplicate_offers(await get_database(), apply=apply)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main(apply="--apply" in sys.argv[1:]))
