"""v3 教学图：讲练合一的三个节点。

    START → lesson（一次调用：讲义 + 3 题）
              → wait（interrupt，等学生答当前这题）
                → judge（判题 + 更新学生模型）
                   ├─ 还有题  → wait（下一题）
                   ├─ 答完 3 题 → lesson（下一轮，讲更深一层）
                   └─ 达到轮数  → END

相对 v2：
    - 节点从 4 个减到 3 个，单轮 LLM 调用从 2 次减到 1 次（首屏靠流式，不靠等）；
    - 判题换成 SymPy 符号等价（见 core/judge.py）；
    - 每轮 3 题，题与讲义同源，避免「讲洛必达、考泰勒」。
"""

from __future__ import annotations

import sqlite3
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from core.config import load_config
from core.judge import judge as judge_answer
from core.llm import LLMClient
from core.nodes import (
    build_request,
    format_lesson_for_history,
    public_question,
    run_lesson_practice,
    unregister_stream_sink,
    _STREAM_SINKS,
)
from core.scoring import score_teaching
from core.student import (
    connect as connect_student_db,
    get_profile,
    record_attempt,
    record_mistake,
    resolve_mistake,
)
from core.trace import Tracer

MAX_HISTORY_TURNS = 20
QUESTIONS_PER_ROUND = 3
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_TRACE = ROOT / "runs" / "trace.jsonl"


class TutorState(TypedDict, total=False):
    session_id: str
    student_id: str
    topic: str
    level: str
    subject: str
    prior_knowledge: str
    misconceptions: str
    learner_note: str
    max_rounds: int
    round: int
    student_message: str
    history: list[dict[str, str]]
    teaching: dict[str, Any] | None
    questions: list[dict[str, Any]]
    q_index: int
    question: dict[str, Any] | None
    answer: str
    answers: list[dict[str, Any]]
    judgement: dict[str, Any] | None
    score: dict[str, Any] | None
    tokens_used: int
    token_budget: int
    ttft_ms: int
    status: str
    error: str | None


@lru_cache(maxsize=1)
def get_client() -> LLMClient:
    return LLMClient(load_config())


@lru_cache(maxsize=1)
def get_student_conn() -> sqlite3.Connection:
    return connect_student_db(DATA_DIR / "students.db")


@lru_cache(maxsize=1)
def get_tracer() -> Tracer:
    return Tracer(DEFAULT_TRACE)


def _history_append(state: TutorState, role: str, content: str) -> list[dict[str, str]]:
    history = list(state.get("history", []))
    history.append({"role": role, "content": content})
    return history[-MAX_HISTORY_TURNS:]


def _learner_note(state: TutorState) -> str:
    try:
        profile = get_profile(
            get_student_conn(),
            student_id=state.get("student_id") or "anonymous",
            subject=state.get("subject", "数学"),
            mistake_limit=3,
        )
    except Exception:  # noqa: BLE001
        return ""
    parts: list[str] = []
    if profile.kps:
        ordered = sorted(profile.kps, key=lambda x: x["mastery"])
        parts.append("历史掌握度最低的三个点：" + "、".join(
            f"{k['kp']}({k['mastery']:.0%})" for k in ordered[:3]))
    if profile.mistakes:
        recent = "；".join(m["kp"] for m in profile.mistakes[:3] if m["kp"])
        if recent:
            parts.append(f"最近做错过的点：{recent}")
    return "；".join(parts)


def _budget_left(state: TutorState) -> int:
    return int(state.get("token_budget", 60000)) - int(state.get("tokens_used", 0))


