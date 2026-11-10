"""FastAPI 最小服务：认证 + 对象级授权 + 教/答/档案/trace。

启动：
    uvicorn api:app --host 127.0.0.1 --port 8010

认证是教学用的 token 映射，不是生产认证：
    STARTER_KIT_TOKENS='{"demo-token":"student-1"}'
请求头：
    X-Student-Token: demo-token
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from langgraph.types import Command

from content import all_kp_ids
from graph import get_graph, get_student_conn, get_tracer, initial_state, public_question
from student_store import get_profile
from trace import aggregate

app = FastAPI(title="starter-kit teaching API", version="0.1.0")

DEFAULT_TOKENS = {"demo-token": "student-1"}
try:
    TOKENS: dict[str, str] = json.loads(os.getenv("STARTER_KIT_TOKENS", json.dumps(DEFAULT_TOKENS)))
except json.JSONDecodeError:
    TOKENS = DEFAULT_TOKENS


def current_student(x_student_token: str | None = Header(default=None, alias="X-Student-Token")) -> str:
    if not x_student_token or x_student_token not in TOKENS:
        raise HTTPException(status_code=401, detail="缺少或无效的 X-Student-Token")
    return TOKENS[x_student_token]


class TeachBody(BaseModel):
    kp_id: str = Field(..., description="必须来自 /health 的 kp_ids")
    session_id: str | None = None
    max_rounds: int = Field(2, ge=1, le=4)


class AnswerBody(BaseModel):
    session_id: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1, max_length=300)


def _config(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}, "recursion_limit": 60}


def _payload(session_id: str, values: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "status": values.get("status"),
        "round": int(values.get("round", 0)),
        "lesson": values.get("lesson"),
        "questions": [public_question(q) for q in values.get("questions", [])],
        "question": public_question(values.get("question")),
        "judgement": values.get("judgement"),
        "answers": values.get("answers", []),
        "tokens": int(values.get("tokens", 0)),
        "error": values.get("error"),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "kp_ids": all_kp_ids(), "mode": os.getenv("STARTER_KIT_MODE", "fake")}


@app.post("/teach")
def teach(body: TeachBody, student_id: str = Depends(current_student)) -> dict[str, Any]:
    graph = get_graph()
    sid = body.session_id or ""
    if not sid:
        sid, state = initial_state(kp_id=body.kp_id, student_id=student_id, max_rounds=body.max_rounds)
    else:
        existing = graph.get_state(_config(sid))
        if existing.values and existing.values.get("status") == "awaiting_answer":
            return _payload(sid, existing.values)
        sid, state = initial_state(
            kp_id=body.kp_id, student_id=student_id, max_rounds=body.max_rounds, session_id=sid
        )
    graph.invoke(state, _config(sid))
    values = graph.get_state(_config(sid)).values
    if values.get("status") == "error":
        raise HTTPException(status_code=502, detail=values.get("error") or "讲练失败")
    return _payload(sid, values)


@app.post("/answer")
def answer(body: AnswerBody, student_id: str = Depends(current_student)) -> dict[str, Any]:
    graph = get_graph()
    config = _config(body.session_id)
    state = graph.get_state(config)
    if not state.values:
        raise HTTPException(status_code=404, detail="会话不存在")
    if state.values.get("student_id") != student_id:
        raise HTTPException(status_code=403, detail="这不是你的会话")
    if state.values.get("status") != "awaiting_answer":
        raise HTTPException(status_code=409, detail=f"当前状态是 {state.values.get('status')}，不接受作答")
    graph.invoke(Command(resume=body.answer), config)
    values = graph.get_state(config).values
    if values.get("status") == "error":
        raise HTTPException(status_code=502, detail=values.get("error") or "判题失败")
    return _payload(body.session_id, values)


@app.get("/profile/{student_id}")
def profile(student_id: str, current: str = Depends(current_student)) -> dict[str, Any]:
    if student_id != current:
        raise HTTPException(status_code=403, detail="不能看别人的档案")
    return get_profile(get_student_conn(), student_id)


@app.get("/trace/summary")
def trace_summary(_: str = Depends(current_student)) -> dict[str, Any]:
    return aggregate(get_tracer().read())
