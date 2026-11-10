"""测试夹具：假 LLM（支持流式）+ 临时持久化，跑图不需要真实 API。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.student import connect as connect_student_db  # noqa: E402
from core.trace import Tracer  # noqa: E402

REPLY = (
    "先别急着记公式。我们把「导数」当成一个动作来看：\n\n"
    "**第一步，看一段的平均。** 你开车从家到学校，10 分钟走了 5 公里，"
    "平均速度就是 0.5 公里每分钟。这是「一段」的账。\n\n"
    "**第二步，把这段缩短。** 缩到 1 分钟、1 秒，平均速度会越来越接近某一个数。"
    "这个「缩到几乎为 0 时逼近的数」，就是瞬时速度。\n\n"
    "**第三步，给它一个名字。** 我们把这个数叫作导数。"
    "它不是另一个公式，它就是「把一段缩到一点」这个动作的结果，"
    "而「变化率」说的就是这种「一个量变化得有多快」。\n\n"
    "**检查一下：** 如果一辆车 2 分钟走了 1 公里，它这 2 分钟的平均速度是多少？"
)

LESSON_JSON: dict[str, Any] = {
    "teaching": {
        "reply_markdown": REPLY,
        "core_idea": "导数是把一段的平均变化缩到一点后逼近的那个数，也就是瞬时变化率。",
        "order_rationale": "学生只会背公式，所以先用开车场景建立一段与一点的区别，再引入名字。",
        "analogy": "汽车速度表：不告诉你整段路开了多久，只告诉你此刻这一刻有多快。",
        "example": "10 分钟 5 公里，平均速度 0.5 公里每分钟；缩到 1 分钟后这个数会变。",
        "jargon": [
            {"term": "导数", "plain_explanation": "把一段的平均变化缩到一点时逼近的那个数。"},
            {"term": "变化率", "plain_explanation": "一个量变化得有多快，比如位置变化快就是速度大。"},
            {"term": "平均速度", "plain_explanation": "一段路的总距离除以总时间，算的是整段的平均。"},
            {"term": "瞬时", "plain_explanation": "某一刻的意思，比如速度表指针此刻指的那个数。"},
        ],
        "check_question": "2 分钟走 1 公里，平均速度是多少？",
        "invite_question": "你是卡在「一段」和「一点」的区别上，还是卡在具体那个数怎么算出来？",
        "next_step": "自己举一个「一段路变短、平均速度趋近某个数」的例子。",
        "assumptions": ["学生会算除法"],
        "confidence": "high",
    },
    "questions": [
        {
            "kind": "choice",
            "stem": "一辆车 2 分钟走了 1 公里，它这 2 分钟的平均速度是多少？",
            "options": ["0.5 公里每分钟", "2 公里每分钟", "1 公里每分钟", "0.2 公里每分钟"],
            "answer": "A",
            "explanation": "平均速度等于总距离除以总时间，1 除以 2 等于 0.5。",
            "tested_points": ["平均速度"],
            "difficulty": "easy",
            "why_this_question": "刚才讲的第一步就是「一段的平均」，这题正好对上学生这一轮的卡点。",
            "source_quote": "如果一辆车 2 分钟走了 1 公里",
            "confidence": "high",
        },
        {
            "kind": "fill",
            "stem": "一辆车 4 分钟走了 2 公里，平均速度是多少公里每分钟？只填数字。",
            "options": [],
            "answer": "0.5",
            "explanation": "2 除以 4 等于 0.5，和上一题是同一个平均速度。",
            "tested_points": ["平均速度"],
            "difficulty": "easy",
            "why_this_question": "换一组数字，检查学生是不是真的会算平均速度，而不是记住上一题。",
            "source_quote": "10 分钟走了 5 公里",
            "confidence": "high",
        },
        {
            "kind": "fill",
            "stem": "把 10 分钟 5 公里缩成 1 分钟，平均速度是多少公里每分钟？",
            "options": [],
            "answer": "0.5",
            "explanation": "距离和时间同比缩小，比值不变，仍然是 0.5。",
            "tested_points": ["变化率"],
            "difficulty": "medium",
            "why_this_question": "这题测「缩到一点」这一步，对应学生这一轮最可能卡住的动作。",
            "source_quote": "缩到 1 分钟、1 秒",
            "confidence": "high",
        },
    ],
}

JUDGE_JSON: dict[str, Any] = {"equivalent": True, "reason": "数值相同，写法不同"}


class FakeClient:
    """按 system prompt 分派假响应；stream_json 会按块回调，模拟真实流式。"""

    def __init__(self, *, fail_lesson: bool = False, payload: dict | None = None) -> None:
        self.calls: list[str] = []
        self.fail_lesson = fail_lesson
        self.payload = payload or LESSON_JSON

    def stream_json(self, messages, temperature=0.3, max_tokens=4000, on_delta=None, retries=2, **_):
        system = messages[0]["content"] if messages else ""
        self.calls.append(system[:40])
        if self.fail_lesson:
            raise RuntimeError("模拟讲练失败")
        text = json.dumps(self.payload, ensure_ascii=False)
        if on_delta is not None:
            for i in range(0, len(text), 80):
                on_delta(text[i : i + 80])
        usage = {"prompt_tokens": 900, "completion_tokens": 900, "total_tokens": 1800}
        return text, usage, 3200, 480

    def chat_json(self, messages, temperature=0.25, max_tokens=3000, **_):
        system = messages[0]["content"] if messages else ""
        self.calls.append(system[:40])
        if "判题助手" in system:
            return json.dumps(JUDGE_JSON, ensure_ascii=False), {"total_tokens": 80}, 40
        if "出题节点" in system:
            return json.dumps(self.payload["questions"][0], ensure_ascii=False), {"total_tokens": 400}, 200
        return json.dumps(self.payload["teaching"], ensure_ascii=False), {"total_tokens": 800}, 300


@pytest.fixture()
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture()
def student_conn(tmp_path):
    conn = connect_student_db(tmp_path / "students.db")
    yield conn
    conn.close()


@pytest.fixture()
def tracer(tmp_path) -> Tracer:
    return Tracer(tmp_path / "trace.jsonl")


@pytest.fixture()
def patched_graph(monkeypatch, fake_client, student_conn, tracer):
    """把图里的三个全局依赖换成测试替身，返回 (graph_module, compiled_graph)。"""
    from core import graph as graph_module
    from langgraph.checkpoint.sqlite import SqliteSaver
    import sqlite3

    monkeypatch.setattr(graph_module, "get_client", lambda: fake_client)
    monkeypatch.setattr(graph_module, "get_student_conn", lambda: student_conn)
    monkeypatch.setattr(graph_module, "get_tracer", lambda: tracer)

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    compiled = graph_module.build_graph(checkpointer=SqliteSaver(conn))
    return graph_module, compiled
