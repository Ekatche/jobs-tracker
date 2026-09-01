from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from tools.custom_tool import TavilyJobBoardSearchTool
import os
import logging

# Configurer le logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

tavily_search = TavilyJobBoardSearchTool()


def get_crew_llm():
    """Sélectionne le LLM optimal selon les clés API disponibles"""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        return LLM(model="gemini/gemini-flash-latest", api_key=gemini_key, temperature=0.1)
    openai_key = os.getenv("OPENAI_API_KEY")
    return LLM(model="gpt-4o-mini", api_key=openai_key, temperature=0.1)


@CrewBase
class JobTrackers:
    """JobTrackers crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def on_task_start(self, task, inputs):
        """Callback qui s'exécute avant chaque tâche"""
        return inputs

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

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def convert_query_task(self) -> Task:
        return Task(
            config=self.tasks_config["convert_query_task"],
            callbacks={"on_task_start": self.on_task_start},  # Associer le callback
        )

    @task
    def execute_search_task(self) -> Task:
        return Task(
            config=self.tasks_config["execute_search_task"],
            callbacks={"on_task_start": self.on_task_start},  # Associer le callback
            # depend_on=["convert_query_task"],  # dépendance logique si supportée par CrewAI
        )

    @task
    def filter_urls_task(self) -> Task:
        return Task(
            config=self.tasks_config["filter_urls_task"],
            callbacks={"on_task_start": self.on_task_start},  # Associer le callback
            # depend_on=["execute_search_task"],  # dépendance logique si supportée par CrewAI
        )

    @crew
    def crew(self) -> Crew:
        """Creates the JobTrackers crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
            verbose_error=False,  # Afficher les détails des erreurs
            hide_errors=True,  # Ne pas masquer les erreurs
            continue_on_errors=False,
        )
