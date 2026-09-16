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


def _openai_llm(api_key: str) -> LLM:
    """LLM OpenAI pour CrewAI. Les modèles gpt-5 n'acceptent que temperature=1."""
    model = os.getenv("CREW_LLM_MODEL", "gpt-5.6-luna")
    temperature = 1 if model.startswith("gpt-5") else 0.1
    return LLM(model=model, api_key=api_key, temperature=temperature)


def _gemini_llm(api_key: str) -> LLM:
    return LLM(
        model=os.getenv("CREW_LLM_MODEL_GEMINI", "gemini/gemini-3.8-flash"),
        api_key=api_key,
        temperature=0.1,
    )


@lru_cache(maxsize=1)
def get_crew_llm() -> LLM:
    """Sélectionne et met en cache le LLM pour query_converter et url_filter.

    Gemini est préféré par défaut (moins cher que gpt-4o-mini/gpt-5.6-luna).
    `PREFER_GEMINI=false` force OpenAI pour qui veut le troquer contre plus de
    fiabilité sur le tool-calling. search_executor a son propre LLM dédié
    (get_search_executor_llm) : priorité coût explicite, indépendante de ce choix.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    prefer_gemini = os.getenv("PREFER_GEMINI", "true").lower() in ("true", "1")

    if gemini_key and prefer_gemini:
        logger.info("Utilisation de Gemini comme moteur LLM pour CrewAI")
        return _gemini_llm(gemini_key)

    if openai_key:
        logger.info("Utilisation d'OpenAI comme moteur LLM pour CrewAI")
        return _openai_llm(openai_key)

    if gemini_key:
        logger.info("Utilisation de Gemini comme moteur LLM pour CrewAI (repli, pas de clé OpenAI)")
        return _gemini_llm(gemini_key)

    raise ValueError("Aucune clé API LLM (OPENAI_API_KEY ou GEMINI_API_KEY) trouvée.")


@lru_cache(maxsize=1)
def get_search_executor_llm() -> LLM:
    """LLM dédié à search_executor (boucle sur les résultats Tavily).

    Priorité coût explicite sur ce rôle : gpt-5-nano bat gemini-3.8-flash sur le
    prix ($0.50/$1.50 vs $0.75/$3.75 par M tokens) tout en gardant le tool-calling
    natif OpenAI, plus mature que l'adaptateur LiteLLM pour Gemini. Indépendant de
    PREFER_GEMINI, qui ne pilote que query_converter/url_filter.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY requise pour search_executor (CREW_LLM_MODEL_SEARCH).")
    model = os.getenv("CREW_LLM_MODEL_SEARCH", "gpt-5-nano")
    temperature = 1 if model.startswith("gpt-5") else 0.1
    return LLM(model=model, api_key=api_key, temperature=temperature)


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
            llm=get_search_executor_llm(),
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
