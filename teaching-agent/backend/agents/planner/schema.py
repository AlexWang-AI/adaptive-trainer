"""路线规划 agent 的输入/输出契约。

角色：总指挥（锚点）。它不讲课、不出题，只回答三件事：
  1) 先学什么、后学什么（单元顺序）
  2) 每个单元「学到什么程度算过」（退出测试）
  3) 一共多少轮、大概多久（可量化进度）
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExitTest(BaseModel):
    """一个单元过不过，只看这三条。缺一条就不算验收通过。"""

    model_config = ConfigDict(extra="forbid")

    must_solve: list[str] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="必须独立做出的教辅/原题范围，如「第1讲 例题1-6 全部独立完成」",
    )
    variant_rule: str = Field(
        ...,
        min_length=10,
        max_length=120,
        description="同构变式题要求：换数字/换函数形态，能独立做出几道",
    )
    pass_rule: str = Field(
        ...,
        min_length=10,
        max_length=150,
        description="一句话判定，必须同时包含「独立」「变式」两个词",
    )


class Unit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^U\d{2}$", description="U01, U02 ...")
    title: str = Field(..., min_length=2, max_length=40)
    kp_ids: list[str] = Field(..., min_length=1, max_length=6, description="必须来自白名单")
    order: int = Field(..., ge=1, le=40)
    est_sessions: int = Field(..., ge=1, le=4, description="每 session 约 40 分钟")
    target_mastery: float = Field(0.9, ge=0.5, le=1.0)
    exit_test: ExitTest
    common_pitfalls: list[str] = Field(default_factory=list, max_length=4)


class StudyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(..., min_length=4, max_length=100)
    textbook: str = Field(..., min_length=2, max_length=40)
    scope: list[str] = Field(..., min_length=1, description="回显本次范围，kp id 或章节 id")
    units: list[Unit] = Field(..., min_length=1, max_length=40)
    total_sessions: int = Field(..., ge=1, le=120, description="必须等于各单元 est_sessions 之和")
    verification_policy: str = Field(
        ...,
        min_length=10,
        max_length=200,
        description="全局验收口径：独立做对 + 变式做对 才算掌握",
    )
    risks: list[str] = Field(default_factory=list, max_length=4)


class PlannerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(..., min_length=4, max_length=100)
    scope: list[str] = Field(..., min_length=1, description="章节 id 或 kp id，如 ['lim'] 或 ['lim.lhopital']")
    days: int = Field(14, ge=1, le=180)
    hours_per_day: float = Field(2.0, ge=0.5, le=12)
    level: str = "大学低年级"
    textbook: str = "张宇基础30讲（高数）"
    student_id: str = ""
    profile_digest: str = Field("", max_length=400)
    style: Literal["systematic", "crash", "weakness_first"] = "systematic"
