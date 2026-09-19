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
        "Effectue des recherches web ciblées sur les principaux job boards avec filtrage temporel récent (dernier mois) et exclusion des agrégateurs spam."
    )
    args_schema: Type[BaseModel] = TavilySearchInput
    client: Optional[TavilyClient] = None

    def __init__(self, **data):
        super().__init__(**data)
        tavily_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_key:
            logger.error("Clé TAVILY_API_KEY non trouvée dans l'environnement")
        self.client = TavilyClient(api_key=tavily_key)

    def _run(self, **kwargs) -> list:
        # Extraire la requête de recherche de façon robuste
        query = kwargs.get("query") or kwargs.get("description")

        if isinstance(query, dict):
            query = query.get("primary_query") or query.get("query") or query.get("description")

        if not query and len(kwargs) > 0:
            for k, v in kwargs.items():
                if isinstance(v, str) and len(v.strip()) > 3:
                    query = v
                    break
                elif isinstance(v, dict):
                    query = v.get("primary_query") or v.get("query") or v.get("description")
                    if query:
                        break

        if not isinstance(query, str) or not query.strip():
            logger.error(f"Requête de recherche invalide: {query}")
            return []

        clean_query = query.strip()
        tavily_client = self.client
        if not tavily_client:
            tavily_key = os.environ.get("TAVILY_API_KEY")
            tavily_client = TavilyClient(api_key=tavily_key)

        all_urls = []
        logger.info(f"🔍 Exécution de la recherche Tavily optimisée pour: '{clean_query}'")

        # Domaines exclus (fermes à clics, agrégateurs spammant des redirections mortes)
        spam_aggregators = [
            "jooble.org",
            "fr.jooble.org",
            "talent.com",
            "neuvoo.com",
            "adzuna.fr",
            "jobrapido.com",
            "fr.jobrapido.com",
            "optioncarriere.com",
        ]

        def _is_valid_job_url(u: str) -> bool:
            if not u or not isinstance(u, str) or not u.startswith("http"):
                return False
            low = u.lower()
            if any(spam in low for spam in spam_aggregators):
                return False
            # Exclure les pages génériques non pertinentes
            excluded_paths = (
                "/blog/",
                "/conseils/",
                "/connexion",
                "/login",
                "/auth/",
                "/register",
                "/signup",
                "/faq",
                "/contact",
                "/mentions-legales",
                "/cgu",
                "/privacy",
                "/conditions-generales",
            )
            if any(p in low for p in excluded_paths):
                return False
            return True

        # Palier 1 : Job boards généralistes & nationaux (Volume et couverture locale)
        national_job_boards = [
            "welcometothejungle.com",
            "apec.fr",
            "francetravail.fr",
            "hellowork.com",
            "indeed.fr",
            "cadremploi.fr",
            "free-work.com",
            "lesjeudis.com",
        ]

        # Palier 2 : Portails carrières directs & ATS d'entreprises (Zero-Token extraction directe)
        company_ats_domains = [
            # ATS Tech & Startups (Greenhouse, Lever, Ashby, Workable)
            "greenhouse.io",
            "lever.co",
            "ashbyhq.com",
            "workable.com",
            # ATS PME & Scale-ups Européennes (Teamtailor, Recruitee, Personio, etc.)
            "teamtailor.com",
            "recruitee.com",
            "personio.de",
            "personio.com",
            "breezy.hr",
            "flatchr.io",
            "bamboohr.com",
            # ATS Grands Groupes & Multinationales (Workday, SmartRecruiters, Taleo, iCIMS)
            "myworkdayjobs.com",
            "smartrecruiters.com",
            "taleo.net",
            "icims.com",
            "jobs2web.com",
        ]

        try:
            # ✅ PASSE 1: Recherche sur les job boards français qualifiés (max 12)
            logger.info(f"🇫🇷 Passe 1 - Job boards qualifiés (offres récentes): {clean_query}")
            try:
                response_fr = tavily_client.search(
                    query=clean_query,
                    search_depth="advanced",
                    time_range="month",
                    max_results=12,
                    include_domains=national_job_boards,
                    exclude_domains=spam_aggregators,
                )
                if response_fr and response_fr.get("results"):
                    for r in response_fr["results"]:
                        url = r.get("url")
                        if url and _is_valid_job_url(url):
                            all_urls.append(url)
                    logger.info(f"📋 {len(response_fr['results'])} résultats trouvés sur job boards")
            except Exception as e_fr:
                logger.warning(f"⚠️ Erreur Passe 1 (Job boards): {e_fr}")

            # ✅ PASSE 2: Recherche directe sur les ATS & carrières d'entreprises (max 10)
            logger.info(f"🏢 Passe 2 - ATS & Carrières directs d'entreprises: {clean_query}")
            try:
                response_ats = tavily_client.search(
                    query=clean_query,
                    search_depth="advanced",
                    time_range="month",
                    max_results=10,
                    include_domains=company_ats_domains,
                    exclude_domains=spam_aggregators,
                )
                if response_ats and response_ats.get("results"):
                    for r in response_ats["results"]:
                        url = r.get("url")
                        if url and _is_valid_job_url(url):
                            all_urls.append(url)
                    logger.info(f"🏢 {len(response_ats['results'])} résultats trouvés sur ATS entreprises")
            except Exception as e_ats:
                logger.warning(f"⚠️ Erreur Passe 2 (ATS): {e_ats}")

            # ✅ PASSE 3: Recherche ciblée LinkedIn Jobs (max 8)
            linkedin_query = f"site:linkedin.com/jobs {clean_query}"
            logger.info(f"💼 Passe 3 - LinkedIn Jobs récents: {linkedin_query}")
            try:
                response_linkedin = tavily_client.search(
                    query=linkedin_query,
                    search_depth="advanced",
                    time_range="month",
                    max_results=8,
                    exclude_domains=spam_aggregators,
                )
                if response_linkedin and response_linkedin.get("results"):
                    for r in response_linkedin["results"]:
                        url = r.get("url")
                        if url and "linkedin.com/jobs" in url and _is_valid_job_url(url):
                            all_urls.append(url)
                    logger.info(f"💼 {len(response_linkedin['results'])} résultats trouvés sur LinkedIn")
            except Exception as e_li:
                logger.warning(f"⚠️ Erreur Passe 3 (LinkedIn): {e_li}")

            # Dédoublonnage en conservant l'ordre
            seen = set()
            unique_urls = []
            for u in all_urls:
                u_clean = u.strip()
                if u_clean not in seen:
                    seen.add(u_clean)
                    unique_urls.append(u_clean)

            logger.info(f"✅ Total: {len(unique_urls)} URLs d'offres uniques et récentes retenues")
            return unique_urls

        except Exception as e:
            logger.error(f"Erreur lors de la recherche Tavily: {str(e)}")
            return []
