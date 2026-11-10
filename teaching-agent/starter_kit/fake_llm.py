"""离线 FakeLLM：不需要 API Key，返回与真实模型同形状的 JSON。

它做三件事：
1. 从 prompt 里解析 `[KP:xxx]`，取出对应知识点；
2. 用 content.QUESTION_BANK 生成「讲义 + 2 题」；
3. `mutate=True` 时故意改错一道题的答案，用来演示「答案键必须独立」。
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from content import get_pack, get_questions


class FakeLLM:
    def __init__(self, *, mutate: bool = False, latency_ms: int = 20) -> None:
        self.mutate = mutate
        self.latency_ms = latency_ms

    @staticmethod
    def _kp_id(messages: list[dict[str, str]]) -> str:
        text = "\n".join(m.get("content", "") for m in messages)
        m = re.search(r"\[KP:([a-zA-Z0-9_.]+)\]", text)
        if not m:
            raise ValueError("prompt 里没有 [KP:xxx] 标记")
        return m.group(1)

    def _payload(self, kp_id: str) -> dict[str, Any]:
        pack = get_pack(kp_id)
        questions = [q.model_dump() for q in get_questions(kp_id)]
        if self.mutate:
            # 模拟模型把第一题答案写错：判题器必须靠独立答案键抓住它
            first = questions[0]
            if first["kind"] == "choice":
                first["answer"] = "A" if first["answer"] != "A" else "B"
            else:
                first["answer"] = "0"
            first["explanation"] = "（FakeLLM 故意写错，用来测试独立答案键）"

        return {
            "teaching": {
                "reply_markdown": (
                    f"这一轮只讲一层：{pack.name}。\n\n"
                    + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(pack.points))
                    + f"\n\n例子：{pack.example}\n\n"
                    + f"检查一下：{pack.points[0]} 你能用自己的话复述吗？"
                ),
                "core_idea": pack.points[0],
                "check_question": "上面这个例子里，哪一步是关键？",
                "confidence": "high",
            },
            "questions": questions,
        }

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2500,
        **_: Any,
    ) -> tuple[str, dict[str, int], int]:
        started = time.perf_counter()
        payload = self._payload(self._kp_id(messages))
        latency = int((time.perf_counter() - started) * 1000) + self.latency_ms
        usage = {"prompt_tokens": 800, "completion_tokens": 600, "total_tokens": 1400}
        return json.dumps(payload, ensure_ascii=False), usage, latency
