# Changelog

## 2026-11-10 · 整合与加固

### 整合

- 把分散的讲课智能体代码、教材树、文档、评估、手册、starter_kit 汇总为本仓库。
- 新增根 `README.md`、`ARCHITECTURE.md`、`SECURITY.md`、`CONTRIBUTING.md`、`.env.example`、`.gitignore`。
- 排除 `.env`、学生数据库、`runs/*.jsonl`、`node_modules`、`.next`、教材 OCR 原文、图片与无关项目。

### 修复

- `/api/judge` 增加 `attempt_id` 幂等：重复提交不再重复加 `attempts`、重复写错题、重复推进复习。
- `v3core.student` 新增 `attempt` 作答账本；`record_attempt` 返回是否首次写入。
- `v3core.judge` 支持独立 `answer_key`，优先于题卡 `answer`。
- `api_server.JudgeBody` 新增 `answer_key` / `attempt_id` / `question_id`；返回 `duplicate` / `attempt_id`。
- `app/api/judge/route.ts` 转发上述字段。
- `scripts/test_backend_hardening.py` 支持 `MN_API_BASE`，并发请求使用唯一 `attempt_id`。
- `agents/planner/test_contract.py` 迁移到当前 `l01-b01-k0x` 知识点 id，9/9 通过。
- `backend/requirements.txt` 补齐 `langgraph-checkpoint-sqlite` / `sympy` / `pytest` / `httpx`。

### 验证

- `scripts/test_judge_ledger.py`：14/14
- `scripts/test_learner_note.py`：11/11
- `teaching_teacher_v2` 快照：93/93
- planner 契约：9/9
- 判题并发：48 请求 / attempts=48 / correct=24
- 前端 `tsc --noEmit`：通过

## 2026-11-09 · v3 讲练合一 + 学习闭环

- 知识树编译为 `curriculum_data.json`（18 讲 / 71 分支 / 232 KP）。
- `graph.py` 改为 lesson-only；判题走 `/api/judge` 旁路。
- 新增 `learning.py`（遗忘衰减、1/3/7 天复习、提分曲线、认知偏差）。
- 新增 `db.py`（每线程连接 + 显式事务）。
- 新增 `/api/analytics`、`/api/review/*`、`/api/ledger`、`/api/practice_more`。

## 2026-11-07 · v3 讲练合一

- 4 节点 → 3 节点，2 次调用 → 1 次。
- SymPy 分层判题；`report/judge_benchmark.json` 24 例。
- `eval_v3.py` 端到端评测；首屏流式解析。

## 2026-11-01 · 早期基线

- 四版教学 prompt、确定性检查、修复环。
- 判题字符串 → 数值/SymPy。
- `MemorySaver` → `SqliteSaver`。
- 显式学生模型（掌握度 + 错题本）。
