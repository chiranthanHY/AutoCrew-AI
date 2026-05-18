"""
base.py — BaseAgent for AutoCrew AI
------------------------------------
Provides the foundational building block for all specialized agents.
All agents inherit from BaseAgent and get LLM invocation, structured output,
and error handling for free.
"""

import logging
from typing import Any, Dict, Optional, Type

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Reusable base class for all AutoCrew AI agents.

    Every agent inherits from here and gains:
    - A configured LLM (Groq or any LangChain-compatible model)
    - A structured ChatPromptTemplate with system instructions
    - `invoke()` for free-form text generation
    - `invoke_structured()` for guaranteed JSON output via Pydantic schemas
    - Built-in logging and error handling
    """

    def __init__(
        self,
        llm: BaseChatModel,
        system_prompt: str,
        agent_name: str = "BaseAgent",
    ) -> None:
        """
        Initialize the BaseAgent.

        Args:
            llm (BaseChatModel): A LangChain-compatible LLM (e.g., ChatGroq).
            system_prompt (str): The system instruction string for the agent.
            agent_name (str): A human-readable name for logging/tracing.
        """
        self.llm = llm
        self.system_prompt = system_prompt
        self.agent_name = agent_name

        # Build a prompt template that injects the system prompt and allows
        # message history to be passed via the "messages" placeholder.
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        logger.info("Initialized agent: %s", self.agent_name)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        state: Dict[str, Any],
        extra_human_message: Optional[str] = None,
    ) -> list:
        """
        Extract messages from state and optionally append an extra human message.

        Args:
            state (Dict[str, Any]): Current LangGraph state dict.
            extra_human_message (str, optional): If provided, appended as HumanMessage.

        Returns:
            list: List of LangChain message objects.
        """
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
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Invoke the agent with free-form text generation.

        Args:
            state (Dict[str, Any]): The current LangGraph state.
            extra_human_message (str, optional): An additional human-turn message
                to append before invoking the LLM.
            **kwargs: Extra template variables forwarded to the prompt.

        Returns:
            Dict[str, Any]: A state-update dict with the AI response appended
                to ``messages``.
        """
        try:
            chain = self.prompt_template | self.llm
            messages = self._build_messages(state, extra_human_message)
            logger.debug("[%s] Invoking with %d messages", self.agent_name, len(messages))

            response: AIMessage = chain.invoke({"messages": messages, **kwargs})
            logger.debug("[%s] Response received: %s...", self.agent_name, str(response.content)[:120])

            return {"messages": [response]}

        except Exception as exc:
            logger.error("[%s] invoke() failed: %s", self.agent_name, exc, exc_info=True)
            raise

    def invoke_structured(
        self,
        state: Dict[str, Any],
        output_schema: Type[BaseModel],
        extra_human_message: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseModel:
        """
        Invoke the agent and coerce the response to a Pydantic schema.

        Uses LangChain's ``with_structured_output`` to guarantee that the LLM
        returns valid JSON that can be parsed into the given schema.

        Args:
            state (Dict[str, Any]): The current LangGraph state.
            output_schema (Type[BaseModel]): The Pydantic model class to use.
            extra_human_message (str, optional): Additional human-turn message.
            **kwargs: Extra template variables forwarded to the prompt.

        Returns:
            BaseModel: An instance of ``output_schema`` populated with the
                LLM's response.
        """
        try:
            structured_llm = self.llm.with_structured_output(output_schema)
            chain = self.prompt_template | structured_llm
            messages = self._build_messages(state, extra_human_message)
            logger.debug(
                "[%s] Invoking structured output with schema: %s",
                self.agent_name,
                output_schema.__name__,
            )

            result = chain.invoke({"messages": messages, **kwargs})
            logger.debug("[%s] Structured result: %s", self.agent_name, result)
            return result

        except Exception as exc:
            logger.error(
                "[%s] invoke_structured() failed: %s", self.agent_name, exc, exc_info=True
            )
            raise
