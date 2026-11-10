"""路线规划 agent 的四个版本 prompt。

四版共用同一套 schema 和同一套确定性 checks，只在**策略**上不同：
  V1 一次性直出（基线）
  V2 两段式：先排骨架，再补验收细节
  V3 白名单强约束（禁止发明知识点）+ 修复环
  V4 白名单 + 教研自评（先挑自己的毛病，再改一遍）
"""

from __future__ import annotations

import json

from curriculum import KP_TABLE, chapter_of, kps_in_scope, render_kp_table, whitelist_for_scope
from .schema import PlannerRequest

JSON_SHAPE = """{
  "goal": "……",
  "textbook": "张宇基础30讲（高数）",
  "scope": ["lim"],
  "units": [
    {
      "id": "U01",
      "title": "……",
      "kp_ids": ["lim.definition"],
      "order": 1,
      "est_sessions": 2,
      "target_mastery": 0.9,
      "exit_test": {
        "must_solve": ["第1讲 例题1-6 全部独立完成"],
        "variant_rule": "换数字与函数形态的同构变式题，独立做出 1 道",
        "pass_rule": "独立做出 ≥2 道原题 + 1 道变式，且步骤无卡顿"
      },
      "common_pitfalls": ["……"]
    }
  ],
  "total_sessions": 2,
  "verification_policy": "每个单元必须独立做对原题并独立做对同构变式，才算掌握",
  "risks": ["……"]
}"""

COMMON_RULES = """硬性要求（违反任何一条都会被机器判错）：
1. 只输出 JSON，不要任何解释文字、不要 markdown 代码块。
2. goal 不超过 100 个汉字，一行说完，不要写长句子。
3. 一个 session 约 40 分钟；est_sessions 只能是 1~4 的整数。
4. total_sessions 必须等于所有单元 est_sessions 之和（自己加一遍再输出）。
5. 每个单元的 pass_rule 必须同时出现「独立」和「变式」两个词。
6. 单元数 3~12 个；一个单元最多覆盖 6 个知识点。
7. 顺序必须满足前置关系：先修知识点必须排在本单元或更早的单元。
8. kp_ids 只能从给定白名单逐字复制；没有白名单时，格式为「章节前缀.英文要点」，如 lim.definition。"""


def _profile_block(request: PlannerRequest) -> str:
    return f"""学习目标：{request.goal}
学生水平：{request.level}
时间预算：{request.days} 天，每天 {request.hours_per_day} 小时
教材：{request.textbook}
学生画像：{request.profile_digest or "暂无历史，按零基础处理"}
范围（scope）：{request.scope}
节奏偏好：{request.style}"""


