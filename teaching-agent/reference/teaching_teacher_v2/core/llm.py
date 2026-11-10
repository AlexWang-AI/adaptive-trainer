from __future__ import annotations

import time
from typing import Any, Callable

from openai import OpenAI

from core.config import Config


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.25,
        max_tokens: int = 3000,
    ) -> tuple[str, dict[str, Any], int]:
        last_error: Exception | None = None
        started = time.perf_counter()

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.config.timeout,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                content = response.choices[0].message.content or ""
                usage_obj = response.usage
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
                }
                latency_ms = int((time.perf_counter() - started) * 1000)
                if not content.strip():
                    raise LLMError("模型返回了空内容")
                return content, usage, latency_ms
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                # 有些 OpenAI 兼容服务不支持 response_format；降级再试一次
                if "response_format" in str(exc) and attempt == 0:
                    try:
                        response = self.client.chat.completions.create(
                            model=self.config.model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=self.config.timeout,
                            extra_body={"thinking": {"type": "disabled"}},
                        )
                        content = response.choices[0].message.content or ""
                        usage_obj = response.usage
                        usage = {
                            "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
                            "completion_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
                            "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
                        }
                        latency_ms = int((time.perf_counter() - started) * 1000)
                        if content.strip():
                            return content, usage, latency_ms
                    except Exception as fallback_exc:  # noqa: BLE001
                        last_error = fallback_exc
                time.sleep(1.5 * (attempt + 1))

        raise LLMError(f"API 调用失败：{type(last_error).__name__}: {last_error}")

    # ------------------------------------------------------------------
    # 流式结构化输出
    #
    # 讲练合一之后只剩一次调用，但一次调用也要 7~9 s。用户要的「首屏 3 秒」
    # 靠的不是让模型变快，而是让**第一个可渲染的字节**先到：
    # 提示词强制 reply_markdown 是 JSON 的第一个字段，这里边收边提取，
    # 一旦攒够可读片段就回调 on_delta，前端立刻显示讲义开头。
    # ------------------------------------------------------------------
    def stream_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,   # 讲义+3 题卡约 1300~2000 token；上限太低会被截断成非法 JSON，触发整轮重生成
        on_delta: Callable[[str], None] | None = None,
        retries: int = 2,
    ) -> tuple[str, dict[str, Any], int, int]:
        """返回 (完整文本, usage, 总耗时 ms, 首字节耗时 ms)。"""
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            started = time.perf_counter()
            ttft_ms = 0
            chunks: list[str] = []
            usage: dict[str, int] = {}
            try:
                stream = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.config.timeout,
                    stream=True,
                    stream_options={"include_usage": True},
                    extra_body={"thinking": {"type": "disabled"}},
                )
                for chunk in stream:
                    delta = ""
                    if getattr(chunk, "choices", None):
                        choice = chunk.choices[0]
                        piece = getattr(choice, "delta", None)
                        delta = getattr(piece, "content", None) or ""
                    if delta:
                        if ttft_ms == 0:
                            ttft_ms = int((time.perf_counter() - started) * 1000)
                        chunks.append(delta)
                        if on_delta is not None:
                            on_delta(delta)
                    chunk_usage = getattr(chunk, "usage", None)
                    if chunk_usage is not None:
                        usage = {
                            "prompt_tokens": getattr(chunk_usage, "prompt_tokens", 0) or 0,
                            "completion_tokens": getattr(chunk_usage, "completion_tokens", 0) or 0,
                            "total_tokens": getattr(chunk_usage, "total_tokens", 0) or 0,
                        }

                text = "".join(chunks)
                if not text.strip():
                    raise LLMError("流式返回空内容")
                if not usage:
                    # 部分兼容服务不返回 usage，按字符数粗估，保证成本统计不断档
                    estimated = max(1, int(len(text) / 1.6))
                    usage = {
                        "prompt_tokens": 0,
                        "completion_tokens": estimated,
                        "total_tokens": estimated,
                        "estimated": 1,
                    }
                total_ms = int((time.perf_counter() - started) * 1000)
                return text, usage, total_ms, ttft_ms
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                detail = str(exc)
                if any(m in detail for m in ("402", "401", "403", "429", "Insufficient")):
                    break  # 余额/鉴权/限流：立即失败，不重试
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))

        raise LLMError(f"流式调用失败：{type(last_error).__name__}: {last_error}")
