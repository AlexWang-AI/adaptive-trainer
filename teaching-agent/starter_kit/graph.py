"""LangGraph 单写者流程：lesson → wait → judge → policy。

对应真实项目的 `v3core/graph.py`，但把「讲义 + 题卡」简化为 2 题，
并把「独立答案键 / 幂等写入 / 预算降级」显式写出来。

图：
    START → lesson（唯一写者）
              → wait（interrupt，等学生答当前题）
                → judge（确定性判题 + 写学生库）
                   ├─ 还有题 → wait
                   ├─ 答完一轮 → lesson（下一轮，最多 max_rounds）
                   └─ 轮数/预算用完 → END
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from content import get_answer_key, get_pack, get_questions
from contracts import LessonPayload, QuestionCard
from judge import judge_answer, normalize_text
from llm import LLMClient
from student_store import connect as connect_student_db, record_attempt
from structured import run_structured
from trace import Tracer

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DEFAULT_BUDGET = 8000
QUESTIONS_PER_ROUND = 2
_OVERRIDES: dict[str, Any] = {}


class TutorState(TypedDict, total=False):
    session_id: str
    student_id: str
    kp_id: str
    level: str
    round: int
    max_rounds: int
    lesson: dict[str, Any] | None
    questions: list[dict[str, Any]]
    q_index: int
    question: dict[str, Any] | None
    answer: str
    student_message: str
    judgement: dict[str, Any] | None
    answers: list[dict[str, Any]]
    history: list[dict[str, str]]
    tokens: int
    token_budget: int
    status: str
    error: str | None


@lru_cache(maxsize=1)
def get_client():
    if "client" in _OVERRIDES:
        return _OVERRIDES["client"]
    if os.getenv("STARTER_KIT_MODE", "fake").lower() == "real":
        return LLMClient()
    from fake_llm import FakeLLM

    return FakeLLM(mutate=os.getenv("STARTER_KIT_MUTATE", "0") == "1")


@lru_cache(maxsize=1)
def get_student_conn() -> sqlite3.Connection:
    if "student_conn" in _OVERRIDES:
        return _OVERRIDES["student_conn"]
    return connect_student_db(DATA / "students.db")


@lru_cache(maxsize=1)
def get_tracer() -> Tracer:
    if "tracer" in _OVERRIDES:
        return _OVERRIDES["tracer"]
    return Tracer(ROOT / "runs" / "trace.jsonl")


def public_question(card: dict[str, Any] | None) -> dict[str, Any] | None:
    if not card:
        return None
    return {
        "id": card["id"],
        "kind": card["kind"],
        "stem": card["stem"],
        "options": card.get("options", []),
        "difficulty": card.get("difficulty", "medium"),
        "tested_points": card.get("tested_points", []),
    }


def _check_lesson(payload: LessonPayload, kp_id: str) -> list[str]:
    issues: list[str] = []
    valid_ids = {q.id for q in get_questions(kp_id)}
    ids = {q.id for q in payload.questions}
    if not ids <= valid_ids:
        issues.append(f"题号不在题库里：{sorted(ids - valid_ids)}")
    if len(ids) != len(payload.questions):
        issues.append("题号重复")
    kinds = {q.kind for q in payload.questions}
    if "choice" not in kinds:
        issues.append("至少要有 1 道选择题")
    if "fill" not in kinds:
        issues.append("至少要有 1 道填空题")
    if not any(q.variant_of for q in payload.questions):
        issues.append("至少要有 1 道变式题（variant_of 指向母题）")
    reply = normalize_text(payload.teaching.reply_markdown)
    for q in payload.questions:
        quote = normalize_text(q.source_quote)
        if len(quote) >= 6 and quote not in reply:
            issues.append(f"{q.id} 的 source_quote 不在讲义里")
    return issues


def lesson_node(state: TutorState) -> dict[str, Any]:
    tracer = get_tracer()
    kp_id = state["kp_id"]
    pack = get_pack(kp_id)
    bank_ids = [q.id for q in get_questions(kp_id)]
    system = (
        f"你是数学老师。这一轮只讲一层，并出 2 道题（1 原题 + 1 变式）。\n"
        f"[KP:{kp_id}] {pack.name}\n"
        f"要点：{'；'.join(pack.points)}\n"
        f"例子：{pack.example}\n"
        f"常见误解：{'；'.join(pack.misconceptions)}\n"
        f"题号只能从这些里选：{', '.join(bank_ids)}。\n"
        "输出 JSON：teaching{reply_markdown, core_idea, check_question, confidence} + "
        "questions[{id, kind, stem, options, answer, explanation, tested_points, difficulty, "
        "source_quote, variant_of, confidence}]。"
    )
    user = state.get("student_message") or "开始吧"
    result = run_structured(
        client=get_client(),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        schema=LessonPayload,
        checks=lambda p: _check_lesson(p, kp_id),
        max_repairs=1,
    )
    tokens = int(state.get("tokens", 0)) + int(result.usage.get("total_tokens", 0))
    tracer.event(
        "node",
        session_id=state.get("session_id"),
        node="lesson",
        attempts=result.attempts,
        tokens=int(result.usage.get("total_tokens", 0)),
        latency_ms=result.latency_ms,
        ok=result.value is not None and not result.issues,
        detail="；".join(result.issues[:3]),
    )
    if result.value is None or result.issues:
        return {"status": "error", "error": "讲练节点失败：" + "；".join(result.issues[:3]), "tokens": tokens}

    payload = result.value
    cards = [q.model_dump() for q in payload.questions]
    history = list(state.get("history", []))
    history.append({"role": "teacher", "content": payload.teaching.reply_markdown})
    status = "degraded" if tokens >= int(state.get("token_budget", DEFAULT_BUDGET)) else "awaiting_answer"
    return {
        "lesson": payload.teaching.model_dump(),
        "questions": cards,
        "q_index": 0,
        "question": cards[0],
        "history": history[-8:],
        "tokens": tokens,
        "status": status,
        "error": None,
        "student_message": "",
    }


def wait_node(state: TutorState) -> dict[str, Any]:
    card = state.get("question") or (state.get("questions") or [None])[0]
    answer = interrupt(
        {
            "type": "question_answer_required",
            "round": int(state.get("round", 0)),
            "index": int(state.get("q_index", 0)),
            "total": len(state.get("questions", [])),
            "question": public_question(card),
        }
    )
    return {"answer": str(answer), "status": "answered"}


def judge_node(state: TutorState) -> dict[str, Any]:
    tracer = get_tracer()
    card = state.get("question") or {}
    key = get_answer_key(card["id"])
    verdict = judge_answer(QuestionCard.model_validate(card), str(state.get("answer", "")), key)
    tracer.event(
        "judge",
        session_id=state.get("session_id"),
        question_id=card["id"],
        layer=verdict.layer,
        correct=verdict.correct,
    )

    attempt_id = f"{state['session_id']}:{int(state.get('round', 0))}:{card['id']}"
    inserted = record_attempt(
        get_student_conn(),
        attempt_id=attempt_id,
        student_id=state.get("student_id", "anonymous"),
        kp_id=state["kp_id"],
        question_id=card["id"],
        correct=verdict.correct,
        layer=verdict.layer,
        is_variant=bool(card.get("variant_of")),
        answer=str(state.get("answer", "")),
        correct_answer=key.answer,
    )
    if not inserted:
        tracer.event("duplicate_attempt", session_id=state.get("session_id"), question_id=card["id"])

    feedback = (
        f"答对了。{card.get('explanation', '')}"
        if verdict.correct
        else f"这题不对。正确答案是 {key.answer}。{card.get('explanation', '')}"
    )
    history = list(state.get("history", []))
    history.append({"role": "student", "content": str(state.get("answer", ""))})
    history.append({"role": "teacher", "content": feedback})
    answers = list(state.get("answers", [])) + [
        {"question_id": card["id"], "correct": verdict.correct, "layer": verdict.layer,
         "reason": verdict.reason, "correct_answer": key.answer}
    ]
    next_index = int(state.get("q_index", 0)) + 1
    questions = state.get("questions", [])

    if next_index < len(questions):
        return {
            "judgement": verdict.model_dump(),
            "answers": answers,
            "q_index": next_index,
            "question": questions[next_index],
            "history": history[-8:],
            "status": "awaiting_answer",
            "answer": "",
        }

    next_round = int(state.get("round", 0)) + 1
    if next_round >= int(state.get("max_rounds", 2)) or int(state.get("tokens", 0)) >= int(state.get("token_budget", DEFAULT_BUDGET)):
        return {
            "judgement": verdict.model_dump(),
            "answers": answers,
            "history": history[-8:],
            "status": "done",
            "round": next_round,
            "question": None,
            "answer": "",
        }

    correct_count = sum(1 for a in answers if a.get("correct"))
    next_message = (
        "这一轮我都答对了，请再讲深一层，并再出 2 道题。"
        if correct_count == len(answers)
        else f"这一轮我答错了 {len(answers) - correct_count} 道，请针对卡点再讲一层，再出 2 道题。"
    )
    return {
        "judgement": verdict.model_dump(),
        "answers": answers,
        "history": history[-8:],
        "status": "teaching",
        "round": next_round,
        "q_index": 0,
        "question": None,
        "questions": [],
        "answer": "",
        "student_message": next_message,
    }


def degrade_node(state: TutorState) -> dict[str, Any]:
    get_tracer().event("degrade", session_id=state.get("session_id"), round=state.get("round", 0))
    return {"status": "degraded", "error": None}


def route_after_lesson(state: TutorState) -> Literal["wait", "degrade", "fail"]:
    if state.get("status") == "error":
        return "fail"
    if state.get("status") == "degraded":
        return "degrade"
    return "wait"


def route_after_judge(state: TutorState) -> Literal["wait", "lesson", "end"]:
    if state.get("status") == "done":
        return "end"
    if state.get("status") == "awaiting_answer":
        return "wait"
    return "lesson"


def build_graph(checkpointer: SqliteSaver | None = None, *, client=None, student_conn=None, tracer=None):
    if client is not None:
        _OVERRIDES["client"] = client
    if student_conn is not None:
        _OVERRIDES["student_conn"] = student_conn
    if tracer is not None:
        _OVERRIDES["tracer"] = tracer
    for fn in (get_client, get_student_conn, get_tracer):
        fn.cache_clear()
    graph = StateGraph(TutorState)
    graph.add_node("lesson", lesson_node)
    graph.add_node("wait", wait_node)
    graph.add_node("judge", judge_node)
    graph.add_node("degrade", degrade_node)
    graph.add_edge(START, "lesson")
    graph.add_conditional_edges("lesson", route_after_lesson, {"wait": "wait", "degrade": "degrade", "fail": END})
    graph.add_edge("wait", "judge")
    graph.add_conditional_edges("judge", route_after_judge, {"wait": "wait", "lesson": "lesson", "end": END})
    graph.add_edge("degrade", END)
    return graph.compile(checkpointer=checkpointer or default_checkpointer())


@lru_cache(maxsize=1)
def default_checkpointer() -> SqliteSaver:
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATA / "checkpoints.sqlite"), check_same_thread=False)
    return SqliteSaver(conn)


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()


def initial_state(
    *,
    kp_id: str,
    student_id: str = "student-1",
    level: str = "大学低年级",
    max_rounds: int = 2,
    token_budget: int = DEFAULT_BUDGET,
    session_id: str | None = None,
) -> tuple[str, TutorState]:
    sid = session_id or uuid.uuid4().hex[:12]
    return sid, {
        "session_id": sid,
        "student_id": student_id,
        "kp_id": kp_id,
        "level": level,
        "round": 0,
        "max_rounds": max_rounds,
        "lesson": None,
        "questions": [],
        "q_index": 0,
        "question": None,
        "answer": "",
        "student_message": "",
        "judgement": None,
        "answers": [],
        "history": [],
        "tokens": 0,
        "token_budget": token_budget,
        "status": "new",
        "error": None,
    }
