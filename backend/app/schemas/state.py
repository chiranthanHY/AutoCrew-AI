"""
schemas/state.py — LangGraph AgentState for AutoCrew AI
---------------------------------------------------------
Defines the shared state TypedDict that flows through every node in the
LangGraph StateGraph. Each field uses an appropriate reducer so updates
from different nodes are merged correctly.

Reducer cheat-sheet
-------------------
- ``add_messages``  → appends new messages (never overwrites history)
- ``operator.add``  → concatenates lists (for research_results, token_usage)
- No annotation     → last-write-wins (scalars like task, draft, score)
"""

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ===========================================================================
# Pydantic helper models (used by agents for structured output)
# ===========================================================================


class PlanStep(BaseModel):
    """A single step in the multi-agent execution plan."""

    step_id: int = Field(
        description="Sequential order of this step (1-indexed)"
    )
    task_description: str = Field(
        description="Detailed, actionable description of what this step must accomplish"
    )
    assignee: str = Field(
        description=(
            "Agent responsible for this step. "
            "Must be one of: Researcher | Executor | Critic | Verifier"
        )
    )
    depends_on: List[int] = Field(
        default_factory=list,
        description="IDs of steps that must complete before this step starts",
    )


class Plan(BaseModel):
    """The full execution plan produced by the Planner agent."""

    title: str = Field(description="Short title summarising the overall task")
    objective: str = Field(
        description="One-sentence statement of what the plan aims to achieve"
    )
    steps: List[PlanStep] = Field(
        description="Ordered list of execution steps (3–8 steps)"
    )


# ===========================================================================
# Main LangGraph State
# ===========================================================================


class AgentState(TypedDict):
    """
    Shared mutable state for the AutoCrew AI LangGraph workflow.

    Passed between every node; each node returns a *partial* dict that
    LangGraph merges according to the reducer for each field.
    """

    # ------------------------------------------------------------------
    # Immutable task context
    # ------------------------------------------------------------------
    task: str
    """The original task string submitted by the user."""

    task_id: str
    """Unique identifier for this task run (UUID)."""

    # ------------------------------------------------------------------
    # Message history  (reducer: append-only via add_messages)
    # ------------------------------------------------------------------
    messages: Annotated[List[AnyMessage], add_messages]
    """Full conversation / agent message history for this task run."""

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------
    plan: List[Dict[str, Any]]
    """
    Serialised list of PlanStep dicts produced by the Planner agent.
    Last-write-wins (Planner always replaces the full plan).
    """

    # ------------------------------------------------------------------
    # Research  (reducer: list concatenation via operator.add)
    # ------------------------------------------------------------------
    research_results: Annotated[List[Dict[str, Any]], operator.add]
    """
    Accumulated research findings from the Researcher agent.
    Uses operator.add so multiple research passes are merged, not overwritten.
    """

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    draft: str
    """Current working draft produced by the Executor agent."""

    # ------------------------------------------------------------------
    # Critique & Quality Gate
    # ------------------------------------------------------------------
    critique: str
    """Textual feedback from the Critic agent on the current draft."""

    critique_score: float
    """Numeric quality score (1.0–10.0) assigned by the Critic agent."""

    # ------------------------------------------------------------------
    # Human-in-the-Loop
    # ------------------------------------------------------------------
    human_feedback: Optional[str]
    """
    Optional feedback injected by a human reviewer via the HITL interrupt.
    None = no human review requested or pending.
    """

    awaiting_human: bool
    """
    Flag set to True when the graph has paused for human review.
    Reset to False once feedback is consumed.
    """

    enable_hitl: bool
    """Whether Human-in-the-Loop review is enabled for this task."""

    # ------------------------------------------------------------------
    # Iteration control
    # ------------------------------------------------------------------
    iteration: int
    """
    Number of Executor→Critic loops completed so far.
    Incremented by the Executor on each revision pass.
    Used as a safety guard against infinite loops.
    """

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------
    next: str
    """
    The name of the next node the conditional router should dispatch to.
    Set by the Critic and Supervisor nodes.
    """

    # ------------------------------------------------------------------
    # Final output
    # ------------------------------------------------------------------
    final_output: str
    """The publication-ready deliverable produced by the Verifier agent."""

    # ------------------------------------------------------------------
    # Error tracking
    # ------------------------------------------------------------------
    error: Optional[str]
    """
    Set to a non-None string if any node raises an unrecoverable error.
    The router uses this to short-circuit to a graceful error node.
    """

    # ------------------------------------------------------------------
    # Token usage & cost tracking  (reducer: accumulate list via operator.add)
    # ------------------------------------------------------------------
    token_usage: Annotated[List[Dict[str, Any]], operator.add]
    """
    List of per-node token usage records. Each record has:
      {"node": str, "input_tokens": int, "output_tokens": int, "total_tokens": int,
       "cost_usd": float, "model": str}
    Accumulated across all nodes using operator.add.
    """

    # ------------------------------------------------------------------
    # Long-term memory context (RAG)
    # ------------------------------------------------------------------
    memory_context: Optional[str]
    """
    Relevant past task summaries retrieved from vector store (RAG).
    Injected into the Executor's prompt to provide institutional memory.
    """
