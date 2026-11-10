"""四个版本的实现。每个版本 = 一个函数 (client, request) -> VariantRun。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from llm import LLMClient
from curriculum import whitelist_for_scope
from runner import NodeResult, call_json, run_structured

from .checks import check_plan
from .prompts import (
    v1_prompts,
    v2_stage1_prompts,
    v2_stage2_prompts,
    v3_prompts,
    v4_critique_prompts,
    v4_prompts,
    v4_revision_prompts,
)
from .schema import PlannerRequest, StudyPlan


@dataclass
class VariantRun:
    variant: str
    plan: StudyPlan | None
    issues: list[str] = field(default_factory=list)
    attempts: int = 0
    calls: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def add_usage(self, usage: dict[str, int], latency: int) -> None:
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            self.usage[key] = self.usage.get(key, 0) + int(usage.get(key, 0) or 0)
        self.latency_ms += latency
        self.calls += 1


def _checks_for(request: PlannerRequest) -> Callable[[StudyPlan], list[str]]:
    whitelist = whitelist_for_scope(request.scope)
    return lambda plan: check_plan(plan, request, whitelist)


def run_v1(client: LLMClient, request: PlannerRequest) -> VariantRun:
    """基线：一次直出，不做修复。"""
    system, user = v1_prompts(request)
    res: NodeResult[StudyPlan] = run_structured(
        client=client,
        system=system,
        user=user,
        schema=StudyPlan,
        checks=_checks_for(request),
        max_repairs=0,
        max_tokens=6000,
    )
    run = VariantRun("V1", res.value, res.issues, res.attempts)
    run.add_usage(res.usage, res.latency_ms)
    return run


def run_v2(client: LLMClient, request: PlannerRequest) -> VariantRun:
    """两段式：先排骨架，再补验收细节。"""
    run = VariantRun("V2", None)
    s_sys, s_user = v2_stage1_prompts(request)
    skeleton, usage, latency = call_json(client, s_sys, s_user, max_tokens=2500)
    run.add_usage(usage, latency)

    t_sys, t_user = v2_stage2_prompts(request, skeleton)
    res: NodeResult[StudyPlan] = run_structured(
        client=client,
        system=t_sys,
        user=t_user,
        schema=StudyPlan,
        checks=_checks_for(request),
        max_repairs=1,
        max_tokens=6000,
    )
    run.add_usage(res.usage, res.latency_ms)
    run.plan = res.value
    run.issues = res.issues
    run.attempts = res.attempts
    run.extra["skeleton_units"] = len(skeleton.get("units", []) or [])
    return run


def run_v3(client: LLMClient, request: PlannerRequest) -> VariantRun:
    """白名单强约束 + 修复环。"""
    system, user = v3_prompts(request)
    res: NodeResult[StudyPlan] = run_structured(
        client=client,
        system=system,
        user=user,
        schema=StudyPlan,
        checks=_checks_for(request),
        max_repairs=1,
        max_tokens=6000,
    )
    run = VariantRun("V3", res.value, res.issues, res.attempts)
    run.add_usage(res.usage, res.latency_ms)
    return run


def run_v4(client: LLMClient, request: PlannerRequest) -> VariantRun:
    """白名单 + 教研自评 + 修订。"""
    run = VariantRun("V4", None)
    system, user = v4_prompts(request)
    first: NodeResult[StudyPlan] = run_structured(
        client=client,
        system=system,
        user=user,
        schema=StudyPlan,
        checks=_checks_for(request),
        max_repairs=1,
        max_tokens=6000,
    )
    run.add_usage(first.usage, first.latency_ms)
    run.plan, run.issues = first.value, first.issues
    if first.value is None:
        run.attempts = first.attempts
        return run

    plan_json = first.value.model_dump()
    c_sys, c_user = v4_critique_prompts(request, plan_json, first.issues)
    try:
        critique, usage2, latency2 = call_json(client, c_sys, c_user, max_tokens=2000)
    except Exception as exc:  # 自评失败不该让整次运行失败
        run.extra["critique_error"] = f"{type(exc).__name__}: {exc}"
        run.attempts = first.attempts
        return run

    run.add_usage(usage2, latency2)
    critiques = critique.get("issues", []) or []
    run.extra["critiques"] = len(critiques)
    if not critiques:
        run.attempts = first.attempts
        return run

    r_sys, r_user = v4_revision_prompts(request, plan_json, critiques, first.issues)
    revised: NodeResult[StudyPlan] = run_structured(
        client=client,
        system=r_sys,
        user=r_user,
        schema=StudyPlan,
        checks=_checks_for(request),
        max_repairs=1,
        max_tokens=6000,
    )
    run.add_usage(revised.usage, revised.latency_ms)
    run.attempts = first.attempts + revised.attempts
    if revised.value is not None:
        run.plan, run.issues = revised.value, revised.issues
    return run


VARIANTS: dict[str, Callable[[LLMClient, PlannerRequest], VariantRun]] = {
    "V1": run_v1,
    "V2": run_v2,
    "V3": run_v3,
    "V4": run_v4,
}


def run_v3r(client: LLMClient, request: PlannerRequest) -> VariantRun:
    """V3 + 确定性规整：模型出内容，代码保证不变量。"""
    from curriculum import whitelist_for_scope

    from .normalize import repair_plan

    run = run_v3(client, request)
    if run.plan is not None:
        run.plan, run.issues, fixed = repair_plan(run.plan, request, whitelist_for_scope(request.scope))
        run.extra["issues_fixed_by_code"] = fixed
    return run


VARIANTS["V3R"] = run_v3r


def run_auto(client: LLMClient, request: PlannerRequest) -> VariantRun:
    """线上默认入口 = V3R。

    实测结论（6 条用例，见 eval/results/）：
      V1  0/6  幻觉 77%（无白名单 → 发明 kp id）
      V2  5/6  两次调用，c5 漏两个考频 4 的知识点
      V3  5/6  一次调用，c5 前置顺序错 2 处
      V4  6/6  三次调用 / 16k tokens / 29s
      V3R 6/6  一次调用 / 4.2k tokens / 10.5s  ← 选定
    即：**能确定性修的问题，不要多花一次 LLM 调用**。
    """
    run = run_v3r(client, request)
    run.extra["route"] = "V3R"
    return run


VARIANTS["AUTO"] = run_auto


# ---------------------------------------------------------------------------
# LangSmith 追踪：未配置 key 时 traceable_agent 原样返回，零开销
# ---------------------------------------------------------------------------
try:
    from tracing import traceable_agent as _traceable

    for _key in list(VARIANTS):
        VARIANTS[_key] = _traceable(f"planner.{_key}")(VARIANTS[_key])
except Exception:  # pragma: no cover
    pass
