from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Final, List, TypedDict

from pydantic import BaseModel, ConfigDict, Field


MIN_SCORE: Final[int] = 0
MAX_SCORE: Final[int] = 100
DEFAULT_CURRENT_SCORE: Final[int] = 0
DEFAULT_TARGET_SCORE: Final[int] = 90


class MistakeEntry(BaseModel):
    """A single mistake-book entry capturing a flawed mental model."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
    )

    concept: str = Field(
        ...,
        min_length=1,
        description="Concept involved in the mistake.",
    )
    user_flaw: str = Field(
        ...,
        min_length=1,
        description="The learner's incorrect reasoning or mental model.",
    )
    key_insight: str = Field(
        ...,
        min_length=1,
        description="The correct underlying understanding that replaces the flaw.",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        min_length=1,
        description="ISO-8601 UTC timestamp recorded when the entry is created.",
    )


class TrainerState(TypedDict):
    """Shared LangGraph state for the adaptive training loop."""

    topic: str
    benchmark_score: int
    benchmark_paper: Dict[str, Any]
    current_score: int
    target_score: int
    knowledge_gaps: List[str]
    learning_plan: str
    dialogue_history: List[Dict[str, Any]]
    current_task: str
    human_response: str
    mistake_book: List[Dict[str, Any]]
    next_agent: str
    iteration_count: int
    audit_feedback: str


def create_initial_state(
    topic: str,
    target_score: int = DEFAULT_TARGET_SCORE,
) -> TrainerState:
    """Build a complete initial state with validated defaults."""
    normalized_topic = topic.strip()
    if not normalized_topic:
        raise ValueError("topic must be a non-empty string")
    if not MIN_SCORE <= target_score <= MAX_SCORE:
        raise ValueError(
            f"target_score must be between {MIN_SCORE} and {MAX_SCORE}, "
            f"got {target_score}"
        )

    state: TrainerState = {
        "topic": normalized_topic,
        "benchmark_score": 0,
        "benchmark_paper": {},
        "current_score": DEFAULT_CURRENT_SCORE,
        "target_score": target_score,
        "knowledge_gaps": [],
        "learning_plan": "",
        "dialogue_history": [],
        "current_task": "",
        "human_response": "",
        "mistake_book": [],
        "next_agent": "diagnostic",
        "iteration_count": 0,
        "audit_feedback": "",
    }
    return state
