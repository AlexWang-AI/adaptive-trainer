from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QuizQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal["choice", "fill"]
    stem: str = Field(..., min_length=8, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=4)
    answer: str = Field(..., min_length=1, max_length=80)
    explanation: str = Field(..., min_length=10, max_length=300)
    tested_points: list[str] = Field(..., min_length=1, max_length=3)
    difficulty: Literal["easy", "medium", "hard"]
    why_this_question: str = Field(..., min_length=10, max_length=220)
    source_quote: str = Field(..., min_length=5, max_length=220)
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("stem", "answer", "explanation", "why_this_question", "source_quote")
    @classmethod
    def normalize_single_line(cls, value: str) -> str:
        return " ".join(str(value).split())

    @field_validator("options")
    @classmethod
    def clean_options(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]

    @model_validator(mode="after")
    def validate_question_shape(self):
        if self.kind == "choice":
            if len(self.options) != 4:
                raise ValueError("选择题必须正好 4 个选项")
            if len(set(self.options)) != 4:
                raise ValueError("选择题选项不能重复")
            if self.answer.strip().upper() not in {"A", "B", "C", "D"}:
                raise ValueError("选择题 answer 必须是 A/B/C/D")
        else:
            if self.options:
                raise ValueError("填空题 options 必须为空数组")
            if not self.answer.strip():
                raise ValueError("填空题 answer 不能为空")
        return self
