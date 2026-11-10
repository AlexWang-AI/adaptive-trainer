"""MathNeuron API Server v3 —— 讲练合一 + SymPy 判题 + 知识树推进。

在旧 sidecar（api.py：/api/agents、/api/teach_turn …）之上挂 v3 接口：

    POST /api/teach_stream   SSE：meta → content*（真实 token 增量）→ quiz_pack(3 题) → done
    POST /api/judge          单题判分（本地 SymPy，无 LLM 成本）
    GET  /api/curriculum     知识树（章 → 知识点 + 掌握状态）
    POST /api/mastery        标记知识点通关
    GET  /api/health         健康检查（含 v3 组件状态）

启动：
    uvicorn api_server:app --host 127.0.0.1 --port 8008
"""

from __future__ import annotations

import json
import hashlib
import logging
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from api import app  # 旧 sidecar：/api/agents、/api/teach_turn …（保持兼容）
from curriculum import (  # noqa: F401
    CHAPTERS,
    CURRICULUM_VERSION,
    KP_TABLE,
    TEXTBOOK_NAME,
    all_kp_ids,
    order_index,
    textbook_block as build_textbook_block,
)
from v3core import db
from v3core.clients import get_llm_client
from v3core.graph import get_graph, initial_state, learner_note, new_session_id
from v3core.judge import judge as v3_judge
from v3core.nodes import active_sinks, register_stream_sink, unregister_stream_sink

logger = logging.getLogger("mn.api")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
MASTERY_DB = DATA_DIR / "mastery.db"

DEFAULT_STUDENT = "local-user"


