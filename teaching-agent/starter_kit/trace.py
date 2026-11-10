"""JSONL trace：每个节点一行，能回答「哪一步慢、哪一步重试、哪个判题层」。"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class Tracer:
    def __init__(self, path: str | Path | None = None, *, echo: bool = False) -> None:
        self.path = Path(path) if path else None
        self.echo = echo
        self.trace_id = uuid.uuid4().hex[:12]
        self._lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, **fields: Any) -> None:
        record = {"trace_id": self.trace_id, "kind": kind, "ts": round(time.time(), 3), **fields}
        line = json.dumps(record, ensure_ascii=False)
        if self.echo:
            print(line)
        if self.path:
            with self._lock, self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def read(self) -> list[dict[str, Any]]:
        if not self.path or not self.path.exists():
            return []
        rows = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [r for r in rows if r.get("kind") == "node"]
    judges = [r for r in rows if r.get("kind") == "judge"]
    latencies = [int(n.get("latency_ms", 0)) for n in nodes]
    tokens = [int(n.get("tokens", 0)) for n in nodes]
    layers: dict[str, int] = {}
    for j in judges:
        layers[str(j.get("layer", "unknown"))] = layers.get(str(j.get("layer", "unknown")), 0) + 1

    def pct(values: list[int], q: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        return float(ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))])

    return {
        "events": len(rows),
        "nodes": len(nodes),
        "tokens_total": sum(tokens),
        "tokens_avg": round(sum(tokens) / len(tokens), 1) if tokens else 0.0,
        "latency_p50_ms": pct(latencies, 0.5),
        "latency_p95_ms": pct(latencies, 0.95),
        "repairs": sum(max(0, int(n.get("attempts", 1)) - 1) for n in nodes),
        "judge_layers": layers,
        "llm_fallback_rate": round(layers.get("fallback", 0) / max(1, sum(layers.values())), 3),
    }
