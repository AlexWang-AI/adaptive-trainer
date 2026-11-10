"""两个轻量 LLM 节点：侧边提问（不污染主干）与思路诊断（错题本）。

设计约束：
- 都不进主图，不写主对话历史 —— 侧问只带「当前这题 + 讲义片段」，诊断只带「题目 + 学生原话」；
- 输出都走严格 JSON，失败即降级为纯文本，不重试（这两个是提升体验的旁路，不该拖慢主链路）；
- token 预算很小（侧问 ~600，诊断 ~700），保证 2 秒级响应。
"""

from __future__ import annotations

import json
import re
from typing import Any

SIDE_SYSTEM = """你是考研数学助教。学生正在看一段讲义、做一道题，有问题想单独问。
要求：
1. 只回答他问的那一点，不要重讲整段课，不要重复讲义原文；
2. 用 3~6 句讲清楚，必要时给一个小例子或反例；
3. 如果问题暴露出概念误解，用一句话点出来；
4. 不主动出题、不扩展话题。
只输出 JSON：{"answer": "正文，允许简单 markdown", "misconception": "如果没有就空字符串"}"""

DIAG_SYSTEM = """你是考研数学的思路诊断老师。学生刚做错一道题，并用自己的话讲了他的思路（可能是语音转写，有口误）。
你的任务不是重讲题，而是**定位他思路断在哪一步**。

输出 JSON：
{
  "steps": [{"step": "他说的第 1 步", "ok": true/false, "issue": "这一步的问题，没问题就空字符串"}],
  "first_break": "最早出错的那一步（一句话）",
  "misconception": "一句话点出错误认知（不是粗心，而是理解偏差）",
  "fix": "一句话给出可执行的纠正动作",
  "severity": "concept | method | careless"
}
要求：steps 不超过 4 条；判断基于学生原话，不要臆测他没说过的步骤。"""


def _extract(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def coerce_card(item: dict[str, Any]) -> dict[str, Any]:
    """把模型常见的不规范字段救回来（tested_points 写成字符串、options 写成字符串…）。"""
    if not isinstance(item, dict):
        return {}
    out = dict(item)
    tp = out.get("tested_points")
    if isinstance(tp, str):
        out["tested_points"] = [tp.strip()] if tp.strip() else []
    elif not isinstance(tp, list):
        out["tested_points"] = []
    out["tested_points"] = [str(x)[:20] for x in out["tested_points"]][:3] or ["未标注知识点"]

    opts = out.get("options")
    if isinstance(opts, str):
        parsed = None
        try:
            import json as _json

            parsed = _json.loads(opts)          # 模型常把数组写成 JSON 字符串
        except Exception:  # noqa: BLE001
            parsed = None
        if isinstance(parsed, list):
            out["options"] = [str(o).strip() for o in parsed if str(o).strip()]
        else:
            out["options"] = [o.strip() for o in opts.replace("\n", "|").split("|") if o.strip()]
    elif not isinstance(opts, list):
        out["options"] = []
    out["options"] = [str(o) for o in out["options"]][:4]

    out["kind"] = "choice" if str(out.get("kind", "")).lower().startswith("choice") or out["options"] else "fill"
    # 题型标签：出题是否真的落在教材题型上，靠这个字段验收
    out["type_name"] = str(out.get("type_name") or "").strip()[:40]
    diff = str(out.get("difficulty", "medium")).lower()
    out["difficulty"] = diff if diff in ("easy", "medium", "hard") else "medium"
    conf = out.get("confidence", "high")
    if isinstance(conf, (int, float)):
        conf = "high" if conf >= 0.8 else "medium" if conf >= 0.5 else "low"
    if str(conf).lower() not in ("high", "medium", "low"):
        conf = "high"
    out["confidence"] = str(conf).lower()
    out.setdefault("explanation", "见解析。")
    out.setdefault("why_this_question", "针对这一层的典型考法。")
    out.setdefault("source_quote", "")
    if out["kind"] == "fill":
        out["options"] = []
    return out

def side_answer(
    client,
    *,
    ask: str,
    question: str,
    lesson: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """侧边提问：上下文只有「这一题 + 讲义片段 + 最近几条侧问」，绝不带主对话。"""
    ctx = []
    for turn in (history or [])[-6:]:
        role = "学生" if turn.get("role") == "student" else "助教"
        ctx.append(f"{role}：{str(turn.get('content', ''))[:300]}")
    messages = [
        {"role": "system", "content": SIDE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"【讲义片段】\n{lesson[:1200]}\n\n"
                f"【当前题目】\n{question[:600]}\n\n"
                f"【侧边对话】\n" + ("\n".join(ctx) if ctx else "（无）") + f"\n\n【学生这次问】\n{ask[:600]}"
            ),
        },
    ]
    raw, usage, latency = client.chat_json(messages, temperature=0.2, max_tokens=700)
    payload = _extract(raw)
    answer = str(payload.get("answer") or raw).strip()
    return {
        "answer": answer,
        "misconception": str(payload.get("misconception") or ""),
        "tokens": usage.get("total_tokens", 0),
        "latency_ms": latency,
    }


def diagnose(
    client,
    *,
    kp_name: str,
    question: str,
    student_answer: str,
    reasoning: str,
) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": DIAG_SYSTEM},
        {
            "role": "user",
            "content": (
                f"【知识点】{kp_name}\n【题目】{question[:600]}\n"
                f"【学生答案】{student_answer[:120]}\n【学生自述思路】{reasoning[:1200]}"
            ),
        },
    ]
    raw, usage, latency = client.chat_json(messages, temperature=0.1, max_tokens=800)
    payload = _extract(raw)
    steps = payload.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    return {
        "steps": [
            {
                "step": str(item.get("step", ""))[:200],
                "ok": bool(item.get("ok")),
                "issue": str(item.get("issue", ""))[:200],
            }
            for item in steps[:4]
            if isinstance(item, dict)
        ],
        "first_break": str(payload.get("first_break", ""))[:200],
        "misconception": str(payload.get("misconception", ""))[:200],
        "fix": str(payload.get("fix", ""))[:200],
        "severity": str(payload.get("severity", "concept")),
        "tokens": usage.get("total_tokens", 0),
        "latency_ms": latency,
    }


