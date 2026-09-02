from functools import lru_cache
from typing import List, Optional
import os
import logging
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

from tools.custom_tool import TavilyJobBoardSearchTool
from models import OptimizedQueries, FilteredJobOffersResult

# Configurer le logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

tavily_search = TavilyJobBoardSearchTool()


@lru_cache(maxsize=1)
def get_crew_llm() -> LLM:
    """Sélectionne et met en cache le LLM optimal selon les clés API disponibles."""
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    # Préférer OpenAI si disponible ou si Gemini n'a pas de crédits prépayés
    if openai_key and not os.getenv("PREFER_GEMINI", "").lower() in ("true", "1"):
        logger.info("Utilisation d'OpenAI gpt-4o-mini comme moteur LLM pour CrewAI")
        return LLM(model="gpt-4o-mini", api_key=openai_key, temperature=0.1)

    if gemini_key:
        logger.info("Utilisation de Gemini comme moteur LLM pour CrewAI")
        return LLM(
            model="gemini/gemini-flash-latest",
            api_key=gemini_key,
            temperature=0.1,
        )

    if openai_key:
        return LLM(model="gpt-4o-mini", api_key=openai_key, temperature=0.1)

    raise ValueError("Aucune clé API LLM (OPENAI_API_KEY ou GEMINI_API_KEY) trouvée.")


@CrewBase
class JobTrackers:
    """JobTrackers crew pour la recherche et le filtrage d'offres d'emploi."""

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def query_converter(self) -> Agent:
        return Agent(
            config=self.agents_config["query_converter"],
            llm=get_crew_llm(),
            verbose=False,
        )

    @agent
    def search_executor(self) -> Agent:
        return Agent(
            config=self.agents_config["search_executor"],
            llm=get_crew_llm(),
            verbose=False,
            tools=[tavily_search],
        )

    @agent
    def url_filter(self) -> Agent:
        return Agent(
            config=self.agents_config["url_filter"],
            llm=get_crew_llm(),
            verbose=False,
        )

    @task
    def convert_query_task(self) -> Task:
        return Task(
            config=self.tasks_config["convert_query_task"],
            output_pydantic=OptimizedQueries,
        )

    @task
    def execute_search_task(self) -> Task:
        return Task(
            config=self.tasks_config["execute_search_task"],
        )

    @task
    def filter_urls_task(self) -> Task:
        return Task(
            config=self.tasks_config["filter_urls_task"],
            output_pydantic=FilteredJobOffersResult,
        )

    @crew
    def crew(self) -> Crew:
        """Crée et configure le Crew JobTrackers séquentiel."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
