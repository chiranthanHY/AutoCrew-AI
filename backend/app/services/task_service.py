"""
services/task_service.py — High-Level Task Orchestration Service
-----------------------------------------------------------------
Interface between the FastAPI layer and the LangGraph workflow.

Handles:
  - Initialising AgentState with proper defaults
  - Running the graph with *streaming* support (node-level SSE events)
  - Wrapping the graph for non-streaming (blocking) invocation
  - Translating raw LangGraph stream events into structured SSE payloads
  - Thread-safe task execution via per-request thread_id (= task_id)
  - Checkpoint state retrieval for HITL and status polling

Stream event types emitted
--------------------------
  ``{"type": "node_start",  "node": "<name>"}``
  ``{"type": "node_update", "node": "<name>", "data": {...}}``
  ``{"type": "final",       "task_id": "...", "output": "...", "score": ...}``
  ``{"type": "error",       "task_id": "...", "message": "..."}``
  ``{"type": "hitl",        "task_id": "...", "draft": "...", "critique": "..."}``
"""

import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import HumanMessage

from app.graph.workflow import get_graph
from app.schemas.state import AgentState

logger = logging.getLogger(__name__)


# ===========================================================================
# State initialiser
# ===========================================================================


def _build_initial_state(task: str, task_id: str, enable_hitl: bool = False) -> AgentState:
    """
    Build a fully initialised AgentState for a new task run.

    All optional / accumulator fields are set to their zero-values here
    so downstream nodes never encounter KeyError.

    Args:
        task: Raw user task string.
        task_id: Unique run identifier (UUID string).
        enable_hitl: Whether human-in-the-loop review is enabled.

    Returns:
        AgentState dict ready to pass as ``graph.invoke()`` input.
    """
    return AgentState(
        task=task,
        task_id=task_id,
        messages=[HumanMessage(content=task)],
        plan=[],
        research_results=[],
        draft="",
        critique="",
        critique_score=0.0,
        human_feedback=None,
        awaiting_human=False,
        enable_hitl=enable_hitl,
        iteration=0,
        next="",
        final_output="",
        error=None,
        token_usage=[],
        memory_context=None,
    )


