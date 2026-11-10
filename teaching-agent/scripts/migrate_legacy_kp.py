"""把旧版手写课程表的 kp id 迁移到新课程表（张宇 18 讲 / 232 点）。

旧 id 形如 `lim.definition`，新 id 形如 `l01-b02-k01`。库里现存旧 id 只有 4 个
（mastery.db 2 个 + students.db 3 个，去重后 4 个），所以做一次性映射，而不是
在运行时长期挂一层 alias。

    python scripts/migrate_legacy_kp.py                 # 只打印候选映射
    python scripts/migrate_legacy_kp.py --apply         # 真正写库（先备份）

映射原则：先按中文名精确命中新树里的知识点名；命中不了就打印候选（名字里含相同
关键词的前 5 个），人工确认后写进 `LEGACY_MAP` 再跑。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from curriculum import KP_TABLE  # noqa: E402

DATA = BACKEND / "data"

# 旧 id → 旧中文名（来自被替换掉的 curriculum.py）。名字只用于找候选。
LEGACY_NAMES = {
    "lim.definition": "极限的定义与性质",
    "lim.taylor": "泰勒公式求极限",
    "der.definition": "导数定义与可导性",
    "ser.p_series": "p级数",
}

# 人工确认后的映射（跑 --apply 用的就是这张表）
LEGACY_MAP = {
    "lim.definition": "l01-b02-k01",   # 第1讲·函数极限的概念与性质·函数极限的定义
    "lim.taylor": "l01-b01-k03",       # 第1讲·计算（求极限的方法）·泰勒公式
    "der.definition": "l03-b01-k01",   # 第3讲·概念·导数的定义
    # ser.p_series 是更早版本的遗留 id（当时课程表里没有它），新树里对应
    # 第16讲「正项级数」下的 p 级数条目；下面查询会自动找候选，找不到就留在库里不管
}

TABLES = [
    ("mastery.db", "kp_mastery", "kp_id"),
    ("students.db", "student_kp", "kp"),
    ("students.db", "mistakes", "kp"),
    ("students.db", "review_queue", "kp_id"),
    ("students.db", "misconception_log", "kp_id"),
    ("mistakes.db", "mistakes", "kp_id"),
]


def candidates(name: str) -> list[tuple[str, str]]:
    key = name.replace("（", "(").replace("）", ")")[:2]
    hits = []
    for kp_id, meta in KP_TABLE.items():
        if name == meta["name"]:
            hits.append((kp_id, meta["name"]))
        elif key and key in meta["name"]:
            hits.append((kp_id, meta["name"]))
    return hits[:8]


def existing_ids() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for db, table, column in TABLES:
        path = DATA / db
        if not path.exists():
            continue
        conn = sqlite3.connect(str(path))
        try:
            rows = conn.execute(f"SELECT DISTINCT {column} FROM {table}").fetchall()
        except sqlite3.OperationalError:
            rows = []
        finally:
            conn.close()
        for (value,) in rows:
            if value and value not in KP_TABLE:
                found.setdefault(value, set()).add(f"{db}.{table}")
    return found


def apply_map(mapping: dict[str, str]) -> None:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for db in dict.fromkeys(db for db, _, _ in TABLES):  # 去重：同一个库只备份一次
        path = DATA / db
        if path.exists():
            backup = path.with_suffix(path.suffix + f".bak-{stamp}")
            shutil.copy2(path, backup)
            print(f"  备份 {db} → {backup.name}")

    for db, table, column in TABLES:
        path = DATA / db
        if not path.exists():
            continue
        conn = sqlite3.connect(str(path))
        try:
            for old, new in mapping.items():
                cur = conn.execute(f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (new, old))
                if cur.rowcount:
                    print(f"  {db}.{table}: {old} → {new} （{cur.rowcount} 行）")
            conn.commit()
        except sqlite3.OperationalError as exc:
            print(f"  {db}.{table}: 跳过（{exc}）")
        finally:
            conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    orphans = existing_ids()
    print(f"库里不在新课程表的 id：{len(orphans)} 个")
    for old, where in sorted(orphans.items()):
        print(f"  {old}  ({', '.join(sorted(where))})")
        if old in LEGACY_MAP:
            target = LEGACY_MAP[old]
            print(f"    → {target}  {KP_TABLE[target]['textbook_ref']}")
        else:
            hits = candidates(LEGACY_NAMES.get(old, old))
            print(f"    候选：{hits if hits else '（无，留作孤儿，不影响新树）'}")

    if not args.apply:
        print("\n（未写库；确认映射后加 --apply）")
        return 0

    print("\n开始迁移…")
    apply_map(LEGACY_MAP)
    print("完成。剩余孤儿：", sorted(existing_ids()) or "无")
    return 0


if __name__ == "__main__":
    sys.exit(main())
