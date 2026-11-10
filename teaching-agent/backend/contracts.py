"""跨 Agent 共享契约（唯一接口层）。

规则：
1. 任何 agent 之间传递的信息，必须在这里有类型。禁止传自由文本 dict。
2. 改这个文件 = 改所有 agent 的接口，必须 review。
3. 每个 agent 自己的输入/输出模型放在 `agents/<name>/schema.py`，但只能组合这里的类型。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# 课程与知识点
# --------------------------------------------------------------------------
class Kp(BaseModel):
    """一个知识点（最小教学单元）。id 全局唯一，禁止 agent 自己发明。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="形如 lim.lhopital，科目前缀.章节.要点")
    name: str = Field(..., description="中文名，给学生看的")
    chapter: str = Field(..., description="所属章节 id，与 curriculum 一致")
    exam_weight: int = Field(3, ge=1, le=5, description="考频 1-5")
    prerequisites: list[str] = Field(default_factory=list, description="前置知识点 id")
    textbook_ref: str = Field("", description="张宇基础30讲 页码/讲次，OCR 校准后填")


class KpState(BaseModel):
    """单个知识点的掌握状态（跨会话持久化，进 Store/DB，绝不进 checkpoint）。"""

    model_config = ConfigDict(extra="forbid")

    kp_id: str
    mastery: float = Field(0.0, ge=0.0, le=1.0)
    attempts: int = 0
    independent_solves: int = 0          # 独立做对的原题数
    variant_solves: int = 0              # 独立做对的变式题数
    last_error: str = ""                 # 最近一次错的根因，一句话
    last_seen: str = ""


class StudentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str
    target_score: int = Field(90, ge=0, le=150)
    level: str = "大学低年级"
    kp: dict[str, KpState] = Field(default_factory=dict)
    # 刻意不放对话历史：历史属于 thread，不属于画像

    def digest(self, limit: int = 400) -> str:
        """压缩成给 LLM 看的一段话，避免把整个 dict 塞进 prompt。"""
        if not self.kp:
            return "（暂无历史，视为零基础）"
        weak = sorted(
            (s for s in self.kp.values() if s.mastery < 0.6),
            key=lambda s: s.mastery,
        )[:8]
        if not weak:
            return f"目标 {self.target_score} 分；已无明显薄弱点。"
        items = "；".join(f"{s.kp_id} 掌握度 {s.mastery:.0%}" for s in weak)
        return f"目标 {self.target_score} 分；薄弱点：{items}"[:limit]


# --------------------------------------------------------------------------
# 掌握标准（全项目唯一口径）
# --------------------------------------------------------------------------
class MasteryRule(BaseModel):
    """一个知识点算不算「掌握」，只认这一条。"""

    model_config = ConfigDict(extra="forbid")

    needs_integrated: bool = Field(
        True, description="是否需要做对该知识点的综合题"
    )
    min_independent: int = Field(2, ge=1, description="独立做对原题/教辅题的最少题数")
    min_variant: int = Field(1, ge=1, description="独立做对同构变式题的最少题数")
    time_limit_min: int = Field(20, ge=5, description="单次验收时限（分钟）")
    pass_rule: str = Field(
        "独立做出 ≥2 道教辅原题 + ≥1 道同构变式，且步骤无卡顿、无提示",
        description="给学生看的一句话验收规则",
    )


# --------------------------------------------------------------------------
# 错题本（负分支自动归档到这里）
# --------------------------------------------------------------------------
class MistakeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["gap", "misconception", "question", "careless"]
    kp_id: str = ""
    summary: str = Field(..., max_length=120, description="一句话摘要")
    root_cause: str = Field("", max_length=200, description="认知层面的原因，不是「粗心」")
    correct_model: str = Field("", max_length=200, description="应该建立的正确心智模型")
    evidence: str = Field("", max_length=200, description="学生原话/原题摘录")
    created_at: str = Field(default_factory=now_iso)


# --------------------------------------------------------------------------
# Agent 元信息（给 UI、给组员、给评测用）
# --------------------------------------------------------------------------
class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    role: str
    owner: str = ""
    version: str = "0.1.0"
    input_model: str = ""
    output_model: str = ""
    memory: Literal["none", "session", "long_term"] = "none"
    deterministic: bool = False
    notes: str = ""


class AgentManifest(BaseModel):
    agents: list[AgentSpec] = Field(default_factory=list)
