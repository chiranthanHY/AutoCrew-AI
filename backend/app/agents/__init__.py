"""
agents/__init__.py — AutoCrew AI agent package.

All five specialist agents are exported from this module so
external code can import them cleanly:

    from app.agents import PlannerAgent, ResearcherAgent, ExecutorAgent

"""

from app.agents.base import BaseAgent
from app.agents.critic import CriticAgent
from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.researcher import ResearcherAgent
from app.agents.verifier import VerifierAgent

__all__ = [
    "BaseAgent",
    "PlannerAgent",
    "ResearcherAgent",
    "ExecutorAgent",
    "CriticAgent",
    "VerifierAgent",
]
