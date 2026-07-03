"""
planner.py — PlannerAgent for AutoCrew AI
------------------------------------------
Decomposes a high-level user task into a structured, step-by-step execution
plan, assigning each step to the most appropriate specialist agent.
"""

import logging
from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.schemas.state import Plan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """You are the **Planner Agent** for AutoCrew AI — an elite \
multi-agent automation system.

Your responsibility is to receive a high-level user task and decompose it into a \
precise, ordered sequence of steps that other specialist agents will execute.

## Available Agents
| Agent Name   | Responsibility                                                          |
|--------------|-------------------------------------------------------------------------|
| Researcher   | Searches the web, gathers facts, retrieves up-to-date information.      |
| Executor     | Produces written deliverables: reports, posts, tables, trip plans, etc. |
| Critic       | Reviews quality, checks accuracy and completeness. Scores output 1–10.  |
| Verifier     | Polishes the final output, resolves critique feedback, finalises work.  |

## Planning Rules
1. Every plan MUST start with a Researcher step unless the task is purely creative.
2. Every plan MUST include a Critic step before the final Verifier step.
3. Steps must be logically ordered with no circular dependencies.
4. Descriptions must be specific and actionable — not vague placeholders.
5. Assign only ONE agent per step.
6. Use between 3 and 8 steps.

## Output Format
Return a structured JSON object matching the Plan schema exactly.
"""

# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class PlannerAgent(BaseAgent):
    """
    Planner Agent — breaks down tasks into structured multi-agent plans.

    Returns a ``Plan`` Pydantic object whose ``steps`` list is serialised into
    the ``plan`` field of ``AgentState``.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        super().__init__(
            llm=llm,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            agent_name="PlannerAgent",
        )

    def invoke(self, state: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """
        Generate a step-by-step plan for the current task.

        Reads ``state["task"]`` and produces a structured plan that is written
        back to ``state["plan"]`` as a list of dicts.

        Args:
            state (Dict[str, Any]): Current LangGraph state.
            **kwargs: Unused; kept for interface compatibility.

        Returns:
            Dict[str, Any]: State update containing ``plan`` (list[dict]).
        """
        task = state.get("task", "").strip()
        if not task:
            logger.warning("[PlannerAgent] No task found in state.")
            return {"plan": []}

        prompt = (
            f"Create a detailed execution plan for the following task:\n\n"
            f"**Task:** {task}\n\n"
            "Return a structured JSON plan using the Plan schema."
        )

        structured_plan: Plan = self.invoke_structured(
            state=state,
            output_schema=Plan,
            extra_human_message=prompt,
            node_name="planner",
        )

        plan_dicts = [step.model_dump() for step in structured_plan.steps]
        logger.info("[PlannerAgent] Generated plan with %d steps.", len(plan_dicts))

        return {
            "plan": plan_dicts,
            "token_usage": [self.last_token_usage] if self.last_token_usage else [],
        }
