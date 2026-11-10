"""后端加固回归：P1-11（连接/事务）、P2-7（LLM 客户端单例）、P2-8（SSE 断连清理）。

    python scripts/test_backend_hardening.py

三段：

1. **P1-11 原子性 + 并发**（纯库层，临时文件，不碰真实数据）
   - 事务中途抛异常 → 一行都不留；
   - 嵌套事务里 `commit()` 不生效，只有最外层提交；
   - 8 线程 × 25 个事务并发写 → 一条不丢、一个 `database is locked` 都没有。

2. **P1-11 端到端并发**（打真实后端，用 p11-stress 这个一次性学生）
   - 8 线程 × 6 次判题，中途成功/失败交替；
   - 断言 `student_kp.attempts` 精确等于 48（丢更新会少）、`correct` 等于 24；
   - 断言每条判题返回 `persisted=True`，错题本条数等于 24。

3. **P2-7 客户端单例 / P2-8 断连清理**
   - `get_llm_client()` 连调 3 次只构造 1 个 `LLMClient`；
   - 中途掐断一条 SSE，`/api/health_v3.streams.active` 必须回到 0；
   - 正常跑完的流也必须归零。
"""

from __future__ import annotations

import concurrent.futures as futures
import os
import json
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = os.getenv("MN_API_BASE", "http://127.0.0.1:8008")
STUDENT = "p11-stress"
KP = "l03-b01-k01"

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"{'PASS' if ok else 'FAIL'}  {label}{('  — ' + detail) if detail else ''}")


# ---------------------------------------------------------------------------
# 1. 库层：原子性 / 嵌套 / 并发
# ---------------------------------------------------------------------------
def test_db_layer() -> None:
    from v3core import db

    tmp = Path(tempfile.mkdtemp(prefix="p11-db-"))
    path = tmp / "t.db"
    conn = db.connection(path, schema="CREATE TABLE IF NOT EXISTS n (id INTEGER PRIMARY KEY, tag TEXT);")

    # 1.1 中途异常整体回滚
    try:
        with db.transaction(conn):
            conn.execute("INSERT INTO n (tag) VALUES ('boom')")
            raise RuntimeError("模拟写一半炸了")
    except RuntimeError:
        pass
    rows = conn.execute("SELECT COUNT(*) AS c FROM n").fetchone()["c"]
    check("事务中途异常 → 一行都不留", rows == 0, f"remaining={rows}")

    # 1.2 嵌套：内层 commit 不生效，外部读不到，直到最外层退出
    with db.transaction(conn):
        conn.execute("INSERT INTO n (tag) VALUES ('outer')")
        with db.transaction(conn):
            conn.execute("INSERT INTO n (tag) VALUES ('inner')")
            conn.commit()  # 内层 commit 必须是 no-op
        outside = sqlite3.connect(str(path))
        visible = outside.execute("SELECT COUNT(*) FROM n").fetchone()[0]
        outside.close()
        check("嵌套事务内 commit 不外泄", visible == 0, f"外部可见={visible}")
    outside = sqlite3.connect(str(path))
    visible = outside.execute("SELECT COUNT(*) FROM n").fetchone()[0]
    outside.close()
    check("最外层退出后两条一起可见", visible == 2, f"可见={visible}")

    # 1.3 并发写：不丢、不锁超时
    errors: list[str] = []

    def write_many(worker: int) -> None:
        try:
            for i in range(25):
                with db.transaction(conn):
                    conn.execute("INSERT INTO n (tag) VALUES (?)", (f"w{worker}-{i}",))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=write_many, args=(w,)) for w in range(8)]
    started = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = (time.perf_counter() - started) * 1000
    total = conn.execute("SELECT COUNT(*) AS c FROM n").fetchone()["c"]
    check("8 线程 × 25 事务一条不丢", total == 202, f"总数={total}（含 2 条前置）")
    check("并发写下没有锁错误", not errors, errors[0] if errors else f"{elapsed:.0f} ms")

    # 1.4 每线程各自一条真实连接
    seen: list[int] = []
    lock = threading.Lock()

    def grab() -> None:
        with lock:
            seen.append(id(conn.raw))

    ts = [threading.Thread(target=grab) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    check("每线程一条真实连接（不跨线程共享游标）", len(set(seen)) == 4, f"{len(set(seen))} 条")


# ---------------------------------------------------------------------------
# 2. 端到端：并发判题不丢写
# ---------------------------------------------------------------------------
def _cleanup_student(student: str) -> None:
    """把上一次跑留下的压测数据清掉，保证 attempts 是绝对值可断言。"""
    conn = sqlite3.connect(str(BACKEND / "data" / "students.db"))
    for table, column in (
        ("attempt", "student_id"),
        ("student_kp", "student_id"),
        ("mistakes", "student_id"),
        ("review_queue", "student_id"),
        ("misconception_log", "student_id"),
    ):
        try:
            conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (student,))
        except sqlite3.OperationalError:
            pass  # 表还没建过
    conn.commit()
    conn.close()