# ---------------------------------------------------------------------------
# 掌握度存储（与 v3core.student 的作答记录分开：这是「通关」而不是「答过」）
# ---------------------------------------------------------------------------
MASTERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS kp_mastery (
    student_id TEXT NOT NULL,
    kp_id      TEXT NOT NULL,
    score      INTEGER,
    mastered_at REAL NOT NULL,
    PRIMARY KEY (student_id, kp_id)
);
"""

# 掌握度库：进程内单例代理，真实连接按线程分发、写事务串行（见 v3core/db.py）
_CONN = db.connection(MASTERY_DB, schema=MASTERY_SCHEMA)


def mastered_map(student_id: str) -> dict[str, dict[str, Any]]:
    rows = _CONN.execute(
        "SELECT kp_id, score, mastered_at FROM kp_mastery WHERE student_id = ?", (student_id,)
    ).fetchall()
    return {r["kp_id"]: {"score": r["score"], "mastered_at": r["mastered_at"]} for r in rows}


# ---------------------------------------------------------------------------
# 知识树
# ---------------------------------------------------------------------------
def _kp_node(kp_id: str, mastered: dict[str, dict[str, Any]]) -> dict[str, Any]:
    meta = KP_TABLE[kp_id]
    return {
        "id": kp_id,
        "name": meta["name"],
        "chapter": meta["chapter"],
        "book": meta.get("book", ""),
        "book_name": meta.get("book_name", ""),
        "block": meta.get("block", ""),
        "block_name": meta.get("block_name", ""),
        "tier": meta.get("tier", ""),
        "tier_label": meta.get("tier_label", ""),
        "exam_weight": meta["exam_weight"],
        "prerequisites": meta["prerequisites"],
        "examples": len(meta.get("examples") or []),
        "mastered": kp_id in mastered,
        "mastered_at": mastered.get(kp_id, {}).get("mastered_at"),
    }


def _tree(student_id: str) -> dict[str, Any]:
    mastered = mastered_map(student_id)
    chapters = []
    for ch in CHAPTERS:
        kps = [_kp_node(kp, mastered) for kp in ch.kps]
        # 三级结构：讲 → 分支 → 知识点（分支里带考频档与结论，前端按它折叠）
        blocks = []
        for block in ch.blocks:
            block_kps = [k for k in kps if k["block"] == block["id"]]
            blocks.append(
                {
                    "id": block["id"],
                    "name": block["name"],
                    "role": block.get("role", ""),
                    "tier": block.get("tier", ""),
                    "tier_label": block.get("tier_label", ""),
                    "conclusions": len(block.get("conclusions") or []),
                    # 结论层是知识树的一层，侧栏要能展开看原文（否则 375 条结论在界面上是隐形的）
                    "conclusion_list": [
                        c.get("statement", "")
                        for c in (block.get("conclusions") or [])
                        if c.get("statement")
                    ][:16],
                    "kps": block_kps,
                }
            )
        chapters.append(
            {
                "id": ch.id,
                "name": ch.name,
                "lecture": ch.lecture,
                "title": ch.title,
                "book": ch.book,
                "kps": kps,
                "blocks": blocks,
                "mastered_count": sum(1 for k in kps if k["mastered"]),
            }
        )
    total = len(all_kp_ids())
    done = len(mastered)
    # 下一个该学的点：未通关里 order_index 最小、且前置已通关（或没有前置）的
    next_kp = None
    for kp in sorted(all_kp_ids(), key=order_index):
        if kp in mastered:
            continue
        pre = KP_TABLE[kp]["prerequisites"]
        if all(p in mastered for p in pre):
            next_kp = _kp_node(kp, mastered)
            break
    if next_kp is None:
        for kp in sorted(all_kp_ids(), key=order_index):
            if kp not in mastered:
                next_kp = _kp_node(kp, mastered)
                break
    return {
        "student_id": student_id,
        "textbook": TEXTBOOK_NAME,
        "curriculum_version": CURRICULUM_VERSION,
        "chapters": chapters,
        "progress": {"total": total, "mastered": done, "ratio": round(done / total, 3) if total else 0},
        "next_kp": next_kp,
    }


@app.get("/api/kp_detail")
def kp_detail(kp_id: str) -> dict[str, Any]:
    """一个知识点的教材细节：考纲、要点、结论、教材例题、题型、提速技巧。

    单独开接口而不是塞进 /api/curriculum：232 个知识点全带要点会有几百 KB，
    只有点开某个知识点时才需要这份细节。
    """
    meta = KP_TABLE.get(kp_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"未知知识点：{kp_id}")
    block = next(
        (b for ch in CHAPTERS for b in ch.blocks if b["id"] == meta["block"]),
        {},
    )
    return {
        "id": kp_id,
        "name": meta["name"],
        "chapter": meta["chapter"],
        "chapter_name": meta["chapter_name"],
        "block": meta["block"],
        "block_name": meta["block_name"],
        "tier": meta["tier"],
        "tier_label": meta["tier_label"],
        "exam_weight": meta["exam_weight"],
        "textbook_ref": meta["textbook_ref"],
        "evidence": meta.get("evidence", ""),
        "points": meta.get("points") or [],
        "conclusions": [c["statement"] for c in (block.get("conclusions") or [])],
        "examples": meta.get("examples") or [],
        "types": meta.get("types") or [],
        "extras": meta.get("extras") or [],
        "textbook_block": build_textbook_block(kp_id),
    }


@app.get("/api/curriculum")
def curriculum(student_id: str = DEFAULT_STUDENT) -> dict[str, Any]:
    return _tree(student_id)


class MasteryBody(BaseModel):
    student_id: str = DEFAULT_STUDENT
    kp_id: str = Field(..., min_length=2)
    score: int | None = None


@app.post("/api/mastery")
def mark_mastery(body: MasteryBody) -> dict[str, Any]:
    if body.kp_id not in KP_TABLE:
        raise HTTPException(status_code=400, detail=f"未知知识点：{body.kp_id}")
    # 通关分数由服务端作答记录推导，不采信客户端传的 score（红队 P0-2）
    rows = _kp_rows(body.student_id)
    rec = rows.get(body.kp_id, {})
    attempts = int(rec.get("attempts", 0))
    correct = int(rec.get("correct", 0))
    if attempts < 3:
        raise HTTPException(status_code=409, detail=f"作答不足 3 题（当前 {attempts}），不能标记通关")
    derived = int(round(((correct + 1) / (attempts + 2)) * 100))
    body = body.model_copy(update={"score": derived})
    # 通关记录（mastery.db）+ 提分曲线快照（students.db）跨两个库，各自一个事务
    with db.transaction(_CONN):
        _CONN.execute(
            "INSERT INTO kp_mastery (student_id, kp_id, score, mastered_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(student_id, kp_id) DO UPDATE SET score = excluded.score, mastered_at = excluded.mastered_at",
            (body.student_id, body.kp_id, body.score, time.time()),
        )
    try:
        with db.transaction(_LEARN_CONN):
            data = _analytics(body.student_id)
            learn.record_snapshot(
                _LEARN_CONN, student_id=body.student_id, overall=data["overall"],
                chapters=data["chapters"], reason=f"master:{body.kp_id}",
            )
    except Exception:  # noqa: BLE001
        # 快照只是曲线上的一个点，失败不该让「通关」失败；但必须留下痕迹
        logger.exception("通关快照写入失败 kp=%s", body.kp_id)
    return {"ok": True, **_tree(body.student_id)}


# ---------------------------------------------------------------------------
# 判题
# ---------------------------------------------------------------------------
class JudgeBody(BaseModel):
    question: dict[str, Any]
    answer: str = Field(..., max_length=300)
    allow_llm: bool = False
    student_id: str = DEFAULT_STUDENT
    kp_id: str = ""
    kp_name: str = ""
    # 独立答案键：题库/验证器传入时优先于 question["answer"]
    answer_key: str | None = None
    # 幂等键：同一题同一答案重复提交只记一次；不传则按 学生+知识点+题号+答案 派生
    attempt_id: str | None = None
    question_id: str = ""


def _derived_attempt_id(body: "JudgeBody", key_text: str, question_id: str) -> str:
    """没有显式 attempt_id 时，用稳定哈希去重。

    同一学生、同一知识点、同一道题、同一个答案，重复提交只算一次；
    换答案（例如先错后对）会产生新的 attempt_id，正常计数。
    """
    stem = str(body.question.get("stem", ""))[:200]
    raw = f"{body.student_id}|{body.kp_id}|{question_id or stem}|{body.answer.strip()}|{key_text}"
    return "auto-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@app.post("/api/judge")
def judge(body: JudgeBody) -> dict[str, Any]:
    """本地判分：选择题 → 文本 → 数值 → SymPy，全部离线，毫秒级。"""
    # 独立答案键：题库/验证器传入时优先于 question["answer"]（模型生成的答案可能错）
    key_text = (body.answer_key or str(body.question.get("answer", ""))).strip()
    need_llm = body.allow_llm or bool(re.search(r"[\u4e00-\u9fff]", key_text))
    client = None
    if need_llm:
        try:
            client = get_llm_client()
        except Exception as exc:  # noqa: BLE001
            # 没有可用 key 就退回纯规则判题，但把原因记下来（以前是静默 None）
            logger.warning("判题 LLM 兜底不可用：%s", exc)
            client = None
    started = time.perf_counter()
    verdict = v3_judge(body.question, body.answer, client=client, allow_llm=need_llm, answer_key=key_text)

    # 幂等键：前端重试/双击不应重复加 attempts、重复写错题、重复推进复习队列
    question_id = body.question_id or str(body.question.get("id") or body.question.get("question_id") or "")
    attempt_id = body.attempt_id or _derived_attempt_id(body, key_text, question_id)

    # 关键：v3 的判题是旁路（不走主图），所以掌握度只能在这里记。
    # 三次写（作答 / 错题 / 复习队列）必须是一个原子单元，否则中途失败会半写（红队 P1-11）。
    persisted, persist_error, duplicate = True, "", False
    if body.kp_id:
        try:
            from v3core.student import record_attempt, record_mistake, resolve_mistake

            with db.transaction(_STUDENT_CONN):
                inserted = record_attempt(
                    _STUDENT_CONN,
                    student_id=body.student_id,
                    subject="数学一",
                    kp=body.kp_id,
                    correct=verdict.correct,
                    attempt_id=attempt_id,
                    question_id=question_id,
                    layer=verdict.layer,
                )
                duplicate = not inserted
                if inserted:
                    if verdict.correct:
                        resolve_mistake(_STUDENT_CONN, student_id=body.student_id, subject="数学一", kp=body.kp_id)
                    else:
                        record_mistake(
                            _STUDENT_CONN,
                            student_id=body.student_id,
                            subject="数学一",
                            kp=body.kp_id,
                            question=str(body.question.get("stem", ""))[:500],
                            student_answer=body.answer[:200],
                            correct_answer=key_text[:200],
                        )
                    learn.enqueue_review(
                        _LEARN_CONN, student_id=body.student_id, kp_id=body.kp_id, correct=verdict.correct
                    )
        except Exception as exc:  # noqa: BLE001
            # 以前这里 except: pass，锁冲突被完全吞掉，前端只看到「掌握度不动」
            persisted, persist_error = False, f"{type(exc).__name__}: {exc}"
            logger.exception("判题落库失败 kp=%s", body.kp_id)

    return {
        "correct": verdict.correct,
        "layer": verdict.layer,
        "reason": verdict.reason,
        "correct_answer": key_text,
        "explanation": str(body.question.get("explanation", "")),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "persisted": persisted,
        "persist_error": persist_error,
        "duplicate": duplicate,
        "attempt_id": attempt_id,
    }


# ---------------------------------------------------------------------------
# 讲练合一 SSE
# ---------------------------------------------------------------------------
class TeachStreamBody(BaseModel):
    session_id: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    student_message: str = ""
    student_id: str = DEFAULT_STUDENT
    kp_id: str | None = None
    topic: str | None = None
    level: str = "大学低年级"
    subject: str = "数学一"
    prior_knowledge: str = ""
    misconceptions: str = ""
    # 知识点内部的子项（左侧知识树展开后点某一条），讲义与题目只围绕它
    focus: str = ""
    max_rounds: int = Field(3, ge=1, le=6)


def _resolve_topic(body: TeachStreamBody) -> tuple[str, str, str, str]:
    """优先用知识点 id 生成教学主题；否则用用户输入的主题。"""
    if body.kp_id:
        if body.kp_id not in KP_TABLE:
            raise HTTPException(status_code=400, detail=f"未知知识点：{body.kp_id}")
        meta = KP_TABLE[body.kp_id]
        topic = body.topic or f"{meta['name']}（考研数学一，考频 {meta['exam_weight']}/5）"
        prior = body.prior_knowledge or "已学完考研数学一基础阶段的前置内容，但只会套公式"
        misconceptions = body.misconceptions or "容易只记结论、不会判断适用条件"
        return topic, prior, misconceptions, meta["name"]
    if not body.topic:
        raise HTTPException(status_code=400, detail="必须提供 kp_id 或 topic")
    return body.topic, body.prior_knowledge, body.misconceptions, body.topic


def _card(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": card.get("kind"),
        "stem": card.get("stem", ""),
        "options": card.get("options", []),
        "answer": card.get("answer", ""),
        "explanation": card.get("explanation", ""),
        "tested_points": card.get("tested_points", []),
        "difficulty": card.get("difficulty", "medium"),
        "why_this_question": card.get("why_this_question", ""),
        # 出题是否落在教材题型上，前端/验收脚本都靠这个字段
        "type_name": card.get("type_name", ""),
    }


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class _StreamBuffer:
    """流式输出的中转站：讲义只留最新一份，控制事件按序排队（红队 P2-8）。

    为什么不用 `queue.Queue`：sink 每次推进来的是**累计全文**，
    无界队列在慢客户端（或客户端已断开但生成器还没被回收）时会在内存里
    堆上千份全文；而且阻塞式 `get()` 让生成器永远等不到「该清理了」的机会。
    这里 `md` 只保留最新值（合并永不丢字，因为它是累计的），
    `pop(timeout)` 保证生成器每秒都有机会检查连接是否还活着。
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._md = ""
        self._md_dirty = False
        self._events: list[tuple[str, Any]] = []

    def push_md(self, text: str) -> None:
        with self._cond:
            # 只保留更长的那个：理论上单调增长，防止乱序把内容弄短
            if len(text) >= len(self._md):
                self._md = text
            self._md_dirty = True
            self._cond.notify()

    def push(self, kind: str, payload: Any = None) -> None:
        with self._cond:
            self._events.append((kind, payload))
            self._cond.notify()

    def pop(self, timeout: float = 1.0) -> tuple[str | None, list[tuple[str, Any]]]:
        with self._cond:
            if not self._md_dirty and not self._events:
                self._cond.wait(timeout)
            md = self._md if self._md_dirty else None
            self._md_dirty = False
            events, self._events = self._events, []
            return md, events


