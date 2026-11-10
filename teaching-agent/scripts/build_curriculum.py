"""把 `textbook/tree/` 的张宇基础30讲知识树，编译成后端运行时课程表。

输入（全部来自教材抽取流水线，不要手改）：

    textbook/tree/lecture_XX_weighted.json   讲 → 分支(L1) → 知识点(L2) → 要点(L3) + 结论
    textbook/tree/lecture_XX_types.json      题型层（144 个题型，含步骤与关联知识点）
    textbook/tree/lecture_XX_extras.json     提速层（秒杀技巧 / 常见陷阱）
    textbook/tree/index.json                 各讲标题与规模

输出：`backend/curriculum_data.json`（唯一运行时来源）

    python scripts/build_curriculum.py            # 编译并打印核对表
    python scripts/build_curriculum.py --check    # 只核对，不写文件

为什么要编译而不是运行时直接读树：树是流水线产物，字段会随重跑漂移；
编译时把 id、顺序、权重、id 前缀一次定死，运行时只读一份稳定 JSON，
这样 `student_kp` 里的历史 id 不会因为重新抽题而错位。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
TREE = ROOT / "textbook" / "tree"
OUT = ROOT / "backend" / "curriculum_data.json"

# 三册统一编号：高数 1-18，线代 19-24，概率 25-30。
# 树文件统一叫 lecture_{全局讲次:02d}_weighted.json（build_tree_v2/weight_one 就是按全局讲次写的），
# 所以这里只需要 start/count，不需要每册一个文件名前缀。
BOOKS = [
    {"key": "gaoshu", "start": 1, "count": 18, "short": "高数", "label": "高等数学分册"},
    {"key": "xiandai", "start": 19, "count": 6, "short": "线代", "label": "线性代数分册"},
    {"key": "gailv", "start": 25, "count": 6, "short": "概率", "label": "概率论与数理统计分册"},
]

# 分支的考频档 → 1~5 的考频（前端雷达、排序都用这个字段）
TIER_WEIGHT = {"must": 5, "high": 4, "edge": 3}
TIER_LABEL = {"must": "必考", "high": "高频", "edge": "边缘"}

# 展示与教学都按「原树有多少就放多少」，只留一个防爆上限
# （原树实测：单点最多 18 个要点 / 6 个题型 / 6 条提速），以前截到 12/4/3 是丢信息的
MAX_POINTS = 40
MAX_CONCLUSIONS = 24
MAX_TYPES = 10
MAX_EXTRAS = 10


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = (item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _strip_solution(text: str, limit: int = 200) -> str:
    """例题原文里带解答，讲课/出题只需要题干。

    OCR 出来的结构是「例1.14 题干 解 …」，有时解答前没有标点标记，
    所以三重截断：去掉开头的例号 → 在「解/分析/答案/解析」处断 → 超长再截。
    """
    body = re.sub(r"^例\s*\d+(?:\s*[\.\-]\s*\d+)?\s*", "", (text or "").strip())
    for marker in ("\n解", " 解", "解 应", "【解】", "分析", "答案", "解析", "\n注"):
        pos = body.find(marker)
        if pos > 20:                      # 太靠前多半是词里带的「解」，不切
            body = body[:pos]
    body = body.strip()
    return body if len(body) <= limit else body[: limit - 1] + "…"


def _emit_lecture(
    book: dict,
    local: int,
    no: int,
    weighted: dict,
    types_doc: dict,
    extras_doc: dict,
    example_texts: dict[str, str],
    kps: dict[str, dict],
    counters: dict[str, int],
) -> dict:
    """把一讲的 weighted 树转成课程表里的一章（讲 → 分支 → 知识点）。"""
    chapter_id = f"l{no:02d}"
    title = (weighted["title"] or "").strip()
    if book["key"] != "gaoshu":
        # 线代的树文件里 title 常写成「第19讲 行列式」，再拼「线代第1讲」会变成双编号
        title = re.sub(r"^第\s*\d+\s*讲\s*", "", title).strip() or title
    chapter_name = (
        f"第{no}讲 {title}" if book["key"] == "gaoshu" else f"{book['short']}第{local}讲 {title}"
    )

    # 题型 / 提速技巧都是按「知识点中文名」挂的，先按讲内索引
    types_by_kp: dict[str, list[dict]] = {}
    for item in types_doc.get("types", []):
        for name in item.get("kps", []):
            types_by_kp.setdefault(name.strip(), []).append(
                {
                    "name": item.get("name", ""),
                    "feature": item.get("feature", ""),
                    "steps": item.get("steps", [])[:5],
                }
            )
            counters["types"] += 1
    extras_by_kp: dict[str, list[dict]] = {}
    for item in extras_doc.get("items", []):
        target = (item.get("enhances") or "").strip()
        if not target:
            continue
        extras_by_kp.setdefault(target, []).append(
            {
                "name": item.get("name", ""),
                "type": item.get("type", ""),
                "when": item.get("when", ""),
                "how": item.get("how", ""),
                "risk": item.get("risk", ""),
            }
        )
        counters["extras"] += 1

    blocks_out: list[dict] = []
    prev_kp_id = ""  # 讲内线性前置：只要求本讲上一节学过，不跨讲强绑
    for bi, block in enumerate(weighted["blocks"], start=1):
        block_id = f"{chapter_id}-b{bi:02d}"
        tier = (block.get("tier") or "high").strip()
        conclusions = [
            {"level": c.get("level", "primary"), "statement": (c.get("statement") or "").strip()}
            for c in block.get("conclusions", [])
            if (c.get("statement") or "").strip()
        ][:MAX_CONCLUSIONS]
        counters["conclusions"] += len(conclusions)

        kp_ids: list[str] = []
        for ki, node in enumerate(block.get("nodes", []), start=1):
            kp_id = f"{block_id}-k{ki:02d}"
            name = (node.get("name") or "").strip()
            points = dedupe([c.get("name", "") for c in node.get("children", [])])[:MAX_POINTS]
            examples = [e for e in node.get("examples", []) if e]
            # 教材例题原文（最多 2 道，带题干）：讲课拿它当锚点，出题拿它当同源母题
            ex_detail = [
                {"id": e, "text": example_texts[e]}
                for e in examples
                if e in example_texts
            ][:2]

            kps[kp_id] = {
                "id": kp_id,
                "name": name,
                "chapter": chapter_id,
                "chapter_no": no,
                "chapter_name": chapter_name,
                "book": book["key"],
                "book_name": book["short"],
                "block": block_id,
                "block_name": (block.get("name") or "").strip(),
                "tier": tier,
                "tier_label": TIER_LABEL.get(tier, tier),
                "exam_weight": TIER_WEIGHT.get(tier, 4),
                "evidence": (node.get("evidence") or "").strip(),
                "points": points,
                "examples": examples,
                "example_texts": ex_detail,
                "types": types_by_kp.get(name, [])[:MAX_TYPES],
                "extras": extras_by_kp.get(name, [])[:MAX_EXTRAS],
                "prerequisites": [prev_kp_id] if prev_kp_id else [],
                "textbook_ref": (
                    f"张宇基础30讲·{book['short']} 第{no}讲《{title}》/ "
                    f"{(block.get('name') or '').strip()} / {name}"
                ),
                # 极少数节点在原树里既没要点也没例题（例如「唯一性」这种一句话考点），
                # 讲解时靠分支结论兜底，这里标出来便于体检
                "thin": not points and not examples,
            }
            prev_kp_id = kp_id
            kp_ids.append(kp_id)
            counters["kps"] += 1
            counters["points"] += len(points)
            counters["examples"] += len(examples)

        blocks_out.append(
            {
                "id": block_id,
                "name": (block.get("name") or "").strip(),
                "role": (block.get("role") or "").strip(),
                "tier": tier,
                "tier_label": TIER_LABEL.get(tier, tier),
                "tier_reason": (block.get("tier_reason") or "").strip(),
                "evidence": (block.get("evidence") or "").strip(),
                "conclusions": conclusions,
                "kps": kp_ids,
            }
        )
        counters["blocks"] += 1

    return {
        "id": chapter_id,
        "no": no,
        "name": chapter_name,
        "title": title,
        "book": book["key"],
        "book_name": book["short"],
        "kps": [kp for block in blocks_out for kp in block["kps"]],
        "blocks": blocks_out,
    }


def build() -> dict:
    chapters: list[dict] = []
    kps: dict[str, dict] = {}
    counters = {"blocks": 0, "kps": 0, "points": 0, "conclusions": 0, "types": 0, "extras": 0, "examples": 0}
    books_done: list[dict] = []

    for book in BOOKS:
        found = 0
        for local in range(1, book["count"] + 1):
            no = book["start"] + local - 1
            wp = TREE / f"lecture_{no:02d}_weighted.json"
            if not wp.exists():
                continue
            tp = TREE / f"lecture_{no:02d}_types.json"
            ep = TREE / f"lecture_{no:02d}_extras.json"
            xp = TREE / f"examples_lecture_{no:02d}.json"
            example_texts: dict[str, str] = {}
            if xp.exists():
                for item in (load(xp).get("unattached") or []):
                    if item.get("id") and item.get("text"):
                        example_texts[item["id"]] = _strip_solution(item["text"])
            chapters.append(
                _emit_lecture(
                    book,
                    local,
                    no,
                    load(wp),
                    load(tp) if tp.exists() else {},
                    load(ep) if ep.exists() else {},
                    example_texts,
                    kps,
                    counters,
                )
            )
            found += 1
        if found:
            books_done.append({"key": book["key"], "label": book["label"], "lectures": found})

    version = "zy30-" + "-".join(b["key"] for b in books_done)
    return {
        "meta": {
            "source": "textbook/tree/<book_prefix><NN>_{weighted,types,extras}.json",
            "textbook": "张宇基础30讲（" + " + ".join(b["label"] for b in books_done) + "）",
            "version": version,
            "books": books_done,
            "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "counts": counters,
        },
        "chapters": chapters,
        "kps": kps,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只核对，不写文件")
    parser.add_argument("--out", default="", help="输出路径（默认 backend/curriculum_data.json，测试时可指定临时文件）")
    args = parser.parse_args()

    data = build()
    chapters = data["chapters"]
    kps = data["kps"]
    counts = data["meta"]["counts"]

    print(f"讲次 {len(chapters)} / 分支 {counts['blocks']} / 知识点 {counts['kps']} / 结论 {counts['conclusions']}")
    print(f"要点 {counts['points']} 条 / 题型挂载 {counts['types']} 次 / 提速技巧挂载 {counts['extras']} 次 / 教材例题 {counts['examples']} 个")
    for ch in chapters:
        tiers = {}
        for block in ch["blocks"]:
            tiers[block["tier"]] = tiers.get(block["tier"], 0) + len(block["kps"])
        print(f"  {ch['id']} {ch['name']}  {len(ch['blocks'])} 分支 / {len(ch['kps'])} 点  {tiers}")

    # 自检：id 唯一、每点都有 name/evidence、id 可反查
    problems: list[str] = []
    if len(kps) != counts["kps"]:
        problems.append("kps 数量与计数器不一致")
    for kp_id, item in kps.items():
        if not item["name"]:
            problems.append(f"{kp_id} 缺 name")
        if not item["evidence"]:
            problems.append(f"{kp_id} 缺考纲依据")
        if item["chapter"] not in {c["id"] for c in chapters}:
            problems.append(f"{kp_id} 的讲次不在 chapters 里")

    thin = [k["id"] for k in kps.values() if k.get("thin")]
    print(f"\n自检：无要点也无例题的点 {len(thin)} 个（靠分支结论兜底）：{thin[:5]}；硬问题 {len(problems)} 条")
    for p in problems[:10]:
        print("  ✗", p)

    # 源码树与已发布 JSON 是否同步：另一个进程往 textbook/tree 里加讲次时，
    # 线上课程表不会自动更新，这里必须显式提示，避免「以为已经上了」
    if args.check and OUT.exists():
        try:
            published = json.loads(OUT.read_text(encoding="utf-8"))
            pub_ch = len(published.get("chapters") or [])
            pub_kp = len(published.get("kps") or {})
            if (pub_ch, pub_kp) != (len(chapters), len(kps)):
                print(
                    f"\n⚠ 源码树与已发布课程表不一致：树是 {len(chapters)} 讲/{len(kps)} 点，"
                    f"线上 JSON 是 {pub_ch} 讲/{pub_kp} 点 —— 需要重新跑一次（去掉 --check）才会生效"
                )
        except Exception as exc:  # noqa: BLE001
            print(f"\n⚠ 读已发布课程表失败：{exc}")

    if args.check:
        return 1 if problems else 0

    target = Path(args.out) if args.out else OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写出 {target}（{target.stat().st_size/1024:.0f} KB）")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
