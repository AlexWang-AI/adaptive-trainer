# 架构说明（Architecture）

> 代码快照：2026-11-10　｜　对应 `backend/v3core` + `app/`
> 这份文档回答：系统由哪些部分组成、一次请求怎么走、为什么这样设计、哪些地方是债。

---

## 1. 目标与非目标

**目标**

- 让学生从「不会」到「能独立做原题 + 同构变式」，核心产物是**掌握判定**；
- 讲课内容以教材树为准，不由模型自由发挥；
- 判题确定性优先，可解释、可回归；
- 跨会话记住掌握度/错题/复习；
- 每一步都能在 trace / 测试里被证明。

**非目标**

- 不做通用聊天机器人；
- 不做「多 agent 自由协商」；
- 不把教材/题库全量塞进 prompt；
- 不在 v1 做多租户、计费、复杂权限。

---

## 2. 运行时拓扑

```
┌──────────────────────────────────────────────────────────────┐
│ 前端 Next.js :3000                                            │
│  app/page.tsx · components/teaching/* · app/api/* 代理         │
└───────────────┬──────────────────────────────────────────────┘
                │ /api/teach_stream (SSE)      /api/judge
                ▼                              ▼
┌──────────────────────────────────────────────────────────────┐
│ FastAPI api_server.py（1010+ 行）                             │
│  知识树 / 讲练 SSE / 判题 / 侧问 / 诊断 / 学习闭环             │
└───────┬───────────────────────┬──────────────────────────────┘
        │                       │
        ▼                       ▼
┌──────────────────┐   ┌─────────────────────────────┐
│ v3core.graph     │   │ v3core.judge                │
│ lesson-only      │   │ choice→text→numeric→sympy   │
│ 1 个写节点        │   │ →cjk→llm→fallback           │
└───────┬──────────┘   └──────────────┬──────────────┘
        │                             │
        ▼                             ▼
┌──────────────────┐   ┌─────────────────────────────┐
│ nodes/prompts    │   │ db.transaction              │
│ 流式解析/校验/重试 │   │ attempt/student_kp/mistakes │
└───────┬──────────┘   │ review_queue/...            │
        │              └─────────────────────────────┘
        ▼
┌──────────────────┐
│ DeepSeek V4 Flash│
│ OpenAI 兼容      │
└──────────────────┘

数据侧：
  curriculum_data.json（232 KP / 18 讲 / 71 分支）
  students.db（学生模型 + 复习 + 提分曲线 + 认知偏差）
  mastery.db（通关）
  mistakes.db（思路诊断）
  checkpoints.sqlite（lesson 图状态）
  runs/trace.jsonl（节点/判题/token）
```

---

## 3. 一次讲课的完整链路

1. 前端 `POST /api/teach_stream`，传 `kp_id` / `student_id` / `history` / `focus`；
2. `api_server` 解析 `kp_id`，从 `KP_TABLE` 取中文名/考频/默认先修；
3. `learner_note(state)` 生成画像：历史薄弱点 + 本轮作答 + 最近认知偏差（≤400 字）；
4. `curriculum.textbook_block(kp_id)` 生成教材依据：考纲 + 要点 + 结论 + 例题 + 题型（≤1200 字）；
5. `v3core.graph` 执行 `lesson_node`：
   - `prompts.build_lesson_practice_system_prompt` 组 prompt；
   - `nodes.run_lesson_practice` 流式调用 LLM；
   - `MarkdownStreamExtractor` 边收边解析 `reply_markdown`；
   - `LessonPayload` 校验 schema；
   - `_check_cards` 校验题卡（选择/填空/难度/source_quote）；
   - 失败带原因修复重试；软问题不重试，只扣分；
6. SSE 推 `meta → content* → quiz_pack → done`；
7. 前端逐题 `POST /api/judge`：
   - `v3core.judge` 分层判题；
   - `db.transaction` 写 `attempt` / `student_kp` / `mistakes` / `review_queue`；
   - 重复提交用 `attempt_id` 去重；
8. 前端展示判题、解析、掌握度；答完 3 题进入下一轮/通关；
9. `runs/trace.jsonl` 记录节点/判题/token，供排障与评测。

---

## 4. 模块职责

### 4.1 前端

| 模块 | 职责 |
|---|---|
| `app/page.tsx` | 主页面 |
| `components/teaching/*` | 聊天、题卡、知识树、学习看板 |
| `app/api/teach_proxy/stream` | 把浏览器 SSE 转发到 Python 后端 |
| `app/api/judge` | 转发判题请求（本轮已支持 answer_key/attempt_id/question_id） |
| `components/teaching/quiz-pack.tsx` | 题卡交互、判题、进度 |

### 4.2 后端

| 模块 | 职责 |
|---|---|
| `api_server.py` | 所有 HTTP 路由、SSE、判题落库、学习闭环 |
| `v3core/graph.py` | lesson-only 图、画像、预算、降级 |
| `v3core/nodes.py` | 讲练合一、流式解析、schema/checks、重试 |
| `v3core/prompts.py` | 讲课提示词（紧凑 schema、字段顺序、教材依据） |
| `v3core/judge.py` | 六层判题、SymPy、中文规则、LLM 兜底 |
| `v3core/student.py` | 作答账本、`student_kp`、错题本 |
| `v3core/learning.py` | 掌握度衰减、1/3/7 天复习、提分曲线、认知偏差 |
| `v3core/db.py` | 每线程连接 + 显式事务 |
| `v3core/clients.py` | 进程内 LLM 单例 |
| `v3core/agents.py` | 侧问、诊断、只出题 |
| `v3core/trace.py` | JSONL trace + aggregate |
| `curriculum.py` | 加载 232 KP 编译表、`textbook_block` |
| `api.py` | 旧 v2 sidecar（兼容，勿在新功能中使用） |

