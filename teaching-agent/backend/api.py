from __future__ import annotations

import json
import re
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

try:
    from langgraph.config import get_stream_writer
except Exception:  # pragma: no cover
    get_stream_writer = None  # type: ignore

from config import load_config
from llm import LLMClient
from node import run_teaching_node
from quiz_node import run_quiz_node
from quiz_schema import QuizQuestion
from schema import HistoryTurn, TeachingRequest

MAX_HISTORY_TURNS = 20
MAX_REASONING_CHARS = 2200


class TutorState(TypedDict, total=False):
    session_id: str
    topic: str
    level: str
    subject: str
    prior_knowledge: str
    misconceptions: str
    max_rounds: int
    round: int
    student_message: str
    teaching_history: list[dict[str, str]]
    teaching_content: str
    thinking: str
    thinking_seconds: int
    quiz: dict[str, Any] | None
    answer: str
    judgement: dict[str, Any] | None
    last_quiz_correct: bool | None
    status: str
    error: str | None


@lru_cache(maxsize=1)
def _client() -> LLMClient:
    """旧 sidecar 也复用同一个客户端（红队 P2-7）。

    这里没有直接换成 v3core.clients：api.py 用的是根目录的 config.py，
    和 v3core/config.py 不是同一份（字段略有差异），换了等于偷偷换配置源。
    给这个工厂函数自己加个缓存，收益一样、风险为零。
    """
    return LLMClient(load_config())


def _teaching_request(state: TutorState) -> TeachingRequest:
    history = state.get("teaching_history", [])
    return TeachingRequest(
        topic=state["topic"],
        level=state.get("level", "初中"),
        subject=state.get("subject", "数学"),
        prior_knowledge=state.get("prior_knowledge", ""),
        misconceptions=state.get("misconceptions", ""),
        student_message=state.get("student_message", ""),
        history=[HistoryTurn(**turn) for turn in history[-MAX_HISTORY_TURNS:]],
    )


def _quiz_request(state: TutorState) -> TeachingRequest:
    # 出题节点只读“当前教学正文 + 学生这一轮的话”，不读主教学历史。
    return TeachingRequest(
        topic=state["topic"],
        level=state.get("level", "初中"),
        subject=state.get("subject", "数学"),
        prior_knowledge=state.get("prior_knowledge", ""),
        misconceptions=state.get("misconceptions", ""),
        student_message=state.get("student_message", ""),
        history=[],
    )


def _append_teaching_history(state: TutorState, role: str, content: str) -> list[dict[str, str]]:
    history = list(state.get("teaching_history", []))
    history.append({"role": role, "content": content})
    return history[-MAX_HISTORY_TURNS:]


def _emit(event: dict[str, Any]) -> None:
    if get_stream_writer is None:
        return
    try:
        writer = get_stream_writer()
        writer(event)
    except Exception:
        # Non-streaming invocations have no writer; ignore.
        pass


def _judge(quiz: QuizQuestion, answer: str) -> dict[str, Any]:
    if quiz.kind == "choice":
        correct = answer.strip().upper()[:1] == quiz.answer.strip().upper()
    else:
        def norm(value: str) -> str:
            text = str(value).strip().lower()
            text = text.replace("−", "-").replace("–", "-").replace("，", ",")
            text = re.sub(r"\s+", "", text)
            text = re.sub(r"[。！？!?；;：:（）()【】\[\]“”\"'`]", "", text)
            return text

        correct = norm(answer) == norm(quiz.answer)
        if not correct:
            try:
                correct = float(norm(answer)) == float(norm(quiz.answer))
            except ValueError:
                pass
    feedback = (
        f"答对了。{quiz.explanation}"
        if correct
        else f"这题答错了。正确答案是 {quiz.answer}。{quiz.explanation}"
    )
    return {
        "correct": correct,
        "correct_answer": quiz.answer,
        "feedback": feedback,
        "explanation": quiz.explanation,
        "tested_points": quiz.tested_points,
        "difficulty": quiz.difficulty,
    }


