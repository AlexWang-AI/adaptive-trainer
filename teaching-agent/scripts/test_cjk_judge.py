import httpx
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(trust_env=False, timeout=180)
B = "http://127.0.0.1:8008"

q = {
    "kind": "fill",
    "stem": "判断级数 Σ1/n 的敛散性。",
    "options": [],
    "answer": "发散",
    "explanation": "p=1 的 p 级数发散",
    "tested_points": ["级数敛散性"],
    "difficulty": "medium",
}

for ans in ["发散", "收敛", "不存在", "发散（调和级数）"]:
    r = c.post(B + "/api/judge", json={"question": q, "answer": ans, "kp_id": "l16-b02-k01"})
    d = r.json()
    print(f"中文判题 {ans!r}: correct={d['correct']} layer={d['layer']} {d['elapsed_ms']}ms")

r = c.get(B + "/api/mistakes?limit=10")
d = r.json()
print("错题本 count:", d["count"], "| 来源:", sorted({i.get("source") for i in d["items"]}))
if d["items"]:
    first = d["items"][0]
    print("  最新一条:", first.get("source"), str(first.get("question"))[:40], "|", str(first["diagnosis"].get("first_break"))[:40])
