from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

DEFAULT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str
    model: str
    timeout: float = 60.0


def load_config(model: str | None = None) -> Config:
    env_path = Path(os.getenv("DEEPSEEK_ENV_PATH", str(DEFAULT_ENV_PATH)))
    values = dotenv_values(env_path) if env_path.exists() else {}

    api_key = os.getenv("DEEPSEEK_API_KEY") or values.get("DEEPSEEK_API_KEY")
    base_url = (
        os.getenv("DEEPSEEK_BASE_URL")
        or values.get("DEEPSEEK_BASE_URL")
        or "https://api.deepseek.com/v1"
    )
    model_name = (
        model
        or os.getenv("DEEPSEEK_MODEL")
        or values.get("DEEPSEEK_CHAT_MODEL")
        or "deepseek-v4-flash"
    )

    if not api_key:
        raise RuntimeError(
            "找不到 DEEPSEEK_API_KEY。请设置环境变量，或把 DEEPSEEK_ENV_PATH 指向现有 .env。"
        )

    return Config(api_key=api_key, base_url=base_url.rstrip("/"), model=model_name)