# ===========================================================================
# Streaming runner
# ===========================================================================
async def run_task_stream(
    task: str,
    task_id: Optional[str] = None,
    human_feedback: Optional[str] = None,
    enable_hitl: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Run the AutoCrew AI graph and yield SSE-formatted JSON strings.

    This is the primary entry point used by the FastAPI streaming endpoint.
    Each yielded string is a ``data: {...}\n\n`` SSE line that the browser
    or curl client receives in real time.

    Args:
        task: The user's task / prompt string.
        task_id: Optional existing task ID to resume (HITL use case).
            If None, a new UUID is generated.
        human_feedback: Optional human reviewer feedback to inject into
            a paused HITL graph before resuming.
        enable_hitl: Whether human-in-the-loop review is enabled.

    Yields:
        str: SSE-formatted JSON event strings.
    """
    task_id = task_id or str(uuid.uuid4())
    graph = get_graph()

    # LangGraph uses thread_id to identify and isolate checkpoint state
    config = {"configurable": {"thread_id": task_id}}

    logger.info("[TaskService] Starting stream | task_id=%s | enable_hitl=%s", task_id, enable_hitl)

    # Emit task start event
    yield _sse({"type": "task_start", "task_id": task_id, "task": task[:200]})

    # ------------------------------------------------------------------
    # Build the input: fresh state for new runs, partial update for HITL
    # ------------------------------------------------------------------
    if human_feedback is not None:
        # Resuming a HITL-paused graph: inject the feedback into the state
        graph_input = {"human_feedback": human_feedback, "awaiting_human": False}
        logger.info("[TaskService] Resuming with human feedback | task_id=%s", task_id)
    else:
        graph_input = _build_initial_state(task=task, task_id=task_id, enable_hitl=enable_hitl)

    try:
        # ------------------------------------------------------------------
        # Stream mode: "updates" yields one dict per node as it completes.
        # "values" yields the full accumulated state — too large.
        # ------------------------------------------------------------------
        async for chunk in graph.astream(graph_input, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                if node_name == "__interrupt__" or not hasattr(node_output, "items"):
                    logger.info("[TaskService] Interrupted or non-dict output from node: %s", node_name)
                    continue

                event = _format_node_event(node_name, node_output)
                logger.debug(
                    "[TaskService] Event from '%s': %s",
                    node_name,
                    str(event)[:200],
                )
                yield _sse(event)

        # ------------------------------------------------------------------
        # After streaming completes, fetch the final state for the summary
        # ------------------------------------------------------------------
        final_state = await graph.aget_state(config)
        if final_state and final_state.values:
            values = final_state.values
            is_hitl = "hitl" in final_state.next

            if is_hitl:
                yield _sse(
                    {
                        "type": "hitl",
                        "task_id": task_id,
                        "message": "Task paused for human review.",
                        "draft": values.get("draft", ""),
                        "critique": values.get("critique", ""),
                        "critique_score": values.get("critique_score", 0.0),
                    }
                )
            else:
                yield _sse(
                    {
                        "type": "final",
                        "task_id": task_id,
                        "output": values.get("final_output", ""),
                        "critique_score": values.get("critique_score", 0.0),
                        "iterations": values.get("iteration", 0),
                        "awaiting_human": False,
                        "token_usage": values.get("token_usage", []),
                        "memory_used": bool(values.get("memory_context")),
                    }
                )
        else:
            yield _sse(
                {"type": "final", "task_id": task_id, "output": "", "critique_score": 0.0}
            )

    except Exception as exc:
        logger.error("[TaskService] Streaming failed: %s", exc, exc_info=True)
        yield _sse({"type": "error", "task_id": task_id, "message": str(exc)})


# ===========================================================================
# Blocking runner (for testing / non-streaming endpoints)
# ===========================================================================


async def run_task(
    task: str,
    task_id: Optional[str] = None,
    enable_hitl: bool = False,
) -> Dict[str, Any]:
    """
    Run the AutoCrew AI graph synchronously and return the final state.

    Intended for simple integrations, admin endpoints, or test harnesses
    that don't need streaming.

    Args:
        task: The user's task string.
        task_id: Optional existing task ID; generates a new UUID if None.
        enable_hitl: Whether human-in-the-loop review is enabled.

    Returns:
        Dict with keys: task_id, final_output, critique_score, iterations, error.
    """
    task_id = task_id or str(uuid.uuid4())
    graph = get_graph()
    config = {"configurable": {"thread_id": task_id}}
    initial_state = _build_initial_state(task=task, task_id=task_id, enable_hitl=enable_hitl)

    logger.info("[TaskService] Blocking invoke | task_id=%s", task_id)

    try:
        final_state = await graph.ainvoke(initial_state, config=config)
        snapshot = await graph.aget_state(config)
        awaiting_human = "hitl" in snapshot.next if (snapshot and snapshot.next) else False
        return {
            "task_id": task_id,
            "final_output": final_state.get("final_output", ""),
            "critique_score": final_state.get("critique_score", 0.0),
            "iterations": final_state.get("iteration", 0),
            "plan": final_state.get("plan", []),
            "awaiting_human": awaiting_human,
            "error": final_state.get("error"),
        }
    except Exception as exc:
        logger.error("[TaskService] Blocking invoke failed: %s", exc, exc_info=True)
        return {
            "task_id": task_id,
            "final_output": "",
            "critique_score": 0.0,
            "iterations": 0,
            "plan": [],
            "awaiting_human": False,
            "error": str(exc),
        }


# ===========================================================================
# HITL: Fetch state for a paused task
# ===========================================================================


async def get_task_state(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the persisted LangGraph state for a given task_id.

    Used by the frontend to check whether a task is awaiting human review
    and to display the current draft.

    Args:
        task_id: The task UUID string.

    Returns:
        Dict with the current AgentState values, or None if not found.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": task_id}}
    try:
        snapshot = await graph.aget_state(config)
        if snapshot and snapshot.values:
            v = snapshot.values
            awaiting_human = "hitl" in snapshot.next if snapshot.next else False
            return {
                "task_id": task_id,
                "task": v.get("task", ""),
                "plan": v.get("plan", []),
                "draft": v.get("draft", ""),
                "critique": v.get("critique", ""),
                "critique_score": v.get("critique_score", 0.0),
                "iteration": v.get("iteration", 0),
                "awaiting_human": awaiting_human,
                "enable_hitl": v.get("enable_hitl", False),
                "token_usage": v.get("token_usage", []),
                "memory_context": v.get("memory_context"),
                "final_output": v.get("final_output", ""),
                "error": v.get("error"),
            }
    except Exception as exc:
        logger.error("[TaskService] get_task_state failed for %s: %s", task_id, exc)
    return None


async def list_task_history(task_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    List checkpoint history for a task (useful for debugging / time-travel).

    Args:
        task_id: The task UUID string.
        limit: Maximum number of checkpoints to return.

    Returns:
        List of checkpoint dicts sorted by creation time (newest first).
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": task_id}}
    checkpoints = []
    try:
        async for state in graph.aget_state_history(config):
            checkpoint = {
                "checkpoint_id": state.config.get("configurable", {}).get("checkpoint_id"),
                "next": list(state.next),
                "created_at": str(state.created_at) if hasattr(state, "created_at") else None,
                "iteration": state.values.get("iteration", 0),
                "critique_score": state.values.get("critique_score", 0.0),
            }
            checkpoints.append(checkpoint)
            if len(checkpoints) >= limit:
                break
    except Exception as exc:
        logger.error("[TaskService] list_task_history failed for %s: %s", task_id, exc)
    return checkpoints


# ===========================================================================
# Internal helpers
# ===========================================================================


def _format_node_event(node_name: str, node_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a raw LangGraph node update into a structured SSE event dict.

    Special handling:
    - ``messages`` lists are serialised to avoid sending huge objects.
    - ``draft`` and ``final_output`` are included verbatim for the UI.
    - All other scalar fields are passed through as-is.

    Args:
        node_name: Name of the LangGraph node that produced the update.
        node_output: Raw output dict from the node function.

    Returns:
        A JSON-serialisable event dict.
    """
    event: Dict[str, Any] = {"type": "node_update", "node": node_name}

    for key, value in node_output.items():
        if key == "messages":
            # Serialise message objects to dicts for JSON transport
            event[key] = [
                {
                    "role": getattr(m, "type", "unknown"),
                    "content": getattr(m, "content", str(m))[:500],
                }
                for m in (value or [])
            ]
        elif key == "plan" and isinstance(value, list):
            # Plans can be large; include them fully
            event[key] = value
        else:
            event[key] = value

    return event


def _sse(data: Dict[str, Any]) -> str:
    """
    Return a plain JSON string for a single SSE event.

    sse_starlette's EventSourceResponse automatically wraps each yielded
    string with  ``data: <value>\\r\\n\\r\\n``, so we must NOT add our own
    ``data:`` prefix here — doing so would produce the double-wrapped
    ``data: data: {...}`` that the browser/frontend cannot parse.

    Args:
        data: JSON-serialisable dict to send as the event payload.

    Returns:
        Plain JSON string (no SSE framing).
    """
    return json.dumps(data, default=str)
