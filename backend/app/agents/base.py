from typing import Any, Dict
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models.chat_models import BaseChatModel

class BaseAgent:
    """
    A reusable base agent class for AutoCrew AI.
    Provides a foundational structure for specialized agents.
    """
    def __init__(self, llm: BaseChatModel, system_prompt: str):
        self.llm = llm
        self.system_prompt = system_prompt
        
        # Base prompt template expects 'messages' in the state
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])

    def invoke(self, state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Invokes the agent with the current state and returns standard output.
        
        Args:
            state (Dict[str, Any]): The current state from the LangGraph.
            **kwargs: Additional variables for prompt template interpolation.
            
        Returns:
            Dict[str, Any]: A dictionary containing the agent's response, appended to "messages".
        """
        chain = self.prompt_template | self.llm
        messages = state.get("messages", [])
        
        response = chain.invoke({"messages": messages, **kwargs})
        return {"messages": [response]}

    def invoke_structured(self, state: Dict[str, Any], output_schema: Any, **kwargs) -> Any:
        """
        Invokes the agent and forces a structured JSON output based on a Pydantic schema.
        
        Args:
            state (Dict[str, Any]): The current state from the LangGraph.
            output_schema (Any): The Pydantic model class to format the output.
            **kwargs: Additional variables for prompt template interpolation.
            
        Returns:
            Any: An instance of the output_schema with the parsed results.
        """
        # We leverage the LLM's with_structured_output method to guarantee JSON output
        chain = self.prompt_template | self.llm.with_structured_output(output_schema)
        messages = state.get("messages", [])
        
        response = chain.invoke({"messages": messages, **kwargs})
        return response
