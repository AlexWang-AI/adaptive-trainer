"""v3 教学图：讲练合一。

    START → lesson（一次调用：讲义 + 3 题）→ END

判题是旁路（/api/judge），前端逐题判、不整篇回传，所以图里只有 lesson 一个节点；
之前留着 interrupt 的 wait/judge 节点，但全项目没有 Command(resume=)，每次讲课都会
留下一个永远不会被恢复的 checkpoint（已累积 117 个 thread），已删除（红队 P1-3）。

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

from v3core.judge import judge as judge_answer
from v3core.llm import LLMClient
from v3core.nodes import (
    build_request,
    format_lesson_for_history,
    public_question,
    run_lesson_practice,
    unregister_stream_sink,
    _STREAM_SINKS,
)
from v3core.scoring import score_teaching
from v3core.student import (
    get_profile,
    record_attempt,
    record_mistake,
    resolve_mistake,
)
from v3core.trace import Tracer

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
    kp: str
    prior_knowledge: str
    misconceptions: str
    learner_note: str
    textbook_block: str
    textbook_ref: str
    type_names: list[str]
    focus: str
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
    """共享单例（红队 P2-7）。保留薄封装是因为测试会 monkeypatch 它。"""
    from v3core.clients import get_llm_client

    return get_llm_client()


@lru_cache(maxsize=1)
def get_student_conn():
    """与 api_server 共用同一个连接代理：同文件、同写锁、每线程一条真实连接（红队 P1-11）。"""
    from v3core.db import connection
    from v3core.learning import SCHEMA as LEARNING_SCHEMA
    from v3core.student import SCHEMA as STUDENT_SCHEMA

    return connection(DATA_DIR / "students.db", schema=STUDENT_SCHEMA + LEARNING_SCHEMA)


def get_learning_conn():
    # 复习队列和作答记录在同一个库文件里，必须用同一个代理，
    # 否则两个连接各持一把写锁，跨表事务就退化成两次独立提交
    return get_student_conn()


@lru_cache(maxsize=1)
def get_tracer() -> Tracer:
    return Tracer(DEFAULT_TRACE)


def _history_append(state: TutorState, role: str, content: str) -> list[dict[str, str]]:
    history = list(state.get("history", []))
    history.append({"role": role, "content": content})
    return history[-MAX_HISTORY_TURNS:]


def _kp_label(kp_id: str) -> str:
    """内部 id（der.definition）→ 学生看得懂的中文名；认不出来的返回空串。

    curriculum 只有后端进程里有，v3core 本身不依赖它，所以懒加载 + 兜底。
    注意空串的语义：这个 id 不在当前课程表里（多半是旧版本遗留的脏数据），
    宁可整条不写，也不要把 `ser.p_series 72%` 这种内部 id 喂给模型。
    """
    try:
        from curriculum import KP_TABLE
    except Exception:  # noqa: BLE001
        return kp_id
    meta = KP_TABLE.get(kp_id)
    return str(meta["name"]) if meta and meta.get("name") else ""


def learner_note(state: dict[str, Any]) -> str:
    """把跨会话的学习历史压成一句画像，交给提示词（schema 上限 400 字）。

    为什么要有「本轮知识点」单独一段：历史里「掌握度最低的三个点」往往来自别的章节，
    模型拿到的全是无关信息；真正决定这一讲讲多细的，是「这个点你练过几次、上次错在哪」。
    红队 P1-4：这段以前被 `round > 0` 挡住，而图里 round 恒为 0 —— 画像从未生效。
    """
    student_id = str(state.get("student_id") or "anonymous")
    subject = str(state.get("subject") or "数学一")
    kp_id = str(state.get("kp") or "")
    parts: list[str] = []

    profile = None
    try:
        profile = get_profile(
            get_student_conn(), student_id=student_id, subject=subject, mistake_limit=3
        )
    except Exception:  # noqa: BLE001
        profile = None

    if profile and profile.kps:
        ordered = sorted(profile.kps, key=lambda x: x["mastery"])
        # 只算「确实薄」的点：练到 80% 以上还叫薄弱点，等于给模型喂噪音
        weak_items: list[str] = []
        for item in ordered[:3]:
            if item["kp"] == kp_id or item["mastery"] >= 0.8:
                continue
            label = _kp_label(str(item["kp"]))
            if label:  # 认不出来的旧 id 直接丢掉，不给模型看内部主键
                weak_items.append(f"{label} {item['mastery']:.0%}")
        if weak_items:
            parts.append("历史薄弱点：" + "、".join(weak_items))

    if profile and kp_id:
        row = next((k for k in profile.kps if k["kp"] == kp_id), None)
        if row and int(row.get("attempts", 0)) > 0:
            label = _kp_label(kp_id) or kp_id
            parts.append(
                f"本轮知识点「{label}」：作答 {int(row['attempts'])} 次、"
                f"答对 {int(row['correct'])} 次，掌握度 {row['mastery']:.0%}"
            )

    if kp_id:
        try:
            from v3core.learning import latest_misconception

            mis = latest_misconception(get_learning_conn(), student_id=student_id, kp_id=kp_id)
            if mis:
                parts.append(f"上次诊断出的认知偏差：{mis[:60]}")
        except Exception:  # noqa: BLE001
            pass

    note = "；".join(parts)
    return note if len(note) <= 400 else note[:396] + "…"


def _budget_left(state: TutorState) -> int:
    return int(state.get("token_budget", 60000)) - int(state.get("tokens_used", 0))


def lesson_node(state: TutorState) -> dict[str, Any]:
    """讲练合一：一次调用产出讲义 + 3 题。"""
    tracer = get_tracer()
    if _budget_left(state) <= 0:
        return {"status": "degraded", "error": "token 预算已用完"}

    note = state.get("learner_note") or learner_note(state)
    req = build_request(state, note)

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
        hard=[a.get("issues") for a in result.attempt_log if not a.get("ok")][:2],
        total_tokens=result.usage.get("total_tokens", 0),
        latency_ms=result.latency_ms,
        ttft_ms=result.ttft_ms,
        questions=len(result.payload.questions) if result.payload else 0,
        # 画像字数写进 trace：以后再有人怀疑「画像到底进没进提示词」，
        # 不用重跑模型，翻 runs/trace.jsonl 就能对账（P1-4）
        learner_note_chars=len(note),
        # 出题是否落在教材题型上：看 trace 就能知道「题型层接没接上」
        textbook_chars=len(state.get("textbook_block") or ""),
        types_tagged=sum(
            1
            for c in (result.payload.questions if result.payload else [])
            if (c.type_name or "") in (state.get("type_names") or [])
        ),
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
    try:
        from v3core.learning import enqueue_review

        enqueue_review(get_learning_conn(), student_id=student_id, kp_id=kp, correct=verdict.correct)
    except Exception:  # noqa: BLE001
        pass

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


def route_after_lesson(state: TutorState) -> Literal["degrade", "fail"]:
    if state.get("status") == "error":
        return "fail"
    return "degrade" if state.get("status") == "degraded" else "fail"


def route_after_judge(state: TutorState) -> Literal["wait", "lesson", "end"]:
    status = state.get("status")
    if status in ("done", "degraded"):
        return "end"
    if status == "awaiting_answer":
        return "wait"
    return "lesson"


def build_graph(checkpointer: SqliteSaver | None = None):
    # 只保留 lesson 一个节点：
    # 判题走旁路 /api/judge（前端逐题判、不整篇回传），所以图里不需要 wait/judge。
    # 之前留着 interrupt 的 wait 节点，但全项目没有 Command(resume=)，导致每次讲课都留一个
    # 永远不会被恢复的 checkpoint（已积累 117 个 thread），judge_node 是死代码。
    graph = StateGraph(TutorState)
    graph.add_node("lesson", lesson_node)
    graph.add_node("degrade", degrade_node)
    graph.add_edge(START, "lesson")
    graph.add_conditional_edges("lesson", route_after_lesson, {"degrade": "degrade", "fail": END})
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
    kp: str = "",
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
        "kp": kp,
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
