from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

try:
    import json_repair
except ImportError:  # pragma: no cover
    json_repair = None

from core.llm import LLMClient
from core.quiz_prompts import (
    build_quiz_repair_prompt,
    build_quiz_system_prompt,
    build_quiz_user_prompt,
)
from core.quiz_schema import QuizQuestion
from core.schema import TeachingRequest, TeachingTurn


@dataclass
class QuizResult:
    response: QuizQuestion | None
    raw: str
    issues: list[str] = field(default_factory=list)
    attempts: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    attempt_log: list[dict[str, Any]] = field(default_factory=list)


def _extract_json(raw: str) -> dict[str, Any]:
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


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("*", "").replace("`", ""))


def check_quiz(quiz: QuizQuestion, teaching: TeachingTurn, req: TeachingRequest) -> list[str]:
    issues: list[str] = []

    if quiz.stem.count("？") + quiz.stem.count("?") > 2:
        issues.append("题干里有超过两个问句，像多道题；只保留一道")
    if re.search(r"第\s*[2-9]\s*题|第[二三四五六七八九]题", quiz.stem):
        issues.append("题干出现“第 2 题”等字样；只能出一道题")

    if quiz.kind == "choice":
        if any(bad in quiz.stem for bad in ["以下哪些", "多选", "以上都"]):
            issues.append("选择题不得出现多选/以上都；只能单选")
    else:
        if len(quiz.answer) > 40:
            issues.append("填空题答案太长；应短、唯一、可判定")

    quote = _norm(quiz.source_quote)
    reply = _norm(teaching.reply_markdown)
    if quote and quote not in reply:
        issues.append("source_quote 不是 teaching_turn.reply_markdown 的原句；题目缺少依据")

    if not any(marker in quiz.why_this_question for marker in ["卡", "这轮", "刚才", "学生说", "你问", "这一步", "这个动作"]):
        issues.append("why_this_question 没有具体对上学生这一轮的卡点")

    if quiz.confidence == "low":
        issues.append("confidence=low 的题不要直接给学生；请改成更确定的一道")

    return list(dict.fromkeys(issues))


def run_quiz_node(
    req: TeachingRequest,
    teaching: TeachingTurn,
    client: LLMClient,
    max_repairs: int = 2,
    temperature: float = 0.25,
) -> QuizResult:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_quiz_system_prompt(req)},
        {"role": "user", "content": build_quiz_user_prompt(req, teaching)},
    ]

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_latency = 0
    attempt_log: list[dict[str, Any]] = []
    last_response: QuizQuestion | None = None
    last_raw = ""
    last_valid_raw = ""
    last_check_issues: list[str] = []
    last_schema_issues: list[str] = []

    for attempt in range(1, max_repairs + 2):
        try:
            raw, usage, latency_ms = client.chat_json(messages, temperature=temperature)
        except Exception as exc:  # noqa: BLE001
            import time

            last_schema_issues = [f"LLM 调用失败：{type(exc).__name__}: {str(exc)[:200]}"]
            attempt_log.append(
                {
                    "attempt": attempt,
                    "ok": False,
                    "issues": last_schema_issues,
                    "usage": {},
                    "latency_ms": 0,
                    "raw_preview": "",
                }
            )
            time.sleep(0.5 * attempt)
            continue
        last_raw = raw
        for key in total_usage:
            total_usage[key] += int(usage.get(key, 0) or 0)
        total_latency += latency_ms

        try:
            payload = _extract_json(raw)
            quiz = QuizQuestion.model_validate(payload)
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            last_schema_issues = [f"输出不是合法 JSON 或不符合 schema：{type(exc).__name__}: {exc}"[:800]]
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
                    {"role": "user", "content": build_quiz_repair_prompt(last_schema_issues)},
                ]
            )
            continue

        last_response = quiz
        last_valid_raw = raw
        last_check_issues = check_quiz(quiz, teaching, req)
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
            return QuizResult(
                response=quiz,
                raw=raw,
                issues=[],
                attempts=attempt,
                usage=total_usage,
                latency_ms=total_latency,
                attempt_log=attempt_log,
            )

        messages.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": build_quiz_repair_prompt(last_check_issues)},
            ]
        )

    return QuizResult(
        response=last_response,
        raw=last_valid_raw or last_raw,
        issues=last_check_issues if last_response else last_schema_issues,
        attempts=max_repairs + 1,
        usage=total_usage,
        latency_ms=total_latency,
        attempt_log=attempt_log,
    )
