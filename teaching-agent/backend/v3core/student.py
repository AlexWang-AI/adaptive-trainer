"""显式学生模型（跨会话长期记忆）。

为什么需要它？
    LangGraph 的 checkpointer 是 **thread 级**的（一次会话），换天 / 换设备就断；
    教学场景真正需要跨会话留存的是「知识点掌握度」和「错题本」，这两样必须
    落在独立的、可查询的存储里，而不是塞在对话历史里。

设计要点：
    - 只存**结构化事实**（知识点、对错、次数、时间），不存自然语言总结；
    - 掌握度用 Laplace 平滑，冷启动不会出现「0 次尝试 = 100% 掌握」的假象；
    - LLM 只负责「更新」这些字段，不负责「记住」它们。

表结构：
    student_kp(student_id, subject, kp) 主键，累计 attempts/correct/last_seen
    attempt(attempt_id) 主键，逐题作答账本，用于幂等去重
    mistakes(id, student_id, subject, kp, question, student_answer, correct_answer,
             created_at, resolved_at)
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS student_kp (
    student_id TEXT NOT NULL,
    subject    TEXT NOT NULL,
    kp         TEXT NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0,
    correct    INTEGER NOT NULL DEFAULT 0,
    last_seen  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (student_id, subject, kp)
);
CREATE TABLE IF NOT EXISTS attempt (
    attempt_id  TEXT PRIMARY KEY,
    student_id  TEXT NOT NULL,
    subject     TEXT NOT NULL,
    kp          TEXT NOT NULL,
    question_id TEXT NOT NULL DEFAULT '',
    correct     INTEGER NOT NULL,
    layer       TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempt_student ON attempt(student_id, created_at DESC);
CREATE TABLE IF NOT EXISTS mistakes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    subject        TEXT NOT NULL,
    kp             TEXT NOT NULL,
    question       TEXT NOT NULL,
    student_answer TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    created_at     REAL NOT NULL,
    resolved_at    REAL
);
CREATE INDEX IF NOT EXISTS idx_mistakes_student ON mistakes(student_id, subject, created_at DESC);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    """打开（必要时创建）学生模型数据库。同一个连接可跨线程复用。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def mastery(attempts: int, correct: int) -> float:
    """Laplace 平滑后的掌握度，范围 (0, 1)。"""
    return round((correct + 1) / (attempts + 2), 4)


@dataclass
class StudentProfile:
    student_id: str
    subject: str
    kps: list[dict[str, Any]] = field(default_factory=list)
    mistakes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def overall_mastery(self) -> float:
        if not self.kps:
            return 0.0
        return round(sum(k["mastery"] for k in self.kps) / len(self.kps), 4)

    @property
    def weak_points(self) -> list[str]:
        return [k["kp"] for k in sorted(self.kps, key=lambda x: x["mastery"]) if k["mastery"] < 0.5]

    def as_dict(self) -> dict[str, Any]:
        return {
            "student_id": self.student_id,
            "subject": self.subject,
            "overall_mastery": self.overall_mastery,
            "weak_points": self.weak_points,
            "kps": self.kps,
            "mistakes": self.mistakes,
            "stats": {
                "kp_count": len(self.kps),
                "mistake_count": len(self.mistakes),
                "attempts": sum(k["attempts"] for k in self.kps),
            },
        }


def record_attempt(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    subject: str,
    kp: str,
    correct: bool,
    attempt_id: str | None = None,
    question_id: str = "",
    layer: str = "",
) -> bool:
    """记一次作答：更新知识点累计，答错则写入错题本。

    幂等：传了 attempt_id 时，同一个 id 只会记一次；重复调用返回 False。
    没传 attempt_id 时自动生成 UUID（兼容旧调用方），返回 True。
    """
    now = time.time()
    aid = attempt_id or f"auto-{uuid.uuid4().hex}"
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO attempt
        (attempt_id, student_id, subject, kp, question_id, correct, layer, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (aid, student_id, subject, kp, question_id[:80], 1 if correct else 0, layer[:20], now),
    )
    if cur.rowcount == 0:
        conn.commit()
        return False  # 已经记过：不重复加 attempts / 不重复写错题

    conn.execute(
        """
        INSERT INTO student_kp (student_id, subject, kp, attempts, correct, last_seen)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(student_id, subject, kp) DO UPDATE SET
            attempts  = attempts + 1,
            correct   = correct + excluded.correct,
            last_seen = excluded.last_seen
        """,
        (student_id, subject, kp, 1 if correct else 0, now),
    )
    conn.commit()
    return True


def record_mistake(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    subject: str,
    kp: str,
    question: str,
    student_answer: str,
    correct_answer: str,
) -> None:
    conn.execute(
        """
        INSERT INTO mistakes (student_id, subject, kp, question, student_answer,
                              correct_answer, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (student_id, subject, kp, question[:500], student_answer[:200],
         correct_answer[:200], time.time()),
    )
    conn.commit()


def resolve_mistake(conn: sqlite3.Connection, *, student_id: str, subject: str, kp: str) -> int:
    """同一知识点答对时，把未解决的错题标记为已解决。返回更新条数。"""
    cur = conn.execute(
        """
        UPDATE mistakes SET resolved_at = ?
        WHERE student_id = ? AND subject = ? AND kp = ? AND resolved_at IS NULL
        """,
        (time.time(), student_id, subject, kp),
    )
    conn.commit()
    return cur.rowcount


def get_profile(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    subject: str,
    mistake_limit: int = 10,
) -> StudentProfile:
    kp_rows = conn.execute(
        """
        SELECT kp, attempts, correct, last_seen FROM student_kp
        WHERE student_id = ? AND subject = ?
        ORDER BY last_seen DESC
        """,
        (student_id, subject),
    ).fetchall()

    kps = [
        {
            "kp": row["kp"],
            "attempts": row["attempts"],
            "correct": row["correct"],
            "mastery": mastery(row["attempts"], row["correct"]),
            "last_seen": row["last_seen"],
        }
        for row in kp_rows
    ]

    mistake_rows = conn.execute(
        """
        SELECT kp, question, student_answer, correct_answer, created_at, resolved_at
        FROM mistakes WHERE student_id = ? AND subject = ?
        ORDER BY created_at DESC LIMIT ?
        """,
        (student_id, subject, mistake_limit),
    ).fetchall()

    mistakes = [dict(row) for row in mistake_rows]
    return StudentProfile(student_id=student_id, subject=subject, kps=kps, mistakes=mistakes)
