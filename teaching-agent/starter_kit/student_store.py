"""显式学生模型：跨会话掌握度 + 错题 + 复习队列 + 幂等写入。

三条设计：
1. 掌握度、错题、复习计划放独立 SQLite，绝不进 LangGraph checkpoint；
2. `attempt_id` 唯一，恢复/重放不会重复计数；
3. 掌握度用战略公式（原题 0.4 + 变式 0.4 + 正确率 0.2），不是「答对率」。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS student (
    student_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kp_state (
    student_id TEXT NOT NULL,
    kp_id      TEXT NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0,
    correct    INTEGER NOT NULL DEFAULT 0,
    independent_solves INTEGER NOT NULL DEFAULT 0,
    variant_solves     INTEGER NOT NULL DEFAULT 0,
    mastery    REAL NOT NULL DEFAULT 0,
    last_seen  REAL NOT NULL DEFAULT 0,
    next_review_at REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (student_id, kp_id)
);
CREATE TABLE IF NOT EXISTS attempt (
    attempt_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    kp_id      TEXT NOT NULL,
    question_id TEXT NOT NULL,
    correct    INTEGER NOT NULL,
    layer      TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS mistake (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    kp_id      TEXT NOT NULL,
    question_id TEXT NOT NULL,
    student_answer TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    layer TEXT NOT NULL,
    created_at REAL NOT NULL,
    resolved_at REAL
);
CREATE TABLE IF NOT EXISTS review (
    student_id TEXT NOT NULL,
    kp_id      TEXT NOT NULL,
    due_at     REAL NOT NULL,
    interval_days INTEGER NOT NULL DEFAULT 1,
    ease       REAL NOT NULL DEFAULT 2.5,
    PRIMARY KEY (student_id, kp_id)
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def mastery(attempts: int, correct: int, independent: int, variant: int) -> float:
    if attempts <= 0:
        return 0.0
    accuracy = correct / attempts
    return round(
        0.4 * min(independent / 2.0, 1.0)
        + 0.4 * min(variant / 1.0, 1.0)
        + 0.2 * min(accuracy, 1.0),
        4,
    )


def record_attempt(
    conn: sqlite3.Connection,
    *,
    attempt_id: str,
    student_id: str,
    kp_id: str,
    question_id: str,
    correct: bool,
    layer: str,
    is_variant: bool,
    answer: str = "",
    correct_answer: str = "",
    now: float | None = None,
) -> bool:
    """幂等记一次作答。返回 True 表示本次真的写入；False 表示重复重放。"""
    now = time.time() if now is None else now
    conn.execute(
        "INSERT OR IGNORE INTO student (student_id, created_at) VALUES (?, ?)",
        (student_id, now),
    )
    cur = conn.execute(
        "INSERT OR IGNORE INTO attempt "
        "(attempt_id, student_id, kp_id, question_id, correct, layer, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (attempt_id, student_id, kp_id, question_id, 1 if correct else 0, layer, now),
    )
    if cur.rowcount == 0:
        conn.commit()
        return False  # 已经记过：不要重复加 attempts / 重复写错题

    row = conn.execute(
        "SELECT attempts, correct, independent_solves, variant_solves FROM kp_state "
        "WHERE student_id=? AND kp_id=?",
        (student_id, kp_id),
    ).fetchone()
    attempts = (row["attempts"] if row else 0) + 1
    correct_n = (row["correct"] if row else 0) + (1 if correct else 0)
    independent = (row["independent_solves"] if row else 0) + (1 if correct and not is_variant else 0)
    variant = (row["variant_solves"] if row else 0) + (1 if correct and is_variant else 0)
    m = mastery(attempts, correct_n, independent, variant)

    interval = _next_interval(conn, student_id, kp_id, correct)
    next_review = now + interval * 86400
    conn.execute(
        "INSERT INTO kp_state "
        "(student_id, kp_id, attempts, correct, independent_solves, variant_solves, mastery, last_seen, next_review_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(student_id, kp_id) DO UPDATE SET "
        "attempts=excluded.attempts, correct=excluded.correct, "
        "independent_solves=excluded.independent_solves, variant_solves=excluded.variant_solves, "
        "mastery=excluded.mastery, last_seen=excluded.last_seen, next_review_at=excluded.next_review_at",
        (student_id, kp_id, attempts, correct_n, independent, variant, m, now, next_review),
    )
    conn.execute(
        "INSERT INTO review (student_id, kp_id, due_at, interval_days, ease) VALUES (?, ?, ?, ?, 2.5) "
        "ON CONFLICT(student_id, kp_id) DO UPDATE SET "
        "due_at=excluded.due_at, interval_days=excluded.interval_days",
        (student_id, kp_id, next_review, interval),
    )
    if not correct:
        conn.execute(
            "INSERT INTO mistake "
            "(student_id, kp_id, question_id, student_answer, correct_answer, layer, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (student_id, kp_id, question_id, answer[:300], correct_answer[:200], layer, now),
        )
    conn.commit()
    return True


def _next_interval(conn: sqlite3.Connection, student_id: str, kp_id: str, correct: bool) -> int:
    row = conn.execute(
        "SELECT interval_days FROM review WHERE student_id=? AND kp_id=?",
        (student_id, kp_id),
    ).fetchone()
    old = int(row["interval_days"]) if row else 1
    return max(1, old * 2) if correct else 1


def get_state(conn: sqlite3.Connection, student_id: str, kp_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM kp_state WHERE student_id=? AND kp_id=?",
        (student_id, kp_id),
    ).fetchone()
    return dict(row) if row else {
        "student_id": student_id,
        "kp_id": kp_id,
        "attempts": 0,
        "correct": 0,
        "independent_solves": 0,
        "variant_solves": 0,
        "mastery": 0.0,
        "last_seen": 0.0,
        "next_review_at": 0.0,
    }


def get_profile(conn: sqlite3.Connection, student_id: str, limit: int = 10) -> dict[str, Any]:
    kps = [dict(r) for r in conn.execute(
        "SELECT * FROM kp_state WHERE student_id=? ORDER BY last_seen DESC", (student_id,)
    ).fetchall()]
    mistakes = [dict(r) for r in conn.execute(
        "SELECT * FROM mistake WHERE student_id=? AND resolved_at IS NULL "
        "ORDER BY created_at DESC LIMIT ?", (student_id, limit)
    ).fetchall()]
    return {
        "student_id": student_id,
        "kps": kps,
        "mistakes": mistakes,
        "attempts": sum(k["attempts"] for k in kps),
        "mastered": [k["kp_id"] for k in kps if k["mastery"] >= 0.9],
    }


def due_reviews(conn: sqlite3.Connection, student_id: str, now: float | None = None) -> list[dict[str, Any]]:
    now = time.time() if now is None else now
    rows = conn.execute(
        "SELECT r.*, s.mastery FROM review r JOIN kp_state s "
        "ON s.student_id=r.student_id AND s.kp_id=r.kp_id "
        "WHERE r.student_id=? AND r.due_at<=? ORDER BY r.due_at",
        (student_id, now),
    ).fetchall()
    return [dict(r) for r in rows]


def count_attempts(conn: sqlite3.Connection, student_id: str) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM attempt WHERE student_id=?", (student_id,)).fetchone()
    return int(row["n"])
