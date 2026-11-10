"""看一眼「老师记得你什么」：把某个学生 / 知识点会注入给模型的学习画像打出来。

    python scripts/show_learner_note.py                       # 默认 local-user 的三个点
    python scripts/show_learner_note.py der.definition lim.definition
    python scripts/show_learner_note.py --student e2e-s1 --base http://127.0.0.1:8008

只读，不花 token。
"""

from __future__ import annotations

import argparse
import sys

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kp", nargs="*", default=["der.definition", "lim.definition"])
    parser.add_argument("--student", default="local-user")
    parser.add_argument("--base", default="http://127.0.0.1:8008")
    args = parser.parse_args()

    client = httpx.Client(trust_env=False, timeout=15.0)
    for kp in args.kp:
        data = client.get(
            f"{args.base}/api/learner_note", params={"kp_id": kp, "student_id": args.student}
        ).json()
        note = data.get("note") or "(空)"
        print(f"[{kp}] {data.get('kp_name')}  —  {data.get('chars', 0)} 字 / 上限 {data.get('limit', 400)}")
        print(f"  {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