@app.post("/api/teach_stream")
def teach_stream(body: TeachStreamBody, request: Request) -> StreamingResponse:
    graph = get_graph()
    sid = body.session_id or new_session_id()
    topic, prior, misconceptions, kp_name = _resolve_topic(body)
    config = {"configurable": {"thread_id": sid}, "recursion_limit": 80}

    sink_q = _StreamBuffer()
    register_stream_sink(sid, sink_q.push_md)

    sid, state = initial_state(
        topic=topic,
        level=body.level,
        subject=body.subject,
        kp=body.kp_id or "",
        prior_knowledge=prior,
        misconceptions=misconceptions,
        max_rounds=body.max_rounds,
        student_id=body.student_id,
        session_id=sid,
    )
    # 追问：把前端带来的对话历史与这句话灌进 state，否则每轮都从 topic 重讲（红队 P1-12）
    if body.student_message:
        state["student_message"] = body.student_message
    if body.history:
        state["history"] = [
            {"role": str(t.get("role", "student")), "content": str(t.get("content", ""))[:2000]}
            for t in body.history[-20:]
            if t.get("content")
        ]
        if not body.student_message and body.history:
            state["student_message"] = str(body.history[-1].get("content", ""))[:1000]
        state["round"] = 1

    # 学习画像：掌握度/认知偏差在讲之前就要算好（红队 P1-4）。
    # 以前这段被 round>0 挡住，而图里 round 恒为 0 → 画像从未进过提示词。
    state["learner_note"] = learner_note(state)

    # 教材依据：这一讲必须按《张宇基础30讲》的骨架讲，不让模型自由发挥
    if body.kp_id and body.kp_id in KP_TABLE:
        state["textbook_block"] = build_textbook_block(body.kp_id)
        state["textbook_ref"] = KP_TABLE[body.kp_id].get("textbook_ref", "")
        state["type_names"] = [
            (t.get("name") or "").strip()
            for t in (KP_TABLE[body.kp_id].get("types") or [])
            if (t.get("name") or "").strip()
        ]
    else:
        state["textbook_block"] = ""
        state["textbook_ref"] = ""
        state["type_names"] = []

    # 知识点内部的子项：只讲这一条（左侧树展开后点「0/0 型」这类叶子）
    state["focus"] = (body.focus or "").strip()[:200]

    def worker() -> None:
        try:
            graph.invoke(state, config)
        except Exception as exc:  # noqa: BLE001
            logger.exception("教学图执行失败 session=%s", sid)
            sink_q.push("err", f"{type(exc).__name__}: {exc}")
        finally:
            sink_q.push("end")

    threading.Thread(target=worker, daemon=True).start()

    async def gen():
        started = time.perf_counter()
        last_send = time.time()
        sent = ""
        finished = False
        # 整个生成过程都包在 try/finally 里：客户端断开、生成器被关闭（GeneratorExit）、
        # 异常，都必须把 sink 摘掉，否则 _STREAM_SINKS 会一直留着死会话（红队 P2-8）
        try:
            yield _sse({
                "type": "meta",
                "session_id": sid,
                "kp_id": body.kp_id,
                "kp_name": kp_name,
                "topic": topic,
                "learner_note": state["learner_note"],
                "textbook_ref": state["textbook_ref"],
                "textbook_chars": len(state["textbook_block"]),
            })
            while not finished:
                # 阻塞取数据放到线程池，主协程才不会被一个 1 秒的 get 卡住；
                # 空闲时主动问一句「客户端还在吗」——只有这里能第一时间发现断连。
                md, events = await run_in_threadpool(sink_q.pop, 0.5)
                if md is None and not events and await request.is_disconnected():
                    logger.info("客户端已断开，提前结束推送 session=%s", sid)
                    return
                if md is not None:
                    if md.startswith(sent):
                        delta = md[len(sent):]
                        sent = md
                    else:
                        # 校验失败后重生成：内容从头开始，必须让前端清空再重放
                        yield _sse({"type": "reset"})
                        delta, sent = md, md
                    if delta:
                        yield _sse({"type": "content", "text": delta})
                        last_send = time.time()
                for kind, payload in events:
                    if kind == "md":
                        continue
                    if kind == "err":
                        yield _sse({"type": "error", "message": str(payload)})
                    elif kind == "end":
                        finished = True
                    last_send = time.time()
                if not finished and md is None and not events and time.time() - last_send > 8:
                    # SSE 注释帧：保活，但不会触发前端 onmessage
                    yield ": keep-alive\n\n"
                    last_send = time.time()

            try:
                values = graph.get_state(config).values
            except Exception:  # noqa: BLE001
                logger.exception("读取会话状态失败 session=%s", sid)
                values = {}

            if values.get("status") == "error":
                yield _sse({"type": "error", "message": values.get("error") or "讲练节点失败"})
                yield _sse({"type": "done", "status": "error", "session_id": sid})
                return

            cards = values.get("questions", [])
            # 题型标签只留教材里真有的（纯概念节点没有题型，模型会自己编一个）
            _valid_types = {
                (t.get("name") or "").strip()
                for t in (KP_TABLE.get(body.kp_id or "", {}).get("types") or [])
            }
            quiz_pack = []
            for c in cards:
                card = _card(c)
                if card["type_name"] not in _valid_types:
                    card["type_name"] = ""
                quiz_pack.append(card)
            yield _sse({
                "type": "quiz_pack",
                "quiz_pack": quiz_pack,
                "kp_id": body.kp_id,
                "kp_name": kp_name,
                "score": values.get("score"),
                "ttft_ms": int(values.get("ttft_ms") or 0),
            })
            yield _sse({
                "type": "done",
                "status": values.get("status", "awaiting_answer"),
                "session_id": sid,
                "round": int(values.get("round", 0)),
                "ttft_ms": int(values.get("ttft_ms") or 0),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "tokens": int(values.get("tokens_used", 0)),
            })
        finally:
            unregister_stream_sink(sid)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@app.get("/api/learner_note")
