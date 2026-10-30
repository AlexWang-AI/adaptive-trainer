from __future__ import annotations

import os
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from core.nodes import (
    auditor_node,
    correction_node,
    diagnostic_node,
    practice_node,
    teacher_node,
)
from core.state import DEFAULT_TARGET_SCORE, TrainerState


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


MAX_CYCLES = _env_int("MAX_CYCLES", 15)


def audit_router(state: TrainerState) -> Literal["teacher", "practice", "end"]:
    target_score = _as_int(state.get("target_score"), DEFAULT_TARGET_SCORE)
    current_score = _as_int(state.get("current_score"), 0)

    if current_score >= target_score:
        return "end"
    if _as_int(state.get("iteration_count"), 0) >= MAX_CYCLES:
        return "end"
    if state.get("next_agent") == "practice":
        return "practice"
    return "teacher"


def build_graph(checkpointer: Any | None = None) -> CompiledStateGraph:
    builder = StateGraph(TrainerState)

    builder.add_node("diagnostic", diagnostic_node)
    builder.add_node("teacher", teacher_node)
    builder.add_node("practice", practice_node)
    builder.add_node("correction", correction_node)
    builder.add_node("auditor", auditor_node)

    builder.add_edge(START, "diagnostic")
    builder.add_edge("diagnostic", "teacher")
    builder.add_edge("teacher", "practice")
    builder.add_edge("practice", "correction")
    builder.add_edge("correction", "auditor")
    builder.add_conditional_edges(
        "auditor",
        audit_router,
        {
            "teacher": "teacher",
            "practice": "practice",
            "end": END,
        },
    )

    if checkpointer is None:
        checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


app = build_graph()

__all__ = ["app", "build_graph", "audit_router", "MAX_CYCLES"]


if __name__ == "__main__":
    print(app.get_graph().draw_mermaid())
