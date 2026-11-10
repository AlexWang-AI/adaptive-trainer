"""LangSmith 追踪接入（可选，缺 key 时全链路自动降级为 no-op）。

原理：
- `langsmith.wrappers.wrap_openai` 包住 openai 客户端 → 每次 LLM 调用（完整 prompt + 完整响应）
  自动变成一条 LangSmith run；
- `@traceable` 包住 agent 函数 → 形成「agent 运行 → 多次 LLM 调用」的树；
- 没配 key 时不加载任何 langsmith 代码路径，行为与现在完全一致。

配置（backend/.env）：
    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=lsv2_pt_xxx
    LANGSMITH_PROJECT=mathneuron-planner
    LANGSMITH_ENDPOINT=https://api.smith.langchain.com
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from dotenv import dotenv_values

ENV_PATH = Path(__file__).resolve().parent / ".env"
_LOADED = False


def load_env() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    if ENV_PATH.exists():
        for key, value in dotenv_values(ENV_PATH).items():
            if value is not None:
                os.environ.setdefault(key, value)


def enabled() -> bool:
    load_env()
    flag = os.getenv("LANGSMITH_TRACING", "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False
    return bool(os.getenv("LANGSMITH_API_KEY", "").strip())


def project() -> str:
    load_env()
    return os.getenv("LANGSMITH_PROJECT", "mathneuron")


def maybe_wrap_openai(client: Any) -> Any:
    """给 openai.OpenAI 客户端套上 LangSmith wrapper（未启用时原样返回）。"""
    if not enabled():
        return client
    try:
        from langsmith.wrappers import wrap_openai

        return wrap_openai(client)
    except Exception:
        return client


def traceable_agent(name: str) -> Callable:
    """装饰 agent 函数；未启用时返回原函数，零开销。"""

    def decorator(func: Callable) -> Callable:
        if not enabled():
            return func
        try:
            from langsmith import traceable

            return traceable(run_type="chain", name=name)(func)
        except Exception:
            return func

    return decorator


def trace_url(run_id: str) -> str:
    base = os.getenv("LANGSMITH_ENDPOINT", "https://smith.langchain.com").rstrip("/")
    if "api.smith" in base:
        base = "https://smith.langchain.com"
    return f"{base}/o/default/projects/p/{project()}/r/{run_id}"
