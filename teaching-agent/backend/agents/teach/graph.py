"""主讲 agent 的确定性门禁（不调 LLM）+ LangGraph 图。

节点：teach → term_gate →（不合格则 repair 一次）→ student → 记录
这一版起，主讲不再是"脚本里的一次调用"，而是图里的节点，状态可检查、可恢复、可追踪。
"""
from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from runner import extract_json

from .prompts import build, build_audit, build_repair, build_student
from .schema import AuditOut, StudentOut, TeachIn, TeachOut

CJK = re.compile(r"[\u4e00-\u9fa5]")


def _norm(t: str) -> str:
    """去掉空格与常见标点，统一全半角，避免"0/0 型" vs "0/0型"误判。"""
    t = t.replace("（", "(").replace("）", ")").replace("，", ",")
    return re.sub(r"[\s·•・\-_,，。、]", "", t)


# ---------------------------------------------------------------- 门禁
def gate(out: TeachOut) -> list[str]:
    """确定性检查：术语是否都解释、要点是否落在包内、检查问题是否存在。"""
    issues: list[str] = []
    explained = {t.term.strip() for t in out.terms}
    used = {t.strip() for t in out.terms_used}
    # 1) 说用到了但没登记解释
    missing = used - explained
    if missing:
        issues.append(f"术语未解释：{sorted(missing)}")
    # 2) 解释过的名词必须在 speech 里真的出现过（防"假解释"）
    speech_n = _norm(out.speech)
    for t in out.terms:
        if t.term and _norm(t.term) not in speech_n:
            issues.append(f"术语 {t.term} 未出现在讲解正文中")
    # 3) 检查问题必须真的是一句问句
    if "？" not in out.check_question and "?" not in out.check_question:
        issues.append("check_question 不是问句")
    return issues


# ---------------------------------------------------------------- 状态
class TeachState(TypedDict, total=False):
    pack_name: str
    kps: list[dict]
    variant: str
    student_say: str
    unknown_terms: list[str]
    out: dict
    issues: list[str]
    repaired: bool
    student: dict
    rounds: int


# ---------------------------------------------------------------- 节点
def make_nodes(client):
    def teach_node(state: TeachState) -> dict:
        inp = TeachIn(
            pack_name=state["pack_name"],
            kps=state["kps"],
            variant=state["variant"],
            unknown_terms=state.get("unknown_terms", []),
        )
        raw, _, _ = client.chat_json(build(inp, state.get("student_say", "")), temperature=0.5, max_tokens=1600)
        payload = extract_json(raw)
        if isinstance(payload.get("speech"), str):
            payload["speech"] = payload["speech"][:2000]
        out = TeachOut.model_validate(payload)
        return {"out": out.model_dump(), "issues": gate(out), "repaired": False}

    def repair_node(state: TeachState) -> dict:
        try:
            return _repair_impl(state)
        except Exception as exc:  # 门禁失败不能拖垮整轮
            print(f'      [warn] repair 跳过: {type(exc).__name__}', flush=True)
            return {'issues': state.get('issues', []), 'repaired': True}

    def _repair_impl(state: TeachState) -> dict:
        out = TeachOut.model_validate(state["out"])
        audit_raw, _, _ = client.chat_json(build_audit(out.speech, [t.term for t in out.terms]),
                                           temperature=0.0, max_tokens=400)
        audit = AuditOut.model_validate(extract_json(audit_raw))
        missing = audit.missing or sorted({t.strip() for t in out.terms_used} - {t.term for t in out.terms})
        if not missing:
            return {"issues": gate(out), "repaired": True}
        raw, _, _ = client.chat_json(build_repair(out.speech, missing), temperature=0.3, max_tokens=900)
        new_speech = raw.strip()
        if len(new_speech) >= 120:   # 修短了就别换，避免触发 schema 下限
            out.speech = new_speech[:2000]
        out.terms_used = sorted(set(out.terms_used) | set(missing))
        from .schema import Term as _Term
        out.terms = list(out.terms) + [_Term(term=m, plain="（本轮补充解释）") for m in missing][:6]
        return {"out": out.model_dump(), "issues": gate(out), "repaired": True}

    def student_node(state: TeachState) -> dict:
        out = TeachOut.model_validate(state["out"])
        raw, _, _ = client.chat_json(build_student(out.speech, out.check_question),
                                     temperature=0.7, max_tokens=300)
        sp = extract_json(raw)
        sp['unknown_terms'] = list(sp.get('unknown_terms', []))[:10]
        s = StudentOut.model_validate(sp)
        return {"student": s.model_dump(), "rounds": state.get("rounds", 0) + 1}

    def route(state: TeachState) -> str:
        if state.get("issues") and not state.get("repaired"):
            return "repair"
        return "student"

    return teach_node, repair_node, student_node, route


def build_graph(client):
    teach_node, repair_node, student_node, route = make_nodes(client)
    g = StateGraph(TeachState)
    g.add_node("teach", teach_node)
    g.add_node("repair", repair_node)
    g.add_node("student", student_node)
    g.add_edge(START, "teach")
    g.add_conditional_edges("teach", route, {"repair": "repair", "student": "student"})
    g.add_edge("repair", "student")
    g.add_edge("student", END)
    return g.compile(checkpointer=MemorySaver())


def run_one(client, inp: TeachIn, thread: str = "t1", student_say: str = "") -> dict[str, Any]:
    graph = build_graph(client)
    state: TeachState = {
        "pack_name": inp.pack_name,
        "kps": [k.model_dump() for k in inp.kps],
        "variant": inp.variant,
        "student_say": student_say,
        "unknown_terms": inp.unknown_terms,
        "rounds": 0,
    }
    res = graph.invoke(state, {"configurable": {"thread_id": thread}})
    return {"out": res.get("out"), "issues": res.get("issues", []), "student": res.get("student")}
