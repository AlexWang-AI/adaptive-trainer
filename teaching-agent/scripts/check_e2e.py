"""端到端联调检查（v3）：模拟前端，走通「讲练流 → 题卡 → SymPy 判题」。

    python scripts/check_e2e.py                  # 打 Next 代理（和浏览器同一条链路）
    python scripts/check_e2e.py --direct         # 直接打 Python 后端
    python scripts/check_e2e.py --kp lim.lhopital --samples 3

验收标准（任一不过即非零退出）：
  1. 首字 TTFT：默认跑 3 次取**中位数** < 2000 ms（单次受模型排队影响会抖动，中位数才是手感）；
  2. 每次返回的正文 >= 200 字，且带 3 道题（至少 1 道选择题、每题 schema 合法）；
  3. 每道题：标准答案判 correct=True，明显错误答案判 correct=False；
  4. 判题层落在 choice / numeric / sympy / text 之内（证明不是纯字符串比较）。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TTFT_BUDGET_MS = 2000


def fail(message: str) -> None:
    print(f"\n[FAIL] {message}")
    sys.exit(1)


def sse_events(client: httpx.Client, url: str, payload: dict):
    with client.stream("POST", url, json=payload, timeout=300.0) as response:
        if response.status_code != 200:
            body = response.read().decode("utf-8", "replace")[:500]
            fail(f"流式请求失败 {response.status_code}：{body}")
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if raw:
                yield json.loads(raw)


def measure(client, url, kp: str, tag: str, student: str | None = None) -> dict:
    started = time.perf_counter()
    ttft = None
    text = ""
    pack = None
    done = None
    meta = None
    payload = {"action": "turn", "kp_id": kp, "student_id": student or f"e2e-{tag}"}
    for event in sse_events(client, url, payload):
        kind = event.get("type")
        if kind == "meta":
            meta = event
        elif kind == "content":
            if ttft is None:
                ttft = (time.perf_counter() - started) * 1000
            text += event.get("text", "")
        elif kind == "quiz_pack":
            pack = event
        elif kind == "done":
            done = event
        elif kind == "error":
            fail(f"流内错误：{event.get('message')}")
    total = (time.perf_counter() - started) * 1000
    note = (meta or {}).get("learner_note") or ""
    print(
        f"  {tag}: 首字 {ttft or 0:.0f} ms ｜ 总 {total:.0f} ms ｜ 正文 {len(text)} 字"
        f" ｜ 画像 {len(note)} 字"
    )
    return {"ttft": ttft, "text": text, "pack": pack, "done": done, "meta": meta}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    parser.add_argument("--direct", action="store_true", help="直接打 Python 后端 8008")
    parser.add_argument("--kp", default="lim.lhopital")
    parser.add_argument("--ttft-budget", type=int, default=TTFT_BUDGET_MS)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument(
        "--student",
        default=None,
        help="指定学生 id（默认每次用 e2e-<tag>）。传 local-user 可验证 P1-4 学习画像注入",
    )
    args = parser.parse_args()

    client = httpx.Client(trust_env=False, timeout=300.0)
    base = "http://127.0.0.1:8008" if args.direct else args.base
    stream_url = f"{base}/api/teach_stream" if args.direct else f"{base}/api/teach_proxy/stream"
    judge_url = f"{base}/api/judge"

    print(f"→ 流式入口：{stream_url}")

    # 预热一次（dev 下路由首次编译 + 模型前缀缓存冷启动都不该算进手感）
    warm = measure(client, stream_url, args.kp, "warmup", args.student)
    print(f"  预热：首字 {warm['ttft'] or 0:.0f} ms（不计入验收）")

    samples = [
        measure(client, stream_url, args.kp, f"s{i + 1}", args.student)
        for i in range(max(1, args.samples))
    ]
    ttfts = [s["ttft"] for s in samples if s["ttft"] is not None]
    if not ttfts:
        fail("没有收到任何 content 事件（流是空的）")
    median = statistics.median(ttfts)

    # ---- 检查 1：TTFT 中位数 ----
    print(f"  TTFT 中位数 {median:.0f} ms（budget {args.ttft_budget}）")
    if median > args.ttft_budget:
        fail(f"TTFT 中位数 {median:.0f} ms 超过预算 {args.ttft_budget} ms")

    # ---- 检查 2：正文与题卡 ----
    for index, sample in enumerate(samples, 1):
        if len(sample["text"]) < 200:
            fail(f"第 {index} 次正文只有 {len(sample['text'])} 字，明显不完整")
        pack = sample["pack"]
        if not pack:
            fail(f"第 {index} 次没有收到 quiz_pack")
        cards = pack.get("quiz_pack") or []
        if len(cards) != 3:
            fail(f"第 {index} 次题卡应为 3 道，实际 {len(cards)} 道")
        if not any(c.get("kind") == "choice" for c in cards):
            fail(f"第 {index} 次 3 道题里没有选择题")
        for q_index, card in enumerate(cards, 1):
            for field in ("stem", "answer", "explanation", "difficulty"):
                if not card.get(field):
                    fail(f"第 {index} 次第 {q_index} 题缺少 {field}")
            if card["kind"] == "choice" and len(card.get("options") or []) != 4:
                fail(f"第 {index} 次第 {q_index} 题是选择题但选项不是 4 个")

    # ---- 检查 3 & 4：判题（用最后一次的题卡） ----
    cards = samples[-1]["pack"]["quiz_pack"]
    layers: set[str] = set()
    for index, card in enumerate(cards, 1):
        good = client.post(judge_url, json={"question": card, "answer": card["answer"]}).json()
        if not good.get("correct"):
            fail(f"第 {index} 题标准答案被判错（{good.get('reason')}）")
        layers.add(good.get("layer"))

        if card["kind"] == "choice":
            wrong = next(letter for letter in "ABCD" if letter != str(card["answer"]).upper()[:1])
        else:
            wrong = "__e2e_wrong__"
        bad = client.post(judge_url, json={"question": card, "answer": wrong}).json()
        if bad.get("correct"):
            fail(f"第 {index} 题明显错误答案被判对")
        layers.add(bad.get("layer"))
        print(f"  第 {index} 题 ✓ {good['layer']:<7} ✗ {bad['layer']:<7} {card['difficulty']}")

    if not (layers & {"sympy", "numeric", "choice", "text"}):
        fail(f"判题层异常：{layers}")

    done = samples[-1]["done"] or {}
    if done.get("status") not in ("awaiting_answer", "done"):
        fail(f"完成事件状态异常：{done.get('status')}")

    # ---- 检查 5（--student 时）：学习画像真的进了这一讲的请求（P1-4） ----
    if args.student:
        preview = client.get(
            "http://127.0.0.1:8008/api/learner_note",
            params={"kp_id": args.kp, "student_id": args.student},
        ).json()
        note = preview.get("note") or ""
        print(f"  画像预览（{args.kp} / {args.student}）：{note or '(空)'}")
        if not note:
            fail(f"学生 {args.student} 对 {args.kp} 的画像为空 —— P1-4 没生效")
        if len(note) > 400:
            fail(f"画像 {len(note)} 字，超过 schema 的 400 字上限")
        for index, sample in enumerate(samples, 1):
            streamed = (sample["meta"] or {}).get("learner_note")
            if streamed != note:
                fail(f"第 {index} 次 meta.learner_note 与 /api/learner_note 不一致：{streamed!r}")
        print(f"  {len(samples)} 次请求的 meta.learner_note 与预览逐字一致（{len(note)} 字）")

    # ---- 检查 6：讲课以教材为准（教材依据进了请求，并真的反映在讲义里） ----
    meta0 = samples[-1]["meta"] or {}
    if meta0.get("kp_id"):
        chars = int(meta0.get("textbook_chars") or 0)
        ref = meta0.get("textbook_ref") or ""
        if chars < 200 or not ref:
            fail(f"教材依据没有进请求：textbook_chars={chars}, ref={ref!r}")
        print(f"  教材依据 {chars} 字 → {ref}")

        # 讲义里至少命中 2 个教材要点/结论的实词（4 字窗口），证明讲解不是自由发挥
        import re as _re

        detail = client.get(
            "http://127.0.0.1:8008/api/kp_detail", params={"kp_id": meta0["kp_id"]}
        ).json()
        if not detail.get("points"):
            fail(f"知识点 {meta0['kp_id']} 在教材树里没有要点")
        text = _re.sub(r"[^\u4e00-\u9fff]", "", samples[-1]["text"])
        windows = set()
        for item in (detail.get("points") or [])[:6] + (detail.get("conclusions") or [])[:3]:
            clean = _re.sub(r"[^\u4e00-\u9fff]", "", item)
            for i in range(0, max(0, len(clean) - 3), 2):
                windows.add(clean[i : i + 4])
        hits = [w for w in windows if w in text]
        print(f"  讲义命中教材要点片段 {len(hits)} 个（共 {len(windows)} 个窗口）")
        if len(hits) < 2:
            fail(f"讲义与教材要点对不上（命中 {len(hits)} 个 4 字片段）——「以教材为准」没生效")

        # 3 道题必须落在教材题型上（题型层接入出题的验收）
        type_names = {t.get("name") for t in (detail.get("types") or []) if t.get("name")}
        cards = (samples[-1]["pack"] or {}).get("quiz_pack") or []
        tagged = [c for c in cards if (c.get("type_name") or "").strip()]
        matched = [c for c in tagged if c["type_name"] in type_names]
        print(f"  题卡题型标注 {len(tagged)}/3，命中教材题型 {len(matched)}/3（清单 {sorted(type_names)}）")
        if type_names and len(matched) < 2:
            fail(f"3 道题里只有 {len(matched)} 道能对上教材题型 —— 出题没接题型层")

    print("\n[PASS] 全链路通过")
    print(f"  · TTFT 中位数 {median:.0f} ms（各次：{'/'.join(f'{t:.0f}' for t in ttfts)}）")
    print(f"  · {len(samples)} 次请求均返回 3 道题卡，判题层 {sorted(layers)}")
    print(f"  · 服务端耗时 {done.get('elapsed_ms', '-')} ms，token {done.get('tokens', '-')}")


if __name__ == "__main__":
    main()