def _clean_option(option: str) -> str:
    return re.sub(r"^\s*[A-Da-d]\s*[.、,:：)）]\s*", "", option).strip()


def _quiz_card(quiz: dict[str, Any] | None) -> dict[str, Any] | None:
    if not quiz:
        return None
    return {
        "question": quiz["stem"],
        "options": [
            f"{chr(65 + index)}. {_clean_option(option)}"
            for index, option in enumerate(quiz.get("options", []))
        ],
        "answer": quiz["answer"],
    }


def teach_node(state: TutorState) -> dict[str, Any]:
    """Run the original B node unchanged, then pace its reply for the typing effect.

    The prompt, Pydantic contract, checks and repair loop are the ones selected in
    the four-way comparison. No extra length suffix, no trimming.
    """
    req = _teaching_request(state)
    result = run_teaching_node(req, _client(), variant="B")
    if not result.response:
        return {"status": "error", "error": "教学节点没有有效输出：" + "；".join(result.issues)}

    teaching = result.response
    content = teaching.reply_markdown.strip()
    if not content:
        return {"status": "error", "error": "教学节点没有产出正文"}

    thinking = (teaching.order_rationale or teaching.core_idea or "").strip()
    if thinking:
        for start_index in range(0, len(thinking), 8):
            chunk = thinking[start_index : start_index + 8]
            _emit({"type": "reasoning", "text": chunk})
            time.sleep(0.008)

    for start_index in range(0, len(content), 4):
        chunk = content[start_index : start_index + 4]
        _emit({"type": "content", "text": chunk})
        time.sleep(0.018)

    new_history = _append_teaching_history(state, "student", state.get("student_message") or state["topic"])
    new_history = new_history + [{"role": "teacher", "content": content}]
    return {
        "teaching_content": content,
        "teaching_history": new_history[-MAX_HISTORY_TURNS:],
        "thinking": thinking,
        "thinking_seconds": max(1, round(result.latency_ms / 1000)),
        "status": "teaching",
        "error": None,
    }


def quiz_node(state: TutorState) -> dict[str, Any]:
    teaching_text = state.get("teaching_content", "")
    if not teaching_text:
        return {"status": "error", "error": "出题节点缺少教学正文"}
    result = run_quiz_node(_quiz_request(state), teaching_text, _client())
    if not result.response:
        return {"status": "error", "error": "出题节点没有有效输出：" + "；".join(result.issues)}
    return {"quiz": result.response.model_dump(), "status": "awaiting_answer", "error": None}


def wait_node(state: TutorState) -> dict[str, Any]:
    answer = interrupt(
        {
            "type": "quiz_answer_required",
            "round": state.get("round", 0),
            "quiz": _quiz_card(state.get("quiz")),
        }
    )
    return {"answer": str(answer), "status": "answered"}


def judge_node(state: TutorState) -> dict[str, Any]:
    quiz = QuizQuestion(**state["quiz"])
    judgement = _judge(quiz, state.get("answer", ""))
    _emit({"type": "judgement", "judgement": judgement})
    next_round = int(state.get("round", 0)) + 1
    max_rounds = int(state.get("max_rounds", 5))

    if next_round >= max_rounds:
        return {
            "judgement": judgement,
            "last_quiz_correct": judgement["correct"],
            "status": "done",
            "quiz": None,
            "answer": "",
        }

    # 教学 Agent 只接收“答对/答错”这个最小信号；题目、答案、解析不进入教学历史。
    next_message = (
        "我答对了。请在这个点上再往下讲一层，并继续出一道题。"
        if judgement["correct"]
        else "我这题答错了。请针对刚才这一层再讲一遍，再出一道更简单的题。"
    )
    return {
        "judgement": judgement,
        "last_quiz_correct": judgement["correct"],
        "status": "teaching",
        "round": next_round,
        "student_message": next_message,
        "answer": "",
        "teaching_content": "",
        "thinking": "",
        "quiz": None,
    }