def learner_note_preview(kp_id: str = "", student_id: str = DEFAULT_STUDENT) -> dict[str, Any]:
    """预览这一讲会注入给模型的学习画像（只读，不花 token，便于验收和排障）。"""
    note = learner_note({"student_id": student_id, "subject": "数学一", "kp": kp_id})
    return {
        "kp_id": kp_id,
        "kp_name": KP_TABLE.get(kp_id, {}).get("name", kp_id),
        "student_id": student_id,
        "note": note,
        "chars": len(note),
        "limit": 400,
    }


@app.get("/api/session/{session_id}")
def session_detail(session_id: str) -> dict[str, Any]:
    state = get_graph().get_state({"configurable": {"thread_id": session_id}}).values
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "session_id": session_id,
        "status": state.get("status"),
        "round": state.get("round"),
        "questions": [_card(c) for c in state.get("questions", [])],
        "ttft_ms": state.get("ttft_ms"),
        "tokens_used": state.get("tokens_used"),
    }


# ---------------------------------------------------------------------------
# 侧边提问（不污染主干）+ 思路诊断（错题本）
# ---------------------------------------------------------------------------
MISTAKE_SCHEMA = """
CREATE TABLE IF NOT EXISTS mistakes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    kp_id       TEXT,
    kp_name     TEXT,
    question    TEXT NOT NULL,
    student_answer TEXT,
    reasoning   TEXT,
    diagnosis   TEXT,
    created_at  REAL NOT NULL
);
"""


