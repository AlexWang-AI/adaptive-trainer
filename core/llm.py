from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, List, Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL_NAME = "deepseek-flash"
PLACEHOLDER_API_KEY = "your_deepseek_or_openai_api_key_here"


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        parts: List[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


class _StructuredOutput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_text_fields(cls, value: Any, info: ValidationInfo) -> Any:
        field = cls.model_fields.get(info.field_name)
        if field is not None and field.annotation is str:
            return _stringify(value)
        return value


class DiagnosticOutput(_StructuredOutput):
    benchmark_score: int = Field(
        ge=0,
        le=100,
        description="Initial mastery score from 0 to 100.",
    )
    knowledge_gaps: List[str] = Field(
        min_length=1,
        description="Priority-ordered list of core knowledge gaps.",
    )
    learning_plan: str = Field(
        min_length=1,
        description="Actionable plan describing what to learn and how to verify it.",
    )
    first_question: str = Field(
        min_length=1,
        description="The first diagnostic question presented to the learner.",
    )

    @field_validator("knowledge_gaps", mode="before")
    @classmethod
    def _coerce_knowledge_gaps(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = re.split(r"[\n;；、]+", value)
        elif isinstance(value, (list, tuple)):
            items = list(value)
        else:
            items = [value]

        cleaned: List[str] = []
        for item in items:
            text = _stringify(item).strip()
            if text:
                cleaned.append(text)
        return cleaned


class DiagnosticQuestion(_StructuredOutput):
    id: int = Field(ge=1, description="Question number, starting at 1.")
    question_type: Literal["single_choice", "blank"] = Field(
        description="Objective question type: single_choice or blank."
    )
    content: str = Field(
        min_length=1,
        description="Question stem. Math must use KaTeX delimiters like $x^2$.",
    )
    options: List[str] = Field(
        default_factory=list,
        description="Four options for single_choice; empty for blank.",
    )
    target_concept: str = Field(
        min_length=1,
        description="The core concept assessed by this question.",
    )
    weight: int = Field(
        ge=1,
        le=100,
        description="Question weight; standardized to 20/25/30/25 by the system.",
    )
    standard_answer: str = Field(
        min_length=1,
        description="A/B/C/D for single_choice; exact expression for blank.",
    )
    misconception_trap: str = Field(
        min_length=1,
        description="The common wrong mental model targeted by this question.",
    )

    @field_validator("question_type", mode="before")
    @classmethod
    def _normalize_question_type(cls, value: Any) -> str:
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if text in {
            "single_choice",
            "singlechoice",
            "choice",
            "single",
            "单选题",
            "单选",
        }:
            return "single_choice"
        return "blank"

    @field_validator("options", mode="before")
    @classmethod
    def _normalize_options(cls, value: Any) -> List[str]:
        if isinstance(value, dict):
            return [f"{key}. {val}" for key, val in value.items()]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value]
        return []

    @model_validator(mode="after")
    def _validate_options(self) -> "DiagnosticQuestion":
        if self.question_type == "single_choice" and len(self.options) != 4:
            raise ValueError("single_choice questions must have exactly 4 options")
        return self


class DiagnosticPaperOutput(_StructuredOutput):
    title: str = Field(
        min_length=1,
        description="Title of the standardized diagnostic paper.",
    )
    total_score: int = Field(
        default=100,
        ge=1,
        le=100,
        description="Total score; standardized to 100 by the system.",
    )
    questions: List[DiagnosticQuestion] = Field(
        min_length=4,
        max_length=4,
        description="Exactly four gradient questions.",
    )

    @model_validator(mode="after")
    def _validate_type_mix(self) -> "DiagnosticPaperOutput":
        types = [question.question_type for question in self.questions]
        if "single_choice" not in types:
            raise ValueError("diagnostic paper must contain at least one single_choice")
        if "blank" not in types:
            raise ValueError("diagnostic paper must contain at least one blank")
        return self


class AnswerEquivalenceOutput(_StructuredOutput):
    is_equivalent: bool = Field(
        description="Whether the learner's answer is mathematically equivalent."
    )
    reason: str = Field(
        default="",
        description="One short sentence explaining the judgment.",
    )


class TeacherOutput(_StructuredOutput):
    instruction_response: str = Field(
        min_length=1,
        description="Socratic feedback that exposes gaps without revealing the final answer.",
    )
    question_to_human: str = Field(
        min_length=1,
        description="One probing or hinting question that forces the learner to reason.",
    )


class PracticeOutput(_StructuredOutput):
    practice_question: str = Field(
        min_length=1,
        description="One concept-trap variant question for the current knowledge gap.",
    )
    hint: str = Field(
        min_length=1,
        description="A directional hint that does not reveal the answer.",
    )


class CorrectionOutput(_StructuredOutput):
    is_correct: bool = Field(
        description="Whether the learner's answer is fundamentally correct.",
    )
    user_flaw: str = Field(
        default="",
        description="The learner's flawed reasoning; empty when the answer is correct.",
    )
    key_insight: str = Field(
        default="",
        description="The correct underlying mental model; empty when the answer is correct.",
    )
    feedback: str = Field(
        min_length=1,
        description="Specific, actionable correction feedback.",
    )


class AuditOutput(_StructuredOutput):
    new_score: int = Field(
        ge=0,
        le=100,
        description="Re-audited overall mastery score from 0 to 100.",
    )
    audit_feedback: str = Field(
        min_length=1,
        description="Evidence-based audit conclusion and next-step instruction.",
    )
    should_pass: bool = Field(
        description="Whether the learner should pass under the hard 90-point gate.",
    )
    decision: Literal["pass", "re_teach", "re_practice"] = Field(
        description="Routing decision for the next training stage.",
    )

    @field_validator("decision", mode="before")
    @classmethod
    def _normalize_decision(cls, value: Any) -> str:
        text = str(value).strip().lower()
        aliases = {
            "pass": "pass",
            "通过": "pass",
            "结业": "pass",
            "re_teach": "re_teach",
            "reteach": "re_teach",
            "re-teach": "re_teach",
            "重教": "re_teach",
            "打回重学": "re_teach",
            "re_practice": "re_practice",
            "repractice": "re_practice",
            "re-practice": "re_practice",
            "重练": "re_practice",
            "打回练习": "re_practice",
        }
        if text in aliases:
            return aliases[text]
        if "pass" in text and "practice" not in text and "teach" not in text:
            return "pass"
        if "practice" in text:
            return "re_practice"
        if "teach" in text:
            return "re_teach"
        return "re_teach"


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """Build a ChatOpenAI client compatible with DeepSeek and OpenAI endpoints."""
    if not 0 <= temperature <= 2:
        raise ValueError(f"temperature must be between 0 and 2, got {temperature}")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == PLACEHOLDER_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. "
            f"Copy {PROJECT_ROOT / '.env.example'} to {PROJECT_ROOT / '.env'} "
            "and set a real API key."
        )

    base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model_name = os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        timeout=60,
        max_retries=3,
    )


__all__ = [
    "DiagnosticOutput",
    "DiagnosticQuestion",
    "DiagnosticPaperOutput",
    "AnswerEquivalenceOutput",
    "TeacherOutput",
    "PracticeOutput",
    "CorrectionOutput",
    "AuditOutput",
    "get_llm",
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL_NAME",
    "PLACEHOLDER_API_KEY",
]