def test_judge_concurrency() -> None:
    client = httpx.Client(trust_env=False, timeout=30.0)
    _cleanup_student(STUDENT)
    q = {
        "kind": "fill",
        "stem": "并发回归用题",
        "answer": "1",
        "explanation": "占位",
        "tested_points": [KP],
        "difficulty": "easy",
    }
    results: list[dict] = []
    errors: list[str] = []

    def one(index: int) -> None:
        answer = "1" if index % 2 == 0 else "2"  # 一半对一半错
        try:
            data = client.post(
                f"{BASE}/api/judge",
                json={"question": q, "answer": answer, "kp_id": KP, "student_id": STUDENT,
                      "attempt_id": f"p11-{index}", "question_id": "p11"},
            ).json()
            results.append(data)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")

    workers = 8
    per_worker = 6
    jobs = list(range(workers * per_worker))
    started = time.perf_counter()
    with futures.ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, jobs))
    elapsed = (time.perf_counter() - started) * 1000

    check("并发判题没有请求失败", not errors, errors[0] if errors else f"{elapsed:.0f} ms / {len(jobs)} 次")
    check("每次判题都真的落库了", all(r.get("persisted") for r in results),
          f"未落库 {sum(1 for r in results if not r.get('persisted'))} 次")

    ledger = client.get(f"{BASE}/api/ledger", params={"kp_id": KP, "student_id": STUDENT}).json()
    check("作答次数精确等于请求数（丢更新会变少）", ledger["attempts"] == len(jobs),
          f"attempts={ledger['attempts']} / 期望 {len(jobs)}")
    check("答对数精确等于一半", ledger["correct"] == len(jobs) // 2,
          f"correct={ledger['correct']} / 期望 {len(jobs) // 2}")

    wrong = client.get(f"{BASE}/api/mistakes", params={"student_id": STUDENT, "limit": 100}).json()
    quiz_items = [i for i in wrong.get("items", []) if i.get("source") == "quiz"]
    check("错题本接口能读回这次答错的题", len(quiz_items) >= 1, f"{len(quiz_items)} 条未解决")

    # 「答对即视为这个点的错题解决了」是产品口径，所以错题本接口只会剩最后几条未解决；
    # 这里直接对库对账：写入行数必须等于答错次数（含已解决的）
    db = sqlite3.connect(str(BACKEND / "data" / "students.db"))
    total_rows = db.execute(
        "SELECT COUNT(*) FROM mistakes WHERE student_id = ? AND subject = '数学一'", (STUDENT,)
    ).fetchone()[0]
    unresolved = db.execute(
        "SELECT COUNT(*) FROM mistakes WHERE student_id = ? AND subject = '数学一' AND resolved_at IS NULL",
        (STUDENT,),
    ).fetchone()[0]
    db.close()
    check("错题写入行数等于答错次数（含已解决）", total_rows == len(jobs) // 2,
          f"{total_rows} / 期望 {len(jobs) // 2}")
    check("答对会把旧错题标记为已解决", unresolved < total_rows, f"未解决 {unresolved}/{total_rows}")


# ---------------------------------------------------------------------------
# 3. P2-7 客户端单例 / P2-8 断连清理
# ---------------------------------------------------------------------------
def test_client_singleton() -> None:
    import v3core.clients as clients
    from v3core.llm import LLMClient

    built: list[int] = []
    original = clients.LLMClient

    class Counting(original):  # type: ignore[misc, valid-type]
        def __init__(self, config):  # noqa: ANN001
            built.append(1)
            super().__init__(config)

    clients.LLMClient = Counting  # type: ignore[assignment]
    clients.reset_llm_client()
    try:
        first = clients.get_llm_client()
        second = clients.get_llm_client()
        third = clients.get_llm_client()
    finally:
        clients.LLMClient = original  # type: ignore[assignment]
        clients.reset_llm_client()

    check("三次 get_llm_client() 只构造一个客户端", len(built) == 1, f"构造 {len(built)} 次")
    check("返回同一个实例", first is second and second is third)


def active_streams(client: httpx.Client) -> int:
    return int(client.get(f"{BASE}/api/health_v3").json()["streams"]["active"])


def test_stream_cleanup() -> None:
    client = httpx.Client(trust_env=False, timeout=60.0)
    check("基线：没有挂着的流", active_streams(client) == 0, f"active={active_streams(client)}")

    # 3.1 中途断开
    payload = {"action": "turn", "kp_id": KP, "student_id": "p28-abort"}
    with client.stream("POST", f"{BASE}/api/teach_stream", json=payload) as response:
        seen_meta = False
        for line in response.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:].strip())
                if event.get("type") == "meta":
                    seen_meta = True
                    break
    check("断开前收到了 meta", seen_meta)

    deadline = time.time() + 20
    while time.time() < deadline and active_streams(client) > 0:
        time.sleep(0.5)
    check("客户端掐断后 sink 被回收（≤20s 归零）", active_streams(client) == 0,
          f"active={active_streams(client)}")

    # 3.2 正常跑完
    ttft = None
    started = time.perf_counter()
    done_seen = False
    with client.stream("POST", f"{BASE}/api/teach_stream", json=payload) as response:
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:].strip())
            if event.get("type") == "content" and ttft is None:
                ttft = (time.perf_counter() - started) * 1000
            elif event.get("type") == "done":
                done_seen = True
    check("正常流跑完收到 done", done_seen, f"首字 {ttft or 0:.0f} ms")
    time.sleep(1.0)
    check("正常结束后 sink 归零", active_streams(client) == 0, f"active={active_streams(client)}")


def main() -> int:
    print("=== 1. 库层：原子性 / 嵌套 / 并发 ===")
    test_db_layer()
    print("\n=== 2. 端到端：并发判题 ===")
    test_judge_concurrency()
    print("\n=== 3. LLM 单例 / SSE 断连清理 ===")
    test_client_singleton()
    test_stream_cleanup()

    total = len(PASSED) + len(FAILED)
    print(f"\n==== {len(PASSED)}/{total} 通过 ====")
    for item in FAILED:
        print(f"  ✗ {item}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

