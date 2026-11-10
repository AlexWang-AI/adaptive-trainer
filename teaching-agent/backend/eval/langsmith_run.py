"""把四个版本跑一遍并上报到 LangSmith，供人肉眼评审。

前置（一次性）：
    1. 打开 https://smith.langchain.com 登录（GitHub/Google 均可，免费额度够）
    2. Settings → API Keys → Create API Key，复制 lsv2_pt_xxx
    3. 写进 backend/.env：
           LANGSMITH_TRACING=true
           LANGSMITH_API_KEY=lsv2_pt_xxx
           LANGSMITH_PROJECT=mathneuron-planner

用法（backend/ 目录下）：
    python -m eval.langsmith_run                 # 4 版 × c1/c5/c6
    python -m eval.langsmith_run --cases c1 c6 --variants V3 V4
    python -m eval.langsmith_run --check         # 只检查配置是否就绪

跑完打开 https://smith.langchain.com → Projects → mathneuron-planner，
每一行是一次 agent 运行，点进去能看到：
    · 完整 System Prompt / User Prompt
    · 模型的原始输出（JSON）
    · 每一次修复轮的重试
    · token 用量与耗时
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from config import load_config  # noqa: E402
from llm import LLMClient  # noqa: E402
from tracing import enabled, load_env, project  # noqa: E402

from agents.planner.checks import evaluate_plan  # noqa: E402
from agents.planner.schema import PlannerRequest  # noqa: E402
from agents.planner.variants import VARIANTS  # noqa: E402

CASES_PATH = BASE / "agents" / "planner" / "cases.jsonl"


def load_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="*", default=["c1", "c5", "c6"])
    parser.add_argument("--variants", nargs="*", default=["V1", "V2", "V3", "V4"])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    load_env()
    if args.check or not enabled():
        print("LangSmith 状态：", "已启用" if enabled() else "未启用")
        print("需要 backend/.env 里设置：")
        print("  LANGSMITH_TRACING=true")
        print("  LANGSMITH_API_KEY=lsv2_pt_xxx   （去 https://smith.langchain.com → Settings → API Keys 生成）")
        if args.check:
            return 0 if enabled() else 2
        print("\n（未启用也继续本地跑，只是不上报）")

    cases = [c for c in load_cases() if c["id"] in set(args.cases)]
    variants = [v for v in args.variants if v in VARIANTS]

    print(f"运行 {len(cases)} 个用例 × {len(variants)} 个版本 → project={project()}")
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
            client = LLMClient(load_config())
            try:
                result = VARIANTS[variant](client, request)
                metrics = evaluate_plan(result.plan, request)
                status = "✅" if not result.issues else "❌"
                print(
                    f"  {status} {variant} {case['id']}: 单元 {metrics['units']} "
                    f"分数 {metrics['score']} tokens {result.usage.get('total_tokens', 0)}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  ❌ {variant} {case['id']}: {type(exc).__name__}: {exc}")

    if enabled():
        print(f"\n去这里看：https://smith.langchain.com → Projects → {project()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
