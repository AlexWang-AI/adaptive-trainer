"""路线规划 agent 的四版对比评测。

用法（在 backend/ 目录下）：
    python -m eval.planner_eval                 # 全部 6 个 case × 4 个版本
    python -m eval.planner_eval --cases c1 c6   # 只跑指定 case
    python -m eval.planner_eval --variants V1 V3 --workers 2

输出：
    eval/results/planner_<时间戳>.json   逐条明细
    eval/results/planner_<时间戳>.md     对比表
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from config import load_config  # noqa: E402
from llm import LLMClient  # noqa: E402

from agents.planner.checks import evaluate_plan  # noqa: E402
from agents.planner.schema import PlannerRequest  # noqa: E402
from agents.planner.variants import VARIANTS  # noqa: E402

CASES_PATH = BASE / "agents" / "planner" / "cases.jsonl"
OUT_DIR = BASE / "eval" / "results"


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def make_request(case: dict) -> PlannerRequest:
    return PlannerRequest(
        goal=case["goal"],
        scope=case["scope"],
        days=case["days"],
        hours_per_day=case["hours_per_day"],
        level=case.get("level", "大学低年级"),
        profile_digest=case.get("profile_digest", ""),
        style=case.get("style", "systematic"),
    )


def run_one(variant: str, case: dict) -> dict:
    request = make_request(case)
    client = LLMClient(load_config())
    started = time.perf_counter()
    error = ""
    try:
        result = VARIANTS[variant](client, request)
        plan = result.plan
        metrics = evaluate_plan(plan, request)
        issues = result.issues
        calls = result.calls
        usage = result.usage
        extra = result.extra
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        metrics = evaluate_plan(None, request)
        issues, calls, usage, extra, plan = [error], 0, {}, {}, None
    elapsed = round(time.perf_counter() - started, 1)

    return {
        "variant": variant,
        "case": case["id"],
        "goal": case["goal"],
        "elapsed_s": elapsed,
        "error": error,
        "calls": calls,
        "tokens": usage.get("total_tokens", 0),
        "latency_ms": getattr(result, "latency_ms", 0) if not error else 0,
        "metrics": metrics,
        "issues": issues[:6],
        "extra": extra,
        "plan_units": [u.model_dump() for u in plan.units] if plan else [],
    }


def aggregate(rows: list[dict], variants: list[str]) -> list[dict]:
    table = []
    for variant in variants:
        sub = [r for r in rows if r["variant"] == variant]
        if not sub:
            continue
        n = len(sub)
        table.append(
            {
                "variant": variant,
                "runs": n,
                "pass": sum(1 for r in sub if not r["issues"]),
                "score": round(sum(r["metrics"]["score"] for r in sub) / n, 3),
                "coverage": round(sum(r["metrics"]["coverage"] for r in sub) / n, 3),
                "hallucination": round(sum(r["metrics"]["hallucination"] for r in sub) / n, 3),
                "order_ok": round(sum(r["metrics"]["order_ok"] for r in sub) / n, 2),
                "sessions_ok": round(sum(r["metrics"]["sessions_ok"] for r in sub) / n, 2),
                "exit_ok": round(sum(r["metrics"]["exit_ok"] for r in sub) / n, 2),
                "calls": round(sum(r["calls"] for r in sub) / n, 1),
                "tokens": round(sum(r["tokens"] for r in sub) / n),
                "elapsed_s": round(sum(r["elapsed_s"] for r in sub) / n, 1),
                "errors": sum(1 for r in sub if r["error"]),
            }
        )
    return sorted(table, key=lambda x: x["score"], reverse=True)


def to_markdown(table: list[dict], rows: list[dict]) -> str:
    head = (
        "| 版本 | 通过率 | 综合分 | 覆盖率 | 幻觉率 | 顺序 | 轮次一致 | 验收完整 | 调用数 | tokens | 耗时(s) |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = ""
    for r in table:
        body += (
            f"| {r['variant']} | {r['pass']}/{r['runs']} | {r['score']} | {r['coverage']} | "
            f"{r['hallucination']} | {r['order_ok']} | {r['sessions_ok']} | {r['exit_ok']} | "
            f"{r['calls']} | {r['tokens']} | {r['elapsed_s']} |\n"
        )
    detail = "\n**逐条问题**\n\n"
    for row in rows:
        if row["issues"]:
            detail += f"- `{row['variant']}` / `{row['case']}`：{row['issues']}\n"
    return head + body + detail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="*", default=None)
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS.keys()))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    cases = load_cases()
    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
    variants = [v for v in args.variants if v in VARIANTS]

    jobs = [(v, c) for c in cases for v in variants]
    print(f"开始：{len(cases)} 个 case × {len(variants)} 个版本 = {len(jobs)} 次运行", flush=True)

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(run_one, v, c) for v, c in jobs]
        for index, fut in enumerate(futures, 1):
            row = fut.result()
            rows.append(row)
            flag = "✅" if not row["issues"] else "❌"
            print(
                f"[{index:02d}/{len(jobs)}] {flag} {row['variant']} {row['case']} "
                f"score={row['metrics']['score']} units={row['metrics']['units']} "
                f"{row['elapsed_s']}s tokens={row['tokens']}",
                flush=True,
            )

    table = aggregate(rows, variants)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = Path(args.out) if args.out else OUT_DIR / f"planner_{stamp}.json"
    out_md = out_json.with_suffix(".md")
    out_json.write_text(
        json.dumps({"table": table, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    out_md.write_text(to_markdown(table, rows), encoding="utf-8")

    print("\n=== 汇总（按综合分排序）===")
    for r in table:
        print(
            f"{r['variant']}  通过 {r['pass']}/{r['runs']}  综合分 {r['score']}  "
            f"覆盖 {r['coverage']}  幻觉 {r['hallucination']}  "
            f"调用 {r['calls']}  tokens {r['tokens']}  耗时 {r['elapsed_s']}s"
        )
    print(f"\n明细：{out_json}\n表格：{out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
