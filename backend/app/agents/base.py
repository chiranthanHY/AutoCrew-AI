"""
base.py — BaseAgent for AutoCrew AI
------------------------------------
Provides the foundational building block for all specialized agents.
All agents inherit from BaseAgent and get LLM invocation, structured output,
error handling, and token usage tracking for free.
"""

import logging
from typing import Any, Dict, Optional, Type

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Groq model pricing table (USD per 1M tokens, as of mid-2026)
# ---------------------------------------------------------------------------
_GROQ_PRICING: Dict[str, Dict[str, float]] = {
    "llama-3.3-70b-versatile":  {"input": 0.59, "output": 0.79},
    "llama-3.1-70b-versatile":  {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant":     {"input": 0.05, "output": 0.08},
    "llama3-8b-8192":           {"input": 0.05, "output": 0.08},
    "llama3-70b-8192":          {"input": 0.59, "output": 0.79},
    "mixtral-8x7b-32768":       {"input": 0.24, "output": 0.24},
    "gemma2-9b-it":             {"input": 0.20, "output": 0.20},
}


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD given model name and token counts."""
    pricing = _GROQ_PRICING.get(model, {"input": 0.59, "output": 0.79})
    return round(
        (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000,
        6,
    )


class BaseAgent:
    """
    Reusable base class for all AutoCrew AI agents.

    Every agent inherits from here and gains:
    - A configured LLM (Groq or any LangChain-compatible model)
    - A structured ChatPromptTemplate with system instructions
    - `invoke()` for free-form text generation
    - `invoke_structured()` for guaranteed JSON output via Pydantic schemas
    - Built-in logging, error handling, and token usage tracking
    """

    def __init__(
        self,
        llm: BaseChatModel,
        system_prompt: str,
        agent_name: str = "BaseAgent",
    ) -> None:
        self.llm = llm
        self.system_prompt = system_prompt
        self.agent_name = agent_name
        self._last_token_usage: Dict[str, Any] = {}

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        logger.info("Initialized agent: %s", self.agent_name)

    # ------------------------------------------------------------------
    # Token usage access
    # ------------------------------------------------------------------

    @property
    def last_token_usage(self) -> Dict[str, Any]:
        """Return token usage metadata from the most recent LLM call."""
        return self._last_token_usage

    def _extract_and_store_usage(
        self, response: AIMessage, node_name: str
    ) -> Dict[str, Any]:
        """
        Extract token usage from an AIMessage response and cache it.
        Returns a usage dict with input_tokens, output_tokens, total_tokens, cost_usd, model.
        """
        input_tokens = 0
        output_tokens = 0
        model_name = getattr(self.llm, "model", "unknown")

        # Try usage_metadata (LangChain standard)
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            input_tokens = um.get("input_tokens", 0)
            output_tokens = um.get("output_tokens", 0)
        # Fallback: Groq response_metadata
        elif hasattr(response, "response_metadata") and response.response_metadata:
            tu = response.response_metadata.get("token_usage", {})
            input_tokens = tu.get("prompt_tokens", 0)
            output_tokens = tu.get("completion_tokens", 0)

        total_tokens = input_tokens + output_tokens
        cost_usd = _compute_cost(model_name, input_tokens, output_tokens)

        usage = {
            "node": node_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "model": model_name,
        }
        self._last_token_usage = usage
        logger.debug(
            "[%s] Token usage — in=%d out=%d total=%d cost=$%.6f",
            self.agent_name, input_tokens, output_tokens, total_tokens, cost_usd,
        )
        return usage

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        state: Dict[str, Any],
        extra_human_message: Optional[str] = None,
    ) -> list:
        messages = list(state.get("messages", []))
        if extra_human_message:
            messages.append(HumanMessage(content=extra_human_message))
        return messages

    # ------------------------------------------------------------------
    # Core invocation methods
    # ------------------------------------------------------------------

    def invoke(
        self,
        state: Dict[str, Any],
        extra_human_message: Optional[str] = None,
        node_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Invoke the agent with free-form text generation.
        Returns state dict with messages and token_usage list.
        """
        try:
            chain = self.prompt_template | self.llm
            messages = self._build_messages(state, extra_human_message)
            logger.debug("[%s] Invoking with %d messages", self.agent_name, len(messages))

            response: AIMessage = chain.invoke({"messages": messages, **kwargs})
            logger.debug("[%s] Response received: %s...", self.agent_name, str(response.content)[:120])

            usage = self._extract_and_store_usage(response, node_name or self.agent_name)
            return {"messages": [response], "token_usage": [usage]}

        except Exception as exc:
            logger.error("[%s] invoke() failed: %s", self.agent_name, exc, exc_info=True)
            raise

    def invoke_structured(
        self,
        state: Dict[str, Any],
        output_schema: Type[BaseModel],
        extra_human_message: Optional[str] = None,
        node_name: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseModel:
        """
        Invoke the agent and coerce the response to a Pydantic schema.
        Also captures token usage from the raw LLM response.
        """
        try:
            structured_llm = self.llm.with_structured_output(output_schema, include_raw=True)
            chain = self.prompt_template | structured_llm
            messages = self._build_messages(state, extra_human_message)
            logger.debug(
                "[%s] Invoking structured output with schema: %s",
                self.agent_name,
                output_schema.__name__,
            )

            raw_result = chain.invoke({"messages": messages, **kwargs})

            # raw_result is {"raw": AIMessage, "parsed": BaseModel, "parsing_error": ...}
            parsed = raw_result.get("parsed")
            raw_msg = raw_result.get("raw")

            if raw_msg and isinstance(raw_msg, AIMessage):
                self._extract_and_store_usage(raw_msg, node_name or self.agent_name)

            if parsed is None:
                raise ValueError(f"Structured output parsing failed: {raw_result.get('parsing_error')}")

            logger.debug("[%s] Structured result: %s", self.agent_name, parsed)
            return parsed

        except Exception as exc:
            logger.error(
                "[%s] invoke_structured() failed: %s", self.agent_name, exc, exc_info=True
            )
            raise
