"""
executor.py — ExecutorAgent for AutoCrew AI
--------------------------------------------
The content-creation powerhouse. Takes a task, plan, and research findings,
then produces rich written deliverables: reports, LinkedIn posts, trip plans,
data tables, email drafts, and more.
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

EXECUTOR_SYSTEM_PROMPT = """You are the **Executor Agent** for AutoCrew AI — a \
world-class content creator and professional writer.

## Your Role
You receive a task description, a structured plan, and research findings, then \
produce high-quality, polished written output tailored to the requested format.

## Deliverable Types You Excel At
- 📄 Long-form reports and analyses
- 📱 LinkedIn posts and social media content
- ✈️ Travel itineraries and trip plans
- 📊 Structured tables and comparison matrices
- 📧 Professional emails and proposals
- 📝 Executive summaries and briefings
- 💡 Strategy documents and recommendations

## Quality Standards
1. **Accuracy**: Ground every claim in the provided research. Do not hallucinate facts.
2. **Clarity**: Write in clear, professional prose appropriate for the audience.
3. **Structure**: Use headings, bullet points, and formatting that aids readability.
4. **Completeness**: Cover all dimensions of the task outlined in the plan.
5. **Tone**: Match the tone to the context — formal for reports, engaging for posts.

## Output
Produce the final written deliverable as a single, well-formatted Markdown document.
Do NOT add meta-commentary like "Here is your report..." — just the deliverable itself.
"""

# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class ExecutorAgent(BaseAgent):
    """
    Executor Agent — transforms research findings into polished content.

    Reads the task, plan, and research_results from the state, then writes a
    complete draft deliverable in Markdown format.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        super().__init__(
            llm=llm,
            system_prompt=EXECUTOR_SYSTEM_PROMPT,
            agent_name="ExecutorAgent",
        )

    def invoke(self, state: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """
        Generate the content draft.

        Args:
            state (Dict[str, Any]): LangGraph state with ``task``, ``plan``,
                and ``research_results``.

        Returns:
            Dict[str, Any]: State update containing ``draft`` (str) and the
                AI response appended to ``messages``.
        """
        task = state.get("task", "")
        plan = state.get("plan", [])
        research_results = state.get("research_results", [])
        iteration = state.get("iteration", 0)
        previous_draft = state.get("draft", "")
        critique = state.get("critique", "")
        memory_context = state.get("memory_context", "")

        memory_section = ""
        if memory_context:
            memory_section = f"\n\n## Relevant Past Tasks (Long-Term Memory)\n{memory_context}\n\nUse these past examples for style and quality reference only.\n"

        # Build the execution prompt, including revision context if iterating
        if iteration > 0 and previous_draft and critique:
            prompt = (
                f"## Task\n{task}\n\n"
                f"## Execution Plan\n{plan}\n\n"
                f"## Research Findings\n{research_results}\n\n"
                f"{memory_section}"
                f"## Previous Draft (Revision #{iteration})\n{previous_draft}\n\n"
                f"## Critic Feedback to Address\n{critique}\n\n"
                "Please revise the draft by incorporating all the critic's feedback. "
                "Produce a significantly improved version that resolves every issue raised."
            )
        else:
            prompt = (
                f"## Task\n{task}\n\n"
                f"## Execution Plan\n{plan}\n\n"
                f"## Research Findings\n{research_results}\n\n"
                f"{memory_section}"
                "Using the plan as a guide and the research findings as your source of truth, "
                "produce a complete, polished deliverable in Markdown format."
            )

        response: Dict[str, Any] = super().invoke(
            state=state,
            extra_human_message=prompt,
            node_name="executor",
        )

        # Extract the text content from the AI response message
        ai_message: AIMessage = response["messages"][0]
        draft_content = ai_message.content

        logger.info(
            "[ExecutorAgent] Draft produced (iteration=%d, length=%d chars).",
            iteration,
            len(draft_content),
        )

        return {
            "draft": draft_content,
            "messages": response["messages"],
            "iteration": iteration + 1,
            "token_usage": response.get("token_usage", []),
        }
