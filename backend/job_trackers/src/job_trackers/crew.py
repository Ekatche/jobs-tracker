import json
import logging
import os
from functools import lru_cache
from typing import List, Optional

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

from tools.custom_tool import TavilyJobBoardSearchTool
from models import OptimizedQueries, FilteredJobOffersResult, JobUrlItem

# Configurer le logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# result_as_answer : la sortie brute de l'outil devient la réponse de la tâche,
# l'agent ne peut pas la réécrire ni y ajouter d'URLs.
tavily_search = TavilyJobBoardSearchTool(result_as_answer=True)


REASONING_MODEL_PREFIXES = ("o1", "o3", "gpt-5", "gpt-o")


def is_reasoning_model(model: Optional[str]) -> bool:
    short = (model or "").split("/")[-1].lower()
    return any(short.startswith(p) for p in REASONING_MODEL_PREFIXES)


def _get_openai_temperature(model: str) -> Optional[float]:
    short = (model or "").split("/")[-1].lower()
    if any(short.startswith(p) for p in ("o1", "o3", "gpt-o")):
        return None
    if short.startswith("gpt-5"):
        return 1.0
    return 0.1


class JobTrackerLLM(LLM):
    """CrewAI LLM subclass designed for reasoning models (o1/o3/gpt-5).

    LiteLLM's static capability table incorrectly lists 'stop' as supported for
    OpenAI reasoning models, causing CrewAI to inject 'stop' sequences into calls.
    This subclass:
    1. Returns False for supports_stop_words() on reasoning models, letting CrewAI
       handle stop parsing post-response.
    2. Strips 'stop' from _prepare_completion_params() so neither stop=[] nor
       stop=['...'] is sent to the OpenAI endpoint.
    3. Adds drop_params=True to drop any other unsupported parameter gracefully.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if is_reasoning_model(self.model):
            self.stop = None

    def supports_stop_words(self) -> bool:
        if is_reasoning_model(self.model):
            return False
        return super().supports_stop_words()

    def _prepare_completion_params(self, messages, tools=None):
        params = super()._prepare_completion_params(messages, tools)
        if is_reasoning_model(self.model):
            params.pop("stop", None)
            params["drop_params"] = True
        return params


def _openai_llm(api_key: str) -> LLM:
    """LLM OpenAI pour CrewAI. Les modèles gpt-5 n'acceptent que temperature=1, o1/o3 aucun temp."""
    model = os.getenv("CREW_LLM_MODEL", "gpt-5.6-luna")
    temperature = _get_openai_temperature(model)
    return JobTrackerLLM(model=model, api_key=api_key, temperature=temperature)


def _gemini_llm(api_key: str) -> LLM:
    return JobTrackerLLM(
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
    def filter_urls_task(self) -> Task:
        return Task(
            config=self.tasks_config["filter_urls_task"],
            output_pydantic=FilteredJobOffersResult,
        )

    def query_crew(self) -> Crew:
        return Crew(
            agents=[self.query_converter()],
            tasks=[self.convert_query_task()],
            verbose=False,
        )

    def filter_crew(self) -> Crew:
        return Crew(
            agents=[self.url_filter()],
            tasks=[self.filter_urls_task()],
            verbose=False,
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

    def optimize_query(self, user_query: str) -> OptimizedQueries:
        """Exécute la conversion de la requête utilisateur en requêtes ciblées."""
        result = self.query_crew().kickoff(inputs={"user_query": user_query})
        pyd = getattr(result, "pydantic", None)
        if isinstance(pyd, OptimizedQueries):
            return pyd
        if isinstance(result, dict) and "primary_query" in result:
            return OptimizedQueries(**result)
        raw = getattr(result, "raw", str(result))
        if isinstance(raw, str):
            try:
                data = json.loads(raw.strip().replace("```json", "").replace("```", "").strip())
                if isinstance(data, dict) and "primary_query" in data:
                    return OptimizedQueries(**data)
            except Exception:
                pass
        return OptimizedQueries(
            primary_query=user_query,
            alternative_queries=[],
            extracted_job_title=user_query,
            extracted_location="",
        )

    def filter_urls(self, original_query: str, urls: List[str]) -> FilteredJobOffersResult:
        """Filtre et score les URLs trouvées via l'agent url_filter."""
        if not urls:
            return FilteredJobOffersResult(urls=[], items=[])
        result = self.filter_crew().kickoff(inputs={
            "original_query": original_query,
            "urls": urls,
        })
        pyd = getattr(result, "pydantic", None)
        if isinstance(pyd, FilteredJobOffersResult):
            return pyd
        if isinstance(result, dict) and "urls" in result:
            return FilteredJobOffersResult(**result)
        raw = getattr(result, "raw", str(result))
        if isinstance(raw, str):
            try:
                data = json.loads(raw.strip().replace("```json", "").replace("```", "").strip())
                if isinstance(data, dict) and "urls" in data:
                    return FilteredJobOffersResult(**data)
            except Exception:
                pass
        return FilteredJobOffersResult(
            urls=urls,
            items=[JobUrlItem(url=u, source_platform="Web", relevance_score=7) for u in urls],
        )