def route_after_judge(state: TutorState) -> Literal["next", "end"]:
    return "end" if state.get("status") == "done" else "next"


def build_graph():
    graph = StateGraph(TutorState)
    graph.add_node("teach", teach_node)
    graph.add_node("quiz", quiz_node)
    graph.add_node("wait", wait_node)
    graph.add_node("judge", judge_node)
    graph.set_entry_point("teach")
    graph.add_edge("teach", "quiz")
    graph.add_edge("quiz", "wait")
    graph.add_edge("wait", "judge")
    graph.add_conditional_edges("judge", route_after_judge, {"next": "teach", "end": END})
    return graph.compile(checkpointer=MemorySaver())


GRAPH = build_graph()

app = FastAPI(title="MathNeuron Teaching Sidecar v2", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
        "http://localhost:3002", "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TeachTurnBody(BaseModel):
    session_id: str | None = None
    topic: str = Field(..., min_length=2, max_length=500)
    level: str = "大学低年级"
    subject: str = "数学一"
    prior_knowledge: str = ""
    misconceptions: str = ""
    student_message: str = ""
    history: list[HistoryTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)
    max_rounds: int = Field(5, ge=1, le=10)


class TeachAnswerBody(BaseModel):
    session_id: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1, max_length=200)


def _initial_state(body: TeachTurnBody, session_id: str) -> TutorState:
    return {
        "session_id": session_id,
        "topic": body.topic,
        "level": body.level,
        "subject": body.subject,
        "prior_knowledge": body.prior_knowledge,
        "misconceptions": body.misconceptions,
        "max_rounds": body.max_rounds,
        "round": 0,
        "student_message": body.student_message,
        "teaching_history": [turn.model_dump() for turn in body.history][-MAX_HISTORY_TURNS:],
        "teaching_content": "",
        "thinking": "",
        "thinking_seconds": 0,
        "quiz": None,
        "answer": "",
        "judgement": None,
        "last_quiz_correct": None,
        "status": "new",
        "error": None,
    }


def _payload(session_id: str, state: TutorState) -> dict[str, Any]:
    done = state.get("status") == "done"
    return {
        "session_id": session_id,
        "status": state.get("status", "unknown"),
        "round": int(state.get("round", 0)),
        "max_rounds": int(state.get("max_rounds", 5)),
        "teaching_content": "" if done else state.get("teaching_content", ""),
        "thinking": "" if done else state.get("thinking", ""),
        "thinking_seconds": int(state.get("thinking_seconds", 0)),
        "quiz_card": None if done else _quiz_card(state.get("quiz")),
        "judgement": state.get("judgement"),
        "error": state.get("error"),
        "history_len": len(state.get("teaching_history", [])),
    }


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _stream_graph(input_value: Any, config: dict[str, Any], meta: dict[str, Any]):
    yield _sse(meta)
    try:
        for mode, chunk in GRAPH.stream(input_value, config, stream_mode=["custom", "values"]):
            if mode == "custom" and isinstance(chunk, dict):
                yield _sse(chunk)
    except Exception as exc:  # noqa: BLE001
        yield _sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        return

    state = GRAPH.get_state(config).values
    if state.get("status") == "error":
        yield _sse({"type": "error", "message": state.get("error") or "教学链失败"})
        return

    quiz = _quiz_card(state.get("quiz")) if state.get("status") != "done" else None
    if quiz:
        yield _sse({"type": "quiz", "quiz_card": quiz})
    yield _sse(
        {
            "type": "done",
            "status": state.get("status", "unknown"),
            "round": int(state.get("round", 0)),
            "max_rounds": int(state.get("max_rounds", 5)),
            "session_id": state.get("session_id", ""),
            "error": state.get("error"),
        }
    )


