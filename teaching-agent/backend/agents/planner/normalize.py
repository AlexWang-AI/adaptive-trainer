"""计划的确定性后处理。

分工：LLM 负责「想内容」，代码负责「保证不变量」——顺序、编号、去重、总轮次
这类事情不该指望模型每次都对，也不该为此多花一次 LLM 调用。

两条原则：
1. **只在检查不通过时才修**，没毛病就不动它（避免"修坏了"）。
2. 排序用「单元级拓扑排序」而不是简单按知识点编号排，否则会把含多个章节的单元排错。
"""

from __future__ import annotations

from curriculum import KP_TABLE, kps_in_scope, order_index, whitelist_for_scope

from .checks import check_plan
from .schema import PlannerRequest, StudyPlan


def _renumber(units: list[dict]) -> list[dict]:
    for index, unit in enumerate(units, start=1):
        unit["order"] = index
        unit["id"] = f"U{index:02d}"
    return units


def normalize_plan(plan: StudyPlan) -> StudyPlan:
    """去重 + 空单元剔除 + 重编号 + 重算总轮次。**不改变单元相对顺序。**"""
    seen: set[str] = set()
    units: list[dict] = []
    for unit in sorted(plan.units, key=lambda u: u.order):
        kps = [kp for kp in unit.kp_ids if kp not in seen]
        seen.update(kps)
        if not kps:
            continue
        payload = unit.model_dump()
        payload["kp_ids"] = kps
        units.append(payload)

    payload = plan.model_dump()
    payload["units"] = _renumber(units)
    payload["total_sessions"] = sum(int(u["est_sessions"]) for u in units)
    return StudyPlan.model_validate(payload)


def _topo_order(units: list[dict]) -> list[dict]:
    """单元级拓扑排序：若 B 里某个知识点的前置在 A 里，则 A 必须排在 B 前。"""
    owner: dict[str, int] = {}
    for index, unit in enumerate(units):
        for kp in unit["kp_ids"]:
            owner.setdefault(kp, index)

    edges: dict[int, set[int]] = {i: set() for i in range(len(units))}
    indeg = [0] * len(units)
    for index, unit in enumerate(units):
        for kp in unit["kp_ids"]:
            for pre in KP_TABLE.get(kp, {}).get("prerequisites", []):
                src = owner.get(pre)
                if src is None or src == index or src in edges[index]:
                    continue
                edges[index].add(src)  # src -> index
                indeg[index] += 1

    ready = sorted(
        [i for i in range(len(units)) if indeg[i] == 0],
        key=lambda i: (min(order_index(kp) for kp in units[i]["kp_ids"]), units[i]["order"]),
    )
    ordered: list[dict] = []
    while ready:
        current = ready.pop(0)
        ordered.append(units[current])
        for nxt in range(len(units)):
            if current in edges[nxt]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)
        ready.sort(key=lambda i: (min(order_index(kp) for kp in units[i]["kp_ids"]), units[i]["order"]))

    if len(ordered) != len(units):  # 有环，退回原顺序
        return units
    return ordered


def _stitch(plan: StudyPlan, required: list[str]) -> StudyPlan:
    """把漏掉的知识点补进去：优先塞进同章节的单元，其次最后一个单元。"""
    present = {kp for unit in plan.units for kp in unit.kp_ids}
    missing = [kp for kp in required if kp not in present]
    if not missing:
        return plan

    payload = plan.model_dump()
    for kp in missing:
        chapter = kp.split(".")[0]
        target = next(
            (u for u in payload["units"] if any(i.split(".")[0] == chapter for i in u["kp_ids"])),
            payload["units"][-1] if payload["units"] else None,
        )
        if target is not None and len(target["kp_ids"]) < 6:
            target["kp_ids"].append(kp)
    return StudyPlan.model_validate(payload)


def repair_plan(
    plan: StudyPlan, request: PlannerRequest, whitelist: list[str] | None = None
) -> tuple[StudyPlan, list[str], int]:
    """检查 →（必要时）补漏 + 拓扑排序 + 规整 → 复查。返回 (计划, 剩余问题, 修了几处)。"""
    whitelist = whitelist or whitelist_for_scope(request.scope)

    issues_before = check_plan(plan, request, whitelist)
    if not issues_before:
        return plan, [], 0

    fixed = normalize_plan(_stitch(plan, kps_in_scope(request.scope)))
    fixed = StudyPlan.model_validate(
        {**fixed.model_dump(), "units": _renumber(_topo_order(fixed.model_dump()["units"]))}
    )
    fixed = normalize_plan(fixed)
    return fixed, check_plan(fixed, request, whitelist), len(issues_before)
