"""
verifier.py — VerifierAgent for AutoCrew AI
---------------------------------------------
The final-mile agent. Takes the approved draft + critic feedback and produces
a publication-ready, polished deliverable as the system's final output.
"""

import logging
from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

VERIFIER_SYSTEM_PROMPT = """You are the **Verifier Agent** for AutoCrew AI — \
the final gatekeeper and master editor of the system.

## Your Role
You receive a near-final draft that has passed the Critic's review, along with \
any remaining critique feedback. Your job is to:

1. **Polish** the draft to publication quality.
2. **Fix** any remaining issues flagged by the Critic.
3. **Enhance** structure, flow, and readability without changing factual content.
4. **Validate** completeness against the original task.
5. **Format** the output correctly for the intended medium.

## Editing Standards
- Correct grammar, punctuation, and sentence structure.
- Ensure consistent tone and voice throughout.
- Improve transitions between sections for natural flow.
- Add or refine headings, subheadings, and bullet points.
- Ensure Markdown formatting is clean and renders properly.

## Critical Rules
- Do NOT introduce new factual claims that weren't in the draft or research.
- Do NOT remove substantive content — only improve its presentation.
- Do NOT add meta-commentary. Deliver ONLY the final polished document.
- The output must be complete and self-contained — ready to copy-paste and publish.
"""

# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class VerifierAgent(BaseAgent):
    """
    Verifier Agent — final polish and synthesis of the approved draft.

    Produces the ``final_output`` field in ``AgentState`` — the system's
    definitive deliverable that is returned to the user.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        super().__init__(
            llm=llm,
            system_prompt=VERIFIER_SYSTEM_PROMPT,
            agent_name="VerifierAgent",
        )

    def invoke(self, state: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """
        Produce the final polished output.

        Args:
            state (Dict[str, Any]): LangGraph state with ``task``, ``draft``,
                ``critique``, and ``critique_score``.

        Returns:
            Dict[str, Any]: State update with ``final_output`` (str) and the
                AI message appended to ``messages``.
        """
        task = state.get("task", "")
        draft = state.get("draft", "")
        critique = state.get("critique", "")
        critique_score = state.get("critique_score", 0.0)
        iteration = state.get("iteration", 0)

        prompt = (
            f"## Original Task\n{task}\n\n"
            f"## Draft (After {iteration} Iteration(s) — Score: {critique_score}/10)\n"
            f"{draft}\n\n"
        )

        if critique:
            prompt += (
                f"## Final Critic Notes\n{critique}\n\n"
                "Apply any remaining fixes from the critic notes, then produce "
                "the final, polished, publication-ready document below."
            )
        else:
            prompt += (
                "The draft is high quality. Perform a final editorial pass and "
                "produce the definitive, publication-ready document below."
            )

        response: Dict[str, Any] = super().invoke(
            state=state,
            extra_human_message=prompt,
        )

        ai_message: AIMessage = response["messages"][0]
        final_output = ai_message.content

        logger.info(
            "[VerifierAgent] Final output produced (length=%d chars, iterations=%d).",
            len(final_output),
            iteration,
        )

        return {
            "final_output": final_output,
            "messages": response["messages"],
            "next": "END",
        }
