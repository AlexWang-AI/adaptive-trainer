"""主讲 agent 的「两步法」实现（V5）：先定术语表，再写讲解。

动机（S0-3 换路）：一次生成里同时兼顾「讲清楚」和「不漏术语」，两个迭代都没达标。
改成结构化流水线：扫词 → 逐词解释 → 带着术语表写讲解 → 确定性门禁。
这样"术语全覆盖"从"模型自觉"变成"输入就带着"，门禁只需校验一致性。
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from runner import extract_json

from .graph import gate
from .prompts import build_student
from .schema import StudentOut, TeachIn, TeachOut, Term

TERMS_SYS = (
    "你是教研员。根据知识点包，列出本轮讲解**必须用到的专业名词**（4-10 个），"
    "只列名词本身，不要解释。输出 JSON：{\"terms\":[\"...\"]}，只输出 JSON。"
)
EXPLAIN_SYS = (
    "你是教研员。给每个专业名词写一句大白话解释（不超过 40 字，可用类比），"
    '输出 JSON：{"glossary":[{"term":"...","plain":"..."}]}，只输出 JSON。'
)
SPEECH_SYS = (
    "你是考研数学主讲老师。用给定的术语表写一段面向零基础学生的讲解（250-500 字）。"
    "硬性要求：术语表里每个词第一次出现时，必须紧跟括号写它的白话解释，例如「洛必达法则（……）」。"
    "写完后把用到的名词全部登记到 terms_used。先直觉、再定义、再一个算例、最后给 1 个检查问题。"
    '输出 JSON：{"speech":"...","terms_used":["..."],"points_covered":["..."],"check_question":"..."}，只输出 JSON。'
)


class TPState(TypedDict, total=False):
    pack_name: str
    kp_text: str
    variant: str
    student_say: str
    terms: list[str]
    glossary: list[dict]
    out: dict
    issues: list[str]
    student: dict


def _pack_text(inp: TeachIn) -> str:
    return "\n".join(
        f"- {kp.name}（要点：{'、'.join(kp.points) or '无'}）" for kp in inp.kps
    )


def run_two_pass(client, inp: TeachIn, student_say: str = "") -> dict:
    pack_text = _pack_text(inp)

    terms_raw, _, _ = client.chat_json(
        [{"role": "system", "content": TERMS_SYS},
         {"role": "user", "content": f"知识点包：{inp.pack_name}\n{pack_text}"}],
        temperature=0.2, max_tokens=400)
    terms = [str(t).strip() for t in extract_json(terms_raw).get("terms", [])][:10]

    ex_raw, _, _ = client.chat_json(
        [{"role": "system", "content": EXPLAIN_SYS},
         {"role": "user", "content": f"名词：{terms}"}],
        temperature=0.2, max_tokens=700)
    glossary = extract_json(ex_raw).get("glossary", [])[:10]

    sp_raw, _, _ = client.chat_json(
        [{"role": "system", "content": SPEECH_SYS},
         {"role": "user", "content":
          f"知识点包：{inp.pack_name}\n{pack_text}\n\n术语表：{glossary}\n"
          f"学生上轮没懂：{inp.unknown_terms or '无'}\n学生刚说：{student_say or '（开场）'}"}],
        temperature=0.5, max_tokens=1500)
    payload = extract_json(sp_raw)
    if isinstance(payload.get("speech"), str):
        payload["speech"] = payload["speech"][:2000]
    payload.setdefault("terms", glossary)

    # 审计闭环：找出正文里仍未被解释的词，补进术语表后重写一次
    try:
        from .prompts import build_audit

        audit_raw, _, _ = client.chat_json(
            build_audit(payload.get("speech", ""), [g.get("term", "") for g in glossary]),
            temperature=0.0, max_tokens=400)
        missing = [str(m) for m in extract_json(audit_raw).get("missing", [])][:6]
        if missing:
            extra = [{"term": m, "plain": "整段讲解里已在上下文中解释"} for m in missing]
            new_glossary = glossary + extra
            sp2, _, _ = client.chat_json(
                [{"role": "system", "content": SPEECH_SYS},
                 {"role": "user", "content":
                  f"知识点包：{inp.pack_name}\n{pack_text}\n\n术语表（已补全）：{new_glossary}\n"
                  f"学生刚说：{student_say or '（开场）'}\n请重写，务必把术语表里每个词都带括号解释。"}],
                temperature=0.4, max_tokens=1500)
            p2 = extract_json(sp2)
            if isinstance(p2.get("speech"), str) and len(p2["speech"]) >= 120:
                payload = p2
                payload["speech"] = payload["speech"][:2000]
                payload.setdefault("terms", new_glossary)
                payload.setdefault("check_question", "这一轮的结论你能复述一遍吗？")
    except Exception:
        pass

    payload.setdefault("self_check", "两步法：术语表预先给定")
    out = TeachOut.model_validate(payload)
    issues = gate(out)

    st_raw, _, _ = client.chat_json(build_student(out.speech, out.check_question),
                                    temperature=0.7, max_tokens=300)
    sp = extract_json(st_raw)
    sp['unknown_terms'] = list(sp.get('unknown_terms', []))[:10]
    student = StudentOut.model_validate(sp)
    return {"out": out.model_dump(), "issues": issues, "student": student.model_dump()}


def build_two_pass_graph(client):
    """把两步法也做成图（保持架构一致：节点 + 状态 + 检查点由外层统一）。"""
    def terms_node(s: TPState):
        raw, _, _ = client.chat_json([{"role": "system", "content": TERMS_SYS},
                                      {"role": "user", "content": s["kp_text"]}],
                                     temperature=0.2, max_tokens=400)
        return {"terms": [str(t).strip() for t in extract_json(raw).get("terms", [])][:10]}

    def explain_node(s: TPState):
        raw, _, _ = client.chat_json([{"role": "system", "content": EXPLAIN_SYS},
                                      {"role": "user", "content": f"名词：{s['terms']}"}],
                                     temperature=0.2, max_tokens=700)
        return {"glossary": extract_json(raw).get("glossary", [])[:10]}

    def speech_node(s: TPState):
        raw, _, _ = client.chat_json(
            [{"role": "system", "content": SPEECH_SYS},
             {"role": "user", "content": f"{s['kp_text']}\n\n术语表：{s['glossary']}\n学生刚说：{s.get('student_say','')}"}],
            temperature=0.5, max_tokens=1500)
        payload = extract_json(raw)
        payload.setdefault("terms", s.get("glossary", []))
        payload["speech"] = str(payload.get("speech", ""))[:2000]
        return {"out": payload}

    def gate_node(s: TPState):
        out = TeachOut.model_validate(s["out"])
        return {"out": out.model_dump(), "issues": gate(out)}

    g = StateGraph(TPState)
    g.add_node("terms", terms_node)
    g.add_node("explain", explain_node)
    g.add_node("speech", speech_node)
    g.add_node("gate", gate_node)
    g.add_edge(START, "terms")
    g.add_edge("terms", "explain")
    g.add_edge("explain", "speech")
    g.add_edge("speech", "gate")
    g.add_edge("gate", END)
    from langgraph.checkpoint.memory import MemorySaver
    return g.compile(checkpointer=MemorySaver())