_MISTAKE_CONN = db.connection(DATA_DIR / "mistakes.db", schema=MISTAKE_SCHEMA)


class SideAskBody(BaseModel):
    ask: str = Field(..., min_length=1, max_length=800)
    question: str = ""
    lesson: str = ""
    history: list[dict[str, Any]] = Field(default_factory=list)


@app.post("/api/side_ask")
def side_ask(body: SideAskBody) -> dict[str, Any]:
    """侧边提问：独立上下文，只带当前题 + 讲义片段，不写主会话。"""
    from v3core.agents import side_answer

    try:
        return side_answer(
            get_llm_client(), ask=body.ask, question=body.question, lesson=body.lesson, history=body.history
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"侧问失败：{type(exc).__name__}: {exc}") from exc


class DiagnoseBody(BaseModel):
    student_id: str = DEFAULT_STUDENT
    kp_id: str = ""
    kp_name: str = ""
    question: str = Field(..., min_length=2, max_length=800)
    student_answer: str = ""
    reasoning: str = Field(..., min_length=2, max_length=1500)


@app.post("/api/diagnose")
def diagnose(body: DiagnoseBody) -> dict[str, Any]:
    """思路诊断：把学生的口述思路拆成步骤，定位最早出错的一步，落错题本。"""
    import json as _json
    import time as _time

    from v3core.agents import diagnose as run_diagnose

    try:
        result = run_diagnose(
            get_llm_client(),
            kp_name=body.kp_name or body.kp_id,
            question=body.question,
            student_answer=body.student_answer,
            reasoning=body.reasoning,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"诊断失败：{type(exc).__name__}: {exc}") from exc

    # 认知偏差（students.db）与诊断记录（mistakes.db）跨两个库，
    # 各自一个事务；失败不再静默，直接告诉前端「没记上」。
    persisted, persist_error = True, ""
    try:
        with db.transaction(_LEARN_CONN):
            if body.kp_id:
                learn.remember_misconception(
                    _LEARN_CONN, student_id=body.student_id, kp_id=body.kp_id,
                    text=result.get("misconception", ""),
                )
        with db.transaction(_MISTAKE_CONN):
            _MISTAKE_CONN.execute(
                "INSERT INTO mistakes (student_id, kp_id, kp_name, question, student_answer, reasoning, diagnosis, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    body.student_id,
                    body.kp_id,
                    body.kp_name,
                    body.question[:800],
                    body.student_answer[:300],
                    body.reasoning[:1500],
                    _json.dumps(result, ensure_ascii=False),
                    _time.time(),
                ),
            )
    except Exception as exc:  # noqa: BLE001
        persisted, persist_error = False, f"{type(exc).__name__}: {exc}"
        logger.exception("诊断落库失败 kp=%s", body.kp_id)

    return {"ok": True, **result, "persisted": persisted, "persist_error": persist_error}


