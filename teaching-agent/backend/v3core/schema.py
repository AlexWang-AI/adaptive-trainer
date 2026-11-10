from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Level = Literal["小学", "初中", "高中", "大学低年级", "成人零基础"]
Difficulty = Literal["easy", "medium", "hard"]


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
    # 显式学生模型压成的一句话提示（跨会话掌握度 / 错题），由 graph 注入
    learner_note: str = Field("", max_length=400)
    # 教材依据：《张宇基础30讲》里这个知识点的考纲 + 要点 + 结论 + 例题 + 题型，
    # 由 curriculum.textbook_block() 生成；讲课以它为准，不由模型自由发挥
    textbook_block: str = Field("", max_length=1400)
    textbook_ref: str = Field("", max_length=200, description="教材出处（讲/分支/知识点）")
    # 该知识点的教材题型名（逐字），用来校验/回填题卡上的 type_name
    type_names: list[str] = Field(default_factory=list, max_length=6)
    # 知识点内部的子项（例如「七种未定式」里的「0/0 型」）：讲义与题目只围绕它展开
    focus: str = Field("", max_length=200)


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


class QuestionCard(BaseModel):
    """题卡：与讲义同一次调用生成，不再单独跑一个出题节点。"""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["choice", "fill"]
    stem: str = Field(..., min_length=8, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=4)
    answer: str = Field(..., min_length=1, max_length=80)
    explanation: str = Field(..., min_length=10, max_length=300)
    tested_points: list[str] = Field(..., min_length=1, max_length=3)
    difficulty: Difficulty
    why_this_question: str = Field(..., min_length=10, max_length=220)
    source_quote: str = Field("", max_length=220)
    # 这道题落在教材题库的哪个题型上（出题门的验收字段，来自 curriculum types[].name）
    type_name: str = Field("", max_length=40)
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
    def validate_shape(self):
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
        return self


class LessonPayload(BaseModel):
    """讲练合一的单次结构化输出：一份讲义 + 3 张题卡。"""

    model_config = ConfigDict(extra="ignore")

    teaching: TeachingTurn
    questions: list[QuestionCard] = Field(..., min_length=3, max_length=3)

    @model_validator(mode="after")
    def cards_should_differ(self):
        stems = {q.stem for q in self.questions}
        if len(stems) < len(self.questions):
            raise ValueError("3 道题不能重复")
        return self

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump()
