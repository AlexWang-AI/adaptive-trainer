"""主讲 agent 契约（结构化输出，禁止自由文本）。"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class KpIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=40)
    points: list[str] = Field(default_factory=list, max_length=8, description="L3 要点")
    examples: list[str] = Field(default_factory=list, max_length=6)


class TeachIn(BaseModel):
    pack_name: str
    kps: list[KpIn]
    variant: Literal["V1", "V2", "V3", "V4", "V5"] = "V4"
    unknown_terms: list[str] = Field(default_factory=list, description="学生上轮没懂的词")


class Term(BaseModel):
    term: str = Field(..., min_length=1, max_length=20)
    plain: str = Field(..., min_length=2, max_length=120)


class TeachOut(BaseModel):
    speech: str = Field(..., min_length=80, max_length=2000)
    terms_used: list[str] = Field(default_factory=list, max_length=20, description="本轮用到的专业名词")
    terms: list[Term] = Field(default_factory=list, max_length=20, description="已解释的名词")
    points_covered: list[str] = Field(default_factory=list, max_length=8)
    check_question: str = Field(..., min_length=5, max_length=120)
    self_check: str = Field("", max_length=200)


class AuditOut(BaseModel):
    missing: list[str] = Field(default_factory=list, description="用了但没解释的名词")


class StudentOut(BaseModel):
    say: str = Field(..., min_length=1, max_length=300)
    understood: bool = False
    unknown_terms: list[str] = Field(default_factory=list, max_length=10)
