"""v3 图流程测试：讲练合一（一次调用）+ 3 题循环 + 错误路由 + 预算降级。"""

from __future__ import annotations

from langgraph.types import Command

from core.student import get_profile


def _cfg(sid: str) -> dict:
    return {"configurable": {"thread_id": sid}, "recursion_limit": 80}


def _run(compiled, state, sid: str):
    compiled.invoke(state, _cfg(sid))
    return compiled.get_state(_cfg(sid)).values


def test_one_call_generates_lesson_and_three_questions(patched_graph, fake_client):
    graph_module, compiled = patched_graph
    sid, state = graph_module.initial_state(topic="什么是导数", max_rounds=3)

    values = _run(compiled, state, sid)
    assert values["status"] == "awaiting_answer"
    assert len(values["questions"]) == 3
    assert values["q_index"] == 0
    assert values["question"]["stem"] == values["questions"][0]["stem"]
    # 只有一次 LLM 调用：讲练合一
    assert len(fake_client.calls) == 1
    assert values["ttft_ms"] > 0
    assert values["score"]["total"] >= 75


def test_three_answers_advance_to_next_round(patched_graph, fake_client):
    graph_module, compiled = patched_graph
    sid, state = graph_module.initial_state(topic="什么是导数", max_rounds=3, student_id="stu-1")
    _run(compiled, state, sid)

    # 第 1 题答对
    compiled.invoke(Command(resume="A"), _cfg(sid))
    values = compiled.get_state(_cfg(sid)).values
    assert values["q_index"] == 1
    assert values["status"] == "awaiting_answer"
    assert values["judgement"]["correct"] is True

    # 第 2 题答错（数值层能判）
    compiled.invoke(Command(resume="0.4"), _cfg(sid))
    values = compiled.get_state(_cfg(sid)).values
    assert values["q_index"] == 2
    assert values["judgement"]["correct"] is False

    # 第 3 题答对 → 进入下一轮，图自动再调一次 lesson
    compiled.invoke(Command(resume="0.5"), _cfg(sid))
    values = compiled.get_state(_cfg(sid)).values
    assert values["round"] == 1
    assert values["status"] == "awaiting_answer"
    assert values["q_index"] == 0
    assert len(fake_client.calls) == 2  # 第二轮又调用了一次

    profile = get_profile(patched_graph[0].get_student_conn(), student_id="stu-1", subject="数学一")
    assert sum(k["attempts"] for k in profile.kps) == 3
    assert profile.mistakes, "第 2 题答错应写入错题本"


def test_last_round_ends_the_session(patched_graph):
    graph_module, compiled = patched_graph
    sid, state = graph_module.initial_state(topic="什么是导数", max_rounds=1)
    _run(compiled, state, sid)

    for answer in ("A", "0.5", "0.5"):
        compiled.invoke(Command(resume=answer), _cfg(sid))

    values = compiled.get_state(_cfg(sid)).values
    assert values["status"] == "done"
    assert values["teaching"] is None


def test_lesson_failure_routes_to_end(patched_graph, monkeypatch):
    graph_module, compiled = patched_graph
    from tests.conftest import FakeClient

    broken = FakeClient(fail_lesson=True)
    monkeypatch.setattr(graph_module, "get_client", lambda: broken)

    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver

    compiled2 = graph_module.build_graph(checkpointer=SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False)))
    sid, state = graph_module.initial_state(topic="什么是导数", max_rounds=3)
    compiled2.invoke(state, _cfg(sid))

    values = compiled2.get_state(_cfg(sid)).values
    assert values["status"] == "error"
    assert "讲练节点失败" in values["error"]
    assert not values.get("questions")


def test_budget_exhaustion_degrades(patched_graph):
    graph_module, compiled = patched_graph
    sid, state = graph_module.initial_state(topic="什么是导数", token_budget=1)
    _run(compiled, state, sid)

    values = compiled.get_state(_cfg(sid)).values
    assert values["status"] == "degraded"
    assert values["history"][-1]["role"] == "teacher"


def test_trace_records_ttft(patched_graph, tracer):
    graph_module, compiled = patched_graph
    sid, state = graph_module.initial_state(topic="什么是导数", max_rounds=1)
    _run(compiled, state, sid)

    nodes = [row for row in tracer.read() if row["kind"] == "node"]
    assert nodes and nodes[0]["node"] == "lesson"
    assert nodes[0]["ttft_ms"] > 0
    assert nodes[0]["latency_ms"] >= nodes[0]["ttft_ms"]
