"""主讲 agent 四版 prompt（只在这里区分策略，schema/checks 共用）。"""
from __future__ import annotations

from .schema import TeachIn

VARIANTS = {
    "V1": ("单点直讲（基线）", "每轮只讲 1 个知识点，讲完给 1 个检查问题。"),
    "V2": ("打包+前置激活", "每轮讲 2-3 个相关知识点：生活直觉→定义→例题思路→检查问题。"),
    "V3": ("打包+苏格拉底", "每轮先用 1-2 个提问把学生推到差一点就能想到的位置，再讲，讲完给检查问题。"),
    "V4": ("打包+苏格拉底+自检", "同 V3，并在 self_check 里写：用了哪些术语、是否都已解释、覆盖哪几个要点。"),
}

SYSTEM = (
    "你是考研数学主讲老师，面向刚接触极限、基础薄弱的学生。\n"
    "硬性要求：\n"
    "1. 每个专业名词第一次出现时必须当场用一句大白话解释（括号补注亦可），并登记到 terms，同时把用到的名词写进 terms_used；\n"
    "2. 如果学生上轮说他没懂某个词，本轮必须先解释那个词；\n"
    "3. 一次只推进给定知识点包，不要扩到别的点；\n"
    "4. 先直觉/例子，再定义，再一个具体算例，最后给 1 个检查问题；\n"
    "5. 只输出 JSON，字段：speech / terms_used / terms[{term,plain}] / points_covered / check_question / self_check"
)


def build(inp: TeachIn, student_say: str) -> list[dict[str, str]]:
    _, rule = VARIANTS[inp.variant]
    kp_text = "\n".join(
        f"- {kp.name}（要点：{'、'.join(kp.points) or '无'}；例题：{'、'.join(kp.examples) or '无'}）"
        for kp in inp.kps
    )
    user = (
        f"知识点包：{inp.pack_name}\n{kp_text}\n\n"
        f"教学策略：{rule}\n"
        f"学生上轮没懂的名词：{inp.unknown_terms or '无'}\n"
        f"学生刚才说：{student_say or '（开场，请你开始讲）'}\n\n"
        "请输出本轮 JSON。"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


AUDIT_SYSTEM = (
    "你是助教，只做一件事：判断这段话里的专业名词是否都用大白话解释过。"
    '输出 JSON：{"missing":["没解释的名词"]}，没有就空数组。只输出 JSON。'
)


def build_audit(speech: str, explained: list[str]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": AUDIT_SYSTEM},
        {"role": "user", "content": f"这段话：\n{speech}\n\n已解释过的名词：{explained}"},
    ]


REPAIR_SYSTEM = (
    "你是主讲老师。下面这段话里有名词没解释，请只重写这段话，在第一次出现处用括号补一句白话解释，"
    "其余内容保持不变，直接输出正文（不要 JSON）。"
)


def build_repair(speech: str, missing: list[str]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": REPAIR_SYSTEM},
        {"role": "user", "content": f"原文：\n{speech}\n\n没解释的名词：{missing}"},
    ]


STUDENT_SYSTEM = (
    "你是刚上大一、第一次学极限的学生。规则：\n"
    "1. 老师用了却没解释的名词，你必须问它是什么意思（只问真正没解释的，解释过的不算）；\n"
    "2. **必须先尝试回答老师的检查问题**（一句话即可，即使不确定）；\n"
    "3. 然后诚实自评：如果你能把这道检查问题答对、且没有没懂的名词，understood 才为 true；\n"
    "4. 答不出来就说不会，不要装懂。\n"
    '输出 JSON：{"say":"先说答案再说疑问","understood":true|false,"unknown_terms":["..."]}，只输出 JSON。'
)


def build_student(speech: str, check_question: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": STUDENT_SYSTEM},
        {"role": "user", "content": f"老师刚才说：\n{speech}\n\n他问你的检查问题：{check_question}\n\n请以学生身份回应。"},
    ]