AGENT_SPECS = [
    {
        "id": "teaching",
        "name": "Teaching Agent",
        "role": "问答 / 教学",
        "folder": "backend/prompts.py",
        "structure": [
            {"key": "输入", "value": "主题 + 学段 + 已有基础 + 教学历史 + 学生这一轮的话"},
            {"key": "输出", "value": "teaching_content（原版 B 完整正文）+ thinking（order_rationale）"},
            {"key": "模型", "value": "DeepSeek V4 Flash，JSON mode，结构化 TeachingTurn"},
            {"key": "约束", "value": "原版 B：核心直觉 / 生活类比 / 拆两步 / 具体例子 / 检查问题；无额外字数限制"},
            {"key": "上下文", "value": "只读 teaching_history；不读题目和判题结果"},
        ],
        "sources": [
            {"label": "prompts.py", "path": "backend/prompts.py"},
            {"label": "api.py · teach_node", "path": "backend/api.py"},
        ],
    },
    {
        "id": "quiz",
        "name": "Quiz Agent",
        "role": "动态出题",
        "folder": "backend/quiz_node.py",
        "structure": [
            {"key": "输入", "value": "当前教学正文 + 学生这一轮的话 + 学段/基础"},
            {"key": "输出", "value": "QuizQuestion：题干 / 4 选项 / 答案 / 解析 / 考点"},
            {"key": "模型", "value": "DeepSeek V4 Flash，JSON mode，thinking disabled"},
            {"key": "约束", "value": "只出一道；只测刚讲的一层；source_quote 必须来自教学正文"},
            {"key": "上下文", "value": "history=[]，只读自己的题卡上下文"},
        ],
        "sources": [
            {"label": "quiz_node.py", "path": "backend/quiz_node.py"},
            {"label": "quiz_prompts.py", "path": "backend/quiz_prompts.py"},
        ],
    },
]


def _source(path: str) -> str:
    try:
        return (Path(__file__).parent / path.removeprefix("backend/")).read_text(encoding="utf-8")
    except OSError as exc:
        return f"（读取失败：{exc}）"


@app.get("/api/agents")
def agents() -> dict[str, Any]:
    return {
        "agents": [
            {
                **spec,
                "sources": [
                    {**source, "code": _source(source["path"])}
                    for source in spec["sources"]
                ],
            }
            for spec in AGENT_SPECS
        ],
        "runtime": [
            {"name": "Judge Node", "kind": "deterministic", "folder": "backend/api.py"},
            {"name": "LangGraph Orchestrator", "kind": "runtime", "folder": "backend/api.py"},
        ],
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/teach_turn")
def teach_turn(body: TeachTurnBody) -> dict[str, Any]:
    session_id = body.session_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}
    try:
        GRAPH.invoke(_initial_state(body, session_id), config)
        state = GRAPH.get_state(config).values
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
    if state.get("status") == "error":
        raise HTTPException(status_code=500, detail=state.get("error") or "教学链失败")
    return _payload(session_id, state)


@app.post("/api/teach_turn_stream")
def teach_turn_stream(body: TeachTurnBody):
    session_id = body.session_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}
    meta = {
        "type": "meta",
        "session_id": session_id,
        "round": 0,
        "max_rounds": body.max_rounds,
    }
    return StreamingResponse(
        _stream_graph(_initial_state(body, session_id), config, meta),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@app.post("/api/teach_answer")
def teach_answer(body: TeachAnswerBody) -> dict[str, Any]:
    config = {"configurable": {"thread_id": body.session_id}}
    state = GRAPH.get_state(config)
    if not state.values:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    try:
        GRAPH.invoke(Command(resume=body.answer), config)
        state = GRAPH.get_state(config).values
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
    if state.get("status") == "error":
        raise HTTPException(status_code=500, detail=state.get("error") or "教学链失败")
    return _payload(body.session_id, state)


@app.post("/api/teach_answer_stream")
def teach_answer_stream(body: TeachAnswerBody):
    config = {"configurable": {"thread_id": body.session_id}}
    state = GRAPH.get_state(config)
    if not state.values:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    meta = {"type": "meta", "session_id": body.session_id, "round": int(state.values.get("round", 0)) + 1}
    return StreamingResponse(
        _stream_graph(Command(resume=body.answer), config, meta),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
