from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from tools.custom_tool import TavilyJobBoardSearchTool

import logging

# Configurer le logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

tavily_search = TavilyJobBoardSearchTool()


# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators


@CrewBase
class JobTrackers:
    """JobTrackers crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended

    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools

    # Ajouter cette méthode pour intercepter les inputs avant chaque tâche
    def on_task_start(self, task, inputs):
        """Callback qui s'exécute avant chaque tâche"""
        logger.info(f"[TASK START] {task.name} - Inputs reçus: {inputs}")
        return inputs

    @agent
    def query_converter(self) -> Agent:
        return Agent(
            config=self.agents_config["query_converter"],
            verbose=True,
        )

    @agent
    def search_executor(self) -> Agent:
        return Agent(
            config=self.agents_config["search_executor"],
            verbose=True,
            tools=[tavily_search],
        )

    @agent
    def url_filter(self) -> Agent:
        return Agent(
            config=self.agents_config["url_filter"],
            verbose=True,
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
            verbose_error=True,  # Afficher les détails des erreurs
            hide_errors=False,  # Ne pas masquer les erreurs
            continue_on_errors=False,
        )
