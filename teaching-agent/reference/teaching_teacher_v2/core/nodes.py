"""节点实现：讲练合一（一次调用出讲义 + 3 张题卡）、等待作答、判题。

设计要点
--------
1. **一个节点做完讲课和出题**。v2 是 teach → quiz 两次串行调用，单轮 12~21 s；
   合并后只有一次调用，题目和讲义共享同一份上下文，还顺带保证「只考刚讲的那一层」。
2. **流式优先**。提示词强制 `teaching.reply_markdown` 是 JSON 的第一个字段，
   `MarkdownStreamExtractor` 边收边解析，第一个可读片段一到就推给前端，
   所以「首屏」看的是 TTFT（首字节），不是等整个 JSON 生成完。
3. **校验不通过才重试**。一次生成讲义 + 3 题，schema 校验和内容检查失败时，
   带着失败原因重试（默认最多 2 次修复），修复轮次会写进评分和 trace。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import ValidationError

from core.checks import check_turn
from core.prompts import (
    build_lesson_practice_system_prompt,
    build_lesson_practice_user_prompt,
    build_lesson_repair_prompt,
)
from core.schema import LessonPayload, TeachingRequest, TeachingTurn

try:
    import json_repair
except ImportError:  # pragma: no cover
    json_repair = None

# 流式回调注册表：API 层按 session_id 注册一个队列，节点把增量推过去
_STREAM_SINKS: dict[str, Callable[[str], None]] = {}

# 这些错误重试没有意义（余额、鉴权、限流），直接失败，避免把一次调用放大成三次
FATAL_ERROR_MARKERS = ("402", "401", "403", "429", "Insufficient Balance", "insufficient_quota")


def register_stream_sink(session_id: str, sink: Callable[[str], None]) -> None:
    _STREAM_SINKS[session_id] = sink


def unregister_stream_sink(session_id: str) -> None:
    _STREAM_SINKS.pop(session_id, None)


class MarkdownStreamExtractor:
    """从流式 JSON 里增量抠出 `teaching.reply_markdown` 的值。

    为什么不用标准 JSON 解析：完整 JSON 要到最后一个 token 才合法，
    而首屏要的是「第一个段落可用」。这里只做一件事——定位字段，
    然后逐字符解码转义，遇到不完整的转义序列就停在原地等下一块。
    """

    KEY = '"reply_markdown"'

    def __init__(self) -> None:
        self.buf = ""
        self.markdown = ""
        self._started = False
        self._finished = False   # 见到收尾引号后必须封口，否则后续 chunk 会被继续吞进来
        self._pos = 0

    def feed(self, delta: str) -> str:
        if self._finished:
            return self.markdown
        self.buf += delta
        if not self._started:
            key_at = self.buf.find(self.KEY)
            if key_at == -1:
                return self.markdown
            colon = self.buf.find(":", key_at + len(self.KEY))
            if colon == -1:
                return self.markdown
            quote = self.buf.find('"', colon + 1)
            if quote == -1:
                return self.markdown
            self._pos = quote + 1
            self._started = True

        out: list[str] = []
        i = self._pos
        buf = self.buf
        while i < len(buf):
            ch = buf[i]
            if ch == "\\":
                if i + 1 >= len(buf):
                    break  # 转义序列还没收全，等下一块
                nxt = buf[i + 1]
                if nxt == "u":
                    if i + 5 >= len(buf):
                        break
                    try:
                        out.append(chr(int(buf[i + 2 : i + 6], 16)))
                    except ValueError:
                        pass
                    i += 6
                    continue
                out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/"}.get(nxt, nxt))
                i += 2
                continue
            if ch == '"':
                i += 1
                self._finished = True
                break
            out.append(ch)
            i += 1
        self._pos = i
        if out:
            self.markdown += "".join(out)
        return self.markdown


@dataclass
class LessonResult:
    payload: LessonPayload | None
    raw: str = ""
    issues: list[str] = field(default_factory=list)
    attempts: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    ttft_ms: int = 0
    attempt_log: list[dict[str, Any]] = field(default_factory=list)


def extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("没有找到 JSON 对象")
    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        if json_repair is None:
            raise
        repaired = json_repair.loads(candidate)
        if not isinstance(repaired, dict):
            raise ValueError("JSON 修复后不是对象")
        return repaired


def _check_cards(payload: LessonPayload) -> list[str]:
    """题卡的内容检查：只查「能不能用」，不查「题好不好」。"""
    issues: list[str] = []
    cards = payload.questions
    kinds = {c.kind for c in cards}
    if "choice" not in kinds:
        issues.append("3 道题里没有选择题")
    if "fill" not in kinds:
        issues.append("3 道题里没有填空题")

    difficulties = [c.difficulty for c in cards]
    if difficulties[:2] == ["hard", "hard"]:
        issues.append("前两道题都是 hard，难度没有递进")

    # source_quote 只做「宽松对位」：去掉标点/空白后再比，前 8 字命中即放过。
    # 之前用严格子串，模型只要少一个逗号就整轮重生成（实测 20% 请求中招，单次多花 6~12 秒）。
    def _norm_q(text: str) -> str:
        return re.sub(r"[^\u4e00-\u9fffa-zA-Z0-9]", "", text or "")

    reply_n = _norm_q(payload.teaching.reply_markdown)
    for index, card in enumerate(cards, start=1):
        quote_n = _norm_q(card.source_quote)
        if quote_n and len(quote_n) >= 8 and quote_n not in reply_n and quote_n[:8] not in reply_n:
            issues.append(f"第 {index} 题的 source_quote 不是讲义原句，题目缺少依据")
        if card.confidence == "low":
            issues.append(f"第 {index} 题置信度 low，不适合直接给学生")
        if card.kind == "fill" and len(card.answer) > 40:
            issues.append(f"第 {index} 题填空答案太长，不可判定")
    return issues


def run_lesson_practice(
    req: TeachingRequest,
    client,
    *,
    variant: str = "B",
    max_repairs: int = 2,
    on_markdown: Callable[[str], None] | None = None,
) -> LessonResult:
    """一次调用产出讲义 + 3 题；只有「硬问题」才重试。

    重试策略（踩过的坑）：
      - schema 不合法 / 题卡结构不成立  → 必须重试；
      - 讲义被检查器挑出「术语没解释」这类软问题 → **不重试**，只扣分。
        v2 里对软问题也重试，一次重试 = 一次完整生成（约 2 倍成本），
        还容易在额度边界上把整轮拖死。
      - 401/402/403/429 这类硬错误 → 立即失败，不重试。
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_lesson_practice_system_prompt(req, variant)},
        {"role": "user", "content": build_lesson_practice_user_prompt(req)},
    ]

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_latency = 0
    first_ttft = 0
    attempt_log: list[dict[str, Any]] = []
    last_payload: LessonPayload | None = None
    last_raw = ""
    last_issues: list[str] = []

    for attempt in range(1, max_repairs + 2):
        extractor = MarkdownStreamExtractor()

        def _on_delta(delta: str, _ex=extractor) -> None:
            _ex.feed(delta)  # 必须先喂给解析器，否则 markdown 永远是空串
            if on_markdown is not None:
                on_markdown(_ex.markdown)

        started = time.perf_counter()
        try:
            raw, usage, latency_ms, ttft_ms = client.stream_json(messages, on_delta=_on_delta)
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}: {exc}"
            last_issues = [f"LLM 调用失败：{detail[:160]}"]
            attempt_log.append({"attempt": attempt, "ok": False, "issues": last_issues})
            if any(marker in detail for marker in FATAL_ERROR_MARKERS):
                break  # 余额不足 / 鉴权失败 / 限流：重试没有意义
            time.sleep(0.5 * attempt)
            continue

        last_raw = raw
        total_latency += latency_ms or int((time.perf_counter() - started) * 1000)
        if first_ttft == 0 and ttft_ms:
            first_ttft = ttft_ms
        for key in total_usage:
            total_usage[key] += int(usage.get(key, 0) or 0)

        try:
            payload = LessonPayload.model_validate(extract_json(raw))
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            last_issues = [f"输出不是合法 JSON 或不符合 schema：{type(exc).__name__}: {str(exc)[:400]}"]
            attempt_log.append({"attempt": attempt, "ok": False, "issues": last_issues, "ttft_ms": ttft_ms})
            messages.extend(
                [
                    {"role": "assistant", "content": raw or "{}"},
                    {"role": "user", "content": build_lesson_repair_prompt(last_issues)},
                ]
            )
            continue

        last_payload = payload
        soft_issues = check_turn(payload.teaching, req)
        hard_issues = _check_cards(payload)
        attempt_log.append(
            {
                "attempt": attempt,
                "ok": not hard_issues,
                "issues": (hard_issues + soft_issues)[:8],
                "ttft_ms": ttft_ms,
                "latency_ms": latency_ms,
                "tokens": usage.get("total_tokens", 0),
            }
        )

        # 软问题（术语、篇幅）只扣分，不重新生成——省一次完整调用
        if not hard_issues:
            return LessonResult(
                payload=payload,
                raw=raw,
                issues=soft_issues,
                attempts=attempt,
                usage=total_usage,
                latency_ms=total_latency,
                ttft_ms=first_ttft,
                attempt_log=attempt_log,
            )

        last_issues = hard_issues
        messages.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": build_lesson_repair_prompt(hard_issues)},
            ]
        )

    return LessonResult(
        payload=last_payload,
        raw=last_raw,
        issues=last_issues,
        attempts=len(attempt_log) or max_repairs + 1,
        usage=total_usage,
        latency_ms=total_latency,
        ttft_ms=first_ttft,
        attempt_log=attempt_log,
    )


