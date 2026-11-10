import json
import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(trust_env=False, timeout=300)
B = "http://127.0.0.1:8008"

payload = {
    "kp_id": "lim.lhopital",
    "student_id": "fu-test",
    "history": [
        {"role": "student", "content": "什么是洛必达法则？"},
        {"role": "teacher", "content": "洛必达法则用于 0/0 或 ∞/∞ 型未定式，需要满足三个条件……"},
    ],
    "student_message": "我还是不懂第三步，能只讲这一步吗？",
}

t0 = time.perf_counter()
done = None
first = None
text = ""
with c.stream("POST", B + "/api/teach_stream", json=payload) as r:
    for line in r.iter_lines():
        if not line.startswith("data:"):
            continue
        ev = json.loads(line[5:].strip())
        if ev["type"] == "content":
            if first is None:
                first = (time.perf_counter() - t0) * 1000
            text += ev["text"]
        elif ev["type"] == "done":
            done = ev
        elif ev["type"] == "error":
            print("ERROR", ev["message"])

print(f"追问流式: TTFT {first:.0f}ms | round={done.get('round')} | status={done.get('status')}")
print("正文开头:", text[:80].replace("\n", " "))
print("是否提到「第三步/这一步」:", ("第三步" in text) or ("这一步" in text))