QUIZ_ONLY_SYSTEM = """你是考研数学出题老师。只出题，不讲新课。
输出 JSON：{"questions": [题卡, 题卡, 题卡]}
题卡字段：kind(choice|fill), stem, options(选择题 4 个/填空 []), answer, explanation,
tested_points(1 个), difficulty(easy|medium|hard), why_this_question, source_quote(可空),
type_name（必须逐字取自给定的【教材题型】名单，选题型里最贴的那个）, confidence。
要求：3 道题只考给定的这一个知识点，难度依次 easy→medium→hard；
如果给了【教材题型】，三道题的解法必须分别落在那几步上，不许自创题型；
如果给了【教材例题】，可以改数字/函数，但考点与解法必须同源；
如果给了「学生曾出现的错误认知」，第 2 题必须专门设计一个会被该错误认知带偏的干扰项。"""


def _finalize_card(card: dict[str, Any], kp_name: str) -> dict[str, Any] | None:
    """把题卡补齐到能过 pydantic 校验；缺到没法用的（无题干/无答案）直接丢。

    为什么不再整批重试：一次 3 张卡里坏 1 张，重试等于多花 1500~2000 token，
    而坏的那张通常只是 explanation 太短 / why_this_question 忘了写。
    """
    stem = str(card.get("stem") or "").strip()
    answer = str(card.get("answer") or "").strip()
    if len(stem) < 8 or not answer:
        return None
    if len(str(card.get("explanation") or "")) < 10:
        card["explanation"] = f"本题考「{kp_name}」，按教材题型的解法步骤逐步求解即可。"
    if len(str(card.get("why_this_question") or "")) < 10:
        type_name = str(card.get("type_name") or "").strip()
        card["why_this_question"] = (
            f"对应教材题型：{type_name}" if type_name else f"对应教材知识点：{kp_name}"
        )
    # 超长也要裁：模型常把解析写成长篇，pydantic 直接判 300 字上限
    limits = {
        "stem": 300,
        "answer": 80,
        "explanation": 300,
        "why_this_question": 220,
        "source_quote": 220,
    }
    for field, limit in limits.items():
        value = str(card.get(field) or "")
        if len(value) > limit:
            card[field] = value[: limit - 1] + "…"
    return card


