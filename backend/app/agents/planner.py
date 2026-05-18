from typing import Dict, Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from app.agents.base import BaseAgent
from app.schemas.state import Plan

PLANNER_SYSTEM_PROMPT = """You are a highly capable Planner Agent for AutoCrew AI.
Your objective is to take a high-level task and break it down into a sequence of detailed, actionable steps.
For each step, assign the most appropriate agent role (e.g., Researcher, Executor, Writer, Critic).
Ensure the plan is comprehensive, logically ordered, and designed to achieve the user's overarching goal.
"""

class PlannerAgent(BaseAgent):
    """
    Planner Agent responsible for breaking down high-level tasks into detailed execution plans.
    """
    def __init__(self, llm: BaseChatModel):
        super().__init__(llm=llm, system_prompt=PLANNER_SYSTEM_PROMPT)
        
    def invoke(self, state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Generates a structured plan based on the current task and conversation history.
        Overrides the standard invoke to utilize structured output returning the Plan schema.
        
        Returns:
            Dict[str, Any]: State update dictionary containing the generated "plan".
        """
        messages = state.get("messages", []).copy()
        task = state.get("task", "")
        
        # Explicitly inject the task as a prompt if provided
        if task:
            task_msg = f"Please create a detailed plan for the following task:\n\n{task}"
            messages.append(HumanMessage(content=task_msg))
            
        # Use structured output to enforce the Plan schema format
        structured_plan: Plan = self.invoke_structured(
            state={"messages": messages}, 
            output_schema=Plan,
            **kwargs
        )
        
        # Convert the Pydantic plan back to a list of dicts to match the state schema
        plan_dicts = [step.model_dump() for step in structured_plan.steps]
        
        return {
            "plan": plan_dicts
        }