def _capacity(request: PlannerRequest) -> int:
    return int(request.days * request.hours_per_day * 60 // 40)


# --------------------------------------------------------------------------
# V1：一次性直出（用知识点中文名，不给 id 白名单）
# --------------------------------------------------------------------------
def v1_prompts(request: PlannerRequest) -> tuple[str, str]:
    scope_kps = kps_in_scope(request.scope)
    names = "\n".join(f"- {KP_TABLE[kp]['name']}（{chapter_of(kp)}）" for kp in scope_kps)
    system = (
        "你是考研数学教研组的课程规划老师，擅长把一大块内容拆成学生能逐周执行的计划。\n"
        + COMMON_RULES
    )
    user = f"""{_profile_block(request)}

本次要覆盖的知识点（按教材顺序）：
{names}

可用课时上限：约 {_capacity(request)} 个 session。

请给出完整学习计划，JSON 结构如下：
{JSON_SHAPE}

kp_ids 用「章节前缀.知识点英文名」的形式自己命名，例如 lim.definition。"""
    return system, user


# --------------------------------------------------------------------------
# V2：两段式
# --------------------------------------------------------------------------
def v2_stage1_prompts(request: PlannerRequest) -> tuple[str, str]:
    scope_kps = kps_in_scope(request.scope)
    table = render_kp_table(whitelist_for_scope(request.scope))
    system = "你是考研数学教研组的排课老师，只负责排顺序和分单元，先不写验收细节。"
    user = f"""{_profile_block(request)}

可排的知识点（格式：id | 名称 | 考频 | 前置）：
{table}

本次必须覆盖：{scope_kps}
课时上限：约 {_capacity(request)} 个 session。

把上面的知识点切成 3~12 个单元，只输出骨架：
{{"units":[{{"id":"U01","title":"……","kp_ids":["…"],"order":1,"est_sessions":2}}],"total_sessions":2}}"""
    return system, user


def v2_stage2_prompts(request: PlannerRequest, skeleton: dict) -> tuple[str, str]:
    system = (
        "你是考研数学教研组的备课老师，已经拿到单元骨架，现在给每个单元补验收标准。\n"
        + COMMON_RULES
    )
    user = f"""{_profile_block(request)}

已有单元骨架（顺序和课时已定，不要改 id/order/kp_ids/est_sessions）：
{json.dumps(skeleton, ensure_ascii=False)}

请为每个单元补上 exit_test（must_solve / variant_rule / pass_rule）、target_mastery、common_pitfalls，
并补齐 goal / textbook / scope / total_sessions / verification_policy / risks。

完整 JSON 结构：
{JSON_SHAPE}"""
    return system, user


# --------------------------------------------------------------------------
# V3：白名单强约束
# --------------------------------------------------------------------------
def v3_prompts(request: PlannerRequest) -> tuple[str, str]:
    whitelist = whitelist_for_scope(request.scope)
    table = render_kp_table(whitelist)
    system = (
        "你是考研数学教研组的课程规划老师。你只能使用给定的知识点 id，"
        "任何情况下都不允许发明新的 id。\n" + COMMON_RULES
    )
    user = f"""{_profile_block(request)}

**可用知识点白名单（只能从这里选，id 必须逐字复制）**：
{table}

必须覆盖的核心知识点（其余白名单项是前置，可按需选入）：{kps_in_scope(request.scope)}
课时上限：约 {_capacity(request)} 个 session。

请输出完整计划：
{JSON_SHAPE}"""
    return system, user


# --------------------------------------------------------------------------
# V4：V3 + 教研自评
# --------------------------------------------------------------------------
def v4_prompts(request: PlannerRequest) -> tuple[str, str]:
    return v3_prompts(request)


def v4_critique_prompts(
    request: PlannerRequest, plan_json: dict, issues: list[str] | None = None
) -> tuple[str, str]:
    whitelist = whitelist_for_scope(request.scope)
    system = "你是教研组长，负责在计划交付前挑毛病。只提可执行的修改意见，不要重写计划。"
    user = f"""{_profile_block(request)}

学生对完这份计划：
{json.dumps(plan_json, ensure_ascii=False)[:6000]}

已知的机器校验问题：{issues or "无"}

请从教研角度检查下面五点，指出具体问题（没有就说没有，不要编）：
1. 单元粒度：有没有「一次讲 5 个知识点」这种执行不了的单元？
2. 前置顺序：有没有该先讲却排到后面的？
3. 验收标准：pass_rule 能不能真的判出来（学生自己能不能对答案）？
4. 时间：{request.days} 天 × {request.hours_per_day} 小时是否排得下？
5. 覆盖：{kps_in_scope(request.scope)} 有没有漏？

输出 JSON：{{"issues":[{{"unit":"U03","problem":"……","fix":"……"}}]}}"""
    return system, user


def v4_revision_prompts(
    request: PlannerRequest, plan_json: dict, critiques: list[dict], issues: list[str] | None = None
) -> tuple[str, str]:
    system = (
        "你是考研数学教研组的课程规划老师，现在根据教研组长的意见修订计划。\n" + COMMON_RULES
    )
    user = f"""{_profile_block(request)}

原计划：
{json.dumps(plan_json, ensure_ascii=False)[:6000]}

教研组长意见：
{json.dumps(critiques, ensure_ascii=False)[:3000]}

机器校验问题：{issues or "无"}

输出修订后的**完整** JSON（结构与原计划一致）：
{JSON_SHAPE}"""
    return system, user
