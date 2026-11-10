from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

try:
    import json_repair
except ImportError:  # pragma: no cover
    json_repair = None

from checks import check_turn
from llm import LLMClient
from prompts import build_repair_prompt, build_system_prompt, build_user_prompt
from schema import TeachingRequest, TeachingTurn


@dataclass
class NodeResult:
    response: TeachingTurn | None
    raw: str
    issues: list[str] = field(default_factory=list)
    attempts: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    attempt_log: list[dict[str, Any]] = field(default_factory=list)
    variant: str = "B"


def extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    start = text.find("{")
    end = text.rfind("}")
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


def _short_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    return text[:800]


def run_teaching_node(
    req: TeachingRequest,
    client: LLMClient,
    variant: str = "B",
    max_repairs: int = 2,
    temperature: float = 0.3,
) -> NodeResult:
    variant = variant.upper()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(req, variant)},
        {"role": "user", "content": build_user_prompt(req)},
    ]

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_latency = 0
    attempt_log: list[dict[str, Any]] = []
    last_response: TeachingTurn | None = None
    last_raw = ""
    last_valid_raw = ""
    last_check_issues: list[str] = []
    last_schema_issues: list[str] = []

    for attempt in range(1, max_repairs + 2):
        raw, usage, latency_ms = client.chat_json(messages, temperature=temperature)
        last_raw = raw
        for key in total_usage:
            total_usage[key] += int(usage.get(key, 0) or 0)
        total_latency += latency_ms

        try:
            payload = extract_json(raw)
            response = TeachingTurn.model_validate(payload)
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            last_schema_issues = [f"输出不是合法 JSON 或不符合 schema：{_short_error(exc)}"]
            attempt_log.append(
                {
                    "attempt": attempt,
                    "ok": False,
                    "issues": last_schema_issues,
                    "usage": usage,
                    "latency_ms": latency_ms,
                    "raw_preview": raw[:300],
                }
            )
            messages.extend(
                [
                    {"role": "assistant", "content": raw or "{}"},
                    {"role": "user", "content": build_repair_prompt(last_schema_issues)},
                ]
            )
            continue

        last_response = response
        last_valid_raw = raw
        last_check_issues = check_turn(response, req)
        last_schema_issues = []
        attempt_log.append(
            {
                "attempt": attempt,
                "ok": not last_check_issues,
                "issues": last_check_issues,
                "usage": usage,
                "latency_ms": latency_ms,
                "raw_preview": raw[:300],
            }
        )

        if not last_check_issues:
            return NodeResult(
                response=response,
                raw=raw,
                issues=[],
                attempts=attempt,
                usage=total_usage,
                latency_ms=total_latency,
                attempt_log=attempt_log,
                variant=variant,
            )

        messages.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": build_repair_prompt(last_check_issues)},
            ]
        )

    return NodeResult(
        response=last_response,
        raw=last_valid_raw or last_raw,
        issues=last_check_issues if last_response else last_schema_issues,
        attempts=max_repairs + 1,
        usage=total_usage,
        latency_ms=total_latency,
        attempt_log=attempt_log,
        variant=variant,
    )
