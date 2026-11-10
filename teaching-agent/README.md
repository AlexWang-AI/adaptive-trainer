# MathNeuron · 讲课智能体系统

> 从教材知识树到「讲一层 → 练三题 → 确定性判题 → 跨会话掌握度」的完整代码、架构与新人指导。
>
> 代码快照：2026-11-10　｜　主栈：Next.js 16 + FastAPI + LangGraph（lesson-only）+ SQLite + DeepSeek

这个仓库把之前分散在多个目录里的**讲课智能体代码、教材数据、架构文档、评估报告、新人手册和参考代码包**整合到一起，目标不是做一个「demo」，而是让一个新同学能按文档跑通、读懂、改对。

---

## 1. 这个系统是什么

学生带着目标进来（例如「两周把极限学扎实」），系统给一条可执行、可量化、能验收的路径，直到他能独立做出教辅原题 + 独立做出同构变式题。

核心交付物不是聊天，而是**「掌握」这个判定**：

- 讲什么：教材知识点 + 要点 + 结论 + 例题 + 题型；
- 练什么：每轮 3 题（至少 1 选择 + 1 填空）；
- 判得准不准：choice → text → numeric → SymPy → 中文规则 → LLM 兜底；
- 记不记得住：`student_kp` + 错题本 + 1/3/7 天复习 + 提分曲线；
- 能不能证明：trace + 回归脚本 + pass^k 评测。

当前内容资产：**18 讲 / 71 分支 / 232 知识点 / 376 结论 / 约 1060 条要点 / 300+ 道例题**。

---

## 2. 仓库地图

| 路径 | 内容 |
|---|---|
| `backend/` | FastAPI 后端、LangGraph 图、判题、学生模型、学习闭环、课程表 |
| `backend/v3core/` | 线上主链路：`graph.py`、`nodes.py`、`prompts.py`、`judge.py`、`learning.py`、`db.py` |
| `backend/agents/` | 实验线：`planner`（路线规划）、`teach`（V5 两步法） |
| `app/` `components/` `lib/` | Next.js 前端：讲练聊天、知识树、题卡、学习看板 |
| `scripts/` | 构建、验收、回归、浏览器 smoke、判题并发/幂等测试 |
| `textbook/tree/` | 教材树 JSON（18 讲 × 3 层）+ 题型/提速/易错点 |
| `docs/` | 战略、Agent 标准、项目地图、验收、交接、流式契约 |
| `docs/research/` | 2026 多智能体前沿调研、架构评审、AI 教育工作流报告 |
| `docs/evaluation/` | 2026-11 系统评估报告 + 本轮代码审核/迭代记录 |
| `docs/handbook/` | 61 页新人上手指南（Markdown / DOCX / PDF） |
| `starter_kit/` | 可离线运行的最小参考实现（18 个测试） |
| `reference/teaching_teacher_v2/` | 早期同源快照（93 个测试、判题基准） |

---

## 3. 30 分钟跑通

### 3.1 环境

- Windows 10/11
- Python 3.11（建议 3.11.x）
- Node.js 20+（浏览器 smoke 需要 22+）
- 一个 OpenAI 兼容的 DeepSeek Key（离线测试不需要）

### 3.2 安装

```powershell
git clone https://github.com/AlexWang-AI/adaptive-trainer.git
cd adaptive-trainer/teaching-agent

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

npm install
```

### 3.3 配置

复制 `.env.example` 为 `backend/.env`，填：

```ini
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_CHAT_MODEL=deepseek-v4-flash
```

后端默认读 `backend/.env`。如果你把 `.env` 放在仓库根，设置：

```powershell
$env:DEEPSEEK_ENV_PATH = (Resolve-Path ".\.env").Path
```

### 3.4 启动

```powershell
# 后端
cd backend
python -m uvicorn api_server:app --host 127.0.0.1 --port 8008

# 前端（另开窗口）
cd ..
npm run dev
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8008/api/health_v3 | ConvertTo-Json -Depth 3
```

预期：`status=ok`、`knowledge_points=232`、`curriculum_version=zy30-gaoshu`。

---

## 4. 测试与验收

### 4.1 离线（不需要 Key / 不需要服务）

```powershell
# 本轮新增：判题幂等 + 独立答案键，14 条
python scripts/test_judge_ledger.py

# 画像注入回归，11 条
python scripts/test_learner_note.py

# 早期快照 93 条
python -m pytest reference/teaching_teacher_v2/tests -q

# planner 契约 9 条
python -m pytest backend/agents/planner/test_contract.py -q

# 参考实现 18 条
cd starter_kit
python -m pytest tests -q
python eval_passk.py --k 3
```

### 4.2 需要服务

```powershell
# 端到端：SSE + 3 题 + 判题层
python scripts/check_e2e.py --direct --kp l01-b01-k01 --samples 1

# 后端加固：事务/并发/单例/SSE 清理
$env:MN_API_BASE = "http://127.0.0.1:8008"
python scripts/test_backend_hardening.py

# 中文判题
python scripts/test_cjk_judge.py

# 浏览器
node scripts/browser_smoke.mjs
node scripts/stream_quality.mjs
```