def _quiz_grounding(
    types: list[dict[str, Any]] | None,
    examples: list[dict[str, Any]] | None,
    conclusions: list[str] | None,
) -> tuple[str, list[str]]:
    """把教材题型/例题/结论拼成出题依据，返回（文本，可用题型名列表）。"""
    parts: list[str] = []
    names: list[str] = []
    if types:
        lines = []
        for i, t in enumerate(types[:4], start=1):
            name = (t.get("name") or "").strip()
            if not name:
                continue
            names.append(name)
            steps = " → ".join(t.get("steps") or [])
            feature = (t.get("feature") or "").strip()
            lines.append(f"{i}. {name}" + (f"｜题干特征：{feature}" if feature else "") + (f"\n   解法步骤：{steps}" if steps else ""))
        if lines:
            parts.append("【教材题型｜必须按这些题型的步骤出题，不许自创】\n" + "\n".join(lines))
    if examples:
        lines = [f"{e.get('id', '')}：{(e.get('text') or '')[:150]}" for e in examples[:2] if e.get("text")]
        if lines:
            parts.append("【教材例题｜可改数字，考点与解法必须同源】\n" + "\n".join(lines))
    if conclusions:
        lines = [f"① {c}" for c in conclusions[:3] if c]
        if lines:
            parts.append("【本讲结论｜题目不许与这些结论矛盾】\n" + "  ".join(lines))
    return "\n\n".join(parts), names


def generate_questions_only(
    client,
    *,
    kp_name: str,
    misconception: str = "",
    types: list[dict[str, Any]] | None = None,
    examples: list[dict[str, Any]] | None = None,
    conclusions: list[str] | None = None,
) -> dict[str, Any]:
    """同知识点「再练一组」：只出 3 道题，不重讲，约 4 秒。

    接了教材题型层之后，出题不再是自由发挥：题型清单决定「考什么解法」，
    教材例题决定「同源母题」，结论决定「不许跟教材冲突」。
    """
    grounding, type_names = _quiz_grounding(types, examples, conclusions)
    extra = f"\n【学生曾出现的错误认知】{misconception[:200]}" if misconception else ""
    user = f"【知识点】{kp_name}{extra}"
    if grounding:
        user += f"\n\n{grounding}"
    user += "\n\n输出 3 道题。"

    raw, usage, latency = client.chat_json(
        [{"role": "system", "content": QUIZ_ONLY_SYSTEM}, {"role": "user", "content": user}],
        temperature=0.4,
        max_tokens=1600,
    )
    calls = 1
    payload = _extract(raw)
    items = payload.get("questions") or []
    if not isinstance(items, list):
        items = []
    cards = [c for c in (_finalize_card(coerce_card(x), kp_name) for x in items[:4]) if c][:3]
    calls = 1

    # 门禁：至少 2 道题能对上给定题型，否则补一次（只补一次，不无限重试）
    def matched(cs: list[dict[str, Any]]) -> int:
        return sum(1 for c in cs if (c.get("type_name") or "").strip() in type_names)

    if type_names and matched(cards) < 2:
        retry_user = (
            user
            + "\n\n上一次输出没有对上题型。请重出，并且每道题的 type_name 必须逐字取自："
            + "、".join(type_names)
        )
        raw2, usage2, latency2 = client.chat_json(
            [{"role": "system", "content": QUIZ_ONLY_SYSTEM}, {"role": "user", "content": retry_user}],
            temperature=0.3,
            max_tokens=1600,
        )
        payload2 = _extract(raw2)
        items2 = payload2.get("questions") or []
        if isinstance(items2, list) and items2:
            cards2 = [c for c in (_finalize_card(coerce_card(x), kp_name) for x in items2[:4]) if c][:3]
            if matched(cards2) >= matched(cards):
                cards = cards2
                usage["total_tokens"] = int(usage.get("total_tokens", 0)) + int(usage2.get("total_tokens", 0))
                latency += latency2
                calls += 1

    return {
        "questions": cards,
        "types_used": sorted({(c.get("type_name") or "").strip() for c in cards if (c.get("type_name") or "").strip() in type_names}),
        "type_names": type_names,
        "calls": calls,
        "tokens": usage.get("total_tokens", 0),
        "latency_ms": latency,
    }
