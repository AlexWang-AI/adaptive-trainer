"""一次性微基准：每个请求新建 LLMClient vs 进程内复用（P2-7）。

只用一次最小的 chat_json 请求（max_tokens 很小），量的是「建连 + TLS 握手 + 请求」
里属于客户端的那部分开销，不评判模型本身的速度。

    python scripts/bench_llm_client.py
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from v3core.config import load_config  # noqa: E402
from v3core.llm import LLMClient  # noqa: E402

PROMPT = [
    {"role": "system", "content": "只回一个词：ok"},
    {"role": "user", "content": "ping"},
]


def once(client: LLMClient) -> float:
    started = time.perf_counter()
    client.chat_json(PROMPT, temperature=0.0, max_tokens=8)
    return (time.perf_counter() - started) * 1000


def main() -> int:
    config = load_config()

    # A：每次新建客户端（修复前的行为）
    fresh = []
    for _ in range(4):
        fresh.append(once(LLMClient(config)))

    # B：复用同一个客户端（修复后的行为）
    shared_client = LLMClient(config)
    once(shared_client)  # 预热连接，第一次本来就要握手
    shared = [once(shared_client) for _ in range(4)]

    print(f"每次新建客户端：{[round(v) for v in fresh]} ms，中位数 {statistics.median(fresh):.0f} ms")
    print(f"复用同一客户端：{[round(v) for v in shared]} ms，中位数 {statistics.median(shared):.0f} ms")
    saved = statistics.median(fresh) - statistics.median(shared)
    print(f"差值（中位数）：{saved:.0f} ms / 次")
    return 0


if __name__ == "__main__":
    sys.exit(main())
