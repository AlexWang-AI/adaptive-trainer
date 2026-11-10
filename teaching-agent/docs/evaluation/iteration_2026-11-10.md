# 本轮代码审核、评估与迭代记录（2026-11-10）

> 范围：`第一版UI_ex_v2/backend`（v3 线上主链路）+ `scripts/` + `agents/planner/`
> 代码快照：2026-11-10 09:27（项目在 01:20–04:38 有一轮更新，09:27 复查无新改动）
> 结论：**完成 1 个 P0 修复 + 1 个 P0 接口升级 + 1 个 P1 测试修复**；14/14 新增回归、9/9 planner、93/93 快照、11/11 画像回归通过；认证/答案键数据/首屏指标仍列为下一轮。

---

## 1. 审核结论

### 1.1 本轮修复

| # | 严重度 | 问题 | 证据 | 处理 |
|---|---|---|---|---|
| 1 | **P0** | `/api/judge` 不幂等：前端重试/双击会重复加 `attempts`、重复写错题、重复推进复习队列 | `api_server.py` 原 `record_attempt` 无 `attempt_id`；`student.py` 无作答账本 | 已加 `attempt` 表 + `attempt_id`，重复判题返回 `duplicate=true`，只写一次 |
| 2 | **P0** | 判题标准答案来自题卡 `question["answer"]`，模型写错答案会被当标准 | `v3core/judge.py` 原 `answer_key = question["answer"]` | 已加 `answer_key` 参数；`/api/judge` 支持传入独立答案键，并回显 `correct_answer` |
| 3 | **P1** | planner 契约测试 3 条失败：fixture 仍用旧 `lim.*` id，当前课程表已改为 `l01-b01-k01` | `pytest agents/planner/test_contract.py` 3 failed | 已把 fixture/断言迁移到当前 6 个 kp id，9/9 通过 |

### 1.2 仍然开放（下一轮）

| # | 严重度 | 问题 | 说明 |
|---|---|---|---|
| 4 | **P0** | 无认证、`student_id` 客户端传，analytics/ledger/mistakes 可按任意 id 读 | 需要 token/JWT + 对象级授权；本轮未动，避免破坏前端 |
| 5 | **P0** | 生成题仍无独立答案键数据源 | 接口已支持 `answer_key`；下一步要让题库/验证器真正提供它 |
| 6 | **P1** | 旧 `api.py` 仍挂载，6 个旧端点用 `MemorySaver` | 生产应关闭/加 410；本轮未动 |
| 7 | **P1** | live `v3core` 没有 pytest | 本轮加了 `scripts/test_judge_ledger.py`；建议下一轮迁移为 `backend/tests/` + pytest |
| 8 | **P2** | `graph.py` docstring 仍写「3 节点」，实际 lesson-only | 文档债，改注释即可 |
| 9 | **P2** | 没有 first-paint 指标，只有 `ttft_ms` | 需要在前端首段 markdown 渲染时打点 |

---

## 2. 代码改动

### 2.1 `v3core/student.py`

- 新增 `attempt` 表：

```sql
CREATE TABLE IF NOT EXISTS attempt (
    attempt_id  TEXT PRIMARY KEY,
    student_id  TEXT NOT NULL,
    subject     TEXT NOT NULL,
    kp          TEXT NOT NULL,
    question_id TEXT NOT NULL DEFAULT '',
    correct     INTEGER NOT NULL,
    layer       TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL
);
```

- `record_attempt(...)` 新增 `attempt_id` / `question_id` / `layer`，返回 `bool`：
  - 传 `attempt_id`：`INSERT OR IGNORE` 成功才更新 `student_kp`，重复返回 `False`；
  - 不传：自动生成 UUID（兼容旧调用方），返回 `True`。

### 2.2 `v3core/judge.py`

- `judge(...)` 新增 `answer_key: str | None = None`。
- 传入时优先使用 `answer_key`，否则回退 `question["answer"]`。
- 各层（choice/text/numeric/sympy/cjk/llm）统一使用 `key_text`，避免只改一半。

### 2.3 `api_server.py`

- `JudgeBody` 新增：

```python
answer_key: str | None = None
attempt_id: str | None = None
question_id: str = ""
```

- 新增 `_derived_attempt_id(...)`：没有显式 `attempt_id` 时，按
  `student_id + kp_id + question_id/stem + answer + answer_key` 生成稳定哈希。
  同一题同一答案重复提交只算一次；换答案会生成新 id。
- `/api/judge`：
  - 用 `answer_key` 判题；
  - 只在 `record_attempt` 返回 `True` 时写错题/推进复习；
  - 返回新增 `duplicate`、`attempt_id`，`correct_answer` 用独立答案键。

### 2.4 `scripts/test_judge_ledger.py`（新增）

14 条离线检查：

- 同一 `attempt_id` 重复写 → 返回 False，`attempts` 仍 1；
- 不同答案 → 新 attempt，`attempts` 2、`correct` 1；
- `judge(..., answer_key=...)` 覆盖题卡 answer；
- 直接调用 `/api/judge` 两次 → 第二次 `duplicate=True`，`attempts` 仍 1；
- API 独立答案键纠正题卡错误答案。

