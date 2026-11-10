"""「高数 18 讲做深」的一键验收。

跑四件事，全绿才算通过（任何一步非零退出即失败）：

1. 课程表编译自检        python scripts/build_curriculum.py --check
2. 出题接题型层（6 个跨讲知识点）  python scripts/test_quiz_grounding.py
3. 讲课端到端（教材依据 + 题型标注 + TTFT）  python scripts/check_e2e.py --kp l01-b01-k01 --samples 2
4. 浏览器闭环（三题通关 + 自动下一站）  node scripts/browser_smoke.mjs

    python scripts/verify_deepening.py            # 全套（约 2~3 分钟，含 4 次模型调用 + 1 次浏览器）
    python scripts/verify_deepening.py --fast     # 跳过浏览器
    python scripts/verify_deepening.py --kp l06-b01-k01
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run(label: str, cmd: list[str], timeout: int = 600) -> tuple[bool, str, float]:
    started = time.time()
    print(f"\n▶ {label}\n  $ {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return False, f"超时（{timeout}s）", time.time() - started
    out = (proc.stdout or "") + (proc.stderr or "")
    elapsed = time.time() - started
    tail = "\n".join(out.strip().splitlines()[-12:])
    print(tail if tail else "  （无输出）")
    return proc.returncode == 0, out, elapsed


def pick(pattern: str, text: str, default: str = "-") -> str:
    m = re.search(pattern, text)
    return m.group(0) if m else default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="跳过浏览器验收")
    ap.add_argument("--kp", default="l01-b01-k01")
    args = ap.parse_args()

    rows: list[tuple[str, bool, str, float]] = []

    ok, out, sec = run("1/5 课程表编译自检", [PY, "scripts/build_curriculum.py", "--check"], 300)
    rows.append((
        "课程表编译自检",
        ok,
        pick(r"讲次 \d+ / 分支 \d+ / 知识点 \d+", out, "-") + "，" + pick(r"硬问题 \d+ 条", out, "-"),
        sec,
    ))

    ok, out, sec = run("2/5 出题接教材题型", [PY, "scripts/test_quiz_grounding.py"], 900)
    rows.append((
        "出题接题型层",
        ok,
        pick(r"==== \d+/\d+ 通过 ====", out, "-"),
        sec,
    ))

    ok2, out2, sec2 = run(
        "3/5 讲课端到端（教材依据 + 题型标注 + TTFT）",
        [PY, "scripts/check_e2e.py", "--kp", args.kp, "--samples", "2"],
        900,
    )
    rows.append((
        "讲课端到端",
        ok2,
        "，".join(
            [
                pick(r"TTFT 中位数 \d+ ms", out2, "-"),
                pick(r"题卡题型标注 \d/\d，命中教材题型 \d/\d", out2, "-"),
            ]
        ),
        sec2,
    ))

    if not args.fast:
        ok3, out3, sec3 = run("4/5 浏览器闭环", ["node", "scripts/browser_smoke.mjs"], 900)
        rows.append((
            "浏览器闭环",
            ok3,
            pick(r"\d+/\d+", out3.split("==== 结果 ====")[-1] if "==== 结果 ====" in out3 else out3, "-"),
            sec3,
        ))

        # 知识树层级完整性：树上有的层，界面上必须点得到（七种未定式必须能点到 7 条子项）
        ok4, out4, sec4 = run("5/5 知识树层级完整", ["node", "scripts/tree_expand_check.mjs"], 900)
        rows.append((
            "知识树层级完整",
            ok4,
            pick(r"展开后出现教材子项（≥7 条） — (\d+ 条)", out4, "-").replace("展开后出现教材子项（≥7 条） — ", ""),
            sec4,
        ))

    print("\n================ 验收汇总 ================")
    all_ok = True
    for name, passed, detail, sec in rows:
        all_ok = all_ok and passed
        print(f"{'✅ PASS' if passed else '❌ FAIL'}  {name:14s} {detail}  ({sec:.0f}s)")
    print("==========================================")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
