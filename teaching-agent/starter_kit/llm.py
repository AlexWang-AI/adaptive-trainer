"""真实模型客户端：OpenAI 兼容接口（DeepSeek / 其他）。

只在 `STARTER_KIT_MODE=real` 或 `demo.py --real` 时使用。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import dotenv_values
from openai import OpenAI

ROOT = Path(__file__).resolve().parent


def _env() -> dict[str, str]:
    values = dict(dotenv_values(ROOT / ".env")) if (ROOT / ".env").exists() else {}
    values = {k: v for k, v in values.items() if v is not None}
    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
        if os.getenv(key):
            values[key] = os.environ[key]
    return values


class LLMClient:
    def __init__(self) -> None:
        env = _env()
        key = env.get("DEEPSEEK_API_KEY", "").strip()
        if not key:
            raise RuntimeError("没有 DEEPSEEK_API_KEY：复制 .env.example 为 .env 并填写")
        self.model = env.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.client = OpenAI(
            api_key=key,
            base_url=env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            timeout=60,
        )

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2500,
    ) -> tuple[str, dict[str, int], int]:
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60,
                )
                text = resp.choices[0].message.content or ""
                if not text.strip():
                    raise RuntimeError("模型返回空内容")
                usage_obj = resp.usage
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
                }
                return text, usage, int((time.perf_counter() - started) * 1000)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f"API 调用失败：{type(last_error).__name__}: {last_error}")
