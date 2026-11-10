"""把 DSH 会话日志（session.v4.jsonl，事件流格式）压成可检索的纯文本。

日志不是「消息数组」，而是一串事件：`user/message` / `assistant/message` / `tool/call` /
`tool/result` / `job/registered` …。这里按时间顺序拼成阅读稿，并单独抽一份「命令清单」，
方便从历史里还原「知识树是怎么一步步建的」。

    python scripts/flatten_session.py [jsonl] [输出目录]

产出：
    <out>/session_flat.md   全量阅读稿（工具输出各自截断）
    <out>/commands.md       只含命令 / 工具调用名 + 参数（还原流水线用）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("work/tree_logs/session.v4.jsonl")
OUT_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else SRC.parent

TEXT_LIMIT = 2600
RESULT_LIMIT = 900


def blocks(content) -> str:
    if isinstance(content, str):
        return content
    out = []
    for item in content or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            if item.get("type") == "text":
                out.append(item.get("text", ""))
            elif item.get("type") == "reasoning":
                out.append("〔思考〕" + (item.get("text", "") or "")[:400])
    return "\n".join(out)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    flat = (OUT_DIR / "session_flat.md").open("w", encoding="utf-8")
    cmds = (OUT_DIR / "commands.md").open("w", encoding="utf-8")
    counts = {"user": 0, "assistant": 0, "tool": 0, "result": 0, "job": 0}
    seq = 0

    with SRC.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            kind = rec.get("type")
            data = rec.get("data") or {}
            seq += 1

            if kind == "user/message":
                text = blocks(data.get("content"))
                if not text.strip():
                    continue
                counts["user"] += 1
                flat.write(f"\n\n===== [{seq}] 用户 =====\n{text[:TEXT_LIMIT]}\n")

            elif kind == "assistant/message":
                msg = data.get("message") or {}
                text = blocks(msg.get("content"))
                if not text.strip():
                    continue
                counts["assistant"] += 1
                flat.write(f"\n\n----- [{seq}] 助手 -----\n{text[:TEXT_LIMIT]}\n")

            elif kind == "tool/call":
                counts["tool"] += 1
                name = data.get("name", "")
                args = data.get("arguments") or "{}"
                short = args if len(args) <= 700 else args[:700] + "…"
                flat.write(f"\n  ▶ {name} {short}\n")
                cmds.write(f"\n### [{seq}] {name}\n{args}\n")

            elif kind == "tool/result":
                counts["result"] += 1
                msg = data.get("message") or {}
                text = blocks(msg.get("content"))
                flag = "（报错）" if data.get("error") or msg.get("isError") else ""
                flat.write(f"  ◀ 结果{flag}：{text[:RESULT_LIMIT]}\n")

            elif kind == "job/registered":
                counts["job"] += 1
                label = data.get("label") or ""
                flat.write(f"\n  ⏱ 后台任务 {data.get('kind')}：\n{label[:1500]}\n")
                cmds.write(f"\n### [{seq}] JOB {data.get('kind')}\n{label}\n")

    flat.close()
    cmds.close()
    print(f"事件 {seq} 条：用户 {counts['user']} / 助手 {counts['assistant']} / 工具 {counts['tool']} / 结果 {counts['result']} / 后台任务 {counts['job']}")
    for name in ("session_flat.md", "commands.md"):
        p = OUT_DIR / name
        print(f"  {p}  {p.stat().st_size/1024/1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
