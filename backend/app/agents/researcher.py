"""
researcher.py — ResearcherAgent for AutoCrew AI
-------------------------------------------------
Conducts multi-query web research using the Tavily Search API and synthesises
findings into structured research results consumed by the Executor agent.
"""

import logging
from typing import Any, Dict, List

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.tools.tavily import TavilySearchTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

RESEARCHER_SYSTEM_PROMPT = """You are the **Researcher Agent** for AutoCrew AI — a \
meticulous and thorough information-gathering specialist.

## Your Role
You receive a research objective and a set of relevant search queries. Your job is to:
1. Critically evaluate the search results provided to you.
2. Identify the most credible, recent, and relevant facts.
3. Discard duplicate, irrelevant, or low-quality information.
4. Synthesise findings into a coherent, well-structured research report.

## Output Standards
- Write in clear, neutral, factual prose.
- Cite sources by URL where available.
- Organise findings under logical headings.
- Flag any contradictions or gaps in the data.
- Do NOT fabricate facts. If information is not in the search results, say so.

## Format
Return a JSON object matching the ResearchOutput schema.
"""

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ResearchFinding(BaseModel):
    """A single research finding."""

    heading: str = Field(description="Short heading / topic of this finding")
    summary: str = Field(description="Detailed summary of the finding (2-4 sentences)")
    sources: List[str] = Field(
        default_factory=list,
        description="List of source URLs supporting this finding",
    )


class ResearchOutput(BaseModel):
    """Structured output from the Researcher agent."""

    overview: str = Field(description="A 2-3 sentence executive summary of all findings")
    findings: List[ResearchFinding] = Field(
        description="List of individual research findings, each with a heading and summary"
    )
    search_queries_used: List[str] = Field(
        description="List of search queries that were executed"
    )


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class ResearcherAgent(BaseAgent):
    """
    Researcher Agent — gathers web data via Tavily and returns structured findings.

    Workflow:
    1. Derives up to ``max_queries`` search queries from the task description.
    2. Executes each query using the :class:`~app.tools.tavily.TavilySearchTool`.
    3. Passes all raw results to the LLM for synthesis into :class:`ResearchOutput`.
    4. Returns state updates for ``research_results`` and ``messages``.
    """

    def __init__(self, llm: BaseChatModel, max_queries: int = 3) -> None:
        """
        Args:
            llm (BaseChatModel): LangChain LLM instance (ChatGroq recommended).
            max_queries (int): Maximum number of Tavily searches to perform.
        """
        super().__init__(
            llm=llm,
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
            agent_name="ResearcherAgent",
        )
        self.search_tool = TavilySearchTool()
        self.max_queries = max_queries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_queries(self, task: str, plan: List[Dict]) -> List[str]:
        """
        Ask the LLM to generate targeted search queries for the given task.

        Args:
            task (str): The high-level user task.
            plan (List[Dict]): The current execution plan for context.

        Returns:
            List[str]: Up to ``self.max_queries`` search query strings.
        """

        class QueryList(BaseModel):
            queries: List[str] = Field(
                description=f"Up to {self.max_queries} specific search queries"
            )

        prompt = (
            f"Given this task:\n{task}\n\n"
            f"And this execution plan:\n{plan}\n\n"
            f"Generate up to {self.max_queries} targeted web search queries "
            "that will gather the most relevant and up-to-date information needed."
        )
        result: QueryList = self.invoke_structured(
            state={"messages": []},
            output_schema=QueryList,
            extra_human_message=prompt,
        )
        return result.queries[: self.max_queries]

    def _run_searches(self, queries: List[str]) -> List[Dict[str, Any]]:
        """Execute each query and collect raw Tavily results."""
        all_results: List[Dict[str, Any]] = []
        for query in queries:
            try:
                logger.info("[ResearcherAgent] Searching: %s", query)
                results = self.search_tool.search(query)
                all_results.extend(results)
            except Exception as exc:
                logger.warning("[ResearcherAgent] Search failed for '%s': %s", query, exc)
        return all_results

    # ------------------------------------------------------------------
    # Public invoke
    # ------------------------------------------------------------------

    def invoke(self, state: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """
        Execute the full research pipeline and update state.

        Args:
            state (Dict[str, Any]): Current LangGraph state with ``task`` and ``plan``.

        Returns:
            Dict[str, Any]: State update with ``research_results`` (list[dict])
                and an AI summary message appended to ``messages``.
        """
        task = state.get("task", "")
        plan = state.get("plan", [])

        # 1. Generate queries
        queries = self._generate_queries(task, plan)
        logger.info("[ResearcherAgent] Using %d queries: %s", len(queries), queries)

        # 2. Run searches
        raw_results = self._run_searches(queries)

        # 3. Build synthesis prompt
        results_text = "\n\n".join(
            f"Source: {r.get('url', 'N/A')}\nTitle: {r.get('title', '')}\nContent: {r.get('content', '')}"
            for r in raw_results
        )
        synthesis_prompt = (
            f"Task: {task}\n\n"
            f"Search Queries Used: {queries}\n\n"
            f"Raw Search Results:\n{results_text}\n\n"
            "Synthesise these results into a structured research report using the ResearchOutput schema."
        )

        # 4. Synthesise with structured output
        research_output: ResearchOutput = self.invoke_structured(
            state=state,
            output_schema=ResearchOutput,
            extra_human_message=synthesis_prompt,
        )

        research_dicts = [f.model_dump() for f in research_output.findings]
        logger.info(
            "[ResearcherAgent] Synthesised %d findings from %d raw results.",
            len(research_dicts),
            len(raw_results),
        )

        return {
            "research_results": research_dicts,
            "messages": [
                HumanMessage(
                    content=f"Research complete. Overview: {research_output.overview}"
                )
            ],
        }
