"""通用结构化节点：LLM → JSON → Pydantic → 确定性 checks → 修复环。

真实项目对应 `backend/runner.py`。所有 agent 共用这一段，新增 agent 只写
「prompt + schema + checks」，不要复制重试逻辑。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

try:
    import json_repair
except ImportError:  # 没装也能跑，只是少一层容错
    json_repair = None

T = TypeVar("T", bound=BaseModel)


@dataclass
class NodeResult(Generic[T]):
    value: T | None
    raw: str
    issues: list[str] = field(default_factory=list)
    attempts: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.value is not None and not self.issues


def extract_json(raw: str) -> dict[str, Any]:
    """从可能带 ```json 围栏的文本里抠出 JSON 对象。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("输出里没有 JSON 对象")
    candidate = text[start : end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        if json_repair is None:
            raise
        payload = json_repair.loads(candidate)
    if not isinstance(payload, dict):
        raise ValueError("JSON 顶层不是对象")
    return payload


def repair_prompt(issues: list[str]) -> str:
    body = "\n".join(f"- {x}" for x in issues[:8])
    return (
        "你上一次的输出没有通过校验，请保持教学内容不变，只修这些问题，"
        "重新输出完整 JSON，不要解释：\n" + body
    )


def run_structured(
    *,
    client,
    messages: list[dict[str, str]],
    schema: type[T],
    checks: Callable[[T], list[str]] | None = None,
    max_repairs: int = 1,
    max_tokens: int = 2500,
) -> NodeResult[T]:
    """跑一个结构化节点，失败时最多修复 max_repairs 次。"""
    msgs = list(messages)
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_latency = 0
    last_value: T | None = None
    last_raw = ""
    last_issues: list[str] = []

    for attempt in range(1, max_repairs + 2):
        try:
            raw, usage, latency = client.chat_json(msgs, max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001
            last_issues = [f"LLM 调用失败：{type(exc).__name__}: {exc}"]
            break

        last_raw = raw
        total_latency += int(latency)
        for key in total_usage:
            total_usage[key] += int(usage.get(key, 0) or 0)

        try:
            value = schema.model_validate(extract_json(raw))
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            last_issues = [f"输出不是合法 JSON 或不符合 schema：{type(exc).__name__}: {str(exc)[:300]}"]
            msgs += [
                {"role": "assistant", "content": raw or "{}"},
                {"role": "user", "content": repair_prompt(last_issues)},
            ]
            continue

        business_issues = checks(value) if checks else []
        last_value = value
        last_issues = business_issues
        if not business_issues:
            return NodeResult(
                value=value,
                raw=raw,
                issues=[],
                attempts=attempt,
                usage=total_usage,
                latency_ms=total_latency,
            )

        msgs += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": repair_prompt(business_issues)},
        ]

    return NodeResult(
        value=last_value,
        raw=last_raw,
        issues=last_issues,
        attempts=len(msgs) // 2,
        usage=total_usage,
        latency_ms=total_latency,
    )


def timed(fn):
    """小工具：给节点计时，写入 trace。"""

    def wrapper(*args, **kwargs):
        started = time.perf_counter()
        result = fn(*args, **kwargs)
        return result, int((time.perf_counter() - started) * 1000)

    return wrapper