def lesson_node(state: TutorState) -> dict[str, Any]:
    """讲练合一：一次调用产出讲义 + 3 题。"""
    tracer = get_tracer()
    if _budget_left(state) <= 0:
        return {"status": "degraded", "error": "token 预算已用完"}

    req = build_request(state, _learner_note(state) if state.get("round", 0) > 0 else "")

    sink = _STREAM_SINKS.get(state.get("session_id", ""))
    result = run_lesson_practice(req, get_client(), on_markdown=sink)

    tracer.event(
        "node",
        session_id=state.get("session_id"),
        node="lesson",
        attempt=state.get("round", 0),
        attempts=result.attempts,
        ok=bool(result.payload) and not result.issues,
        issues=result.issues[:5],
        total_tokens=result.usage.get("total_tokens", 0),
        latency_ms=result.latency_ms,
        ttft_ms=result.ttft_ms,
        questions=len(result.payload.questions) if result.payload else 0,
    )

    tokens = int(state.get("tokens_used", 0)) + int(result.usage.get("total_tokens", 0))
    if not result.payload:
        return {
            "status": "error",
            "error": "讲练节点失败：" + "；".join(result.issues[:3]),
            "tokens_used": tokens,
        }

    payload = result.payload
    teaching = payload.teaching.model_dump()
    cards = [card.model_dump() for card in payload.questions]
    card = score_teaching(payload.teaching, req, issues=result.issues, attempts=result.attempts)

    student_text = state.get("student_message") or state["topic"]
    history = _history_append(state, "student", student_text)
    history = history + [{"role": "teacher", "content": format_lesson_for_history(teaching, cards)}]

    status = "degraded" if tokens >= int(state.get("token_budget", 60000)) else "awaiting_answer"
    return {
        "teaching": teaching,
        "questions": cards,
        "q_index": 0,
        "question": cards[0],
        "score": card.as_dict(),
        "history": history[-MAX_HISTORY_TURNS:],
        "student_message": "",
        "status": status,
        "tokens_used": tokens,
        "ttft_ms": result.ttft_ms,
        "error": None,
    }


def wait_node(state: TutorState) -> dict[str, Any]:
    card = state.get("question") or (state.get("questions") or [None])[0]
    answer = interrupt(
        {
            "type": "question_answer_required",
            "round": state.get("round", 0),
            "index": int(state.get("q_index", 0)),
            "total": len(state.get("questions", [])),
            "question": public_question(card),
            "score": state.get("score"),
            "ttft_ms": state.get("ttft_ms", 0),
        }
    )
    return {"answer": str(answer), "status": "answered"}


