"""可视化评审报告：把四个版本的「完整思考过程 + 完整输出 + 机器校验」摊开给人看。

用途：人肉眼判定选哪一版（机器打分只作参考，不作结论）。

用法（backend/ 目录下）：
    python -m eval.trace_report                      # 默认 4 版 × c1/c5/c6
    python -m eval.trace_report --cases c1 c5 --variants V1 V3 V4
    python -m eval.trace_report --open               # 生成后自动用浏览器打开

输出：
    eval/results/trace_<时间戳>.html    自包含（无 CDN、无外链），双击即可看
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from config import load_config  # noqa: E402
from llm import LLMClient  # noqa: E402

from agents.planner.checks import evaluate_plan  # noqa: E402
from agents.planner.schema import PlannerRequest  # noqa: E402
from agents.planner.variants import VARIANTS  # noqa: E402
from tracing import enabled as tracing_enabled, project as tracing_project  # noqa: E402

OUT_DIR = BASE / "eval" / "results"
CASES_PATH = BASE / "agents" / "planner" / "cases.jsonl"


class RecordingClient(LLMClient):
    """记录每一次真实 LLM 调用（完整 prompt + 完整响应）。"""

    def __init__(self, config):
        super().__init__(config)
        self.calls: list[dict[str, Any]] = []

    def chat_json(self, messages, temperature=0.25, max_tokens=3000):  # type: ignore[override]
        started = time.perf_counter()
        raw, usage, latency_ms = super().chat_json(
            messages, temperature=temperature, max_tokens=max_tokens
        )
        self.calls.append(
            {
                "messages": messages,
                "raw": raw,
                "usage": usage,
                "latency_ms": latency_ms,
                "elapsed_s": round(time.perf_counter() - started, 1),
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        return raw, usage, latency_ms


def load_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def esc(text: str) -> str:
    return html.escape(str(text))


def pretty(raw: str) -> str:
    try:
        payload = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        return raw


def render_plan(plan) -> str:
    if plan is None:
        return "<p class='bad'>❌ 没有产出合法计划（schema 未通过）</p>"
    rows = ""
    for unit in sorted(plan.units, key=lambda u: u.order):
        kps = "、".join(unit.kp_ids)
        rows += f"""
        <tr>
          <td class="c">{esc(unit.id)}</td>
          <td><b>{esc(unit.title)}</b><div class="kps">{esc(kps)}</div></td>
          <td class="c">{unit.est_sessions}</td>
          <td>{esc(unit.exit_test.pass_rule)}<div class="dim">原题：{esc('；'.join(unit.exit_test.must_solve))}</div>
              <div class="dim">变式：{esc(unit.exit_test.variant_rule)}</div></td>
        </tr>"""
    return f"""
    <p class="dim">目标：{esc(plan.goal)} ｜ 教材：{esc(plan.textbook)} ｜ 总轮次：{plan.total_sessions}</p>
    <table class="plan">
      <tr><th>#</th><th>单元 / 知识点</th><th>轮次</th><th>验收标准</th></tr>
      {rows}
    </table>
    <p class="dim">全局验收：{esc(plan.verification_policy)}</p>
    """


def render_calls(calls: list[dict]) -> str:
    if not calls:
        return "<p class='bad'>没有发生 LLM 调用</p>"
    out = ""
    for index, call in enumerate(calls, 1):
        system = next((m["content"] for m in call["messages"] if m["role"] == "system"), "")
        user = next((m["content"] for m in call["messages"] if m["role"] == "user"), "")
        extra_msgs = [m for m in call["messages"] if m["role"] == "assistant"]
        usage = call["usage"]
        out += f"""
        <details class="call" {"open" if index == 1 else ""}>
          <summary>第 {index} 次调用 · {call['elapsed_s']}s · tokens {usage.get('total_tokens', 0)}
            （prompt {usage.get('prompt_tokens', 0)} / completion {usage.get('completion_tokens', 0)}）</summary>
          <h4>System Prompt</h4><pre>{esc(system)}</pre>
          <h4>User Prompt</h4><pre>{esc(user)}</pre>
          {f'<h4>修复轮追加的消息（{len(extra_msgs) // 2} 组）</h4><pre>{esc(json.dumps(extra_msgs, ensure_ascii=False, indent=2))}</pre>' if extra_msgs else ''}
          <h4>模型原始输出（未加工）</h4><pre class="raw">{esc(call['raw'])}</pre>
          <h4>解析后的 JSON</h4><pre>{esc(pretty(call['raw']))}</pre>
        </details>"""
    return out


def render_run(case: dict, variant: str, row: dict) -> str:
    metrics = row["metrics"]
    bad = bool(row["issues"])
    badge = "<span class='badge bad'>校验未通过</span>" if bad else "<span class='badge ok'>校验通过</span>"
    issues = "".join(f"<li>{esc(i)}</li>" for i in row["issues"]) or "<li class='dim'>无</li>"
    score_color = "#c0392b" if bad else "#27ae60"
    return f"""
    <section class="run">
      <h3>{esc(variant)} · {esc(case['id'])} · {esc(case['goal'])} {badge}</h3>
      <div class="stats">
        <span style="color:{score_color}">综合分 <b>{metrics['score']}</b></span>
        <span>覆盖率 <b>{metrics['coverage']}</b></span>
        <span>幻觉率 <b>{metrics['hallucination']}</b></span>
        <span>单元 <b>{metrics['units']}</b></span>
        <span>tokens <b>{row['tokens']}</b></span>
        <span>耗时 <b>{row['elapsed_s']}s</b></span>
      </div>
      <h4>① 模型思考过程（每一次调用、完整 prompt、完整原始输出）</h4>
      {render_calls(row['calls'])}
      <h4>② 最终产出的计划（这是学生真正会看到的东西）</h4>
      {render_plan(row['plan'])}
      <h4>③ 机器校验（确定性规则，不是模型判断）</h4>
      <ul>{issues}</ul>
    </section>"""


CSS = """
body{font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;margin:0;background:#f6f7f9;color:#1f2328}
header{background:#111827;color:#fff;padding:22px 32px}
header h1{margin:0 0 6px;font-size:22px} header p{margin:0;opacity:.75;font-size:13px}
main{padding:20px 32px 60px;max-width:1500px;margin:0 auto}
table.sum{border-collapse:collapse;width:100%;background:#fff;margin:18px 0;font-size:13px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
table.sum th,table.sum td{border:1px solid #e5e7eb;padding:7px 10px;text-align:center}
table.sum th{background:#f3f4f6}
table.plan{border-collapse:collapse;width:100%;background:#fff;font-size:13px;margin:8px 0}
table.plan th{background:#f3f4f6;text-align:left} table.plan td,table.plan th{border:1px solid #e5e7eb;padding:8px;vertical-align:top}
td.c{text-align:center;width:52px} .kps{color:#6b7280;font-size:12px;margin-top:3px}
.dim{color:#6b7280;font-size:12px}
.run{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;margin:18px 0}
.run h3{margin:0 0 10px;font-size:16px}
.badge{font-size:12px;padding:2px 8px;border-radius:10px;margin-left:8px}
.badge.ok{background:#def7ec;color:#046c4e} .badge.bad{background:#fde8e8;color:#9b1c1c}
.stats{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:#4b5563;margin-bottom:12px}
pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:6px;overflow:auto;max-height:460px;font-size:12px;line-height:1.55;white-space:pre-wrap;word-break:break-word}
pre.raw{background:#1f2937}
details.call{border:1px solid #e5e7eb;border-radius:6px;padding:8px 12px;margin:8px 0;background:#fcfcfd}
details.call summary{cursor:pointer;font-size:13px;font-weight:600;color:#111827}
h4{margin:14px 0 6px;font-size:13px;color:#374151}
.bad{color:#c0392b}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="*", default=["c1", "c5", "c6"])
    parser.add_argument("--variants", nargs="*", default=["V1", "V2", "V3", "V4"])
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    cases = [c for c in load_cases() if c["id"] in set(args.cases)]
    variants = [v for v in args.variants if v in VARIANTS]
    print(f"追踪 {len(cases)} 个 case × {len(variants)} 个版本", flush=True)

    rows: list[dict] = []
    for case in cases:
        request = PlannerRequest(
            goal=case["goal"],
            scope=case["scope"],
            days=case["days"],
            hours_per_day=case["hours_per_day"],
            level=case.get("level", "大学低年级"),
            profile_digest=case.get("profile_digest", ""),
            style=case.get("style", "systematic"),
        )
        for variant in variants:
            client = RecordingClient(load_config())
            started = time.perf_counter()
            try:
                result = VARIANTS[variant](client, request)
                plan, issues = result.plan, result.issues
                metrics = evaluate_plan(plan, request)
            except Exception as exc:  # noqa: BLE001
                plan, issues = None, [f"{type(exc).__name__}: {exc}"]
                metrics = evaluate_plan(None, request)
            rows.append(
                {
                    "case": case,
                    "variant": variant,
                    "plan": plan,
                    "issues": issues,
                    "metrics": metrics,
                    "calls": client.calls,
                    "tokens": sum(int(c["usage"].get("total_tokens", 0)) for c in client.calls),
                    "elapsed_s": round(time.perf_counter() - started, 1),
                }
            )
            print(
                f"  {variant} {case['id']} 完成：tokens={rows[-1]['tokens']} "
                f"{'✅' if not issues else '❌'}",
                flush=True,
            )

    # 汇总矩阵
    head = "".join(f"<th>{esc(c['id'])}</th>" for c in cases)
    body = ""
    for variant in variants:
        cells = ""
        for case in cases:
            row = next(r for r in rows if r["variant"] == variant and r["case"]["id"] == case["id"])
            color = "#c0392b" if row["issues"] else "#27ae60"
            cells += f"<td style='color:{color}'>{row['metrics']['score']}<br><span class='dim'>{row['tokens']} tok · {row['elapsed_s']}s</span></td>"
        body += f"<tr><th>{esc(variant)}</th>{cells}</tr>"

    tracing_note = (
        f"LangSmith 已启用（project: {tracing_project()}），本次运行已上报，去 smith.langchain.com 查看。"
        if tracing_enabled()
        else "LangSmith 未启用（backend/.env 里没有 LANGSMITH_API_KEY）。本报告已包含完整 prompt 与原始输出，可先看这里。"
    )

    doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>planner 四版评审报告</title><style>{CSS}</style></head><body>
<header>
  <h1>路线规划 agent（指挥官）四版评审报告</h1>
  <p>生成时间 {time.strftime('%Y-%m-%d %H:%M:%S')} ｜ 模型 deepseek-v4-flash ｜ {esc(tracing_note)}</p>
  <p>这份报告只提供证据，选哪一版由人决定。</p>
</header>
<main>
  <h2>一、速览矩阵（分数 / tokens / 耗时）</h2>
  <table class="sum"><tr><th>版本</th>{head}</tr>{body}</table>
  <h2>二、逐条展开（思考过程 → 产出 → 校验）</h2>
  {''.join(render_run(r['case'], r['variant'], r) for r in rows)}
</main></body></html>"""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"trace_{time.strftime('%Y%m%d_%H%M%S')}.html"
    out.write_text(doc, encoding="utf-8")
    print(f"\n报告：{out}")
    if args.open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