---

## 5. 关键设计决策

### 5.1 为什么是 lesson-only，而不是多节点图

- 判题是前端逐题调 `/api/judge`，不需要 `interrupt` 暂停；
- 之前保留 `wait/judge` 却没有 `Command(resume=)`，留下 117 个永不恢复的 checkpoint；
- 结论：**只保留有真实进入/退出路径的节点**。不要为了「架构完整」保留死节点。

### 5.2 为什么判题是旁路

- 判题不产生教学内容，不需要改主图状态；
- 逐题判可以让前端立即反馈，不必等整轮结束；
- 写库集中在 `/api/judge` 的事务里，避免图内多次写。

### 5.3 为什么教材依据要进 prompt

- 模型对考研数学的「考纲/题型/易错点」不可靠；
- `textbook_block` 把「讲什么」变成可验证的边界；
- `source_quote` 检查「这句话在讲义或教材依据里」，至少保证有据可查（不保证数学正确）。

### 5.4 为什么判题要分层

- 选择题/文本/数值/SymPy 能覆盖大部分客观题；
- 中文答案（发散/不存在）需要规则层；
- LLM 只做最后兜底，避免「LLM 当第一判官」；
- 每层写 `layer`，可统计 `fallback` 比例。

### 5.5 为什么学生模型独立于 checkpoint

- checkpoint 是 thread 级，换天/换设备就断；
- 掌握度/错题/复习必须跨会话；
- `students.db` 与 `db.transaction` 保证原子写。

### 5.6 为什么加 attempt 账本

- 前端重试/双击/网络重放会重复请求 `/api/judge`；
- 没有账本时 `attempts` 会被重复加，掌握度虚高；
- `attempt_id` 唯一 + `INSERT OR IGNORE` 保证幂等；
- 独立答案键 `answer_key` 保证判题不被题卡错误答案带偏。

---

## 6. 数据模型

### `students.db`

| 表 | 关键字段 | 作用 |
|---|---|---|
| `attempt` | `attempt_id` PK, student_id, kp, correct, layer | 逐题作答账本，幂等 |
| `student_kp` | (student_id, subject, kp) PK, attempts, correct | 累计掌握度 |
| `mistakes` | id, student_id, kp, question, answer | 错题本 |
| `review_queue` | (student_id, kp) PK, stage, streak, due_at | 1/3/7 天复习 |
| `mastery_history` | id, overall, chapters, reason | 提分曲线 |
| `misconception_log` | (student_id, kp) PK, text | 最近认知偏差 |

### `mastery.db`

`kp_mastery(student_id, kp_id, score, mastered_at)`：通关标记；`/api/mastery` 要求 attempts≥3，分数服务端推导。

### `mistakes.db`

思路诊断记录：`steps / first_break / misconception / fix / severity`。

---

## 7. 质量门禁

| 门禁 | 位置 | 判据 |
|---|---|---|
| schema | `LessonPayload.model_validate` | 字段/长度/选项数量 |
| 题卡 | `nodes._check_cards` | 选择/填空、难度递进、source_quote |
| 题型 | `nodes._auto_tag_types` | type_name 命中教材题型 |
| 判题 | `judge.judge` | 分层确定性 |
| 事务 | `db.transaction` | 作答/错题/复习原子 |
| 幂等 | `student.record_attempt` | attempt_id 唯一 |
| 回归 | `scripts/test_*` | 离线/并发/画像 |

---

## 8. 已知债与下一轮路线

| 优先级 | 债 | 方案 |
|---|---|---|
| P0 | 无认证/对象级授权 | token/JWT + student_id 从 token 取 |
| P0 | 生成题没有独立答案键数据源 | 题库/验证器产出 `answer_key` |
| P1 | 旧 `api.py` 仍挂载 | 生产关闭/410 |
| P1 | live v3core 无 pytest | 迁移 `scripts` 到 `backend/tests` + CI |
| P2 | 只有 `ttft_ms`，无 first-paint | 前端首段渲染打点 |
| P2 | `graph.py` docstring 仍写 3 节点 | 改 lesson-only |
| P2 | 232 KP 数据版权 | 公开前替换/脱敏 |

---

## 9. 相关文档

- [`docs/handbook/handbook.md`](docs/handbook/handbook.md) — 新人上手指南
- [`docs/AGENT_STANDARD.md`](docs/AGENT_STANDARD.md) — Agent 制作标准
- [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) — 项目地图
- [`docs/战略.md`](docs/战略.md) — 产品战略
- [`docs/evaluation/multi-agent-2026-and-teaching-eval.md`](docs/evaluation/multi-agent-2026-and-teaching-eval.md) — 前沿与评估
- [`docs/evaluation/iteration_2026-11-10.md`](docs/evaluation/iteration_2026-11-10.md) — 本轮修复记录
