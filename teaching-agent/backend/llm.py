from __future__ import annotations

import time
from typing import Any

from openai import OpenAI

from config import Config


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        raw = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )
        try:  # LangSmith 未配置时原样返回，零副作用
            from tracing import maybe_wrap_openai

            self.client = maybe_wrap_openai(raw)
        except Exception:
            self.client = raw

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

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 1200,
        temperature: float = 0.4,
        reasoning_effort: str = "low",
    ):
        """Yield reasoning/content deltas from DeepSeek's OpenAI-compatible stream.

        The visible answer is streamed separately from reasoning_content, so the
        frontend can reproduce the old MathNeuron typing experience. max_tokens
        includes reasoning tokens on DeepSeek V4; callers should leave headroom.
        """
        def create(extra_body: dict[str, Any] | None):
            return self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                stream=True,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=120,
                extra_body=extra_body,
            )

        stream = None
        try:
            try:
                stream = create(
                    {"thinking": {"type": "enabled"}, "reasoning_effort": reasoning_effort}
                )
            except Exception:
                # Some compatible endpoints reject reasoning_effort; keep thinking.
                stream = create({"thinking": {"type": "enabled"}})
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"流式调用失败：{type(exc).__name__}: {exc}") from exc

        try:
            for chunk in stream:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                if isinstance(reasoning, str) and reasoning:
                    yield {"type": "reasoning", "text": reasoning}
                content = getattr(delta, "content", None)
                if isinstance(content, str) and content:
                    yield {"type": "content", "text": content}
        finally:
            try:
                stream.close()
            except Exception:
                pass
