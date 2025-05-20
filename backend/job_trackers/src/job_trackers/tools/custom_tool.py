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
        ..., description="Requête de recherche pour trouver des offres d'emploi."
    )
    description: Any = Field(None, description="Alias pour la requête si jamais query n'est pas utilisé.")

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

    def _run(self, **kwargs) -> list:  # Changement du type d'entrée
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

        french_boards = [
            "francetravail.fr",
            "hellowork.com",
            "apec.fr",
            "welcometothejungle.com",
        ]
        global_boards = ["linkedin.com", "indeed.com", "glassdoor.com"]
        include_domains = french_boards + global_boards
        tavily_client = self.client

        logger.info(f"Exécution de la recherche Tavily avec query: {query}")

        try:
            response_w_domains = tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=30,
                include_domains=include_domains,
            )
            return self._process_response(response_w_domains)

        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {str(e)}")
            return ["ERREUR: L'outil de recherche n'a pas pu s'exécuter correctement."]

    def _process_response(self, response: dict) -> list:
        if not response.get("results"):
            return "No results found."

        urls = [result["url"] for result in response["results"]]
        logger.info(f"Récupération de {len(urls)} URLs")

        return urls