> 部分脚本仍硬编码 `8008`；本轮已把 `test_backend_hardening.py` 改为读 `MN_API_BASE`。

---

## 5. 架构一屏

```
前端 Next.js :3000
  └─ POST /api/teach_stream（SSE）
       └─ api_server.py
            ├─ learner_note（掌握度/错因）
            ├─ curriculum.textbook_block（考纲/要点/结论/例题/题型）
            ├─ v3core.graph（lesson-only）
            │    └─ lesson_node → run_lesson_practice → prompts → LLM
            └─ SSE: meta → content* → quiz_pack → done
  └─ POST /api/judge（逐题判，旁路）
       └─ v3core.judge（choice → text → numeric → sympy → cjk → llm → fallback）
            └─ db.transaction：attempt 账本 + student_kp + mistakes + review_queue
```

关键决策：

1. **单写者**：只有 `lesson` 写教学内容；判题/侧问/诊断都是旁路。
2. **lesson-only**：判题是前端逐题调 `/api/judge`，图里不需要 `interrupt` 等作答。
3. **教材接地**：每个 `kp_id` 从 `curriculum_data.json` 取 `textbook_block`，不让模型自由发挥。
4. **确定性门禁**：schema + `_check_cards` + SymPy；LLM 只做兜底。
5. **显式学生模型**：掌握度/错题/复习在 `students.db`，不进 checkpoint。
6. **幂等**：`attempt` 账本用 `attempt_id` 去重；重复判题不会重复计数。

更完整的设计见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

---

## 6. 文档索引

| 文档 | 适合谁 |
|---|---|
| [`docs/handbook/handbook.md`](docs/handbook/handbook.md) | 新同学：30 分钟跑通、7 天独立交付、代码地图、调试、模板 |
| [`docs/handbook/讲课智能体系统_新人上手指南_2026-11.pdf`](docs/handbook/讲课智能体系统_新人上手指南_2026-11.pdf) | 打印/直接阅读版（61 页） |
| [`docs/AGENT_STANDARD.md`](docs/AGENT_STANDARD.md) | 写新 agent 的人：目录结构、五条硬规矩、四版对比、DoD |
| [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) | 想快速知道「一共有哪些角色/边界」的人 |
| [`docs/战略.md`](docs/战略.md) | 产品目标、掌握判定、六道门禁、角色边界 |
| [`docs/STREAMING_CONTRACT.md`](docs/STREAMING_CONTRACT.md) | 改前端流式体验的人 |
| [`docs/evaluation/multi-agent-2026-and-teaching-eval.md`](docs/evaluation/multi-agent-2026-and-teaching-eval.md) | 2026-11 多智能体前沿 + 系统评估 |
| [`docs/evaluation/iteration_2026-11-10.md`](docs/evaluation/iteration_2026-11-10.md) | 本轮代码审核、修复、测试证据 |
| [`docs/research/multi-agent-2026-research.md`](docs/research/multi-agent-2026-research.md) | 2026 框架/协议/评测的调研底稿 |
| [`starter_kit/README.md`](starter_kit/README.md) | 想先跑一个最小闭环的人 |

---

## 7. 已知限制（诚实清单）

| 限制 | 影响 | 下一步 |
|---|---|---|
| **没有认证** | `student_id` 客户端传，analytics/ledger/mistakes 可按 id 读 | 加 token/JWT + 对象级授权 |
| **独立答案键数据源未接完** | `/api/judge` 已支持 `answer_key`，但题库还没真正提供 | 题库/验证器产出独立答案键 |
| **旧 `backend/api.py` 仍挂载** | 6 个旧端点用 `MemorySaver`，重启丢会话 | 生产关闭旧路由/410 |
| **first-paint 未单独打点** | 只有 `ttft_ms`，没有首段 markdown 渲染时间 | 前端打点 |
| **live v3core 无 pytest** | 回归靠 `scripts/` 脚本 | 迁移到 `backend/tests/` + CI |
| **教材数据版权** | `textbook/tree` 来自教辅抽取，未授权公开再分发 | 保持私有；公开前替换/脱敏 |

本仓库默认按**私有**用途整理；如果要公开，请先处理上表第 1、3、6 条。

---

## 8. 目录约定

- 改代码前先读 [`docs/handbook/handbook.md`](docs/handbook/handbook.md) 第 2–4 章；
- 新功能按 [`docs/AGENT_STANDARD.md`](docs/AGENT_STANDARD.md) 的目录结构；
- 修改 prompt 必须同时改 schema/checks/测试；
- 不要提交 `.env`、`backend/data/*.db`、`runs/*.jsonl`、学生原始作答。

---

## 9. License

未声明开源许可证。代码与教材数据的使用权归项目作者；公开分发前请先确认教材内容的授权范围。
