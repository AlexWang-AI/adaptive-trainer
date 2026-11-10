"""课程表：严格对齐《张宇基础 30 讲（高等数学分册）》的 18 讲 / 232 个知识点。

数据来源不是手写，而是教材抽取流水线的产物（`textbook/tree/lecture_XX_*.json`），
由 `scripts/build_curriculum.py` 编译成同目录下的 `curriculum_data.json`：

    讲（chapter）      = 第 N 讲，共 18 讲
    分支（block）      = 讲内的 L1 分支，带考频档 must/high/edge 与结论
    知识点（kp）       = 分支内的 L2 节点，带考纲依据、要点(L3)、教材例题、题型、提速技巧

为什么要编译成 JSON 而不是运行时直读树：树是流水线产物，重跑会漂移；编译时把
id、顺序、权重一次定死（id 形如 `l01-b02-k03`），`student_kp` 里的历史记录才不会错位。

对外 API（保持旧版全部函数名，避免上层改动）：

    CHAPTERS / KP_TABLE / all_kp_ids() / chapter_of() / order_index()
    kps_in_scope() / prereq_closure() / whitelist_for_scope() / render_kp_table()

新增：

    kp_meta(kp_id) / chapter_meta(chapter_id) / blocks_of(chapter_id)
    textbook_block(kp_id)   —— 该知识点的教材依据（考纲 + 要点 + 结论 + 例题 + 题型），
                               直接进讲课提示词，让「讲课以教材为准」可验证
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).with_name("curriculum_data.json")
_DATA: dict[str, Any] = json.loads(_DATA_PATH.read_text(encoding="utf-8"))

META: dict[str, Any] = _DATA.get("meta", {})
CURRICULUM_VERSION: str = META.get("version", "unknown")
TEXTBOOK_NAME: str = META.get("textbook", "张宇基础30讲")


@dataclass(frozen=True)
class Chapter:
    id: str
    name: str
    lecture: int                       # 讲次（1~30，三册统一编号）
    title: str = ""                    # 去掉「第N讲」的讲名
    book: str = ""                     # gaoshu / xiandai / gailv
    kps: tuple[str, ...] = field(default_factory=tuple)
    blocks: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def _make_chapter(raw: dict[str, Any]) -> Chapter:
    return Chapter(
        id=raw["id"],
        name=raw["name"],
        lecture=int(raw["no"]),
        title=raw.get("title", ""),
        book=raw.get("book", ""),
        kps=tuple(raw["kps"]),
        blocks=tuple(raw.get("blocks", [])),
    )


CHAPTERS: list[Chapter] = [_make_chapter(raw) for raw in _DATA["chapters"]]
_CHAPTER_BY_ID: dict[str, Chapter] = {ch.id: ch for ch in CHAPTERS}

KP_TABLE: dict[str, dict[str, Any]] = _DATA["kps"]

# 教学顺序：讲 → 分支 → 知识点，与教材目录一致
_ORDER: dict[str, int] = {}
for _ch in CHAPTERS:
    for _kp_id in _ch.kps:
        _ORDER[_kp_id] = len(_ORDER)


def all_kp_ids() -> list[str]:
    return list(_ORDER)


def order_index(kp_id: str) -> int:
    return _ORDER.get(kp_id, 10**6)


def chapter_of(kp_id: str) -> str:
    return KP_TABLE.get(kp_id, {}).get("chapter", "")


def kp_meta(kp_id: str) -> dict[str, Any]:
    return KP_TABLE.get(kp_id, {})


def chapter_meta(chapter_id: str) -> dict[str, Any]:
    ch = _CHAPTER_BY_ID.get(chapter_id)
    if not ch:
        return {}
    return {"id": ch.id, "name": ch.name, "no": ch.lecture, "title": ch.title, "kp_count": len(ch.kps)}


def blocks_of(chapter_id: str) -> list[dict[str, Any]]:
    ch = _CHAPTER_BY_ID.get(chapter_id)
    return list(ch.blocks) if ch else []


def kps_in_scope(scope: list[str]) -> list[str]:
    """scope 可以是讲次 id（l01）、分支 id（l01-b02）或知识点 id，返回展开后的知识点列表。"""
    out: list[str] = []
    for token in scope:
        token = token.strip()
        if token in _CHAPTER_BY_ID:
            out.extend(_CHAPTER_BY_ID[token].kps)
            continue
        block_hit = next((b for b in _DATA["chapters"] for b in b["blocks"] if b["id"] == token), None)
        if block_hit:
            out.extend(block_hit["kps"])
            continue
        if token in KP_TABLE:
            out.append(token)
    # 去重保序
    return list(dict.fromkeys(out))


def prereq_closure(kp_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    stack = list(kp_ids)
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in KP_TABLE:
            continue
        seen.add(cur)
        stack.extend(KP_TABLE[cur]["prerequisites"])
    return sorted(seen, key=order_index)


def whitelist_for_scope(scope: list[str]) -> list[str]:
    """给规划 agent 的白名单：范围内知识点 + 其前置闭包（保证先修顺序可排）。"""
    return prereq_closure(kps_in_scope(scope))


def render_kp_table(kp_ids: list[str]) -> str:
    """把知识点渲染成紧凑表格，直接塞进 prompt。"""
    lines = []
    for kp in sorted(kp_ids, key=order_index):
        meta = KP_TABLE[kp]
        pre = ",".join(meta["prerequisites"]) or "-"
        lines.append(f"{kp} | {meta['name']} | 考频{meta['exam_weight']} | 前置:{pre}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 教材依据：讲课提示词里那段「以教材为准」的原文
# ---------------------------------------------------------------------------
def _bigrams(text: str) -> set[str]:
    cleaned = "".join(ch for ch in text if ch.strip())
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def _overlap(text: str, pool: set[str]) -> int:
    """按二元组算重合度。中文按单字重合会被虚词带偏，二元组才认得出「四则运算」这种术语。"""
    return len(_bigrams(text) & pool)


def textbook_block(kp_id: str, max_chars: int = 1200) -> str:
    """把一个知识点的教材依据压成可注入提示词的短块。

    结构固定（缺省的行直接省略），这样提示词里「教材说了什么」和
    「模型自己补充什么」是分开的，出问题能一眼看出是哪一边。

        第N讲《讲名》· 分支名
        【考纲】……
        【教材要点】① … ② …
        【本讲结论】① … ② …
        【教材例题】例1.14：<题干>  例1.21：<题干>
        【对应题型】0/0型未定式求极限：步骤一 → 步骤二
    """
    meta = KP_TABLE.get(kp_id)
    if not meta:
        return ""

    block = next(
        (b for ch in _DATA["chapters"] for b in ch["blocks"] if b["id"] == meta["block"]),
        None,
    )
    lines: list[str] = [f"{meta['chapter_name']}（{meta['tier_label']}）· {meta['block_name']}"]

    if meta.get("evidence"):
        lines.append(f"【考纲】{meta['evidence']}")

    points = meta.get("points") or []
    if points:
        shown = points[:6]
        body = "  ".join(f"{'①②③④⑤⑥⑦⑧'[i]}{text}" for i, text in enumerate(shown))
        lines.append(f"【教材要点】{body}")

    conclusions = (block or {}).get("conclusions") or []
    if conclusions:
        pool = _bigrams(meta["name"] + "".join(points))
        ranked = sorted(
            enumerate(conclusions),
            key=lambda pair: (-_overlap(pair[1]["statement"], pool), pair[0]),
        )
        picked = [c for _, c in ranked[:3]]
        body = "  ".join(f"{'①②③'[i]}{c['statement']}" for i, c in enumerate(picked))
        lines.append(f"【本讲结论】{body}")

    examples = meta.get("examples") or []
    ex_texts = meta.get("example_texts") or []
    if ex_texts:
        # 带题干原文：模型能直接拿来当讲解锚点/同源母题，不用自己编题
        body = "  ".join(f"{e['id']}：{e['text'][:150]}" for e in ex_texts)
        lines.append(f"【教材例题】{body}")
    elif examples:
        lines.append(f"【教材例题】{'、'.join(examples[:4])}")

    types = meta.get("types") or []
    if types:
        # 一个知识点常被多个题型引用，按名称重合度挑最贴的那个（否则会给「四则运算」配「夹逼准则」）
        pool = _bigrams(meta["name"] + "".join(points))
        best = max(
            enumerate(types),
            key=lambda pair: (_overlap(pair[1].get("name", "") + pair[1].get("feature", ""), pool), -pair[0]),
        )[1]
        steps = " → ".join(best.get("steps") or [])
        lines.append(f"【对应题型】{best['name']}" + (f"：{steps}" if steps else ""))

    text = "\n".join(lines)
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


if __name__ == "__main__":
    print(f"{TEXTBOOK_NAME} · {CURRICULUM_VERSION}")
    print(f"讲次 {len(CHAPTERS)} 个，分支 {sum(len(c.blocks) for c in CHAPTERS)} 个，知识点 {len(KP_TABLE)} 个")
    for ch in CHAPTERS:
        print(f"  {ch.id} {ch.name}  ({len(ch.blocks)} 分支 / {len(ch.kps)} 点)")
    sample = all_kp_ids()[0]
    print(f"\n示例教材依据（{sample}）：\n{textbook_block(sample)}")
