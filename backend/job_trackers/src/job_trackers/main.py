#!/usr/bin/env python
import sys
import os
import warnings


current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from .crew import JobTrackers  # noqa: E402


warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information


def run_crew(user_query: str):
    """
    Run the crew.
    """

    try:
        inputs = {"user_query": user_query}
        result = JobTrackers().crew().kickoff(inputs=inputs)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")
