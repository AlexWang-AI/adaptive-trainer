"""评测：独立答案键 + pass^k。

pass^k 的定义：同一用例跑 k 次，k 次全部「判题与期望一致」才算通过。
只看 pass@1 会掩盖「偶尔判错」的可靠性问题。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from content import EVAL_CASES
from fake_llm import FakeLLM
from graph import build_graph, initial_state
from student_store import connect
from trace import Tracer, aggregate

ROOT = Path(__file__).resolve().parent


def run_once(case: dict, *, mutate: bool) -> dict:
    tracer = Tracer(ROOT / "runs" / f"eval-{case['id']}-{uuid.uuid4().hex[:6]}.jsonl")
    conn = connect(":memory:")
    graph = build_graph(
        SqliteSaver(sqlite3.connect(":memory:", check_same_thread=False)),
        client=FakeLLM(mutate=mutate),
        student_conn=conn,
        tracer=tracer,
    )
    sid, state = initial_state(
        kp_id=case["kp_id"],
        student_id=f"eval-{case['id']}",
        max_rounds=1,
    )
    config = {"configurable": {"thread_id": sid}, "recursion_limit": 40}
    graph.invoke(state, config)

    judged: list[bool] = []
    guard = 0
    while graph.get_state(config).values.get("status") == "awaiting_answer" and guard < 6:
        current = graph.get_state(config).values
        idx = int(current.get("q_index", 0))
        answer = case["answers"][idx]
        graph.invoke(Command(resume=answer), config)
        j = graph.get_state(config).values.get("judgement") or {}
        judged.append(bool(j.get("correct")))
        guard += 1

    expected = case["expected"]
    agreement = sum(1 for a, b in zip(judged, expected) if a == b) / max(1, len(expected))
    return {
        "case": case["id"],
        "judged": judged,
        "expected": expected,
        "agreement": round(agreement, 3),
        "trace": aggregate(tracer.read()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--mutate", action="store_true")
    parser.add_argument("--out", default="runs/eval_passk.json")
    args = parser.parse_args()

    records = []
    for case in EVAL_CASES:
        runs = [run_once(case, mutate=args.mutate) for _ in range(max(1, args.k))]
        all_pass = all(r["agreement"] == 1.0 for r in runs)
        records.append(
            {
                "case": case["id"],
                "pass_k": all_pass,
                "mean_agreement": round(sum(r["agreement"] for r in runs) / len(runs), 3),
                "runs": runs,
            }
        )

    summary = {
        "k": args.k,
        "cases": len(records),
        "pass_k_rate": round(sum(1 for r in records if r["pass_k"]) / len(records), 3),
        "mean_agreement": round(sum(r["mean_agreement"] for r in records) / len(records), 3),
        "mutate": args.mutate,
        "records": records,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "records"}, ensure_ascii=False, indent=2))
    print("结果：", out)


if __name__ == "__main__":
    main()
