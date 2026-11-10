"""环境自检：Python、依赖、目录写权限、API key 是否存在。

不联网、不打印 key。
"""

from __future__ import annotations

import importlib.metadata as md
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    ("pydantic", "2.7"),
    ("langgraph", "1.0"),
    ("langgraph-checkpoint-sqlite", "3.0"),
    ("sympy", "1.12"),
    ("fastapi", "0.115"),
    ("uvicorn", "0.30"),
    ("pytest", "8.0"),
    ("httpx", "0.27"),
]


def version_of(pkg: str) -> str:
    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return "MISSING"


def main() -> int:
    print("=" * 66)
    print("starter_kit 环境自检")
    print("=" * 66)
    print("Python:", sys.version.split()[0], "|", sys.executable)
    print("工作目录:", ROOT)

    missing = []
    for pkg, minimum in REQUIRED:
        v = version_of(pkg)
        print(f"  {pkg:32s} {v:12s} (需要 >= {minimum})")
        if v == "MISSING":
            missing.append(pkg)

    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(dir=data, delete=True) as f:
            f.write(b"ok")
        print("data/ 写入: OK")
    except Exception as exc:  # noqa: BLE001
        print("data/ 写入: FAIL", exc)
        missing.append("data-writable")

    env_file = ROOT / ".env"
    print(".env:", "存在" if env_file.exists() else "不存在（离线模式不需要）")
    print("DEEPSEEK_API_KEY:", "已设置" if os.getenv("DEEPSEEK_API_KEY") else "未设置（离线模式不需要）")
    print("STARTER_KIT_MODE:", os.getenv("STARTER_KIT_MODE", "fake"))
    print("-" * 66)
    if missing:
        print("缺少：", ", ".join(missing))
        print("处理：用 deeptutor_env 的 Python，或按 README 安装依赖。")
        return 1
    print("自检通过。下一步：python demo.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
