"""判题账本回归：幂等 + 独立答案键。

    python scripts/test_judge_ledger.py

不联网、不启服务。覆盖：
1. `record_attempt` 同一 attempt_id 只记一次；
2. 不同 attempt 正常累计，错题只写一次；
3. `judge(..., answer_key=...)` 优先于题卡里的 answer；
4. `/api/judge` 直接调用两次，第二次 duplicate=True，attempts 仍为 1；
5. 独立答案键能纠正题卡里的错误答案。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from v3core import db  # noqa: E402
from v3core.judge import judge  # noqa: E402
from v3core.learning import SCHEMA as LEARN_SCHEMA  # noqa: E402
from v3core.student import SCHEMA as STUDENT_SCHEMA, connect as student_connect, record_attempt  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"{'PASS' if ok else 'FAIL'}  {label}{('  — ' + detail) if detail else ''}")


def test_record_attempt_idempotent() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="judge-ledger-"))
    conn = student_connect(tmp / "students.db")
    kwargs = dict(
        student_id="s1", subject="数学一", kp="l01-b01-k01",
        correct=True, attempt_id="s1:q1:B", question_id="q1", layer="choice",
    )
    check("首次写入返回 True", record_attempt(conn, **kwargs) is True)
    check("重复写入返回 False", record_attempt(conn, **kwargs) is False)

    row = conn.execute(
        "SELECT attempts, correct FROM student_kp WHERE student_id=? AND kp=?",
        ("s1", "l01-b01-k01"),
    ).fetchone()
    check("重复后 attempts 仍为 1", int(row["attempts"]) == 1, f"attempts={row['attempts']}")
    n = conn.execute("SELECT COUNT(*) AS n FROM attempt WHERE student_id='s1'").fetchone()["n"]
    check("attempt 账本只有 1 行", int(n) == 1, f"n={n}")

    # 换答案（先错后对）应产生新 attempt
    ok = record_attempt(
        conn, student_id="s1", subject="数学一", kp="l01-b01-k01",
        correct=False, attempt_id="s1:q1:A", question_id="q1", layer="choice",
    )
    row = conn.execute(
        "SELECT attempts, correct FROM student_kp WHERE student_id=? AND kp=?",
        ("s1", "l01-b01-k01"),
    ).fetchone()
    check("不同答案产生新 attempt", ok is True and int(row["attempts"]) == 2, f"attempts={row['attempts']}")
    check("答错不污染 correct", int(row["correct"]) == 1, f"correct={row['correct']}")


def test_judge_answer_key_override() -> None:
    question = {
        "kind": "choice",
        "stem": "设 f(x)=x²，f'(2)=？",
        "options": ["2", "4", "8", "1"],
        "answer": "B",  # 题卡声称 B
        "explanation": "2x 代入 2 得 4",
        "tested_points": ["l03-b01-k01"],
        "difficulty": "easy",
    }
    v1 = judge(question, "A", answer_key="A", allow_llm=False)
    check("独立答案键 A 时，答 A 判对", v1.correct is True and v1.layer == "choice", v1.reason)
    v2 = judge(question, "A", answer_key="B", allow_llm=False)
    check("独立答案键 B 时，答 A 判错", v2.correct is False and v2.layer == "choice", v2.reason)
    v3 = judge(question, "B", answer_key="A", allow_llm=False)
    check("题卡 B 不会覆盖独立答案键 A", v3.correct is False, v3.reason)


def test_api_judge_duplicate() -> None:
    import api_server

    tmp = Path(tempfile.mkdtemp(prefix="judge-api-"))
    conn = db.connection(tmp / "students.db", schema=STUDENT_SCHEMA + LEARN_SCHEMA)
    api_server._STUDENT_CONN = conn  # type: ignore[attr-defined]
    api_server._LEARN_CONN = conn  # type: ignore[attr-defined]

    body = api_server.JudgeBody(
        question={
            "id": "q-api-1",
            "kind": "choice",
            "stem": "1+1=？",
            "options": ["1", "2", "3", "4"],
            "answer": "B",
            "explanation": "显然",
            "tested_points": ["l01-b01-k01"],
            "difficulty": "easy",
        },
        answer="B",
        student_id="api-student",
        kp_id="l01-b01-k01",
        question_id="q-api-1",
        answer_key="B",
        allow_llm=False,
    )
    r1 = api_server.judge(body)
    r2 = api_server.judge(body)
    check("首次判题 duplicate=False", r1["duplicate"] is False, str(r1.get("attempt_id")))
    check("重复判题 duplicate=True", r2["duplicate"] is True, str(r2.get("attempt_id")))
    check("两次 attempt_id 一致", r1["attempt_id"] == r2["attempt_id"])

    row = conn.execute(
        "SELECT attempts, correct FROM student_kp WHERE student_id='api-student' AND kp='l01-b01-k01'"
    ).fetchone()
    check("重复判题后 attempts 仍为 1", int(row["attempts"]) == 1, f"attempts={row['attempts']}")

    # 独立答案键纠正题卡：题卡写 A，答案键写 B，学生答 B 应判对
    body2 = api_server.JudgeBody(
        question={
            "id": "q-api-2", "kind": "choice", "stem": "2+2=？",
            "options": ["3", "4", "5", "6"], "answer": "A",
            "explanation": "4", "tested_points": ["l01-b01-k01"], "difficulty": "easy",
        },
        answer="B",
        student_id="api-student-2",
        kp_id="l01-b01-k01",
        question_id="q-api-2",
        answer_key="B",
        allow_llm=False,
    )
    r3 = api_server.judge(body2)
    check("API 独立答案键纠正题卡", r3["correct"] is True and r3["correct_answer"] == "B", str(r3))


def main() -> int:
    test_record_attempt_idempotent()
    test_judge_answer_key_override()
    test_api_judge_duplicate()
    print(f"\n==== {len(PASSED)}/{len(PASSED) + len(FAILED)} 通过 ====")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())
