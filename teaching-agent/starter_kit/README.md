# starter_kit · 讲课 Agent 新人参考实现

这是《新人上手指南》配套的**可运行最小实现**，目标是让一个新同学在 30 分钟内：

1. 不配 API Key，跑通 `lesson → wait → judge → policy` 的完整一课；
2. 看懂「单写者 + 只读旁路 + 显式学生模型 + 确定性判题 + trace」怎么写；
3. 把 FakeLLM 换成真实 DeepSeek，跑一次真实模型；
4. 用 `eval_passk.py` 跑一次评测，理解 pass^k。

它**不是**生产代码，而是把 `第一版UI_ex_v2/backend/v3core` 的核心结构抽成 8 个文件，
每个文件都能单独读、单独测、单独改。

## 30 秒跑通

```powershell
# 1) 进入目录
cd C:\Users\明\Desktop\claude deepseek\reports\2026-11-multiagent-teaching-eval\starter_kit

# 2) 用本机已验证的 Python（不要新建 venv，先把流程跑通）
$PY = C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe

# 3) 环境自检
& $PY 00_env_check.py

# 4) 离线演示：不需要 API Key
& $PY demo.py

# 5) 跑单测
& $PY -m pytest tests -q

# 6) 跑评测（pass^k）
& $PY eval_passk.py --k 3
```

## 接真实模型

```powershell
# 复制 .env.example 为 .env，填入 DeepSeek key
Copy-Item .env.example .env
notepad .env

# 用真实模型跑一课（会消耗 token）
& $PY demo.py --real
```

## 目录

| 文件 | 作用 | 先读谁 |
|---|---|---|
| `contracts.py` | 所有 Pydantic 契约：讲义、题卡、判分、学生状态 | ① |
| `content.py` | 知识点包 + 独立题库（判题的标准答案在这里） | ② |
| `structured.py` | 通用结构化节点：LLM → JSON → 校验 → 修复环 | ③ |
| `judge.py` | 五层判题：choice → text → numeric → sympy → fallback | ④ |
| `student_store.py` | 学生模型：掌握度、错题、复习队列、幂等写入 | ⑤ |
| `graph.py` | LangGraph 单写者流程：lesson → wait → judge → policy | ⑥ |
| `trace.py` | JSONL 追踪 + 聚合 | ⑦ |
| `api.py` | FastAPI + 最小认证 + 对象级授权 | ⑧ |
| `demo.py` | 离线 CLI 演示 | 跑 |
| `eval_passk.py` | 评测：独立答案键 + pass^k | 跑 |
| `tests/` | 离线单测，不联网 | 跑 |

## 与线上代码的关系

线上主图是 **lesson-only**：只保留 `lesson` 一个写节点，判题走 `/api/judge` 旁路
（因为前端逐题判，不需要 `Command(resume=)`）。本 kit 保留
`lesson → wait → judge` 三节点，是为了让你在离线环境里看清 `interrupt` 怎么工作。
读的时候分清：

- **生产模式**（`第一版UI_ex_v2/backend/v3core`）：lesson-only + `/api/judge`；
- **教学模式**（本 kit）：lesson → wait → judge，用 FakeLLM 跑完整闭环。

两者共享同一套原则：单写者、确定性判题、显式学生模型、幂等写入、trace。

## 三条铁律

1. **写者只有一个**：`lesson` 写教学内容；`wait` / `judge` / `policy` 是确定性节点。
2. **答案键独立**：题卡里的 `answer` 是模型生成的，可能错；判题只认 `content.QUESTION_BANK` 的答案键。
3. **副作用幂等**：`attempt_id = session_id:question_id`，重复恢复/重放不会重复计数。

## 已知边界

- 这是**单进程、SQLite、单机**的最小实现，不是多租户生产系统。
- `api.py` 的 token 映射是教学用，不是生产认证；生产要 JWT/OIDC + RBAC。
- 没有接 232 个知识点的树；`content.py` 只放了 3 个知识点包，方便阅读。
- 没有 SSE 流式；真实系统在 `v3core/nodes.py` 的 `MarkdownStreamExtractor`，手册第 6 章逐段讲。
- 没有接 MCP/A2A；手册第 5 章讲什么时候需要、什么时候不需要。

## 配套阅读

- `../report.md`：2026-11 多智能体架构前沿 + 讲课系统评估
- `第一版UI_ex_v2/docs/AGENT_STANDARD.md`：项目自己的 Agent 制作标准
- `第一版UI_ex_v2/战略.md`：产品战略与掌握判定口径
