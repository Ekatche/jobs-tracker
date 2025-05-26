import os
import logging
from crewai.tools import BaseTool
from typing import Type, Any, Optional
from pydantic import BaseModel, Field
from tavily import TavilyClient
from dotenv import load_dotenv

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement depuis le .env
load_dotenv()


class TavilySearchInput(BaseModel):
    query: Any = Field(
        None, description="Requête de recherche pour trouver des offres d'emploi."
    )
    description: Any = Field(
        None, description="Alias pour la requête si jamais query n'est pas utilisé."
    )

    @property
    def effective_query(self):
        return self.query or self.description


class TavilyJobBoardSearchTool(BaseTool):
    name: str = "Recherche d'offres d'emploi sur job boards"
    description: str = (
        "Utiliser l'API Tavily pour effectuer une recherche web et obtenir des résultats organisés par IA."
    )
    args_schema: Type[BaseModel] = TavilySearchInput
    client: Optional[TavilyClient] = None  # Déclare l'attribut ici

    def __init__(self, **data):
        super().__init__(**data)
        print(f"DEBUG TAVILY INPUT: {data}")  # Affiche ce que reçoit Pydantic
        tavily_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_key:
            logger.error("Clé Tavily non trouvée dans les variables d'environnement")
            # Lève une exception ou définis un drapeau d'erreur
        self.client = TavilyClient(api_key=tavily_key)

    def _run(self, **kwargs) -> list:
        # Extraire la requête selon différents formats possibles
        query = None

        # Si on reçoit directement un argument 'query'
        query = kwargs.get("query") or kwargs.get("description")

        # Cas où CrewAI envoie la requête dans un format imbriqué
        if isinstance(query, dict) and "description" in query:
            query = query["description"]

        # Si on n'a pas encore trouvé la requête, rechercher dans kwargs
        if not query and len(kwargs) > 0:
            # Chercher dans n'importe quel champ qui pourrait contenir la requête
            for k, v in kwargs.items():
                if isinstance(v, dict) and "description" in v:
                    query = v["description"]
                    break

        # Deuxième vérification de type après extraction
        if not isinstance(query, str):
            logger.error(f"Impossible de convertir en chaîne: {type(query)}")
            return []

        tavily_client = self.client
        all_urls = []
        logger.info(f"Exécution de la recherche Tavily avec query: {query}")

        try:

            # ✅ PASSE 1: Sites français fiables
            french_sites = [
                "francetravail.fr",
                "hellowork.com",
                "apec.fr",
                "welcometothejungle.com",
            ]

            # Recherche sites français
            logger.info(f"🇫🇷 Recherche sites français: {query}")
            response_fr = tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=15,
                include_domains=french_sites,
            )

            if response_fr.get("results"):
                all_urls.extend([r["url"] for r in response_fr["results"]])
                logger.info(f"📋 {len(response_fr['results'])} URLs sites français")

            # ✅ PASSE 2: LinkedIn spécifiquement
            linkedin_query = f"site:linkedin.com/jobs {query}"
            logger.info(f"💼 Recherche LinkedIn: {linkedin_query}")

            response_linkedin = tavily_client.search(
                query=linkedin_query,
                search_depth="advanced",
                max_results=15,
            )

            if response_linkedin.get("results"):
                linkedin_urls = [r["url"] for r in response_linkedin["results"]]
                all_urls.extend(linkedin_urls)
                logger.info(f"💼 {len(linkedin_urls)} URLs LinkedIn")

            # ✅ PASSE 3: LinkedIn - URL générique de recherche
            linkedin_search_url = "https://www.linkedin.com/jobs/search/?currentJobId=4235097194&f_TPR=r86400&geoId=103623254&keywords=data%20scientist&origin=JOB_SEARCH_PAGE_LOCATION_AUTOCOMPLETE&refresh=true"
            all_urls.append(linkedin_search_url)
            logger.info("💼 Ajout URL de recherche LinkedIn générique")

            # Dédoublonnage
            unique_urls = list(set(all_urls))
            logger.info(f"✅ Total: {len(unique_urls)} URLs uniques trouvées")

            return unique_urls

        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {str(e)}")
            return []
