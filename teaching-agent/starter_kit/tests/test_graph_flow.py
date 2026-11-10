import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from fake_llm import FakeLLM
from graph import build_graph, initial_state
from student_store import connect, count_attempts, get_state
from trace import Tracer


def _make(tmp_path, *, mutate=False):
    conn = connect(":memory:")
    tracer = Tracer(tmp_path / "trace.jsonl")
    graph = build_graph(
        SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False)),
        client=FakeLLM(mutate=mutate),
        student_conn=conn,
        tracer=tracer,
    )
    return graph, conn, tracer


def test_full_round_and_mastery(tmp_path):
    graph, conn, _ = _make(tmp_path)
    sid, state = initial_state(kp_id="der.basic", student_id="s1", max_rounds=1)
    config = {"configurable": {"thread_id": sid}, "recursion_limit": 40}
    graph.invoke(state, config)

    values = graph.get_state(config).values
    assert values["status"] == "awaiting_answer"
    assert len(values["questions"]) == 2
    assert values["question"]["id"] == "der.q1"

    graph.invoke(Command(resume="B"), config)
    values = graph.get_state(config).values
    assert values["status"] == "awaiting_answer"
    assert values["q_index"] == 1

    graph.invoke(Command(resume="2x"), config)
    values = graph.get_state(config).values
    assert values["status"] == "done"
    assert len(values["answers"]) == 2
    assert count_attempts(conn, "s1") == 2
    assert get_state(conn, "s1", "der.basic")["mastery"] == 0.8


def test_wrong_answer_is_judged_false(tmp_path):
    graph, conn, _ = _make(tmp_path)
    sid, state = initial_state(kp_id="der.basic", student_id="s2", max_rounds=1)
    config = {"configurable": {"thread_id": sid}, "recursion_limit": 40}
    graph.invoke(state, config)
    graph.invoke(Command(resume="A"), config)
    values = graph.get_state(config).values
    assert values["judgement"]["correct"] is False
    assert values["judgement"]["layer"] == "choice"


def test_mutated_question_answer_does_not_fool_judge(tmp_path):
    """FakeLLM 把第一题答案写错，但判题用独立答案键，学生答 B 仍应判对。"""
    graph, _, _ = _make(tmp_path, mutate=True)
    sid, state = initial_state(kp_id="der.basic", student_id="s3", max_rounds=1)
    config = {"configurable": {"thread_id": sid}, "recursion_limit": 40}
    graph.invoke(state, config)
    values = graph.get_state(config).values
    assert values["questions"][0]["answer"] != "B"  # 模型写错了
    graph.invoke(Command(resume="B"), config)
    values = graph.get_state(config).values
    assert values["judgement"]["correct"] is True  # 独立答案键纠偏