def build_request(state: dict[str, Any], learner_note: str = "") -> TeachingRequest:
    from core.schema import HistoryTurn

    return TeachingRequest(
        topic=state["topic"],
        level=state.get("level", "初中"),
        subject=state.get("subject", "数学"),
        prior_knowledge=state.get("prior_knowledge", ""),
        misconceptions=state.get("misconceptions", ""),
        student_message=state.get("student_message", ""),
        history=[HistoryTurn(**turn) for turn in state.get("history", [])[-20:]],
        learner_note=learner_note,
    )


def public_question(card: dict[str, Any] | None) -> dict[str, Any] | None:
    if not card:
        return None
    return {
        "kind": card["kind"],
        "stem": card["stem"],
        "options": card.get("options", []),
        "difficulty": card["difficulty"],
        "tested_points": card.get("tested_points", []),
    }


def format_lesson_for_history(teaching: dict[str, Any], cards: list[dict[str, Any]]) -> str:
    lines = [teaching["reply_markdown"], "", "【本轮练习题】"]
    for index, card in enumerate(cards, start=1):
        lines.append(f"{index}. {card['stem']}")
        if card.get("options"):
            lines.extend(f"   {chr(65 + i)}. {option}" for i, option in enumerate(card["options"]))
    return "\n".join(lines)


def summarize_teaching(turn: TeachingTurn) -> dict[str, Any]:
    return turn.model_dump()
