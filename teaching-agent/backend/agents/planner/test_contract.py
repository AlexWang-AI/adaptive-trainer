"""路线规划 agent 的契约测试（离线，不打 API）。

跑法（backend/ 目录下）：python -m pytest agents/planner/test_contract.py -q
"""

from __future__ import annotations

import copy

import pytest

import curriculum
from agents.planner.checks import check_plan, evaluate_plan
from agents.planner.schema import PlannerRequest, StudyPlan

BASE_PLAN = {
    "goal": "两周把极限这一讲学扎实",
    "textbook": "张宇基础30讲（高数）",
    "scope": [
        "l01-b01-k01", "l01-b01-k02", "l01-b01-k03",
        "l01-b01-k04", "l01-b01-k05", "l01-b01-k06",
    ],
    "units": [
        {
            "id": "U01",
            "title": "极限四则运算规则",
            "kp_ids": ["l01-b01-k01"],
            "order": 1,
            "est_sessions": 2,
            "target_mastery": 0.9,
            "exit_test": {
                "must_solve": ["第1讲 例题1-3 全部独立完成"],
                "variant_rule": "换函数形态的同构变式题，独立做出 1 道",
                "pass_rule": "独立做出 2 道原题 + 1 道变式，步骤无卡顿",
            },
            "common_pitfalls": ["把极限存在当成函数值存在"],
        },
        {
            "id": "U02",
            "title": "洛必达与泰勒",
            "kp_ids": ["l01-b01-k02", "l01-b01-k03"],
            "order": 2,
            "est_sessions": 3,
            "target_mastery": 0.9,
            "exit_test": {
                "must_solve": ["第1讲 例题4-6 全部独立完成"],
                "variant_rule": "换等价无穷小替换形式的变式题，独立做出 1 道",
                "pass_rule": "独立完成原题并按条件判断后独立完成变式",
            },
            "common_pitfalls": ["不验证洛必达使用条件"],
        },
        {
            "id": "U03",
            "title": "无穷小运算与展开原则",
            "kp_ids": ["l01-b01-k04", "l01-b01-k05"],
            "order": 3,
            "est_sessions": 2,
            "target_mastery": 0.9,
            "exit_test": {
                "must_solve": ["第1讲 例题7-9 全部独立完成"],
                "variant_rule": "换展开阶数的变式题，独立做出 1 道",
                "pass_rule": "独立做出原题并独立做出变式，能说清阶数怎么定",
            },
            "common_pitfalls": ["展开阶数取不够"],
        },
        {
            "id": "U04",
            "title": "两个重要极限收尾",
            "kp_ids": ["l01-b01-k06"],
            "order": 4,
            "est_sessions": 1,
            "target_mastery": 0.9,
            "exit_test": {
                "must_solve": ["第1讲 例题10 独立完成"],
                "variant_rule": "含参数的分式函数变式，独立做出 1 道",
                "pass_rule": "独立求出两类重要极限并独立完成变式",
            },
            "common_pitfalls": ["漏掉 1^∞ 型"],
        },
    ],
    "total_sessions": 8,
    "verification_policy": "每个单元必须独立做对原题并独立做对同构变式，才算掌握",
    "risks": ["时间紧时容易只刷题不理解"],
}


def _req(scope=None, days=14, hours=2):
    return PlannerRequest(
        goal="两周把极限这一讲学扎实",
        scope=scope or list(BASE_PLAN["scope"]),
        days=days,
        hours_per_day=hours,
    )


def _plan(mutate=None):
    payload = copy.deepcopy(BASE_PLAN)
    if mutate:
        mutate(payload)
    return StudyPlan.model_validate(payload)


def test_curriculum_ids_are_consistent():
    """所有前置 id 必须真实存在，否则曲线救国等于没做。"""
    ids = set(curriculum.all_kp_ids())
    for kp_id, meta in curriculum.KP_TABLE.items():
        for pre in meta["prerequisites"]:
            assert pre in ids, f"{kp_id} 的前置 {pre} 不存在"


def test_happy_path_passes():
    assert check_plan(_plan(), _req(), curriculum.whitelist_for_scope(list(BASE_PLAN["scope"]))) == []
    metrics = evaluate_plan(_plan(), _req())
    assert metrics["coverage"] == 1.0
    assert metrics["hallucination"] == 0.0
    assert metrics["score"] >= 0.9


def test_invented_kp_is_caught():
    def mutate(p):
        p["units"][0]["kp_ids"] = ["l01-b01-k99"]

    issues = check_plan(_plan(mutate), _req(), curriculum.whitelist_for_scope(list(BASE_PLAN["scope"])))
    assert any("发明" in issue for issue in issues)


def test_missing_scope_is_caught():
    def mutate(p):
        p["units"] = p["units"][:3]  # 少了 l01-b01-k06
        p["total_sessions"] = 7

    issues = check_plan(_plan(mutate), _req(), curriculum.whitelist_for_scope(list(BASE_PLAN["scope"])))
    assert any(("覆盖率" in issue) or ("必须覆盖" in issue) for issue in issues)


def test_order_violation_is_caught():
    def mutate(p):
        # 把 l01-b01-k02（前置 k01）挪到第一单元，k01 放到第二单元
        p["units"][0]["kp_ids"] = ["l01-b01-k02"]
        p["units"][1]["kp_ids"] = ["l01-b01-k01", "l01-b01-k03"]

    issues = check_plan(_plan(mutate), _req(), curriculum.whitelist_for_scope(list(BASE_PLAN["scope"])))
    assert any("前置" in issue for issue in issues)


def test_session_sum_mismatch_is_caught():
    def mutate(p):
        p["total_sessions"] = 99

    issues = check_plan(_plan(mutate), _req(), curriculum.whitelist_for_scope(list(BASE_PLAN["scope"])))
    assert any("total_sessions" in issue for issue in issues)


def test_over_capacity_is_caught():
    issues = check_plan(
        _plan(), _req(days=1, hours=1), curriculum.whitelist_for_scope(list(BASE_PLAN["scope"]))
    )
    assert any("产能" in issue for issue in issues)


def test_pass_rule_must_mention_independent_and_variant():
    def mutate(p):
        p["units"][0]["exit_test"]["pass_rule"] = "做对就行，学生自己能对答案"

    issues = check_plan(_plan(mutate), _req(), curriculum.whitelist_for_scope(list(BASE_PLAN["scope"])))
    assert any("独立" in issue and "变式" in issue for issue in issues)


def test_schema_rejects_bad_unit_id():
    def mutate(p):
        p["units"][0]["id"] = "unit-1"

    with pytest.raises(Exception):
        _plan(mutate)


