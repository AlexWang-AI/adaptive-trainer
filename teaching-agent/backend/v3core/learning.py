"""学习闭环的数据层：掌握度模型 / 间隔复习队列 / 提分曲线 / 考点热力图。

三条原则：
1. **可解释**：每个分数都能拆成「答对率 × 遗忘衰减 × 考频权重」，学生点开能看到算式；
2. **不假精确**：冷启动用 Laplace 平滑（0 次作答 = 50%，不是 100%），区间给 P50；
3. **只读事实**：这里只做聚合与调度，不调用 LLM。

表：
    review_queue   间隔复习（1 / 3 / 7 天三档，连续答对 2 次才升级）
    mastery_history 提分曲线快照（每次通关/复习后记一笔）
    misconception_log 每个知识点最近一次被诊断出的认知偏差（喂回出题）
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS review_queue (
    student_id TEXT NOT NULL,
    kp_id      TEXT NOT NULL,
    stage      INTEGER NOT NULL DEFAULT 0,
    streak     INTEGER NOT NULL DEFAULT 0,
    due_at     REAL NOT NULL,
    last_result INTEGER,
    updated_at REAL NOT NULL,
    PRIMARY KEY (student_id, kp_id)
);
CREATE TABLE IF NOT EXISTS mastery_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    ts          REAL NOT NULL,
    overall     REAL NOT NULL,
    chapters    TEXT NOT NULL,
    reason      TEXT
);
CREATE TABLE IF NOT EXISTS misconception_log (
    student_id TEXT NOT NULL,
    kp_id      TEXT NOT NULL,
    text       TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (student_id, kp_id)
);
"""

REVIEW_INTERVALS = (1.0, 3.0, 7.0)  # 天
HALF_LIFE_DAYS = 14.0


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# 掌握度
# ---------------------------------------------------------------------------
def kp_mastery(attempts: int, correct: int, last_seen: float | None, now: float | None = None) -> dict[str, Any]:
    """单知识点掌握度 = 平滑答对率 × 遗忘衰减。

    返回可解释的中间量，前端点击分数能展开看到。
    """
    now = now or time.time()
    if attempts <= 0:
        return {
            "attempts": 0, "correct": 0, "accuracy": 0.0, "recency": 1.0,
            "days_since": None, "score": 0.0, "unknown": True, "explain": "尚未练习",
        }
    accuracy = (correct + 1) / (attempts + 2)  # Laplace
    days = (now - last_seen) / 86400 if last_seen else 999
    recency = 0.5 ** (max(0.0, days) / HALF_LIFE_DAYS)
    # 最近练过才可信：0.7 基础 + 0.3 新鲜度
    score = accuracy * (0.7 + 0.3 * recency)
    return {
        "attempts": attempts,
        "correct": correct,
        "accuracy": round(accuracy, 3),
        "recency": round(recency, 3),
        "days_since": None if not last_seen else round(max(0.0, days), 1),
        "score": round(max(0.0, min(1.0, score)), 3),
        "unknown": False,
        "explain": f"({correct}+1)/({attempts}+2)={accuracy:.2f} × (0.7+0.3×新鲜度{recency:.2f})",
    }


