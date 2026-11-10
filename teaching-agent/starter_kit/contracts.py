"""所有跨模块契约。

规则：
1. 任何跨文件传递的数据，必须在这里有 Pydantic 模型；
2. 字段带 description 与长度约束，LLM 输出才可校验；
3. 改这里 = 改所有模块的接口，必须 review。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Level = Literal["小学", "初中", "高中", "大学低年级", "成人零基础"]
Difficulty = Literal["easy", "medium", "hard"]
QuestionKind = Literal["choice", "fill"]


class KpPack(BaseModel):
    """一个知识点的最小教学包：讲什么、例子、常见误解。"""

    model_config = ConfigDict(extra="forbid")

    kp_id: str = Field(..., description="形如 der.basic，必须来自 content.KP_PACKS")
    name: str = Field(..., description="中文名，给学生看")
    points: list[str] = Field(..., min_length=2, description="这一层必须覆盖的 2-4 个要点")
    example: str = Field(..., description="一个具体例子，不能是空话")
    misconceptions: list[str] = Field(default_factory=list, description="学生常见误解")


class TeachingTurn(BaseModel):
    """老师这一轮讲的内容。"""

    model_config = ConfigDict(extra="ignore")

    reply_markdown: str = Field(..., min_length=120, max_length=1600)
    core_idea: str = Field(..., min_length=8, max_length=120)
    check_question: str = Field(..., min_length=5, max_length=120)
    confidence: Literal["high", "medium", "low"] = "medium"

    @model_validator(mode="after")
    def question_mark(self):
        if not self.check_question.rstrip().endswith(("?", "？")):
            raise ValueError("check_question 必须以问号结尾")
        return self


class QuestionCard(BaseModel):
    """题卡：模型生成的内容，answer 可能是错的；判题要用独立答案键。"""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., min_length=2, max_length=40, description="题号，必须能在题库里找到")
    kind: QuestionKind
    stem: str = Field(..., min_length=8, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=4)
    answer: str = Field(..., min_length=1, max_length=80, description="模型给的答案，仅作展示/兜底")
    explanation: str = Field(..., min_length=10, max_length=300)
    tested_points: list[str] = Field(..., min_length=1, max_length=3)
    difficulty: Difficulty = "medium"
    source_quote: str = Field("", max_length=220)
    variant_of: str | None = Field(None, description="变式题指向的母题 id；不是变式就为 None")
    confidence: Literal["high", "medium", "low"] = "medium"

    @model_validator(mode="after")
    def shape(self):
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
    """讲练合一的单次结构化输出：一份讲义 + 2 道题（一原题 + 一变式）。"""

    model_config = ConfigDict(extra="ignore")

    teaching: TeachingTurn
    questions: list[QuestionCard] = Field(..., min_length=2, max_length=3)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("同一轮的题号不能重复")
        return self


class AnswerKey(BaseModel):
    """独立答案键：不是模型生成的，判题只认它。"""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    answer: str
    kind: QuestionKind
    explanation: str


class Judgement(BaseModel):
    """判题结果：必须可解释、可统计。"""

    model_config = ConfigDict(extra="forbid")

    correct: bool
    layer: Literal["choice", "text", "numeric", "sympy", "llm", "fallback"]
    reason: str
    correct_answer: str


class StudentKpState(BaseModel):
    """一个学生在一个知识点上的状态；跨会话，绝不进 checkpoint。"""

    model_config = ConfigDict(extra="forbid")

    student_id: str
    kp_id: str
    attempts: int = 0
    correct: int = 0
    independent_solves: int = 0
    variant_solves: int = 0
    mastery: float = Field(0.0, ge=0.0, le=1.0)
    last_seen: float = 0.0
    next_review_at: float = 0.0


class TraceEvent(BaseModel):
    """一行 JSONL trace。"""

    model_config = ConfigDict(extra="allow")

    trace_id: str
    kind: str
    ts: float
    session_id: str = ""
    node: str = ""
    latency_ms: int = 0
    tokens: int = 0
    ok: bool = True
    detail: str = ""