@app.get("/api/mistakes")
def list_mistakes(student_id: str = DEFAULT_STUDENT, limit: int = 20) -> dict[str, Any]:
    """错题本合并两个来源：
    1) mistakes.db —— 「说说我的思路」的诊断记录（有断点归因）；
    2) students.db mistakes —— 题卡答错（只有题目与正确答案，未做思路诊断）。
    以前只读第一张表，导致题卡答错永远不进错题本（红队 P1-10）。
    """
    import json as _json

    items: list[dict[str, Any]] = []
    rows = _MISTAKE_CONN.execute(
        "SELECT id, kp_id, kp_name, question, student_answer, diagnosis, created_at "
        "FROM mistakes WHERE student_id = ? ORDER BY created_at DESC LIMIT ?",
        (student_id, max(1, min(limit, 100))),
    ).fetchall()
    for row in rows:
        item = dict(row)
        try:
            item["diagnosis"] = _json.loads(item["diagnosis"] or "{}")
        except Exception:  # noqa: BLE001
            item["diagnosis"] = {}
        item["source"] = "diagnosed"
        items.append(item)

    quiz_rows = _STUDENT_CONN.execute(
        "SELECT id, kp, question, student_answer, correct_answer, created_at FROM mistakes "
        "WHERE student_id = ? AND subject = '数学一' AND resolved_at IS NULL "
        "ORDER BY created_at DESC LIMIT ?",
        (student_id, max(1, min(limit, 100))),
    ).fetchall()
    for row in quiz_rows:
        items.append({
            "id": f"quiz-{row['id']}",
            "kp_id": row["kp"],
            "kp_name": KP_TABLE.get(row["kp"], {}).get("name", row["kp"]),
            "question": row["question"],
            "student_answer": row["student_answer"],
            "created_at": row["created_at"],
            "source": "quiz",
            "diagnosis": {
                "first_break": "题卡答错（未做思路诊断）",
                "fix": f"正确答案：{row['correct_answer']}。点「说说我的思路」可以补一次诊断。",
            },
        })

    items.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
    return {"student_id": student_id, "items": items[:limit], "count": len(items)}