### 2.5 `agents/planner/test_contract.py`

- fixture 从旧 `lim.*` id 迁移到当前 6 个 `l01-b01-k0x`；
- 顺序/漏覆盖/发明 id 的断言改为当前 id；
- 9/9 通过。

### 2.6 测试与前端代理

- `scripts/test_backend_hardening.py`：
  - `BASE` 改为 `MN_API_BASE` 环境变量（默认 8008），可在 8011 验证新代码；
  - 并发判题请求带唯一 `attempt_id`，避免被幂等去重误伤压测；
  - 清理逻辑增加 `attempt` 表。
- `app/api/judge/route.ts`：转发可选 `answer_key` / `attempt_id` / `question_id`，为前端后续传独立答案键/幂等键留好通路。
- 前端 `tsc --noEmit` 通过（无输出）。

---

## 3. 验证

### 3.1 自动化

| 命令 | 结果 |
|---|---|
| `python -m py_compile`（backend 全部 .py） | 0 failures |
| `python scripts/test_judge_ledger.py` | **14/14 通过** |
| `pytest agents/planner/test_contract.py -q` | **9 passed** |
| `pytest teaching_teacher_v2/tests -q` | **93 passed** |
| `python scripts/test_learner_note.py` | **11/11 通过** |
| `tsc --noEmit`（前端） | 通过（无输出） |
| 判题并发回归（8011） | **7/7 通过**：48 请求、attempts=48、correct=24、错题 24 |

### 3.2 API 冒烟（升级后 8011 端口，不影响 8008 的旧服务）

第一次判题：

```json
{"correct": true, "duplicate": false, "persisted": true,
 "attempt_id": "auto-3f341a088409a3c498ca6fe5", "correct_answer": "B"}
```

第二次同题同答案：

```json
{"correct": true, "duplicate": true, "persisted": true,
 "attempt_id": "auto-3f341a088409a3c498ca6fe5", "correct_answer": "B"}
```

数据库：`student_kp.attempts = 1`，`attempt` 账本 1 行。

独立答案键（题卡 answer=A，answer_key=B，学生答 B）：

```json
{"correct": true, "layer": "choice", "correct_answer": "B"}
```

对照：升级前 8008 旧服务同一题提交两次，`student_kp.attempts=2` 且没有 `attempt` 账本行，证明问题真实存在、修复有效。

判题并发（8011，48 个唯一 `attempt_id`，8 线程）：

```
PASS 并发判题没有请求失败 — 1809 ms / 48 次
PASS 每次判题都真的落库了 — 未落库 0 次
PASS 作答次数精确等于请求数 — attempts=48 / 期望 48
PASS 答对数精确等于一半 — correct=24 / 期望 24
PASS 错题写入行数等于答错次数 — 24 / 期望 24
```

### 3.3 未运行

- `scripts/test_backend_hardening.py` 的流式/断连部分：需要真实模型与前端；判题并发 7/7 已单独跑通。
- `scripts/check_e2e.py` / `browser_smoke.mjs`：需要真实模型/前端/Edge，本轮未跑。
- `scripts/test_cjk_judge.py`：会打 8008 旧服务，未作为本轮验收；中文判题逻辑本身未改。

---

## 4. 兼容性与回滚

- `/api/judge` 只**新增**字段，未删除旧字段；旧前端忽略新字段即可。
- `attempt` 表由 `CREATE TABLE IF NOT EXISTS` 自动创建，旧数据不动。
- `record_attempt` 不传 `attempt_id` 时仍按旧行为写（自动 UUID），旧调用方不崩。
- 回滚：恢复 `v3core/student.py`、`v3core/judge.py`、`api_server.py` 三个文件；`attempt` 表可保留（不影响旧逻辑）。

---

## 5. 下一轮建议（按优先级）

1. **认证 + 对象级授权**：`X-Student-Token`/JWT，`student_id` 从 token 取；analytics/ledger/mistakes 校验归属。
2. **独立答案键数据源**：题库/验证器给 `answer_key`；生成题先过 SymPy/独立求解器再进判题。
3. **first-paint 指标**：前端首段 markdown 渲染打点，和 `ttft_ms` 分开。
4. **关闭旧 `api.py`**：生产路由只保留 v3；旧端点 410。
5. **pytest 化**：把 `scripts/test_judge_ledger.py` 迁到 `backend/tests/`，接入 CI。
6. **文档同步**：`graph.py` docstring 改 lesson-only；手册 09:00 快照加一条本轮升级说明。

---

## 6. 复跑命令

```powershell
$PY = "C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe"
cd "C:\Users\明\Desktop\第一版UI_ex_v2"

& $PY -m py_compile backend\api_server.py backend\v3core\student.py backend\v3core\judge.py
& $PY scripts\test_judge_ledger.py
& $PY -m pytest backend\agents\planner\test_contract.py -q
& $PY -m pytest "C:\Users\明\Desktop\claude deepseek\teaching_teacher_v2\tests" -q
& $PY scripts\test_learner_note.py
```
