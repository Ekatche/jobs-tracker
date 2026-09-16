import asyncio
import sys
sys.path.insert(0, "/Users/elielkatche/job-tracker/backend")

from app.database import get_database

ALREADY_USED = {
    "https://fr.indeed.com/viewjob?from=app-tracker-saved-appcard&hl=fr&jk=afd42d866addd921&tk=1k2d1c9ri229i000",
    "https://www.welcometothejungle.com/fr/companies/nexton-consulting/jobs/ai-developer-h-f_lyon",
    "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles=Ing%C3%A9nieur+Plateforme+IA+%2F+MLOps",
    "https://www.hellowork.com/fr-fr/emplois/83256458.html",
    "https://candidat.francetravail.fr/offres/recherche/detail/209VCCG",
    "https://candidat.francetravail.fr/offres/recherche/detail/213WXYS",
    "https://fr.linkedin.com/jobs/view/ai-engineer-at-scaleway-4465566696",
    "https://fr.linkedin.com/jobs/view/data-engineer-at-n%C3%A9osoft-4465711480",
}


async def main():
    db = await get_database()
    cursor = db["job_offers"].find(
        {"url": {"$type": "string", "$ne": ""}, "is_deleted": {"$ne": True}},
        {"url": 1, "poste": 1, "entreprise": 1, "created_at": 1},
    ).sort("created_at", -1).limit(60)
    fresh = []
    async for doc in cursor:
        url = doc.get("url")
        if url and url not in ALREADY_USED:
            fresh.append(doc)
    for doc in fresh[:20]:
        print(doc.get("url"), "|", doc.get("poste"), "|", doc.get("entreprise"), "|", doc.get("created_at"))


asyncio.run(main())
