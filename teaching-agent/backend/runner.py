"""通用结构化节点执行器。

所有 agent 共用这一段：调 LLM → 抽 JSON → 修复 LaTeX → Pydantic 校验 → 业务 checks → 回灌修复。
新增一个 agent 只需要写「prompt 构造函数 + schema + checks」，不用再抄一遍重试逻辑。

用法：
    from runner import run_structured
    res = run_structured(
        client=client, system=sys_prompt, user=user_prompt,
        schema=StudyPlan, checks=lambda p: check_plan(p, case),
    )
    if res.value is None: ...  # res.issues 里有原因
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

try:
    import json_repair
except ImportError:  # pragma: no cover
    json_repair = None

from llm import LLMClient

T = TypeVar("T", bound=BaseModel)

LATEX_COMMANDS = (
    "frac|dfrac|tfrac|sqrt|Delta|delta|cdot|times|le|ge|leq|geq|neq|infty|"
    "alpha|beta|gamma|theta|lambda|mu|pi|sigma|omega|sum|int|lim|to|"
    "rightarrow|Rightarrow|approx|sim|partial|nabla|overline|vec|hat|"
    "left|right|text|mathrm|mathbf|mathbb|begin|end|quad|qquad"
)


@dataclass
class NodeResult(Generic[T]):
    value: T | None
    raw: str
    issues: list[str] = field(default_factory=list)
    attempts: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    log: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.value is not None and not self.issues


def _escape_latex_json(raw: str) -> str:
    """JSON mode 会吞掉单反斜杠；先把 \\frac \\Delta 之类补成双反斜杠。"""
    return re.sub(rf"(?<!\\)\\(?=(?:{LATEX_COMMANDS})\b)", lambda _: "\\\\", raw)


def _fix_latex_text(text: str) -> str:
    if "$" not in text:
        return text
    return re.sub(rf"(?<!\\)\b({LATEX_COMMANDS})\b", r"\\\1", text)


def extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("输出里没有 JSON 对象")
    candidate = _escape_latex_json(text[start : end + 1])
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        if json_repair is None:
            raise
        payload = json_repair.loads(candidate)
    if not isinstance(payload, dict):
        raise ValueError("JSON 顶层不是对象")
    return payload


def deep_fix_latex(value: Any) -> Any:
    if isinstance(value, str):
        return _fix_latex_text(value)
    if isinstance(value, list):
        return [deep_fix_latex(item) for item in value]
    if isinstance(value, dict):
        return {key: deep_fix_latex(item) for key, item in value.items()}
    return value


def build_repair_prompt(issues: list[str], schema_hint: str = "") -> str:
    body = "\n".join(f"- {issue}" for issue in issues)
    hint = f"\n输出必须严格符合这个结构：\n{schema_hint}\n" if schema_hint else ""
    return (
        "你上一次的输出有以下问题，必须全部修掉后重新输出**完整**的 JSON（不要解释、不要省略字段）：\n"
        f"{body}\n{hint}"
    )


def _schema_hint(schema: type[BaseModel]) -> str:
    try:
        return json.dumps(schema.model_json_schema(), ensure_ascii=False)[:3000]
    except Exception:
        return ""


def run_structured(
    *,
    client: LLMClient,
    system: str,
    user: str,
    schema: type[T],
    checks: Callable[[T], list[str]] | None = None,
    preprocess: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    max_repairs: int = 1,
    temperature: float = 0.2,
    max_tokens: int = 6000,
    messages: list[dict[str, str]] | None = None,
) -> NodeResult[T]:
    """跑一个结构化节点，带校验与修复环。checks 返回非空即触发一次修复。"""
    msgs = messages or [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_latency = 0
    log: list[dict[str, Any]] = []
    last_value: T | None = None
    last_issues: list[str] = []
    last_raw = ""
    hint = _schema_hint(schema)

    for attempt in range(1, max_repairs + 2):
        raw, usage, latency = client.chat_json(
            msgs, temperature=temperature, max_tokens=max_tokens
        )
        last_raw = raw
        for key in total_usage:
            total_usage[key] += int(usage.get(key, 0) or 0)
        total_latency += latency

        try:
            payload = extract_json(raw)
            payload = deep_fix_latex(payload)
            if preprocess:
                payload = preprocess(payload)
            value = schema.model_validate(payload)
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            issue = f"不符合 schema：{type(exc).__name__}: {exc}"[:600]
            last_issues = [issue]
            log.append({"attempt": attempt, "ok": False, "issues": last_issues, "latency_ms": latency, "usage": usage})
            msgs = msgs + [
                {"role": "assistant", "content": raw or "{}"},
                {"role": "user", "content": build_repair_prompt(last_issues, hint)},
            ]
            continue

        business_issues = checks(value) if checks else []
        log.append(
            {
                "attempt": attempt,
                "ok": not business_issues,
                "issues": business_issues,
                "latency_ms": latency,
                "usage": usage,
            }
        )
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
                log=log,
            )

        msgs = msgs + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": build_repair_prompt(business_issues, hint)},
        ]

    return NodeResult(
        value=last_value,
        raw=last_raw,
        issues=last_issues,
        attempts=max_repairs + 1,
        usage=total_usage,
        latency_ms=total_latency,
        log=log,
    )


def call_json(
    client: LLMClient,
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 4000,
) -> tuple[dict[str, Any], dict[str, int], int]:
    """不需要 schema 的一次性结构化调用（两段式 agent 的第一段用）。"""
    raw, usage, latency = client.chat_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return extract_json(raw), usage, latency
