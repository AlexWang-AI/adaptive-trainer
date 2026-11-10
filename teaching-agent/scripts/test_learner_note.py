"""P1-4 回归：学习画像必须真的进到讲课请求里。

红队原话：`learner_note` 只在 `round > 0` 时注入，而 v3 的图只剩 lesson 一个节点、
round 永远是 0 —— 也就是说「按你的掌握度调整讲解」从来没生效过。

本脚本验三件事：
1. 接线：`lesson_node` 在 round=0 时也会把画像交给 `build_request`；
2. 内容：画像里有当前知识点的中文名、作答次数、掌握度、上次诊断出的认知偏差，
   且长度不超 schema 的 400 字上限；
3. 提示词：非空画像会带一句「怎么用这条画像」的指令，空画像不会凭空多出这一段。

用法（后端那套 Python，带 langgraph）：

    cd backend && ..\\..\\python  scripts\\test_learner_note.py
    # 实际：
    C:\\...\\Python311\\python.exe scripts\\test_learner_note.py
"""

from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import v3core.graph as graph  # noqa: E402
import v3core.learning as learn  # noqa: E402
import v3core.student as student_mod  # noqa: E402
from curriculum import KP_TABLE  # noqa: E402
from v3core.prompts import build_lesson_practice_system_prompt  # noqa: E402
from v3core.schema import TeachingRequest  # noqa: E402

KP_NAME = KP_TABLE["l03-b01-k01"]["name"]

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"{'PASS' if ok else 'FAIL'}  {label}{('  — ' + detail) if detail else ''}")


def build_temp_profile() -> tuple[object, object]:
    """临时库里的学生：2 次作答答对 1 次 + 一条认知偏差。"""
    tmp = Path(tempfile.mkdtemp(prefix="p14-"))
    conn = student_mod.connect(tmp / "students.db")
    student_mod.record_attempt(conn, student_id="u1", subject="数学一", kp="l03-b01-k01", correct=True)
    student_mod.record_attempt(conn, student_id="u1", subject="数学一", kp="l03-b01-k01", correct=False)
    student_mod.record_attempt(conn, student_id="u1", subject="数学一", kp="l01-b02-k01", correct=True)
    learning = learn.connect(tmp / "students.db")
    learn.remember_misconception(
        learning,
        student_id="u1",
        kp_id="l03-b01-k01",
        text="把「可导」和「连续」当成同一件事，先算再说条件",
    )
    return conn, learning


def main() -> int:
    conn, learning = build_temp_profile()
    graph.get_student_conn = lambda: conn  # type: ignore[assignment]
    graph.get_learning_conn = lambda: learning  # type: ignore[assignment]

    # --- 1. 画像内容 -------------------------------------------------------
    note = graph.learner_note({"student_id": "u1", "subject": "数学一", "kp": "l03-b01-k01"})
    print(f"\n画像原文（{len(note)} 字）：{note}\n")
    check("画像非空（round=0 也有）", bool(note.strip()))
    check("用了中文知识点名而不是内部 id", KP_NAME in note and "l03-b01-k01" not in note, KP_NAME)
    check("带上本轮知识点的作答次数", "2 次作答" in note or "作答 2 次" in note, note[:80])
    check("带上掌握度百分比", "50%" in note)
    check("带上上次诊断出的认知偏差", "可导" in note and "连续" in note)
    check("长度不超过 schema 上限 400", len(note) <= 400, f"{len(note)} 字")

    # 没练过的知识点不能编造「本轮作答」；跨知识点的历史薄弱点仍然可以给
    empty_note = graph.learner_note({"student_id": "u1", "subject": "数学一", "kp": "ser.fourier"})
    check("没练过的点不编造本轮数据", "本轮知识点" not in empty_note, empty_note or "(空)")

    # --- 2. 接线：lesson_node 必须把画像交给 build_request ---------------
    captured: dict[str, str] = {}
    real_build_request = graph.build_request

    def spy_build_request(state, learner_note=""):  # noqa: ANN001
        captured["note"] = learner_note
        return real_build_request(state, learner_note)

    class FakeResult:
        payload = None
        raw = ""
        issues = ["fake：只为抓到请求就返回"]
        attempts = 1
        usage: dict = {}
        latency_ms = 0.0
        ttft_ms = 0.0
        attempt_log: list = []

    graph.build_request = spy_build_request  # type: ignore[assignment]
    graph.run_lesson_practice = lambda req, client, on_markdown=None: FakeResult()  # type: ignore[assignment]
    graph.get_client = lambda: None  # type: ignore[assignment]
    graph.get_tracer = lambda: types.SimpleNamespace(event=lambda *a, **k: None)  # type: ignore[assignment]

    state = {
        "session_id": "p14-test",
        "student_id": "u1",
        "subject": "数学一",
        "topic": "导数的定义",
        "kp": "l03-b01-k01",
        "round": 0,  # ← 红队指的就是这个 0
        "token_budget": 60000,
        "tokens_used": 0,
        "student_message": "",
        "history": [],
    }
    graph.lesson_node(state)
    check("lesson_node 在 round=0 时把画像交给 build_request", bool(captured.get("note", "").strip()),
          f"note={captured.get('note', '')[:40]}...")

    # --- 3. 提示词 --------------------------------------------------------
    req = TeachingRequest(topic="导数的定义", level="大学低年级", subject="数学一", learner_note=note)
    system_prompt = build_lesson_practice_system_prompt(req)
    check("系统提示词里出现画像原文", note in system_prompt)
    check("系统提示词告诉模型怎么用画像", "学习画像" in system_prompt and "掌握度" in system_prompt)

    bare = build_lesson_practice_system_prompt(
        TeachingRequest(topic="导数的定义", level="大学低年级", subject="数学一", learner_note="")
    )
    check("空画像不凭空出现画像段", "学习画像" not in bare)

    total = len(PASSED) + len(FAILED)
    print(f"\n==== {len(PASSED)}/{total} 通过 ====")
    if FAILED:
        for item in FAILED:
            print(f"  ✗ {item}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
