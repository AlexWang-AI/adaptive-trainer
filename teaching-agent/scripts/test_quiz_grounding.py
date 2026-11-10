"""出题是否真的接上了教材题型（题型层验收）。

背景：`/api/practice_more`（再练一组）和讲练合一的 3 道题，过去都是模型自由生成。
接上教材树之后，出题必须落在 `lecture_XX_types.json` 的题型上，并且卡里要带 `type_name`。

    python scripts/test_quiz_grounding.py                 # 默认测 6 个跨讲知识点
    python scripts/test_quiz_grounding.py --kp l01-b01-k01

验收：
1. 每题都能返回 3 张卡；
2. ≥2 张卡的 type_name 命中该知识点的教材题型（逐字一致）；
3. 成本可控：calls ≤ 2、tokens ≤ 5000（题型重试只允许一次）。
"""

from __future__ import annotations

import argparse
import sys

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8008"
DEFAULT_KPS = [
    "l01-b01-k01",   # 第1讲 极限四则运算规则
    "l05-b02-k01",   # 第5讲 拐点的定义
    "l06-b01-k01",   # 第6讲 中值定理类
    "l13-b02-k01",   # 第13讲 多元微分
    "l16-b01-k01",   # 第16讲 幂级数
    "l18-b01-k01",   # 第18讲 多元积分
]

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"{'✅' if ok else '❌'} {label}{('  — ' + detail) if detail else ''}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kp", action="append", default=None)
    args = ap.parse_args()
    kps = args.kp or DEFAULT_KPS
    client = httpx.Client(trust_env=False, timeout=240.0)

    for kp in kps:
        detail = client.get(f"{BASE}/api/kp_detail", params={"kp_id": kp}).json()
        types = {t.get("name") for t in (detail.get("types") or []) if t.get("name")}
        resp = client.post(f"{BASE}/api/practice_more", json={"kp_id": kp, "student_id": "ground-check"})
        if resp.status_code != 200:
            check(f"{kp} 返回 200", False, resp.text[:120])
            continue
        data = resp.json()
        cards = data.get("questions") or []
        tagged = [c for c in cards if (c.get("type_name") or "").strip()]
        matched = [c for c in tagged if c["type_name"] in types]
        calls = int(data.get("calls") or 0)
        tokens = int(data.get("tokens") or 0)

        print(f"\n== {data['kp_name']}（{kp}）")
        print(f"   教材题型：{sorted(types)}")
        for c in cards:
            print(f"   - {c['difficulty']:6s} type={c.get('type_name') or '(空)'}  {c['stem'][:46]}")
        check(f"{kp} 返回 3 张卡", len(cards) == 3, f"{len(cards)} 张")
        if types:
            check(f"{kp} ≥2 道题命中教材题型", len(matched) >= 2, f"{len(matched)}/{len(cards)}")
        else:
            # 纯概念节点没有题型（如「无穷大的定义」），这类只要求不瞎标题型
            stray = [c for c in cards if (c.get("type_name") or "").strip()]
            check(f"{kp} 无教材题型时不乱标", not stray, f"{len(stray)} 张乱标")
        check(f"{kp} 成本可控", calls <= 2 and tokens <= 5000, f"calls={calls} tokens={tokens}")

    total = len(PASSED) + len(FAILED)
    print(f"\n==== {len(PASSED)}/{total} 通过 ====")
    for item in FAILED:
        print(f"  ✗ {item}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