def judge_node(state: TutorState) -> dict[str, Any]:
    tracer = get_tracer()
    card = state.get("question") or {}
    verdict = judge_answer(card, state.get("answer", ""), client=get_client())

    tracer.event(
        "judge",
        session_id=state.get("session_id"),
        layer=verdict.layer,
        correct=verdict.correct,
        kp=(card.get("tested_points") or [None])[0],
    )

    kp = (card.get("tested_points") or ["未标注知识点"])[0]
    student_id = state.get("student_id") or "anonymous"
    subject = state.get("subject", "数学")
    conn = get_student_conn()

    record_attempt(conn, student_id=student_id, subject=subject, kp=kp, correct=verdict.correct)
    if verdict.correct:
        resolve_mistake(conn, student_id=student_id, subject=subject, kp=kp)
    else:
        record_mistake(
            conn,
            student_id=student_id,
            subject=subject,
            kp=kp,
            question=card.get("stem", ""),
            student_answer=str(state.get("answer", "")),
            correct_answer=card.get("answer", ""),
        )

    feedback = (
        f"答对了。{card.get('explanation', '')}"
        if verdict.correct
        else f"这题答错了。正确答案是 {card.get('answer', '')}。{card.get('explanation', '')}"
    )
    judgement = {
        "correct": verdict.correct,
        "layer": verdict.layer,
        "correct_answer": card.get("answer", ""),
        "feedback": feedback,
        "reason": verdict.reason,
        "index": int(state.get("q_index", 0)),
    }

    history = _history_append(state, "student", str(state.get("answer", "")))
    history = history + [{"role": "teacher", "content": feedback}]

    answers = list(state.get("answers", [])) + [judgement]
    next_index = int(state.get("q_index", 0)) + 1
    questions = state.get("questions", [])

    if next_index < len(questions):
        return {
            "judgement": judgement,
            "answers": answers,
            "q_index": next_index,
            "question": questions[next_index],
            "history": history[-MAX_HISTORY_TURNS:],
            "status": "awaiting_answer",
            "answer": "",
        }

    next_round = int(state.get("round", 0)) + 1
    max_rounds = int(state.get("max_rounds", 3))
    if next_round >= max_rounds or _budget_left(state) <= 0:
        return {
            "judgement": judgement,
            "answers": answers,
            "history": history[-MAX_HISTORY_TURNS:],
            "status": "done",
            "round": next_round,
            "teaching": None,
            "question": None,
            "answer": "",
        }

    correct_count = sum(1 for a in answers if a.get("correct"))
    if correct_count == len(answers):
        next_message = "这 3 题我都答对了。请在这个点上再往下讲一层，再给我 3 道更难的题。"
    else:
        next_message = (
            f"这 3 题我答错了 {len(answers) - correct_count} 道，正确答案分别是 "
            f"{'、'.join(str(a.get('correct_answer')) for a in answers if not a.get('correct'))}。"
            "请针对这些卡点再讲一遍，再出 3 道题。"
        )

    return {
        "judgement": judgement,
        "answers": answers,
        "history": history[-MAX_HISTORY_TURNS:],
        "status": "teaching",
        "round": next_round,
        "q_index": 0,
        "question": None,
        "questions": [],
        "student_message": next_message,
        "answer": "",
        "teaching": None,
    }


def degrade_node(state: TutorState) -> dict[str, Any]:
    get_tracer().event("degrade", session_id=state.get("session_id"), round=state.get("round", 0))
    note = (
        "本轮先到这里。下次我们从这一点接着讲；先把上面那道题的解法自己复述一遍，"
        "比继续刷新题更有用。"
    )
    return {"status": "degraded", "error": None, "history": _history_append(state, "teacher", note)}


def route_after_lesson(state: TutorState) -> Literal["wait", "degrade", "fail"]:
    if state.get("status") == "error":
        return "fail"
    if state.get("status") == "degraded":
        return "degrade"
    return "wait"


def route_after_judge(state: TutorState) -> Literal["wait", "lesson", "end"]:
    status = state.get("status")
    if status in ("done", "degraded"):
        return "end"
    if status == "awaiting_answer":
        return "wait"
    return "lesson"


def build_graph(checkpointer: SqliteSaver | None = None):
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATA_DIR / "checkpoints.sqlite"), check_same_thread=False)
    return SqliteSaver(conn)


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()


def new_session_id() -> str:
    return str(uuid.uuid4())


def initial_state(
    *,
    topic: str,
    level: str = "大学低年级",
    subject: str = "数学一",
    prior_knowledge: str = "",
    misconceptions: str = "",
    student_message: str = "",
    max_rounds: int = 3,
    student_id: str = "anonymous",
    token_budget: int = 60000,
    session_id: str | None = None,
) -> tuple[str, TutorState]:
    sid = session_id or new_session_id()
    state: TutorState = {
        "session_id": sid,
        "student_id": student_id,
        "topic": topic,
        "level": level,
        "subject": subject,
        "prior_knowledge": prior_knowledge,
        "misconceptions": misconceptions,
        "max_rounds": max_rounds,
        "round": 0,
        "student_message": student_message,
        "history": [],
        "teaching": None,
        "questions": [],
        "q_index": 0,
        "question": None,
        "answer": "",
        "answers": [],
        "judgement": None,
        "score": None,
        "tokens_used": 0,
        "token_budget": token_budget,
        "ttft_ms": 0,
        "status": "new",
        "error": None,
    }
    return sid, state