# ---------------------------------------------------------------------------
# 学习闭环：掌握度 / 复习队列 / 提分曲线 / 热点图 / 账本 / 再练一组
# ---------------------------------------------------------------------------
from v3core import learning as learn  # noqa: E402
from v3core.learning import SCHEMA as LEARN_SCHEMA  # noqa: E402
from v3core.student import SCHEMA as STUDENT_SCHEMA  # noqa: E402

# student_kp / mistakes / review_queue / mastery_history 都在同一个库文件里。
# 以前是两个独立连接「一人一半」，现在合成一个连接代理：
# 「记作答 + 记错题 + 排复习」才能落在同一个事务里（红队 P1-11）
_STUDENTS = db.connection(DATA_DIR / "students.db", schema=STUDENT_SCHEMA + LEARN_SCHEMA)
_STUDENT_CONN = _STUDENTS
_LEARN_CONN = _STUDENTS

CHAPTER_NAMES = {ch.id: ch.name for ch in CHAPTERS}


def _kp_rows(student_id: str, subject: str = "数学一") -> dict[str, dict]:
    rows = _STUDENT_CONN.execute(
        "SELECT kp, attempts, correct, last_seen FROM student_kp WHERE student_id=? AND subject=?",
        (student_id, subject),
    ).fetchall()
    return {r["kp"]: dict(r) for r in rows}


def _analytics(student_id: str) -> dict[str, Any]:
    rows = _kp_rows(student_id)
    mastered = mastered_map(student_id)

    heatmap = []
    kp_scores = []
    for kp, meta in KP_TABLE.items():
        rec = rows.get(kp)
        m = learn.kp_mastery(
            int(rec["attempts"]) if rec else 0,
            int(rec["correct"]) if rec else 0,
            float(rec["last_seen"]) if rec else None,
        )
        kp_scores.append({"kp": kp, **m})
        heatmap.append({
            "kp": kp,
            "name": meta["name"],
            "chapter": meta["chapter"],
            "exam_weight": meta["exam_weight"],
            "mastery": m["score"],
            "unknown": m["unknown"],
            "mastered": kp in mastered,
        })

    chapters = learn.chapter_rollup(kp_scores, kp_meta=KP_TABLE)
    for ch in chapters:
        ch["name"] = CHAPTER_NAMES.get(ch["chapter"], ch["chapter"])

    weight_sum = sum(c["weight_sum"] for c in chapters) or 1
    overall = round(sum(c["mastery"] * c["weight_sum"] for c in chapters) / weight_sum, 3)

    due = learn.due_reviews(_LEARN_CONN, student_id=student_id, limit=200)
    for item in due:
        item["name"] = KP_TABLE.get(item["kp_id"], {}).get("name", item["kp_id"])
    return {
        "student_id": student_id,
        "overall": overall,
        "chapters": chapters,
        "heatmap": heatmap,
        "history": learn.history(_LEARN_CONN, student_id=student_id),
        "due": {"count": len(due), "items": due[:10]},
        "coverage": {
            "practiced": sum(1 for h in heatmap if not h["unknown"]),
            "total": len(heatmap),
            "mastered": len(mastered),
        },
    }


@app.get("/api/analytics")
def analytics(student_id: str = DEFAULT_STUDENT) -> dict[str, Any]:
    return _analytics(student_id)


@app.get("/api/review/due")
def review_due(student_id: str = DEFAULT_STUDENT, limit: int = 20) -> dict[str, Any]:
    items = learn.due_reviews(_LEARN_CONN, student_id=student_id, limit=limit)
    for item in items:
        item["name"] = KP_TABLE.get(item["kp_id"], {}).get("name", item["kp_id"])
    return {"student_id": student_id, "items": items, "count": len(items)}


class ReviewAnswerBody(BaseModel):
    student_id: str = DEFAULT_STUDENT
    kp_id: str = Field(..., min_length=2)
    correct: bool


@app.post("/api/review/answer")
def review_answer(body: ReviewAnswerBody) -> dict[str, Any]:
    # 队列推进与曲线快照是一个原子单元：否则可能出现「升档了但曲线没点」
    with db.transaction(_LEARN_CONN):
        result = learn.enqueue_review(
            _LEARN_CONN, student_id=body.student_id, kp_id=body.kp_id, correct=body.correct
        )
        data = _analytics(body.student_id)
        learn.record_snapshot(
            _LEARN_CONN,
            student_id=body.student_id,
            overall=data["overall"],
            chapters=data["chapters"],
            reason=f"review:{body.kp_id}:{'ok' if body.correct else 'fail'}",
        )
    return {"ok": True, **result}


