"""结构化追踪：每个节点的耗时、token、修复次数、判题分层都落成 JSONL。

为什么不用 Langfuse？
    比赛环境里自建 ClickHouse/PG 太重。这里用最轻的方式拿到同样的东西：
    一行一个事件、可直接被 jq / pandas / 报表脚本消费；接口留好，
    将来要接 Langfuse 只需在 `Tracer.event` 里加一个 callback。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


class Tracer:
    def __init__(self, path: str | Path | None = None, *, echo: bool = False) -> None:
        self.path = Path(path) if path else None
        self.echo = echo
        self._lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, **fields: Any) -> None:
        record = {"ts": round(time.time(), 3), "kind": kind, **fields}
        line = json.dumps(record, ensure_ascii=False)
        if self.echo:
            print(line)
        if self.path:
            with self._lock, self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def read(self) -> list[dict[str, Any]]:
        if not self.path or not self.path.exists():
            return []
        rows = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """把事件流压成一份可做报表的指标。"""
    turns = [r for r in rows if r.get("kind") == "turn"]
    nodes = [r for r in rows if r.get("kind") == "node"]
    judges = [r for r in rows if r.get("kind") == "judge"]

    def _pct(values: list[float], q: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
        return round(float(ordered[idx]), 1)

    latencies = [float(n.get("latency_ms", 0)) for n in nodes]
    tokens = [int(n.get("total_tokens", 0)) for n in nodes]
    layers: dict[str, int] = {}
    for j in judges:
        key = str(j.get("layer", "unknown"))
        layers[key] = layers.get(key, 0) + 1

    return {
        "turns": len(turns),
        "nodes": len(nodes),
        "tokens_total": sum(tokens),
        "tokens_avg": round(sum(tokens) / len(tokens), 1) if tokens else 0.0,
        "latency_p50_ms": _pct(latencies, 0.5),
        "latency_p95_ms": _pct(latencies, 0.95),
        "repair_attempts": sum(int(n.get("attempts", 1)) - 1 for n in nodes),
        "judge_layers": layers,
        "llm_fallback_rate": round(
            layers.get("llm", 0) / max(1, sum(layers.values())), 3
        ),
    }