def chapter_rollup(
    kps: list[dict[str, Any]],
    *,
    kp_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """把知识点聚合到章节（考频加权），给能力雷达用。"""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in kps:
        chapter = kp_meta.get(item["kp"], {}).get("chapter", "other")
        buckets.setdefault(chapter, []).append(item)

    out = []
    for chapter, items in buckets.items():
        weight_sum = sum(kp_meta.get(i["kp"], {}).get("exam_weight", 3) for i in items)
        weighted = sum(
            i["score"] * kp_meta.get(i["kp"], {}).get("exam_weight", 3) for i in items
        )
        # 没练过的知识点按「未知」计入分母，避免只练 1 个点就显示 100%
        out.append(
            {
                "chapter": chapter,
                "mastery": round(weighted / weight_sum, 3) if weight_sum else 0.0,
                "covered": len(items),
                "weight_sum": weight_sum,
            }
        )
    return sorted(out, key=lambda x: x["chapter"])


# ---------------------------------------------------------------------------
# 间隔复习
# ---------------------------------------------------------------------------
def enqueue_review(conn: sqlite3.Connection, *, student_id: str, kp_id: str, correct: bool) -> dict[str, Any]:
    """答错进 1 天档；复习答对累计 streak，满 2 次升一档，7 天档满 2 次毕业。"""
    now = time.time()
    row = conn.execute(
        "SELECT stage, streak, due_at FROM review_queue WHERE student_id=? AND kp_id=?",
        (student_id, kp_id),
    ).fetchone()

    if not correct:
        stage, streak = 0, 0
        due = now + REVIEW_INTERVALS[0] * 86400
        conn.execute(
            "INSERT INTO review_queue (student_id, kp_id, stage, streak, due_at, last_result, updated_at) "
            "VALUES (?,?,?,?,?,0,?) ON CONFLICT(student_id, kp_id) DO UPDATE SET "
            "stage=excluded.stage, streak=excluded.streak, due_at=excluded.due_at, "
            "last_result=0, updated_at=excluded.updated_at",
            (student_id, kp_id, stage, streak, due, now),
        )
        conn.commit()
        return {"stage": stage, "streak": streak, "due_at": due, "graduated": False}

    if row is None:
        # 没进过队列却答对了：不排复习（说明只是随堂答对）
        return {"stage": 0, "streak": 0, "due_at": None, "graduated": False}

    # 没到期就答对不算复习成功——否则同一场练习连点两次就能「毕业」（红队 P1-1）
    if float(row["due_at"]) > now:
        return {"stage": int(row["stage"]), "streak": int(row["streak"]),
                "due_at": float(row["due_at"]), "graduated": False, "not_due": True}

    stage = int(row["stage"])
    streak = int(row["streak"]) + 1
    graduated = False
    if streak >= 2:
        stage += 1
        streak = 0
        if stage >= len(REVIEW_INTERVALS):
            graduated = True

    if graduated:
        conn.execute(
            "DELETE FROM review_queue WHERE student_id=? AND kp_id=?", (student_id, kp_id)
        )
        conn.commit()
        return {"stage": stage, "streak": 0, "due_at": None, "graduated": True}

    due = now + REVIEW_INTERVALS[min(stage, len(REVIEW_INTERVALS) - 1)] * 86400
    conn.execute(
        "UPDATE review_queue SET stage=?, streak=?, due_at=?, last_result=1, updated_at=? "
        "WHERE student_id=? AND kp_id=?",
        (stage, streak, due, now, student_id, kp_id),
    )
    conn.commit()
    return {"stage": stage, "streak": streak, "due_at": due, "graduated": False}


def due_reviews(conn: sqlite3.Connection, *, student_id: str, limit: int = 20) -> list[dict[str, Any]]:
    now = time.time()
    rows = conn.execute(
        "SELECT kp_id, stage, streak, due_at FROM review_queue "
        "WHERE student_id=? AND due_at<=? ORDER BY due_at ASC LIMIT ?",
        (student_id, now, limit),
    ).fetchall()
    return [
        {
            "kp_id": r["kp_id"],
            "stage": r["stage"],
            "streak": r["streak"],
            "due_at": r["due_at"],
            "overdue_days": round((now - r["due_at"]) / 86400, 1),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 提分曲线 / 认知偏差
# ---------------------------------------------------------------------------
def record_snapshot(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    overall: float,
    chapters: list[dict[str, Any]],
    reason: str = "",
) -> None:
    conn.execute(
        "INSERT INTO mastery_history (student_id, ts, overall, chapters, reason) VALUES (?,?,?,?,?)",
        (student_id, time.time(), round(overall, 4), json.dumps(chapters, ensure_ascii=False), reason),
    )
    conn.commit()


def history(conn: sqlite3.Connection, *, student_id: str, limit: int = 40) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT ts, overall, reason FROM mastery_history WHERE student_id=? ORDER BY ts DESC LIMIT ?",
        (student_id, limit),
    ).fetchall()
    return [{"ts": r["ts"], "overall": r["overall"], "reason": r["reason"]} for r in reversed(rows)]


def remember_misconception(conn: sqlite3.Connection, *, student_id: str, kp_id: str, text: str) -> None:
    if not text.strip():
        return
    conn.execute(
        "INSERT INTO misconception_log (student_id, kp_id, text, created_at) VALUES (?,?,?,?) "
        "ON CONFLICT(student_id, kp_id) DO UPDATE SET text=excluded.text, created_at=excluded.created_at",
        (student_id, kp_id, text.strip()[:300], time.time()),
    )
    conn.commit()


def latest_misconception(conn: sqlite3.Connection, *, student_id: str, kp_id: str) -> str:
    row = conn.execute(
        "SELECT text FROM misconception_log WHERE student_id=? AND kp_id=?", (student_id, kp_id)
    ).fetchone()
    return row["text"] if row else ""