@app.get("/api/ledger")
def ledger(kp_id: str, student_id: str = DEFAULT_STUDENT) -> dict[str, Any]:
    import time as _time

    meta = KP_TABLE.get(kp_id, {})
    row = _kp_rows(student_id).get(kp_id, {})
    attempts = int(row.get("attempts", 0))
    correct = int(row.get("correct", 0))
    m = learn.kp_mastery(attempts, correct, row.get("last_seen"))

    mistakes = _MISTAKE_CONN.execute(
        "SELECT diagnosis, created_at FROM mistakes WHERE student_id=? AND kp_id=? "
        "ORDER BY created_at DESC LIMIT 1",
        (student_id, kp_id),
    ).fetchone()
    diagnosis = {}
    if mistakes:
        try:
            import json as _json
            diagnosis = _json.loads(mistakes["diagnosis"] or "{}")
        except Exception:  # noqa: BLE001
            diagnosis = {}

    due = _LEARN_CONN.execute(
        "SELECT stage, streak, due_at FROM review_queue WHERE student_id=? AND kp_id=?",
        (student_id, kp_id),
    ).fetchone()

    return {
        "kp_id": kp_id,
        "kp_name": meta.get("name", kp_id),
        "scope": "lifetime",
        "attempts": attempts,
        "correct": correct,
        "mastery": m,
        "first_break": diagnosis.get("first_break", ""),
        "misconception": diagnosis.get("misconception", ""),
        "fix": diagnosis.get("fix", ""),
        "next_review": (
            {"stage": due["stage"], "due_at": due["due_at"],
             "in_days": round((due["due_at"] - _time.time()) / 86400, 1),
             "overdue": due["due_at"] <= _time.time()}
            if due else None
        ),
    }


class PracticeMoreBody(BaseModel):
    student_id: str = DEFAULT_STUDENT
    kp_id: str = Field(..., min_length=2)


@app.post("/api/practice_more")
def practice_more(body: PracticeMoreBody) -> dict[str, Any]:
    from v3core.agents import generate_questions_only
    from v3core.schema import QuestionCard

    meta = KP_TABLE.get(body.kp_id)
    if not meta:
        raise HTTPException(status_code=400, detail=f"未知知识点：{body.kp_id}")
    misconception = learn.latest_misconception(_LEARN_CONN, student_id=body.student_id, kp_id=body.kp_id)

    # 出题依据全部来自教材树：题型（解法步骤）+ 例题（同源母题）+ 分支结论
    block = next((b for ch in CHAPTERS for b in ch.blocks if b["id"] == meta.get("block")), {})
    conclusions = [c.get("statement", "") for c in (block.get("conclusions") or []) if c.get("statement")]
    types = meta.get("types") or []
    type_names_set = {(t.get("name") or "").strip() for t in types if t.get("name")}
    examples = meta.get("example_texts") or []

    client = get_llm_client()
    cards: list[dict[str, Any]] = []
    tokens = 0
    calls = 0
    last_error = ""
    types_used: list[str] = []
    for _ in range(2):
        try:
            data = generate_questions_only(
                client,
                kp_name=meta["name"],
                misconception=misconception,
                types=types,
                examples=examples,
                conclusions=conclusions,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue
        tokens += int(data.get("tokens") or 0)
        calls += int(data.get("calls") or 0)
        cards = []
        for item in data["questions"]:
            try:
                card = QuestionCard.model_validate(item).model_dump()
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)[:200]
                logger.warning("题卡校验失败 kp=%s：%s", body.kp_id, last_error)
                continue
            # 纯概念类知识点没有题型，模型会把自己编的题型名填进来 —— 不在清单里的一律清空
            if card.get("type_name") not in type_names_set:
                card["type_name"] = ""
            cards.append(card)
        types_used = [t for t in (data.get("types_used") or []) if t in type_names_set]
        if len(cards) >= 3:
            break
    if len(cards) < 3:
        raise HTTPException(status_code=502, detail=f"题卡不足 3 道：{last_error}")
    return {
        "kp_id": body.kp_id,
        "kp_name": meta["name"],
        "questions": cards[:3],
        "misconception_used": misconception,
        "types_used": types_used,
        "type_names": [t.get("name") for t in types[:4]],
        "examples_used": [e.get("id") for e in examples[:2]],
        "tokens": tokens,
        "calls": calls,
    }


@app.get("/api/health_v3")
def health_v3() -> dict[str, Any]:
    sinks = active_sinks()
    return {
        "status": "ok",
        "version": "3.0.0",
        "components": {
            "lesson": "v3core.nodes.run_lesson_practice",
            "judge": "v3core.judge (SymPy)",
            "checkpointer": "SqliteSaver",
            "llm_client": "v3core.clients.get_llm_client（进程内单例）",
            "db": "v3core.db（每线程连接 + 显式事务）",
        },
        "knowledge_points": len(all_kp_ids()),
        "textbook": TEXTBOOK_NAME,
        "curriculum_version": CURRICULUM_VERSION,
        "mastery_db": str(MASTERY_DB),
        # 断连清理的观测点：正常应为 0，涨上去说明有会话没被回收（红队 P2-8）
        "streams": {"active": len(sinks), "sessions": sinks[:5]},
    }
