"""
tavily.py — Tavily Search Tool Wrapper for AutoCrew AI
"""

import logging
from typing import Any, Dict, List, Optional

from tavily import TavilyClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class TavilySearchTool:
    """
    Wraps the Tavily Search API for AutoCrew AI agents.
    Provides a simple search() method with error handling.
    """

    def __init__(
        self,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_answer: bool = True,
    ) -> None:
        if not settings.tavily_api_key:
            raise ValueError("TAVILY_API_KEY is not set. Configure it in your .env file.")

        self.client = TavilyClient(api_key=settings.tavily_api_key)
        self.max_results = max_results
        self.search_depth = search_depth
        self.include_answer = include_answer
        logger.info("TavilySearchTool initialised (depth=%s, max_results=%d).", search_depth, max_results)

    def search(
        self,
        query: str,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a Tavily web search and return normalised results.

        Returns:
            List of dicts with keys: title, url, content, score.
        """
        logger.info("[TavilySearchTool] Searching: %s", query)
        try:
            kwargs: Dict[str, Any] = {
                "query": query,
                "max_results": self.max_results,
                "search_depth": self.search_depth,
                "include_answer": self.include_answer,
            }
            if include_domains:
                kwargs["include_domains"] = include_domains
            if exclude_domains:
                kwargs["exclude_domains"] = exclude_domains

            response = self.client.search(**kwargs)
            results = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0.0),
                }
                for r in response.get("results", [])
            ]
            logger.info("[TavilySearchTool] Got %d results for: '%s'", len(results), query)
            return results
        except Exception as exc:
            logger.error("[TavilySearchTool] Search failed for '%s': %s", query, exc, exc_info=True)
            return []

    def search_context(self, query: str, max_tokens: int = 4000) -> str:
        """Return a condensed context string — for direct injection into prompts."""
        try:
            return self.client.get_search_context(query=query, max_tokens=max_tokens)
        except Exception as exc:
            logger.error("[TavilySearchTool] search_context failed for '%s': %s", query, exc, exc_info=True)
            return ""
