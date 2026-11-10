"""离线演示：不需要 API Key，跑完一课并打印判题/掌握度/trace。"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from content import DEMO_ANSWERS, all_kp_ids, get_answer_key
from graph import build_graph, initial_state
from student_store import connect, get_profile
from trace import Tracer, aggregate

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kp", default="der.basic", choices=all_kp_ids())
    parser.add_argument("--real", action="store_true", help="用真实 DeepSeek，而不是 FakeLLM")
    parser.add_argument("--mutate", action="store_true", help="FakeLLM 故意写错一题，验证独立答案键")
    args = parser.parse_args()

    if args.real:
        from llm import LLMClient

        client = LLMClient()
    else:
        from fake_llm import FakeLLM

        client = FakeLLM(mutate=args.mutate)

    student_conn = connect(":memory:")
    sid, state = initial_state(kp_id=args.kp, student_id="demo-student", max_rounds=2)
    tracer = Tracer(ROOT / "runs" / f"demo-{sid}.jsonl")
    graph = build_graph(
        SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False)),
        client=client,
        student_conn=student_conn,
        tracer=tracer,
    )
    config = {"configurable": {"thread_id": sid}, "recursion_limit": 60}

    graph.invoke(state, config)
    values = graph.get_state(config).values
    print("=" * 72)
    print(f"知识点：{args.kp}　会话：{sid}　模式：{'real' if args.real else 'fake'}")
    print("=" * 72)
    print(values.get("lesson", {}).get("reply_markdown", ""))
    print("\n--- 题卡 ---")
    for i, q in enumerate(values.get("questions", []), 1):
        key = get_answer_key(q["id"])
        print(f"{i}. [{q['kind']}] {q['stem']}  {q.get('options', [])}")
        print(f"   模型答案：{q['answer']}　｜　独立答案键：{key.answer}")

    answers = DEMO_ANSWERS[args.kp]
    guard = 0
    while graph.get_state(config).values.get("status") == "awaiting_answer" and guard < 8:
        current = graph.get_state(config).values
        idx = int(current.get("q_index", 0))
        q = current["question"]
        answer = answers[idx] if idx < len(answers) else "0"
        print(f"\n>>> 作答 {q['id']}：{answer}")
        graph.invoke(Command(resume=answer), config)
        latest = graph.get_state(config).values
        j = latest.get("judgement") or {}
        print(f"    判题：{j.get('correct')}　layer={j.get('layer')}　{j.get('reason')}")
        guard += 1

    final = graph.get_state(config).values
    print("\n--- 最终状态 ---")
    print("status:", final.get("status"), "| tokens:", final.get("tokens"), "| answers:", len(final.get("answers", [])))
    profile = get_profile(student_conn, "demo-student")
    print("掌握度：", {k["kp_id"]: k["mastery"] for k in profile["kps"]})
    print("错题数：", len(profile["mistakes"]))
    print("trace：", aggregate(tracer.read()))
    print("\n提示：把 --mutate 加上再跑一次，观察题卡答案错了但判题仍按独立答案键判。")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
