import asyncio
from typing import Dict, Any, List
import json
from litellm import completion
from crawl4ai import AsyncWebCrawler

async def extract_url_with_llm(url: str, context: str) -> Dict[str, Any]:
    """Scrape une URL avec Crawl4AI et extrait les infos avec Gemini."""
    try:
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(url=url)
            
            if not result.markdown:
                return {}

            prompt = f"""
Voici le texte extrait d'un site web ({context}).
Extraire les informations pertinentes pour un profil de candidat.

Texte du site :
-----------------
{result.markdown[:15000]} # Limiter la taille
-----------------

Instructions : Renvoie un JSON avec les clés :
- "summary": (bio ou résumé)
- "projects": [{{"name", "description", "stack": []}}]
- "skills": {{"categorie": ["skill1"]}}
- "experiences": [{{"company", "role", "start", "end", "missions": [], "stack": []}}]
S'il manque des infos, renvoie des tableaux vides.
"""
            response = completion(
                model="gemini/gemini-3.8-flash",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content)
    except Exception as e:
        print(f"Erreur Extraction {context} ({url}): {e}")
        return {}

async def enrich_profile_from_urls(github_url: str = None, linkedin_url: str = None, portfolio_url: str = None) -> Dict[str, Any]:
    """Compile les informations de toutes les URLs fournies."""
    enriched_data = {
        "projects": [],
        "experiences": [],
        "skills": {},
        "summary": ""
    }

    tasks = []
    if github_url:
        tasks.append(extract_url_with_llm(github_url, "Profil GitHub"))
    if linkedin_url:
        # Transformation de l'URL pour LinkedIn Guest API si c'est un profil (souvent bloqué mais on tente)
        tasks.append(extract_url_with_llm(linkedin_url, "Profil LinkedIn"))
    if portfolio_url:
        tasks.append(extract_url_with_llm(portfolio_url, "Portfolio Personnel"))

    if not tasks:
        return enriched_data

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception) or not result:
            continue
        
        # Merge projects
        if "projects" in result:
            enriched_data["projects"].extend(result["projects"])
            
        # Merge experiences
        if "experiences" in result:
            enriched_data["experiences"].extend(result["experiences"])
        
        # Merge summary
        if result.get("summary") and not enriched_data["summary"]:
            enriched_data["summary"] = result["summary"]
        elif result.get("summary") and len(result["summary"]) > len(enriched_data["summary"]):
             # Garder le summary le plus long (potentiellement plus riche)
             enriched_data["summary"] = result["summary"]

        # Merge skills
        if "skills" in result and isinstance(result["skills"], dict):
            for cat, skills in result["skills"].items():
                if cat not in enriched_data["skills"]:
                    enriched_data["skills"][cat] = []
                enriched_data["skills"][cat].extend(skills)

    # Clean up duplicates
    for cat in enriched_data["skills"]:
        enriched_data["skills"][cat] = list(set(enriched_data["skills"][cat]))

    return enriched_data

