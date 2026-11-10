from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Level = Literal["小学", "初中", "高中", "大学低年级", "成人零基础"]


class HistoryTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Literal["student", "teacher"]
    content: str = Field(..., min_length=1, max_length=3000)


class TeachingRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic: str = Field(..., min_length=2, max_length=500, description="想学的知识模块/问题")
    level: Level = "初中"
    subject: str = Field("数学", min_length=1, max_length=20)
    prior_knowledge: str = Field("", max_length=300, description="学生已经会什么")
    misconceptions: str = Field("", max_length=300, description="学生常见的误解")
    student_message: str = Field("", max_length=1000, description="学生这一轮说的话；第一轮可为空")
    history: list[HistoryTurn] = Field(default_factory=list, max_length=20)
    tone: str = Field("耐心、具体、不居高临下", max_length=60)
    max_reply_chars: int = Field(900, ge=300, le=1500)


class JargonItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    term: str = Field(..., min_length=1, max_length=20)
    plain_explanation: str = Field(..., min_length=5, max_length=120)


class TeachingTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reply_markdown: str = Field(..., min_length=150, max_length=1600)
    core_idea: str = Field(..., min_length=8, max_length=120)
    order_rationale: str = Field(..., min_length=10, max_length=300)
    analogy: str = Field("", max_length=300)
    example: str = Field("", max_length=400)
    jargon: list[JargonItem] = Field(default_factory=list, max_length=10)
    check_question: str = Field(..., min_length=5, max_length=120)
    invite_question: str = Field(..., min_length=5, max_length=150)
    next_step: str = Field(..., min_length=5, max_length=150)
    assumptions: list[str] = Field(default_factory=list, max_length=3)
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("core_idea", "order_rationale", "check_question", "invite_question", "next_step")
    @classmethod
    def normalize_single_line(cls, value: str) -> str:
        return " ".join(str(value).split())

    @field_validator("check_question")
    @classmethod
    def question_must_end_with_mark(cls, value: str) -> str:
        if not value.rstrip().endswith(("?", "？")):
            raise ValueError("check_question 必须以问号结尾")
        return value

    @field_validator("reply_markdown")
    @classmethod
    def reply_not_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("reply_markdown 不能为空")
        return text
