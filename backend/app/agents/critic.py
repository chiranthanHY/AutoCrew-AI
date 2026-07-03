"""
critic.py — CriticAgent for AutoCrew AI
-----------------------------------------
Quality-assurance specialist that reviews executor drafts for accuracy,
completeness, and clarity. Returns a numeric score and detailed feedback.
"""

import logging
from typing import Any, Dict, List

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

CRITIC_SYSTEM_PROMPT = """You are the **Critic Agent** for AutoCrew AI — a rigorous \
quality-assurance reviewer with exceptionally high standards.

## Your Role
You receive the original task, the research findings, and a draft deliverable. \
Your job is to evaluate the draft objectively and provide actionable feedback.

## Evaluation Criteria
Score the draft on each dimension from 1 (poor) to 10 (excellent):

| Dimension     | What to Evaluate                                                    |
|---------------|---------------------------------------------------------------------|
| Accuracy      | Are all claims grounded in the research? No hallucinations?         |
| Completeness  | Does it cover every dimension of the task / plan?                   |
| Clarity       | Is it well-written, easy to understand, free of jargon overload?    |
| Structure     | Is it logically organised with appropriate headings and formatting? |
| Tone          | Is the tone appropriate for the deliverable type and audience?      |

## Scoring
- **8-10**: Excellent — minor polish only needed.
- **5-7**: Good — specific improvements required before finalising.
- **1-4**: Needs significant rework — return to Executor with detailed guidance.

## Output Format
Return a structured JSON object matching the CritiqueOutput schema exactly.
Be specific and constructive. Vague feedback like "needs improvement" is unacceptable.
"""

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class IssueDetail(BaseModel):
    """A specific issue found in the draft."""

    dimension: str = Field(
        description="The evaluation dimension affected (e.g., Accuracy, Completeness)"
    )
    description: str = Field(
        description="Clear description of the issue and why it is a problem"
    )
    suggestion: str = Field(
        description="Concrete suggestion for how to fix this issue"
    )


class CritiqueOutput(BaseModel):
    """Full structured critique returned by the Critic agent."""

    overall_score: float = Field(
        ge=1.0,
        le=10.0,
        description="Overall quality score from 1.0 (worst) to 10.0 (best)",
    )
    accuracy_score: float = Field(ge=1.0, le=10.0)
    completeness_score: float = Field(ge=1.0, le=10.0)
    clarity_score: float = Field(ge=1.0, le=10.0)
    structure_score: float = Field(ge=1.0, le=10.0)
    tone_score: float = Field(ge=1.0, le=10.0)

    strengths: List[str] = Field(
        description="List of specific things the draft does well"
    )
    issues: List[IssueDetail] = Field(
        description="List of specific issues that must be addressed"
    )
    summary_feedback: str = Field(
        description="A concise paragraph summarising overall quality and priority changes"
    )
    approved: bool = Field(
        description="True if the draft is good enough (score >=8.0) to proceed to Verifier"
    )


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class CriticAgent(BaseAgent):
    """
    Critic Agent — reviews drafts and returns scored, structured feedback.

    The ``approved`` field in :class:`CritiqueOutput` is used by the LangGraph
    routing logic to decide whether to loop back to the Executor or advance to
    the Verifier.
    """

    APPROVAL_THRESHOLD = 8.0

    def __init__(self, llm: BaseChatModel) -> None:
        super().__init__(
            llm=llm,
            system_prompt=CRITIC_SYSTEM_PROMPT,
            agent_name="CriticAgent",
        )

    def invoke(self, state: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """
        Review the current draft and return structured critique.

        Args:
            state (Dict[str, Any]): LangGraph state with ``task``,
                ``research_results``, ``draft``, and ``iteration``.

        Returns:
            Dict[str, Any]: State update with ``critique`` (str),
                ``critique_score`` (float), and ``next`` routing key.
        """
        task = state.get("task", "")
        draft = state.get("draft", "")
        research_results = state.get("research_results", [])
        iteration = state.get("iteration", 0)

        if not draft:
            logger.warning("[CriticAgent] No draft found in state to review.")
            return {"critique": "No draft available.", "critique_score": 0.0, "next": "executor"}

        prompt = (
            f"## Original Task\n{task}\n\n"
            f"## Research Findings (Ground Truth)\n{research_results}\n\n"
            f"## Draft to Review (Iteration #{iteration})\n{draft}\n\n"
            f"Evaluate this draft against the task and research findings. "
            f"Return a detailed CritiqueOutput. "
            f"Mark `approved=true` only if the overall score is {self.APPROVAL_THRESHOLD} or above."
        )

        critique_output: CritiqueOutput = self.invoke_structured(
            state=state,
            output_schema=CritiqueOutput,
            extra_human_message=prompt,
            node_name="critic",
        )

        # Determine routing: go to verifier if approved, else loop to executor
        next_node = "verifier" if critique_output.approved else "executor"

        logger.info(
            "[CriticAgent] Score: %.1f | Approved: %s | Next: %s",
            critique_output.overall_score,
            critique_output.approved,
            next_node,
        )

        return {
            "critique": critique_output.summary_feedback,
            "critique_score": critique_output.overall_score,
            "next": next_node,
            "token_usage": [self.last_token_usage] if self.last_token_usage else [],
        }
