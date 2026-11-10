"""进程内共享的 LLM 客户端（红队 P2-7）。

以前每个请求都 `LLMClient(load_config())`：等于每次新建一个 `OpenAI` → 新建
httpx 连接池，请求前还要重新 TCP + TLS 握手。判题兜底、侧问、诊断、加练
四个接口都在重复这件事，单次多几十到几百毫秒，并发一上来连接数也跟着涨。

`OpenAI` 客户端本身是线程安全的（内部 httpx.Client 支持连接复用），
一个进程一个就够。这里用 lru_cache 做懒加载：没有 key 时不会在 import 阶段炸。

测试可以用 `reset_llm_client()` 让缓存失效。
"""

from __future__ import annotations

from functools import lru_cache

from v3core.config import load_config
from v3core.llm import LLMClient


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return LLMClient(load_config())


def reset_llm_client() -> None:
    get_llm_client.cache_clear()
