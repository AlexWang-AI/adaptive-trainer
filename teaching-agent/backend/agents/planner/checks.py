"""路线规划 agent 的确定性校验与量化打分。

这些检查是「objective」，不依赖另一个 LLM 的判断 —— 所以四版对比才是公平的。
"""

from __future__ import annotations

from curriculum import KP_TABLE, kps_in_scope, order_index, whitelist_for_scope
from .schema import PlannerRequest, StudyPlan


def check_plan(plan: StudyPlan, request: PlannerRequest, whitelist: list[str]) -> list[str]:
    """返回问题清单；空列表 = 通过。会被 runner 回灌给模型做修复。"""
    issues: list[str] = []

    # 1. 顺序必须是 1..N 连续
    orders = sorted(u.order for u in plan.units)
    if orders != list(range(1, len(orders) + 1)):
        issues.append(f"order 必须是 1..{len(orders)} 连续递增，当前是 {orders}")

    # 2. unit id 唯一
    ids = [u.id for u in plan.units]
    if len(set(ids)) != len(ids):
        issues.append("unit id 有重复")

    # 3. 禁止发明知识点
    invented = sorted({kp for u in plan.units for kp in u.kp_ids if kp not in whitelist})
    if invented:
        issues.append(f"出现了白名单外的知识点 id（禁止发明）：{invented}")

    # 4. 范围覆盖：高权重(≥4)必须全覆盖，整体覆盖率不低于 90%
    need = set(kps_in_scope(request.scope))
    must_cover = {kp for kp in need if KP_TABLE.get(kp, {}).get("exam_weight", 0) >= 4}
    got = {kp for u in plan.units for kp in u.kp_ids}
    missing_must = sorted(must_cover - got, key=order_index)
    if missing_must:
        issues.append(f"考频≥4 的知识点必须覆盖，漏了：{missing_must}")
    if need:
        coverage = len(need & got) / len(need)
        if coverage < 0.9:
            missing = sorted(need - got, key=order_index)
            issues.append(f"覆盖率 {coverage:.0%} 低于 90%，漏了：{missing}")

    # 5. 前置顺序：前置在计划里出现过就必须排在本单元或更早的单元
    seen: set[str] = set()
    for unit in sorted(plan.units, key=lambda u: u.order):
        unit_kps = set(unit.kp_ids)
        for kp in unit.kp_ids:
            for pre in KP_TABLE.get(kp, {}).get("prerequisites", []):
                if pre in got and pre not in seen and pre not in unit_kps:
                    issues.append(f"{kp} 的前置 {pre} 排在了它后面")
        seen.update(unit.kp_ids)

    # 6. 总轮次一致
    total = sum(u.est_sessions for u in plan.units)
    if plan.total_sessions != total:
        issues.append(f"total_sessions 应等于各单元之和 {total}，当前 {plan.total_sessions}")

    # 7. 验收口径必须同时包含「独立」和「变式」
    for unit in plan.units:
        rule = unit.exit_test.pass_rule
        if "独立" not in rule or "变式" not in rule:
            issues.append(f"{unit.id} 的 pass_rule 必须同时包含「独立」和「变式」")
            break

    # 8. 产能校验：总轮次不能超过时间预算
    capacity = int(request.days * request.hours_per_day * 60 // 40)
    if plan.total_sessions > capacity:
        issues.append(
            f"总轮次 {plan.total_sessions} 超过 {request.days} 天 × {request.hours_per_day} 小时的产能 {capacity} 轮"
        )

    return list(dict.fromkeys(issues))


def evaluate_plan(plan: StudyPlan | None, request: PlannerRequest) -> dict[str, float | int | bool]:
    """给四版对比用的量化指标（0~1）。"""
    whitelist = whitelist_for_scope(request.scope)
    need = set(kps_in_scope(request.scope))

    if plan is None:
        return {
            "schema_ok": 0, "coverage": 0.0, "hallucination": 1.0, "order_ok": 0,
            "sessions_ok": 0, "exit_ok": 0, "units": 0, "sessions": 0, "score": 0.0,
        }

    got = {kp for u in plan.units for kp in u.kp_ids}
    invented = {kp for kp in got if kp not in whitelist}
    coverage = len(need & got) / len(need) if need else 1.0
    hallucination = len(invented) / max(1, len(got))
    orders = sorted(u.order for u in plan.units)
    order_ok = int(orders == list(range(1, len(orders) + 1)))
    sessions_ok = int(plan.total_sessions == sum(u.est_sessions for u in plan.units))
    exit_ok = int(
        all(("独立" in u.exit_test.pass_rule and "变式" in u.exit_test.pass_rule) for u in plan.units)
    )

    score = (
        1.0 * coverage
        + 1.0 * (1 - hallucination)
        + 0.6 * order_ok
        + 0.6 * sessions_ok
        + 0.8 * exit_ok
    ) / 4.0

    return {
        "schema_ok": 1,
        "coverage": round(coverage, 3),
        "hallucination": round(hallucination, 3),
        "order_ok": order_ok,
        "sessions_ok": sessions_ok,
        "exit_ok": exit_ok,
        "units": len(plan.units),
        "sessions": plan.total_sessions,
        "score": round(score, 3),
    }
