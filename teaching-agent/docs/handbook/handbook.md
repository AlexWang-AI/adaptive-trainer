# 讲课智能体系统 · 新人上手指南

## 30 分钟跑通 · 7 天独立交付 · 代码级参考

**版本**：v1.0　｜　**代码快照**：2026-11-10 09:00（Asia/Shanghai）　｜　**适用对象**：刚拿到 DSH harness、会基本 Python、但没读过本项目的新同学

**配套代码**：`reports/2026-11-multiagent-teaching-eval/starter_kit/`（18 个离线测试，全部通过）
**配套报告**：`reports/2026-11-multiagent-teaching-eval/report.md`（2026-11 多智能体架构前沿 + 系统评估）
**项目根目录**：`C:\Users\明\Desktop\第一版UI_ex_v2`

---

## 先读这一页

## 你不需要先读完所有代码

这套系统有 1010 行的 `api_server.py`、488 行的 `v3core/graph.py`、232 个知识点、18 讲教材树。**没有人能在第一天读完。** 你只需要先建立一张「请求怎么走」的地图，然后每天改一个点、跑一次验证。

## 你第一天只做五件事

1. 跑 `starter_kit/00_env_check.py`，确认 Python 和依赖；
2. 跑 `starter_kit/demo.py`，看一次完整的「讲义 → 题卡 → 判题 → 掌握度」；
3. 跑 `starter_kit/tests`，看到 `18 passed`；
4. 启动后端，访问 `http://127.0.0.1:8008/api/health_v3`；
5. 打开 `v3core/graph.py`，只看 `lesson_node` 和 `build_graph` 两个函数。

完成这五件事，你就已经比「读了一天文档但没跑过」的人更接近能干活。

## 三条铁律（违反任何一条，代码 review 直接打回）

| # | 铁律 | 含义 | 代码里怎么体现 |
|---|---|---|---|
| 1 | **写者只有一个** | 只有 `lesson` 节点写教学内容；判题、侧问、诊断都是旁路 | `graph.py` 只有 `lesson` + `degrade` 两个节点；`judge` 走 `/api/judge` |
| 2 | **答案键独立** | 题卡里的 `answer` 是模型生成的，可能错；判题必须有独立标准 | 线上还没完全做到；`starter_kit` 用 `content.ANSWER_KEYS` 演示正确做法 |
| 3 | **副作用幂等** | 恢复/重试/重复点击不能重复计数、重复写错题 | `attempt_id` 唯一；`db.transaction` 包住三次写；`api_server` 的 `persisted` 字段 |

## 你怎么用 DSH harness 干活

不要一上来就说「帮我改这个项目」。先给它一个**上下文包**：

```text
你要改的是：<一句话任务>
先读这些文件（按顺序）：
1. 第一版UI_ex_v2/backend/api_server.py（只看路由和你要改的函数）
2. 第一版UI_ex_v2/backend/v3core/graph.py（lesson_node / build_graph）
3. 第一版UI_ex_v2/backend/v3core/schema.py（相关 Pydantic 模型）
4. 第一版UI_ex_v2/scripts/test_<相关>.py（验收脚本）

约束：
- 不要改 contracts.py / curriculum_data.json / api.py 旧栈 / .env
- 不要新增全局依赖；需要新依赖先写进 requirements.txt
- 改完必须跑：<具体命令>
- 输出：改了哪些文件、为什么、测试输出、还有什么风险

验收：
- <可执行的验收标准，不要写「看起来对」>
```

完整的 3 个提示词模板在第 11 章，可以直接复制。

## 五个不要

1. **不要第一天就改 `contracts.py`**：它是跨 agent 接口，改一次全项目返工。
2. **不要用 `MemorySaver` 跑真实会话**：旧 `api.py` 就是反面教材，重启即丢。
3. **不要把整段对话塞进下一个节点**：`history` 只留最近 20 条，且只放必要内容。
4. **不要让 LLM 当第一判官**：能 SymPy/字符串/数值判的，绝不问模型。
5. **不要为了「多 agent」拆图**：2026 年的共识是单写者 + 只读旁路；拆图之前先证明有增量。

---

## 目录

**第 1 章　项目全景：你到底在维护什么**

- 1.1 产品是什么：掌握判定，不是聊天
- 1.2 当前系统真实形态（2026-11-10 快照）
- 1.3 18 讲 / 71 分支 / 232 知识点：内容资产怎么组织
- 1.4 角色地图：哪些已实现，哪些是实验线
- 1.5 七个必须知道的真相
- 1.6 一张图看懂当前架构

**第 2 章　环境准备：从零到能跑**

- 2.1 机器与路径清单
- 2.2 Python：用哪一个、为什么
- 2.3 Node / 前端：Next.js 16 + React 19
- 2.4 API Key：放哪里、怎么不泄露
- 2.5 启动后端与前端
- 2.6 第一次运行 starter_kit
- 2.7 环境验收清单（12 项）
- 2.8 环境类常见错误

**第 3 章　代码地图：每个文件干什么、能不能改**

- 3.1 顶层目录
- 3.2 backend 逐文件
- 3.3 v3core 逐文件
- 3.4 内容资产与生成脚本
- 3.5 teaching_teacher_v2 快照：93 个测试在哪
- 3.6 scripts 下的真实回归脚本
- 3.7 读 / 改 / 禁改三色表
- 3.8 新人先读的 6 个文件

**第 4 章　系统怎么跑：一次请求的完整生命周期**

- 4.1 启动链路与端口
- 4.2 /api/teach_stream：meta → content → quiz_pack → done
- 4.3 流式解析：MarkdownStreamExtractor
- 4.4 /api/judge：五层判题 + 事务落库
- 4.5 旁路：侧问、诊断、再练一组
- 4.6 学习闭环：analytics / review / ledger
- 4.7 数据模型：4 个 SQLite 文件、8 张表
- 4.8 trace：一行 JSONL 怎么读
- 4.9 用命令行跑一次真实会话
- 4.10 用命令行验收一次判题

**第 5 章　架构规则：2026 前沿怎么落到这套代码**

- 5.1 workflow 优先：为什么图里只剩 lesson
- 5.2 单写者与只读旁路
- 5.3 契约：Pydantic 是接口，不是装饰
- 5.4 确定性门禁：checks 与 judge 的分工
- 5.5 上下文工程：教材依据 + 画像 + focus + history
- 5.6 记忆分层：checkpoint / 学生库 / trace
- 5.7 可靠性与事务：db.py 的三条规则
- 5.8 可观测与评测：trace 只是起点
- 5.9 安全：当前缺口与最小修法
- 5.10 什么时候才加 agent：三问门禁

**第 6 章　代码走读：关键文件逐段讲**

- 6.1 schema.py：字段为什么这么定
- 6.2 prompts.py：一次调用怎么同时出讲义和题
- 6.3 nodes.py：流式解析、检查、重试
- 6.4 graph.py：lesson-only 图与 learner_note
- 6.5 judge.py：六层判题与 SymPy
- 6.6 student.py + learning.py：掌握度与复习
- 6.7 db.py：每线程连接 + 显式事务
- 6.8 api_server.py：SSE、判题落库、学习闭环
- 6.9 agents.py：侧问、诊断、再练一组
- 6.10 curriculum.py：232 个知识点怎么进 prompt
- 6.11 starter_kit：把缺失的模式补齐

**第 7 章　工作流：从接任务到合并**

- 7.1 任务卡：没有验收标准不开工
- 7.2 15 分钟定位法
- 7.3 新增一个确定性 checks
- 7.4 新增一个只读接口
- 7.5 新增一个知识点（走数据管线）
- 7.6 新增一个只读 agent
- 7.7 TDD 循环与测试矩阵
- 7.8 Git 分支、提交、PR
- 7.9 与 DSH harness 协作的 3 个模板
- 7.10 Code Review 12 条
- 7.11 定义完成（DoD）

**第 8 章　调试手册：症状 → 原因 → 先查什么**

- 8.1 五步定位法
- 8.2 启动类
- 8.3 LLM 类
- 8.4 SSE / 前端类
- 8.5 LangGraph 类
- 8.6 SQLite / 事务类
- 8.7 判题类
- 8.8 数据 / 知识树类
- 8.9 20 行速查表
- 8.10 事故复盘模板

**第 9 章　评测：怎么证明「教得对」**

- 9.1 六个指标
- 9.2 独立答案键
- 9.3 pass^k
- 9.4 30 条 / 100 条用例怎么造
- 9.5 LLM judge 的正确用法
- 9.6 评测报告模板
- 9.7 上线门槛

**第 10 章　7 天训练计划**

- 10.1 总览
- 10.2 Day 1–Day 7 逐日任务
- 10.3 只有 2 天 / 1 天的压缩版
- 10.4 每天日报模板

**第 11 章　模板库**

- 11.1 任务卡
- 11.2 PR 模板
- 11.3 DSH harness 提示词
- 11.4 评测卡
- 11.5 事故复盘
- 11.6 Code Review checklist

**第 12 章　附录**

- 12.1 命令速查
- 12.2 文件索引
- 12.3 术语表
- 12.4 依赖版本
- 12.5 当前代码与 00:37 报告的差异
- 12.6 参考来源
- 12.7 新人第一周只记这 10 句
# 第 1 章　项目全景：你到底在维护什么

## 1.1 产品是什么：掌握判定，不是聊天

一句话：

> 学生带着目标进来（「两周把极限学扎实」），系统给一条能执行、能量化、能验收的路径，直到他能独立做出教辅原题 + 独立做出同构变式题。

核心交付物不是「讲得好」，是**「掌握」这个判定**。所以这套系统的重心不在聊天框，而在：

- 讲什么（教材知识点 + 例题 + 题型）；
- 练什么（3 道题，至少 1 选择 + 1 填空）；
- 判得准不准（SymPy / 数值 / 文本 / 中文规则）；
- 记不记得住（跨会话掌握度 + 错题 + 复习队列）；
- 能不能证明（trace + 评测 + 学习曲线）。

你以后改任何代码，都先问一句：**这个改动让「掌握判定」更可信，还是只是让界面更热闹？**

## 1.2 当前系统真实形态（2026-11-10 快照）

先纠正三个常见误解：

| 误解 | 实际 |
|---|---|
| 「这是一个多 agent 系统，有 7 个 agent」 | 线上主图只有 **1 个写节点** `lesson`；判题、侧问、诊断都是**旁路函数/接口**，不在图里 |
| 「知识树只有 69 个点」 | 当前 `curriculum_data.json` 是 **18 讲 / 71 分支 / 232 知识点 / 376 结论 / 约 1060 条要点 / 300+ 道例题** |
| 「有 93 个测试保护线上代码」 | 93 个测试在 `teaching_teacher_v2` **快照**里；线上 `backend/v3core` **没有 pytest**，真实验收靠 `scripts/` 下的回归脚本 |

当前主链路：

```
前端 Next.js :3000
  └─ POST /api/teach_stream（SSE）
       └─ api_server.py
            ├─ 解析 kp_id / history / focus
            ├─ learner_note(state)         ← 画像（掌握度/错因）
            ├─ curriculum.textbook_block() ← 教材依据（考纲/要点/结论/例题/题型）
            ├─ v3core.graph（lesson-only）
            │    └─ lesson_node → run_lesson_practice → prompts → LLM
            └─ SSE: meta → content* → quiz_pack → done
  └─ POST /api/judge（逐题判，旁路）
       └─ v3core.judge（choice → text → numeric → sympy → cjk → llm → fallback）
            └─ db.transaction：记作答 + 记错题 + 排复习
```

**为什么图里只剩 lesson？** 因为判题是前端逐题调 `/api/judge`，不需要在图里 `interrupt` 等学生作答。之前图里留着 `wait/judge` 节点，但全项目没有 `Command(resume=)`，每次讲课都会留一个永远不会恢复的 checkpoint（已累积 117 个 thread），所以被删掉了。这是一个很好的工程教训：**不要保留「看起来完整但没人恢复」的节点。**

## 1.3 18 讲 / 71 分支 / 232 知识点：内容资产怎么组织

内容资产在：

```
C:\Users\明\Desktop\第一版UI_ex_v2\textbook\tree\
  lecture_01_weighted.json ... lecture_18_weighted.json   # 教材树：L1 分支 / L2 知识点 / L3 要点 / 结论 / 例题
  lecture_01_extras.json   ... lecture_18_extras.json     # 提速层：124 条秒杀技巧/特殊结论
  lecture_01_types.json    ... lecture_18_types.json      # 题型层：144 个题型（特征/步骤/关联知识点）
  index.json / MISTAKES.md / overview.png / lecture_XX_tree.png
```

运行时**不直接读这些 JSON**，而是读编译产物：

```
backend/curriculum_data.json   # 602 KB，由 scripts/build_curriculum.py 生成
```

`curriculum.py` 把它加载成：

- `CHAPTERS`：18 个 `Chapter`，每个带 `blocks`；
- `KP_TABLE`：232 个知识点，每个带 `name / chapter / block / tier / exam_weight / prerequisites / points / conclusions / examples / types / extras / textbook_ref`；
- `textbook_block(kp_id)`：压成 ≤1200 字的「考纲 + 要点 + 结论 + 例题 + 题型」，直接进讲课 prompt。

**新同学不要手改 `curriculum_data.json`。** 正确流程是：

```
改 textbook/tree/lecture_XX_*.json
  → 跑 scripts/build_curriculum.py
  → 校验 scripts/check_* / audit
  → 重启后端
```

原因：树是流水线产物，重跑会漂移；编译时把 id、顺序、权重一次定死，`student_kp` 里的历史记录才不会错位。

## 1.4 角色地图：哪些已实现，哪些是实验线

| 角色 | 职责 | 当前实现 | 状态 |
|---|---|---|---|
| `lesson`（teach） | 讲一层 + 出 3 题 | `v3core.graph.lesson_node` + `nodes.run_lesson_practice` | ✅ 线上 |
| `judge` | 确定性判题 | `v3core.judge.judge` + `/api/judge` | ✅ 线上（旁路） |
| `sideqa` | 侧边提问，不污染主干 | `v3core.agents.side_answer` + `/api/side_ask` | ✅ 线上（旁路） |
| `diagnose` | 学生自述思路 → 最早出错步 | `v3core.agents.diagnose` + `/api/diagnose` | ✅ 线上（旁路） |
| `practice_more` | 再练一组，按教材题型/例题出题 | `v3core.agents.generate_questions_only` + `/api/practice_more` | ✅ 线上（旁路） |
| `learning` | 掌握度/复习/提分曲线/热点图 | `v3core.learning` + `/api/analytics`、`/api/review/*`、`/api/ledger` | ✅ 线上 |
| `planner` | 把目标拆成单元序列 | `backend/agents/planner/`（V3R，6/6 用例） | 🧪 实验线，**未接线上** |
| `teach V5` | 两步法主讲（先术语表再讲解） | `backend/agents/teach/` | 🧪 实验线，**未接线上** |
| `exam` | 单元综合卷 | 无 | ⬜ 未实现 |
| `arbiter` | 门禁/仲裁/熔断 | 无独立节点；部分 checks 分散在 nodes/judge | ⬜ 未实现 |

**不要被目录名骗了**：`agents/planner` 和 `agents/teach` 是实验线，`api_server.py` 没有 import 它们。新人改线上功能，优先看 `v3core/`。

## 1.5 七个必须知道的真相

1. **图是 lesson-only**：`v3core/graph.py` 的 `build_graph` 只 add 了 `lesson` 和 `degrade`；`judge_node` 是死代码。docstring 还写着「3 节点」，以代码为准。
2. **知识树已接线**：`api_server` 对每个 `kp_id` 调 `build_textbook_block`，并把结果放进 `TeachingRequest.textbook_block`；这是最近一次大的升级。
3. **判题是旁路**：`/api/judge` 独立落库，用 `db.transaction` 把「作答 + 错题 + 复习」包成一个原子单元。
4. **线上没有认证**：所有接口的 `student_id` 都是客户端传的；`/api/analytics`、`/api/ledger`、`/api/mistakes` 都能按 id 读。生产前必须补。
5. **旧栈还挂着**：`api_server.py` 通过 `from api import app` 把旧 v2 的 6 个端点一起挂载；旧栈用 `MemorySaver`，重启丢会话。不要在新功能里调旧端点。
6. **线上 v3core 没有 pytest**：唯一 pytest 是 `agents/planner/test_contract.py`（9 条）。真正的回归在 `scripts/` 下，靠 httpx/Node 打真实服务。
7. **报告是 00:37 的快照**：本手册按 09:00 当前代码写；两处最大差异是「232 知识点已接线」「图从 3 节点变 lesson-only」。第 12.5 节列了完整差异。

## 1.6 一张图看懂当前架构

![图 1　当前讲课系统架构（2026-11-10 快照）](figures/fig_current.png)

读图顺序：

1. 绿色是新栈主链路：前端 → `api_server` → `lesson` → `nodes/prompts` → LLM；
2. 橙色是旁路：`judge`、`side_ask`、`diagnose`、`practice_more`；
3. 蓝色是数据：教材树、学生库、会话/观测；
4. 红色虚线是历史包袱：旧 `api.py`、无认证、线上无 pytest。

**你要改的东西，90% 在这张图的绿色/橙色区域。** 红色区域先别碰，除非任务就是「清理旧栈」。






# 第 2 章　环境准备：从零到能跑

## 2.1 机器与路径清单

先确认你在一台 Windows 机器上，并且下面这些路径存在。**不要凭记忆猜路径**，用 `Test-Path`。

| 名称 | 路径 | 用途 |
|---|---|---|
| 项目根 | `C:\Users\明\Desktop\第一版UI_ex_v2` | 前端 + 后端 + 教材树 |
| 后端 | `...\第一版UI_ex_v2\backend` | FastAPI、v3core、agents |
| 前端 | `...\第一版UI_ex_v2\app` | Next.js 页面 |
| 教材树 | `...\第一版UI_ex_v2\textbook\tree` | 18 讲 × 3 层 JSON |
| 编译课程表 | `...\backend\curriculum_data.json` | 232 个知识点，运行时读它 |
| 已验证 Python | `C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe` | 本项目测试用它跑通 |
| 报告目录 | `C:\Users\明\Desktop\claude deepseek\reports\2026-11-multiagent-teaching-eval` | 报告 + starter_kit |

在 PowerShell 里一次确认：

```powershell
$ROOT = "C:\Users\明\Desktop\第一版UI_ex_v2"
$PY   = "C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe"

Test-Path $ROOT
Test-Path "$ROOT\backend\api_server.py"
Test-Path "$ROOT\backend\curriculum_data.json"
Test-Path "$ROOT\textbook\tree\lecture_01_weighted.json"
Test-Path $PY
& $PY --version
```

预期：前五个都是 `True`，最后输出 `Python 3.11.x`。

## 2.2 Python：用哪一个、为什么

这台机器上至少有两个 Python 候选：

| 候选 | 路径 | 现状 |
|---|---|---|
| `deeptutor_env` | `C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe` | **已验证**：langgraph 1.2.20、pydantic 2.14.2、sympy 1.14.0、fastapi 0.162.0、pytest 9.2.0 |
| `start_all.ps1` 里的 Python311 | `C:\Users\明\AppData\Local\Programs\Python\Python311\python.exe` | 项目脚本默认它，但**不保证**装齐 langgraph/sympy/pytest |

**新人统一用 `deeptutor_env`。** 如果 `start_all.ps1` 启动失败，先检查它用的 Python 是不是缺包，不要先怀疑代码。

检查依赖：

```powershell
$PY = "C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe"
& $PY -c @"
import importlib.metadata as md
for p in ['langgraph','langgraph-checkpoint-sqlite','pydantic','sympy','fastapi','uvicorn','pytest','httpx','openai','json-repair']:
    try: print(f'{p:32s}', md.version(p))
    except Exception: print(f'{p:32s}', 'MISSING')
"@
```

预期（本机实测）：

```
langgraph                        1.2.20
langgraph-checkpoint-sqlite      3.1.3
pydantic                         2.14.2
sympy                            1.14.0
fastapi                          0.162.0
uvicorn                          0.54.0
pytest                           9.2.0
httpx                            0.28.1
openai                           2.54.0
json-repair                      （有就行）
```

如果缺包，**不要**直接 `pip install` 到全局；先问清楚应该装到哪个环境，或者用 `requirements.txt` 在项目虚拟环境里装。这个项目曾经因为「每个人 Python 不一样」踩过坑。

## 2.3 Node / 前端：Next.js 16 + React 19

前端在项目根目录，`package.json` 关键信息：

```json
{
  "scripts": { "dev": "next dev", "build": "next build", "start": "next start" },
  "dependencies": { "next": "16.4.3", "react": "^19", "katex": "^0.19.0" }
}
```

检查：

```powershell
node -v          # 预期 v20+（脚本里的 browser_smoke 需要 Node 22+ 的 WebSocket）
npm -v
cd $ROOT
if (Test-Path node_modules) { "node_modules OK" } else { "需要 npm install" }
```

如果 `node_modules` 不存在：

```powershell
cd $ROOT
npm install
```

> 项目里同时有 `pnpm-lock.yaml` 和 `package-lock.json`。新人不要混用包管理器；跟当前 `node_modules` 的来源保持一致。`start_all.ps1` 用的是 `npm run`。

## 2.4 API Key：放哪里、怎么不泄露

后端配置在 `backend/v3core/config.py`（以及旧 `backend/config.py`），默认读：

```
C:\Users\明\Desktop\claude deepseek\ai_math_institute\.env
```

可用环境变量覆盖：

```powershell
$env:DEEPSEEK_ENV_PATH = "C:\path\to\your\.env"
$env:DEEPSEEK_API_KEY  = "sk-..."          # 不建议写在命令行历史里
$env:DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
$env:DEEPSEEK_MODEL    = "deepseek-v4-flash"
```

`.env` 里至少要有：

```ini
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_CHAT_MODEL=deepseek-v4-flash
```

规则：

1. **不要把 `.env` 提交到 git**；`backend/.gitignore` 应该已经忽略。
2. **不要在截图、日志、文档里出现 key**；`trace` 只记 token，不记 prompt 原文。
3. **不要用 `Write-Host $env:DEEPSEEK_API_KEY` 检查**；用下面的布尔检查：

```powershell
& $PY -c "from v3core.config import load_config; c=load_config(); print('key set:', bool(c.api_key), '| model:', c.model, '| base:', c.base_url)"
```

预期：`key set: True | model: deepseek-v4-flash | base: https://api.deepseek.com/v1`。

如果报「找不到 DEEPSEEK_API_KEY」，先检查 `DEEPSEEK_ENV_PATH`，再检查 `.env` 的编码（必须是 UTF-8，不要带 BOM 以外的怪字符）。

## 2.5 启动后端与前端

### 方式 A：手动启动（推荐新人）

开两个 PowerShell 窗口。

**窗口 1：后端**

```powershell
$PY = "C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe"
cd "C:\Users\明\Desktop\第一版UI_ex_v2\backend"
& $PY -m uvicorn api_server:app --host 127.0.0.1 --port 8008
```

看到：

```
INFO:     Uvicorn running on http://127.0.0.1:8008
INFO:     Application startup complete.
```

**窗口 2：前端**

```powershell
cd "C:\Users\明\Desktop\第一版UI_ex_v2"
npm run dev
```

看到 `Ready in ...` 后打开 `http://localhost:3000`。

### 方式 B：一键脚本

```powershell
cd "C:\Users\明\Desktop\第一版UI_ex_v2"
powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
```

它会：

1. 用 `Python311` 启动后端 :8008；
2. 如果 `.next\BUILD_ID` 存在就 `npm run start`，否则 `npm run dev`；
3. 轮询 `/api/health_v3`，就绪后打开浏览器。

**注意**：脚本里的 Python 是 `C:\Users\明\AppData\Local\Programs\Python\Python311\python.exe`，不一定等于 `deeptutor_env`。如果后端窗口报 `ModuleNotFoundError: langgraph`，就改用手动方式 A。

### 端口冲突

```powershell
Get-NetTCPConnection -LocalPort 8008 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
```

有占用就：

```powershell
Get-NetTCPConnection -LocalPort 8008 | Select-Object OwningProcess
Stop-Process -Id <PID> -Force
```

不要随便杀不认识的进程；先确认 `OwningProcess` 对应的是 uvicorn/node。

### 健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:8008/api/health_v3 | ConvertTo-Json -Depth 4
```

预期字段：

```json
{
  "status": "ok",
  "version": "3.0.0",
  "components": {
    "lesson": "v3core.nodes.run_lesson_practice",
    "judge": "v3core.judge (SymPy)",
    "checkpointer": "SqliteSaver",
    "llm_client": "v3core.clients.get_llm_client（进程内单例）",
    "db": "v3core.db（每线程连接 + 显式事务）"
  },
  "knowledge_points": 232,
  "textbook": "张宇基础30讲（高等数学分册）",
  "curriculum_version": "zy30-gaoshu",
  "streams": { "active": 0, "sessions": [] }
}
```

`streams.active` 正常应为 0；如果你断开页面后它一直大于 0，说明 SSE 清理有 bug（见第 8 章）。

## 2.6 第一次运行 starter_kit

`starter_kit` 是配套的**离线最小实现**，不依赖 API Key。它的作用是让你先看清「契约 → 图 → 判题 → 学生库 → 评测」的骨架，再读线上代码。

```powershell
$KIT = "C:\Users\明\Desktop\claude deepseek\reports\2026-11-multiagent-teaching-eval\starter_kit"
cd $KIT
$PY = "C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe"

& $PY 00_env_check.py
& $PY demo.py
& $PY -m pytest tests -q
& $PY eval_passk.py --k 3
```

预期：

- `00_env_check.py`：全部依赖 `>=` 要求，输出「自检通过」；
- `demo.py`：打印讲义、2 道题、逐题判分、掌握度 `1.0`、trace 摘要；
- `pytest`：`18 passed`；
- `eval_passk.py`：`pass_k_rate: 1.0`、`mean_agreement: 1.0`。

再跑一次「故意写错答案」的演示：

```powershell
& $PY demo.py --mutate
```

你会看到：

```
1. [choice] 设 f(x)=x²，则 f'(2) 等于多少？
   模型答案：A　｜　独立答案键：B
...
判题：True　layer=choice　选项 B vs B
```

这就是「独立答案键」的价值：**模型写错了，判题器不被带偏。**

也可以用 `start.ps1`：

```powershell
.\start.ps1 check
.\start.ps1 demo
.\start.ps1 test
.\start.ps1 eval
.\start.ps1 api      # 启动 :8010 的 starter_kit API
```

## 2.7 环境验收清单（12 项）

把下面每一项都跑一遍，打勾才算「环境就绪」。

| # | 命令 | 预期 |
|---|---|---|
| 1 | `& $PY --version` | Python 3.11.x |
| 2 | `Test-Path $ROOT\backend\api_server.py` | True |
| 3 | `Test-Path $ROOT\backend\curriculum_data.json` | True |
| 4 | `& $PY -c "import langgraph, sympy, fastapi"` | 无报错 |
| 5 | `& $PY -c "from v3core.config import load_config; print(bool(load_config().api_key))"`（在 backend 下） | True |
| 6 | 启动 uvicorn | 8008 监听 |
| 7 | `Invoke-RestMethod http://127.0.0.1:8008/api/health_v3` | `status=ok`、`knowledge_points=232` |
| 8 | `Invoke-RestMethod http://127.0.0.1:8008/api/curriculum` | 18 个 chapters |
| 9 | `Invoke-RestMethod "http://127.0.0.1:8008/api/kp_detail?kp_id=l01-b01-k01"` | 有 `textbook_block` |
| 10 | 前端 `http://localhost:3000` | 页面打开，左侧树可见 |
| 11 | starter_kit `pytest` | 18 passed |
| 12 | starter_kit `eval_passk.py --k 3` | pass_k_rate 1.0 |

## 2.8 环境类常见错误

| 现象 | 最可能原因 | 先查什么 |
|---|---|---|
| `ModuleNotFoundError: langgraph` | 用错 Python | `& $PY -c "import sys; print(sys.executable)"` |
| `找不到 DEEPSEEK_API_KEY` | `.env` 路径不对 / 没配 | `DEEPSEEK_ENV_PATH`、`load_config()` |
| `Address already in use` | 8008/3000 被占 | `Get-NetTCPConnection` |
| 前端 404 / API 502 | 后端没起 / 代理地址错 | 先直接打 8008 |
| `npm run dev` 报 Node 版本 | Node 太旧 | `node -v`，需要 20+ |
| PowerShell 输出中文乱码 | 控制台编码 | `[Console]::OutputEncoding=[Text.Encoding]::UTF8` |
| 页面能开但流式不动 | SSE 被缓冲 / 代理 | 看 Network 里 `text/event-stream` |
| 后端启动很慢 | 加载 602 KB `curriculum_data.json` + 依赖 | 正常 1–3 秒 |

---

# 第 3 章　代码地图：每个文件干什么、能不能改

## 3.1 顶层目录

```
第一版UI_ex_v2/
├── app/                  Next.js 页面（聊天、知识树、学习看板）
├── components/           UI 组件
├── lib/                  前端工具
├── backend/              FastAPI + v3core + agents + data
├── textbook/
│   ├── chunks/           MinerU 解析出的教材原文（33 个 md）
│   └── tree/             18 讲 × 3 层 JSON（知识树/提速/题型）
├── scripts/              构建、验收、回归、浏览器 smoke
├── docs/                 验收报告、交接、流式契约、战略
├── 战略.md               产品战略基线（用户批准，AI 无权改）
└── package.json
```

## 3.2 backend 逐文件

| 文件 | 大小/行数 | 作用 | 新人能不能改 |
|---|---:|---|---|
| `api_server.py` | 41.5 KB / 1010 行 | 新栈 API：讲课 SSE、判题、知识树、侧问、诊断、学习闭环 | ✅ 可改，必须跑 `scripts/check_e2e.py` |
| `api.py` | 18.7 KB / 502 行 | 旧 v2 sidecar，6 个旧端点，`MemorySaver` | ❌ 不要改；只用于兼容 |
| `curriculum.py` | 9.0 KB / 234 行 | 加载 `curriculum_data.json`，提供 `KP_TABLE` / `textbook_block` | ⚠️ 改 API 要 review |
| `curriculum_data.json` | 602 KB | 232 个知识点的编译产物 | ❌ 不手改；跑 `scripts/build_curriculum.py` |
| `contracts.py` | 5.3 KB | 跨 agent 契约（Kp/KpState/StudentProfile/MasteryRule） | ❌ 改 = 全项目返工，必须 review |
| `runner.py` | 7.1 KB | 通用结构化执行器（planner/teach 实验线用） | ⚠️ 改要跑 planner 测试 |
| `llm.py` / `config.py` | 5.8 KB / 1.2 KB | 旧版 LLM 客户端 / 配置 | ⚠️ 新代码用 `v3core.llm` / `v3core.config` |
| `tracing.py` | 2.4 KB | LangSmith 可选接入（planner eval 用） | ✅ 可读，别乱改 |
| `agents/planner/` | 9 文件 | 路线规划 agent（V3R，6/6） | 🧪 实验线，未接线上 |
| `agents/teach/` | 4 文件 | 主讲 V5 两步法 | 🧪 实验线，未接线上 |
| `data/` | SQLite | `students.db` / `mastery.db` / `mistakes.db` / `checkpoints.sqlite` | ❌ 不要手删；备份再动 |
| `eval/` | 脚本 | planner 四版对比、LangSmith trace | ✅ 可读 |
| `runs/trace.jsonl` | JSONL | 线上节点/判题 trace | ✅ 只读，排障用 |

## 3.3 v3core 逐文件

| 文件 | 大小/行数 | 作用 | 关键函数 |
|---|---:|---|---|
| `graph.py` | 17.5 KB / 488 行 | lesson-only 图 + 画像 + 预算 + 降级 | `lesson_node` / `build_graph` / `learner_note` |
| `nodes.py` | 15.2 KB / 380 行 | 讲练合一：流式解析、schema、checks、重试 | `MarkdownStreamExtractor` / `run_lesson_practice` / `_check_cards` |
| `prompts.py` | 17.2 KB | 讲课提示词（紧凑 schema、字段顺序、教材依据） | `build_lesson_practice_system_prompt` |
| `schema.py` | 6.4 KB | `TeachingRequest` / `TeachingTurn` / `QuestionCard` / `LessonPayload` | 字段校验 |
| `judge.py` | 21.5 KB / 534 行 | 六层判题 + SymPy + 中文规则 + LLM 兜底 | `judge` / `sympy_equivalent` |
| `student.py` | 6.5 KB | `student_kp` / `mistakes` 表与 Laplace 掌握度 | `record_attempt` / `get_profile` |
| `learning.py` | 9.6 KB / 245 行 | 衰减掌握度、1/3/7 天复习、提分曲线、认知偏差 | `kp_mastery` / `enqueue_review` |
| `db.py` | 6.0 KB / 171 行 | 每线程连接代理 + `BEGIN IMMEDIATE` 事务 | `connection` / `transaction` |
| `clients.py` | 0.9 KB | 进程内 LLM 客户端单例 | `get_llm_client` |
| `agents.py` | 13.6 KB / 312 行 | 侧问、诊断、只出题 | `side_answer` / `diagnose` / `generate_questions_only` |
| `trace.py` | 3.1 KB | JSONL trace + aggregate | `Tracer` / `aggregate` |
| `scoring.py` | 5.3 KB | 6 维教学 rubric（确定性） | `score_teaching` |
| `checks.py` | 3.7 KB | 讲义内容检查（术语/长度/目录化） | `check_turn` |
| `config.py` / `llm.py` | — | 配置 / 流式 LLM 客户端 | `load_config` / `stream_json` |

## 3.4 内容资产与生成脚本

| 路径 | 内容 | 什么时候用 |
|---|---|---|
| `textbook/tree/lecture_XX_weighted.json` | 教材树：分支/知识点/要点/结论/例题 | 内容修改的源头 |
| `textbook/tree/lecture_XX_extras.json` | 124 条提速技巧 | 讲「秒杀」时用 |
| `textbook/tree/lecture_XX_types.json` | 144 个题型 | 出题接地、`type_name` 校验 |
| `textbook/tree/MISTAKES.md` | 175 条易错点 | 出题/诊断素材 |
| `scripts/build_curriculum.py` | 树 → `curriculum_data.json` | 改完树后必须跑 |
| `scripts/check_checklist.py` | 88 条必会清单 | 内容验收 |
| `scripts/check_headings.py` | 272 个章节标题 | OCR 覆盖检查 |
| `scripts/check_syllabus_syn.py` | 145 条考点 | 考纲覆盖检查 |
| `scripts/coverage_check.py` | 例题覆盖率 | 内容验收 |

**一条硬规则**：`curriculum_data.json` 是编译产物，不要手改。改树、跑编译、重启后端；否则下一次编译会把你的手改冲掉。

## 3.5 teaching_teacher_v2 快照：93 个测试在哪

`C:\Users\明\Desktop\claude deepseek\teaching_teacher_v2` 是 2026-11-09 的同源快照，包含：

```
core/        graph/nodes/judge/student/scoring/trace/prompts/schema/llm
tests/       7 个测试文件，93 条
runs/        eval_v3.json / trace.jsonl
report/      judge_benchmark.json / dashboard_v3.html
```

它的价值：

- 93 条测试是**很好的写法参考**（判题、评分、学生模型、图流程）；
- `judge_benchmark.json` 是判题分层收益的证据（24 例，v1 50% → v3 100%）；
- `eval_v3.py` 是端到端评测脚本的样板。

它的局限：

- 它是快照，**不是线上代码**；线上 `v3core/graph.py` 已经变成 lesson-only，快照里还是 3 节点；
- 快照的 `judge.py` 与线上版本有差异；
- 93 条测试没有覆盖 `learning.py`、`db.py`、`api_server.py` 的新逻辑。

新人的正确态度：**把快照当参考实现，把线上当唯一事实。**

## 3.6 scripts 下的真实回归脚本

线上没有 pytest，但有一批「打真实服务」的脚本。它们才是当前系统的验收网。

| 脚本 | 检查什么 | 前置 | 命令 |
|---|---|---|---|
| `scripts/test_backend_hardening.py` | 事务原子性、8 线程并发、LLM 单例、SSE 断连清理 | 后端 :8008 | `python scripts/test_backend_hardening.py` |
| `scripts/test_learner_note.py` | 画像是否真的进 prompt（11 项） | 无（离线） | `python scripts/test_learner_note.py` |
| `scripts/test_cjk_judge.py` | 中文答案判题（发散/收敛） | 后端 :8008 | `python scripts/test_cjk_judge.py` |
| `scripts/test_quiz_grounding.py` | 出题是否落在教材题型 | 后端 + LLM | `python scripts/test_quiz_grounding.py` |
| `scripts/check_e2e.py` | 端到端 SSE + 3 题 + 判题层 | 后端 + 前端 | `python scripts/check_e2e.py` |
| `scripts/verify_deepening.py` | 追问是否讲深一层 | 后端 + LLM | `python scripts/verify_deepening.py` |
| `scripts/browser_smoke.mjs` | 真浏览器点知识点→流式→闯关→打勾 | 前端 + Edge | `node scripts/browser_smoke.mjs` |
| `scripts/stream_quality.mjs` | 滚动/节流/长任务/回到底部 | 前端 + Edge | `node scripts/stream_quality.mjs` |
| `scripts/build_css.mjs` | Tailwind CSS 预编译 | 前端 | `node scripts/build_css.mjs` |

> 本手册编写时实际跑过：`test_learner_note.py` **11/11 通过**；`starter_kit` **18 passed**；`teaching_teacher_v2` **93 passed**。其余脚本需要真实服务/API，未在本轮全部重跑。

## 3.7 读 / 改 / 禁改三色表

| 颜色 | 文件 | 规则 |
|---|---|---|
| 🟢 可改 | `v3core/nodes.py` 的 checks、`prompts.py`、`scoring.py`、`agents.py`、`trace.py` | 改完跑对应测试/脚本 |
| 🟡 小心改 | `graph.py`、`schema.py`、`student.py`、`learning.py`、`api_server.py` | 改接口要同步前端/测试；必须 review |
| 🔴 禁改 | `contracts.py`、`curriculum_data.json`、`api.py` 旧栈、`.env`、`data/*.db` | 需要负责人批准；改数据先备份 |

## 3.8 新人先读的 6 个文件

按这个顺序读，每个文件只回答一个问题：

1. `v3core/schema.py`：**数据长什么样？**（TeachingRequest / QuestionCard / LessonPayload）
2. `v3core/prompts.py`：**模型被要求输出什么？**（只看 `build_lesson_practice_system_prompt`）
3. `v3core/nodes.py`：**一次生成怎么校验、怎么重试？**（`run_lesson_practice` + `_check_cards`）
4. `v3core/graph.py`：**图怎么跑？**（`lesson_node` + `build_graph`）
5. `v3core/judge.py`：**判题分几层？**（`judge` 函数从头读到尾）
6. `api_server.py`：**前端怎么进来？**（`teach_stream` + `judge` 两个路由）

读完后，你应该能画出这张图：

```
schema → prompt → LLM → JSON → schema 校验 → checks → 重试
                                      ↓
                                   lesson_node
                                      ↓
                               SSE content/quiz_pack
                                      ↓
                             前端逐题 /api/judge
                                      ↓
                         student_kp / mistakes / review_queue
```

画不出来就回去重读，不要急着改代码。

---

# 第 4 章　系统怎么跑：一次请求的完整生命周期

## 4.1 启动链路与端口

| 服务 | 端口 | 启动 | 健康检查 |
|---|---:|---|---|
| 后端 | 8008 | `uvicorn api_server:app` | `/api/health_v3` |
| 前端 | 3000 | `npm run dev` / `npm run start` | `http://localhost:3000` |
| starter_kit API | 8010 | `uvicorn api:app` | `/health` |

前端请求走后端；SSE 必须直连或经过不缓冲的代理。生产模式（`npm run start`）的 SSE 比 dev 模式稳，`start_all.ps1` 里有注释：dev 模式偶尔会把流缓冲到 4 秒以上。

## 4.2 `/api/teach_stream`：meta → content → quiz_pack → done

请求体（`TeachStreamBody`）：

```json
{
  "session_id": null,
  "student_id": "local-user",
  "kp_id": "l01-b01-k01",
  "topic": null,
  "level": "大学低年级",
  "subject": "数学一",
  "prior_knowledge": "",
  "misconceptions": "",
  "focus": "",
  "student_message": "我还是不懂为什么分母不能为 0",
  "history": [{"role": "student", "content": "..."}],
  "max_rounds": 3
}
```

服务端做六件事（按代码顺序）：

1. `sid = body.session_id or new_session_id()`；
2. `_resolve_topic`：用 `kp_id` 从 `KP_TABLE` 取中文名、考频、默认先修/误解；
3. `register_stream_sink(sid, sink_q.push_md)`：把流式增量接到 `_StreamBuffer`；
4. `initial_state(...)`：把 topic/level/kp/history 装进图状态；
5. `state["learner_note"] = learner_note(state)`：画像；
6. `state["textbook_block"] = build_textbook_block(kp_id)`：教材依据。

然后起一个线程跑图，主协程用 SSE 推事件。

**SSE 事件顺序**：

| 事件 | 字段 | 前端动作 |
|---|---|---|
| `meta` | `session_id` / `kp_id` / `kp_name` / `topic` / `learner_note` / `textbook_ref` / `textbook_chars` | 建会话、显示知识点名、可展开画像 |
| `content` | `text`（增量） | 追加到讲义气泡；支持 `reset` 清空重放 |
| `quiz_pack` | `quiz_pack`（3 张卡）/ `score` / `ttft_ms` | 渲染题卡 |
| `done` | `status` / `round` / `ttft_ms` / `elapsed_ms` / `tokens` | 结束 loading |
| `error` | `message` | 显示错误，不要静默 |

**关键实现点**：

- `_StreamBuffer` 只保留最新一份累计 markdown，避免慢客户端把上千份全文堆在内存；
- `gen()` 用 `try/finally` 保证 `unregister_stream_sink(sid)` 一定执行；
- 空闲 8 秒发 `: keep-alive\n\n`，避免代理断流；
- 每 0.5 秒检查 `request.is_disconnected()`，客户端断开就提前 return；
- 校验失败重生成时，内容会从头开始，所以推 `reset` 让前端清空。

## 4.3 流式解析：`MarkdownStreamExtractor`

模型输出的是 JSON：

```json
{"teaching":{"reply_markdown":"...","core_idea":"...",...},"questions":[...]}
```

如果等整个 JSON 生成完再渲染，首屏要 7–9 秒。`MarkdownStreamExtractor` 做一件事：**从流式 JSON 里增量抠出 `reply_markdown` 的值**。

它不解析完整 JSON，只做：

1. 找到 `"reply_markdown"` 键；
2. 找到冒号和起始引号；
3. 逐字符解码转义（`\n`、`\"`、`\uXXXX`）；
4. 遇到未完成的转义序列就停下，等下一块；
5. 遇到收尾引号就封口，后续 chunk 不再吞。

这就是「首屏看 TTFT，不看整轮耗时」的实现基础。

## 4.4 `/api/judge`：五层判题 + 事务落库

请求：

```json
{
  "question": {
    "kind": "fill",
    "stem": "lim(x→0) (e^x-1)/x = ?",
    "options": [],
    "answer": "1",
    "explanation": "洛必达或等价无穷小",
    "tested_points": ["l01-b03-k02"],
    "difficulty": "medium"
  },
  "answer": "1",
  "allow_llm": false,
  "student_id": "local-user",
  "kp_id": "l01-b03-k02"
}
```

判题顺序（`v3core/judge.py`）：

| 层 | 判什么 | 例子 | 是否调 LLM |
|---|---|---|---|
| L1 `choice` | 选项字母 / 选项全文 | `B`、`选B`、`4` → B | 否 |
| L2 `text` | 归一化文本完全一致 | `x^2+C` vs `x^2+c` | 否 |
| L3 `numeric` | 数值等价 | `1/2` vs `0.5` vs `50%` | 否 |
| L4 `sympy` | 符号等价 / 方程解 | `2x` vs `2*x`、`x=3` vs `3` | 否（有 3 秒超时） |
| L4.5 `cjk` | 中文答案规则 | `发散` vs `发散（调和级数）` | 否 |
| L5 `llm` | 语义兜底 | 开放题 / 规则覆盖不到 | 是（可选） |
| fallback | 都不命中 | 判错，提示人工复核 | 否 |

**落库**（`/api/judge` 里）：

```python
with db.transaction(_STUDENT_CONN):
    record_attempt(...)       # 作答
    if correct: resolve_mistake(...)
    else: record_mistake(...) # 错题
    learn.enqueue_review(...) # 复习队列
```

这三件事必须在一个事务里，否则会出现「答了题但没进错题本」的半写状态。`persisted` / `persist_error` 字段会告诉前端有没有落库成功。

## 4.5 旁路：侧问、诊断、再练一组

| 接口 | 输入 | 输出 | 上下文边界 |
|---|---|---|---|
| `/api/side_ask` | `ask` + 当前题 + 讲义片段 + 最近 6 条侧问 | `answer` + `misconception` | 不带主对话全文 |
| `/api/diagnose` | 题目 + 学生答案 + 学生自述思路 | `steps` / `first_break` / `misconception` / `fix` / `severity` | 只看这道题 + 这段思路 |
| `/api/practice_more` | `kp_id` + `student_id` | 3 张新题卡 + `types_used` / `examples_used` | 用教材题型/例题/结论 + 最近错因 |

这三条都是「只读旁路」：不写主图状态，只写自己的表（诊断写 `mistakes.db` + 认知偏差；再练一组只返回题卡，不写库）。

## 4.6 学习闭环：analytics / review / ledger

| 接口 | 作用 | 关键逻辑 |
|---|---|---|
| `GET /api/analytics?student_id=` | 总掌握度、章节雷达、热点图、提分曲线、到期复习 | `learning.kp_mastery`（Laplace × 遗忘衰减）+ `chapter_rollup` |
| `GET /api/review/due` | 今天到期的复习 | `review_queue.due_at <= now` |
| `POST /api/review/answer` | 复习答对/答错 | 1/3/7 天三档；连续答对 2 次升档；7 天档满 2 次毕业 |
| `GET /api/ledger?kp_id=` | 一个知识点的「账本」 | 作答次数、掌握度、最近错因、下次复习 |
| `POST /api/mastery` | 标记通关 | **要求 attempts ≥ 3**，分数由服务端推导，不采信客户端 `score` |

`learning.kp_mastery` 的口径：

```
accuracy = (correct + 1) / (attempts + 2)      # Laplace
recency  = 0.5 ** (days_since / 14)            # 14 天半衰期
score    = accuracy × (0.7 + 0.3 × recency)
```

为什么不是「答对率」？因为：
- 0 次作答不能显示 100%（Laplace 平滑）；
- 两周前练过、现在可能忘了（遗忘衰减）；
- 学生点开分数能看到算式（可解释）。

## 4.7 数据模型：4 个 SQLite 文件、8 张表

| 文件 | 表 | 作用 | 主键/索引 |
|---|---|---|---|
| `data/checkpoints.sqlite` | LangGraph checkpoint | lesson 状态、恢复 | `thread_id` |
| `data/students.db` | `student_kp` | 每知识点 attempts/correct/last_seen | `(student_id, subject, kp)` |
| | `mistakes` | 题卡答错 | `id` |
| | `review_queue` | 1/3/7 天复习 | `(student_id, kp_id)` |
| | `mastery_history` | 提分曲线快照 | `id` |
| | `misconception_log` | 最近一次认知偏差 | `(student_id, kp_id)` |
| `data/mastery.db` | `kp_mastery` | 通关标记 | `(student_id, kp_id)` |
| `data/mistakes.db` | `mistakes` | 思路诊断记录 | `id` |

**注意**：`students.db` 里的 `mistakes` 与 `mistakes.db` 里的 `mistakes` 是两张不同的表：
- `students.db.mistakes`：题卡答错，只有题目/答案/作答；
- `mistakes.db.mistakes`：学生点「说说我的思路」后的诊断，带 `steps/first_break/fix`。
`/api/mistakes` 会把两个来源合并返回，`source` 字段区分 `quiz` / `diagnosed`。

## 4.8 trace：一行 JSONL 怎么读

`backend/runs/trace.jsonl` 每行一个事件。典型两行：

```json
{"trace_id":"a1b2c3","kind":"node","ts":1794273000.1,"session_id":"...","node":"lesson","attempt":0,"attempts":1,"ok":true,"issues":[],"total_tokens":1815,"latency_ms":7700,"ttft_ms":1010,"questions":3,"learner_note_chars":105,"textbook_chars":980,"types_tagged":2}
{"trace_id":"a1b2c3","kind":"judge","ts":1794273010.2,"session_id":"...","layer":"sympy","correct":true,"kp":"l01-b03-k02"}
```

读法：

- `attempts > 1`：这一轮重试过，查 `issues` / `hard`；
- `learner_note_chars = 0`：画像没进 prompt（P1-4 回归点）；
- `textbook_chars = 0`：教材依据没接上；
- `types_tagged < questions`：题卡题型标签没打全；
- `ttft_ms` 与 `latency_ms` 差距大：首屏快、整轮慢，正常；
- `judge.layer` 分布：`fallback` 比例高说明规则覆盖不足。

聚合：

```powershell
& $PY -c "from v3core.trace import Tracer, aggregate; import json; print(json.dumps(aggregate(Tracer(r'C:\Users\明\Desktop\第一版UI_ex_v2\backend\runs\trace.jsonl').read()), ensure_ascii=False, indent=2))"
```

## 4.9 用命令行跑一次真实会话

> 会消耗真实 token（约 2k–5k/轮）。先用最便宜的一个知识点试。

PowerShell 直接打后端（注意：PowerShell 5.1 可能把 UTF-8 中文显示成乱码，用 `Invoke-WebRequest` + `[Text.Encoding]::UTF8.GetString` 更稳）：

```powershell
$body = @{ kp_id = "l01-b01-k01"; student_id = "smoke-1" } | ConvertTo-Json
$resp = Invoke-WebRequest -Method Post -Uri "http://127.0.0.1:8008/api/teach_stream" `
  -ContentType "application/json" -Body $body
[Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray())
```

更推荐用项目自带脚本（它会解析 SSE、统计 TTFT、校验 3 题、判题）：

```powershell
cd "C:\Users\明\Desktop\第一版UI_ex_v2"
& $PY scripts\check_e2e.py --direct --kp l01-b01-k01 --samples 1
```

预期输出包含：

- 首字 TTFT 中位数 < 2000 ms；
- 正文 ≥ 200 字；
- 3 道题、至少 1 道选择；
- 标准答案判对、错误答案判错；
- 判题层落在 choice/numeric/sympy/text。

## 4.10 用命令行验收一次判题

```powershell
$body = @{
  question = @{
    kind = "fill"; stem = "lim(x→0) (e^x-1)/x = ?"; options = @();
    answer = "1"; explanation = "洛必达"; tested_points = @("l01-b03-k02"); difficulty = "medium"
  }
  answer = "1"; student_id = "smoke-1"; kp_id = "l01-b03-k02"
} | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8008/api/judge" `
  -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 5
```

预期：

```json
{
  "correct": true,
  "layer": "text",
  "reason": "归一化后完全一致",
  "correct_answer": "1",
  "persisted": true,
  "persist_error": ""
}
```

如果 `persisted=false`，看 `persist_error` 与后端日志；不要忽略。


# 第 5 章　架构规则：2026 前沿怎么落到这套代码

这一章不讲抽象概念，只讲「这条规则在这套代码里对应哪一行、违反会长什么样」。

## 5.1 workflow 优先：为什么图里只剩 lesson

2026 年的共识是：**流程确定时，用确定性 workflow；只有开放式任务才用自主 agent。** 讲课的流程是确定的：

```
讲一层 → 出 3 题 → 学生逐题作答 → 判题 → 记录 → 下一轮/结束
```

所以正确形态是「图 + 节点」，不是「一群 agent 自由协商」。

这套系统进一步把图简化成 **lesson-only**：

```python
# v3core/graph.py（当前）
def build_graph(checkpointer=None):
    graph = StateGraph(TutorState)
    graph.add_node("lesson", lesson_node)
    graph.add_node("degrade", degrade_node)
    graph.add_edge(START, "lesson")
    graph.add_conditional_edges("lesson", route_after_lesson, {"degrade": "degrade", "fail": END})
    graph.add_edge("degrade", END)
    return graph.compile(checkpointer=checkpointer or default_checkpointer())
```

为什么删掉 `wait/judge`？

1. 判题是前端逐题调 `/api/judge`，不需要在图里暂停等学生；
2. 全项目没有 `Command(resume=)`，`wait` 节点会留下永远不会恢复的 checkpoint（已累积 117 个 thread）；
3. `judge_node` 成了死代码，留在图里只会增加阅读负担。

**教训**：图里每个节点都必须有真实的进入/退出路径；「为了架构完整」保留一个没人调用的节点，是负资产。

## 5.2 单写者与只读旁路

| 角色 | 写什么 | 不写什么 |
|---|---|---|
| `lesson` | `TeachingTurn` + `QuestionCard[]` + history | 不写学生掌握度、不写错题本 |
| `/api/judge` | `student_kp` / `mistakes` / `review_queue` | 不写讲义、不改主图状态 |
| `/api/side_ask` | 只返回答案，不写主会话 | 不写 history、不改进度 |
| `/api/diagnose` | `mistakes.db` + `misconception_log` | 不写讲义、不改掌握度 |
| `/api/practice_more` | 只返回新题卡 | 不写库 |
| `learning` | 只做聚合/调度，不调 LLM | 不生成教学内容 |

代码里的保证：

- `lesson_node` 是唯一返回 `teaching` / `questions` 的节点；
- 判题在 `/api/judge` 里，不在图里；
- 侧问/诊断是普通函数，接收 `client`，不接收 graph state。

**如果你要加一个新能力，先问：它是写还是读？** 写就进主图（而且尽量只有一个写者）；读就做旁路函数/接口。

## 5.3 契约：Pydantic 是接口，不是装饰

`schema.py` 里每个字段都有长度/枚举约束，不是为了好看，是为了让 LLM 输出可校验、让下游可消费。

```python
class QuestionCard(BaseModel):
    kind: Literal["choice", "fill"]
    stem: str = Field(..., min_length=8, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=4)
    answer: str = Field(..., min_length=1, max_length=80)
    explanation: str = Field(..., min_length=10, max_length=300)
    tested_points: list[str] = Field(..., min_length=1, max_length=3)
    difficulty: Difficulty
    why_this_question: str = Field(..., min_length=10, max_length=220)
    source_quote: str = Field("", max_length=220)
    type_name: str = Field("", max_length=40)
```

三个必须遵守的契约规则：

1. **跨文件传递的数据必须有模型**；不要传自由文本 dict。
2. **字段名不要「约定俗成」**；改字段 = 改接口，必须 review。
3. **校验失败要能修复**；`run_lesson_practice` 会把失败原因回灌给模型重试。

## 5.4 确定性门禁：checks 与 judge 的分工

| 门禁 | 在哪 | 判什么 | 失败怎么办 |
|---|---|---|---|
| schema 校验 | `LessonPayload.model_validate` | 字段/长度/选项数量 | 重试（最多 2 次） |
| 题卡检查 | `nodes._check_cards` | 有没有选择/填空、难度递进、`source_quote` 是否在讲义/教材 | 重试 |
| 题型兜底 | `nodes._auto_tag_types` | `type_name` 是否在教材题型里 | 确定性匹配，不重试 |
| 判题 | `judge.judge` | 数学等价 | 分层返回，不重试 |
| 事务 | `db.transaction` | 三次写是否原子 | 回滚 + `persisted=false` |

**原则**：能代码判的，绝不问模型。`source_quote` 只证明「有依据」，不证明「数学正确」；数学正确要靠 SymPy/独立答案键（见第 9 章）。

## 5.5 上下文工程：教材依据 + 画像 + focus + history

当前 `TeachingRequest` 里有五个上下文块：

| 字段 | 来源 | 作用 | 上限 |
|---|---|---|---|
| `textbook_block` | `curriculum.textbook_block(kp_id)` | 考纲/要点/结论/例题/题型，让讲课以教材为准 | 1400 字 |
| `learner_note` | `graph.learner_note(state)` | 历史薄弱点 + 本轮作答 + 最近认知偏差 | 400 字 |
| `focus` | 前端传入 | 只讲知识点内部某一条（如「0/0 型」） | 200 字 |
| `history` | 前端/图状态 | 最近 20 条对话 | 每条 3000 字 |
| `student_message` | 前端传入 | 本轮学生的话 | 1000 字 |

**为什么不是把整棵树塞进去？** 232 个知识点全量是几百 KB，模型会 context rot。正确做法是「最小充分上下文」：一个知识点的教材依据 + 一句画像 + 最近几轮。

**当前的一个隐患**：`history` 每条最多 3000 字，20 条就是 6 万字；如果前端把整段讲义反复塞进 history，token 会爆。新人改前端时，history 只传「学生说的话 + 老师的关键反馈」，不要传整篇讲义。

## 5.6 记忆分层：checkpoint / 学生库 / trace

| 层 | 存什么 | 存哪 | 生命周期 |
|---|---|---|---|
| 图状态 | 本轮 topic/questions/answers/tokens | `checkpoints.sqlite` | 一次会话 |
| 学生模型 | 掌握度/错题/复习/认知偏差 | `students.db` | 跨会话 |
| 通关标记 | 哪些 kp 已通关 | `mastery.db` | 跨会话 |
| 诊断记录 | 思路断点/纠正动作 | `mistakes.db` | 跨会话 |
| 观测 | 节点耗时/token/判题层 | `runs/trace.jsonl` | 可长期 |

**不要把掌握度放进 graph state**：state 是 thread 级的，换会话就丢。`learner_note` 每次从 `students.db` 重新算，就是为了避免这个坑。

## 5.7 可靠性与事务：db.py 的三条规则

`v3core/db.py` 解决的是真实踩过的坑：

1. **每线程一条真实连接**：`sqlite3` 连接不是线程安全的，`check_same_thread=False` 只是关掉检查，不会让它变安全。
2. **同文件共享一个连接代理**：同进程里对同一文件的写事务串行，避免两个连接互抢。
3. **显式事务**：`with db.transaction(conn):` 用 `BEGIN IMMEDIATE`，内层 `commit()` 变成 no-op，最外层统一提交/回滚。

```python
with db.transaction(_STUDENT_CONN):
    record_attempt(...)
    if correct: resolve_mistake(...)
    else: record_mistake(...)
    learn.enqueue_review(...)
```

没有这个事务，进程在「记作答」和「记错题」之间挂掉，就会留下半写状态。新人改判题落库时，**不要自己在事务里再 `commit()`**。

## 5.8 可观测与评测：trace 只是起点

当前 trace 记录：

- 节点：`attempts` / `tokens` / `latency_ms` / `ttft_ms` / `issues` / `questions` / `learner_note_chars` / `textbook_chars` / `types_tagged`；
- 判题：`layer` / `correct` / `kp`；
- 降级：`degrade`。

它能回答「这一步慢不慢、重试没重试、画像/教材接没接上」，但不能回答：

- 这一版比上一版讲得好吗？
- 判题在真实学生答案上准吗？
- 学生学完了真的会了吗？

后三个要靠第 9 章的评测。新人不要看到 trace 全绿就以为「系统没问题」。

## 5.9 安全：当前缺口与最小修法

当前明确缺口（按严重度）：

| # | 缺口 | 代码证据 | 最小修法 |
|---|---|---|---|
| 1 | 无认证，`student_id` 客户端传 | `api_server.py` 所有 `student_id` 参数 | 加 `Depends(current_student)`，从 token 取 id |
| 2 | 对象级越权 | `/api/analytics`、`/api/ledger`、`/api/mistakes` 可按任意 id 读 | 校验 `student_id == token.student_id` |
| 3 | 学生输入直入 prompt | `history` / `student_message` 直接进 `TeachingRequest` | 长度限制 + 注入检测 + 明确「学生输入只是数据」 |
| 4 | 旧栈仍挂载 | `api_server.py: from api import app` | 生产关闭旧路由，或加 410 |
| 5 | 原始作答/思路长期留存 | `mistakes` / `diagnose` 存原文 | 保留期限 + 删除接口 + 脱敏 |
| 6 | 无审计 | 掌握度/通关/复习写入无操作者 | 加 `audit_log`（谁、何时、改了什么） |

一个最小认证依赖（starter_kit 里有完整版）：

```python
from fastapi import Depends, Header, HTTPException

TOKENS = {"demo-token": "student-1"}

def current_student(x_student_token: str | None = Header(default=None, alias="X-Student-Token")) -> str:
    if not x_student_token or x_student_token not in TOKENS:
        raise HTTPException(status_code=401, detail="缺少或无效的 token")
    return TOKENS[x_student_token]
```

注意：这只是一个教学示例，不是生产认证；生产要 JWT/OIDC + RBAC + 短期 token。

## 5.10 什么时候才加 agent：三问门禁

每增加一个 agent/节点，必须回答：

1. **它解决的是能力缺口，还是组织分工？** 只是「想让代码看起来多 agent」→ 不做。
2. **它的上下文是否必须与主写者不同？** 必须共享全部上下文 → 它应该是一个函数/工具，不是 agent。
3. **有没有可度量的增量？** 在 20 条固定用例上，加它前后 task success / error rate / cost 的变化是多少？没有增量就回滚。

当前真正值得加的只读 agent：

- **验证 agent**：独立解一遍题，抓模型写错的答案键；
- **诊断 agent**：根据学生作答 + 自述，定位先修缺口；
- **错因 agent**：把 `diagnose` 的结果归一成 `concept/method/careless`，喂回出题。

它们都只读、都不写主图，符合 2026 年的「读并行、写串行」。

---

# 第 6 章　代码走读：关键文件逐段讲

## 6.1 `schema.py`：字段为什么这么定

先看 `TeachingRequest` 的五个关键字段：

```python
textbook_block: str = Field("", max_length=1400)
textbook_ref: str = Field("", max_length=200)
type_names: list[str] = Field(default_factory=list, max_length=6)
focus: str = Field("", max_length=200)
learner_note: str = Field("", max_length=400)
```

- `textbook_block` 上限 1400：再长会挤占模型输出空间，且 context rot；
- `learner_note` 上限 400：画像只给结论，不给历史；
- `focus` 上限 200：只讲一个子项，防止一轮塞太多；
- `type_names` 最多 6：教材题型名，用来校验题卡。

`QuestionCard` 的校验：

```python
if self.kind == "choice":
    if len(self.options) != 4: raise ValueError("选择题必须正好 4 个选项")
    if len(set(self.options)) != 4: raise ValueError("选择题选项不能重复")
    if self.answer.strip().upper() not in {"A","B","C","D"}: ...
else:
    if self.options: raise ValueError("填空题 options 必须为空数组")
```

这些校验会在 `LessonPayload.model_validate` 时触发；失败就重试。**不要为了「让模型通过」把约束放宽**，放宽的代价是下游拿到脏数据。

## 6.2 `prompts.py`：一次调用怎么同时出讲义和题

当前 prompt 的核心约束：

1. 讲义 350–600 字，只讲一层，不排目录；
2. 3 道题只考这一层，至少 1 选择 + 1 填空，难度 easy/medium/hard；
3. `source_quote` 必须能在讲义或教材依据里找到；
4. 输出一个 JSON，字段顺序固定：`teaching.reply_markdown` 最先；
5. 知识点内部子项（`focus`）只讲那一条；
6. 教材依据（`textbook_block`）作为「讲什么」的边界。

为什么字段顺序要固定？因为 `MarkdownStreamExtractor` 要从流里找 `reply_markdown`；如果它出现在 JSON 最后，首屏就退化成整轮耗时。

**改 prompt 的正确顺序**：

1. 先改 `schema.py`（如果要新字段）；
2. 再改 `prompts.py`（要求模型输出新字段）；
3. 再改 `nodes.py` 的 checks（校验新字段）；
4. 再跑 `pytest` + `check_e2e.py`；
5. 最后看 trace 里的 `issues` / `attempts`。

不要只改 prompt 就跑，模型输出会漂移。

## 6.3 `nodes.py`：流式解析、检查、重试

三个关键函数：

### `MarkdownStreamExtractor`

```python
KEY = '"reply_markdown"'

def feed(self, delta: str) -> str:
    self.buf += delta
    # 找 key → 找冒号 → 找起始引号 → 逐字符解码转义
    ...
```

它只做「增量抠字符串」，不解析完整 JSON。这是首屏 1–2 秒的关键。

### `run_lesson_practice`

```python
for attempt in range(1, max_repairs + 2):
    raw, usage, latency_ms, ttft_ms = client.stream_json(messages, on_delta=_on_delta)
    payload = LessonPayload.model_validate(extract_json(raw))
    soft_issues = check_turn(payload.teaching, req)
    hard_issues = _check_cards(payload, req.textbook_block)
    if not hard_issues:
        return LessonResult(...)
    messages += [assistant raw, user repair_prompt(hard_issues)]
```

重试策略：

- schema 不合法 / 题卡结构不成立 → 重试；
- 术语/篇幅这类软问题 → **不重试**，只扣分；
- 401/402/403/429 → 立即失败，不重试。

为什么软问题不重试？一次重试 = 一次完整生成（约 2 倍成本），还容易在额度边界上把整轮拖死。这是踩过坑的结论。

### `_check_cards`

检查：

- 3 题里有没有选择题、填空题；
- 前两道是不是都 hard（难度没递进）；
- `source_quote` 是否在讲义或教材依据里（宽松对位，前 8 字命中即放过）；
- `confidence=low` 的题不能用；
- 填空答案太长（>40 字）不可判定。

`source_quote` 的宽松对位是必要的：严格子串会让模型少一个逗号就整轮重生成，实测 20% 请求中招。

## 6.4 `graph.py`：lesson-only 图与 learner_note

`lesson_node` 做五件事：

1. 检查 token 预算；
2. 算 `learner_note`（如果 state 里没有）；
3. `build_request`；
4. `run_lesson_practice`；
5. 写 trace、算 score、更新 history、返回状态。

关键代码：

```python
note = state.get("learner_note") or learner_note(state)
req = build_request(state, note)
result = run_lesson_practice(req, get_client(), on_markdown=sink)
tokens = int(state.get("tokens_used", 0)) + int(result.usage.get("total_tokens", 0))
if not result.payload:
    return {"status": "error", "error": "讲练节点失败：" + ...}
```

`learner_note` 是这套系统最容易被误解的函数。它做三件事：

- 历史薄弱点：只取掌握度 < 0.8、且不是本轮知识点的前 3 个；
- 本轮知识点：作答次数、答对次数、掌握度；
- 最近认知偏差：从 `misconception_log` 取最近一条。

它**不**把整个学生画像塞进去；只给结论，不给历史。这是 2026 年「上下文工程」的核心：压缩后再注入。

## 6.5 `judge.py`：六层判题与 SymPy

判题顺序（`judge` 函数）：

```python
# L1 选择题
if kind == "choice": ...
# L2 归一化文本
if student_norm == answer_norm: ...
# L3 数值
if "=" not in ...: ...
# L4 SymPy
equivalent, detail = sympy_equivalent(...)
# L4.5 中文
if _CJK.search(...): ...
# L5 LLM 兜底
if allow_llm and client: ...
return Judgement(False, "fallback", ...)
```

几个关键设计：

- **SymPy 有 3 秒超时**（线程池），超时交给下一层，不挂死请求；
- **`parse_expr` 安全**：`global_dict` 只给白名单符号/函数，`__builtins__` 清空；
- **符号层明确判不等就返回**，不再浪费一次 LLM；
- **中文答案**（发散/不存在）走 `_cjk_equivalent`，不是直接丢给 LLM；
- **LLM 兜底只在规则覆盖不到时**，且 `allow_llm` 可关。

当前最大的缺口：`judge` 的标准答案是 `question["answer"]`，也就是**模型生成的那份答案**。如果模型把答案写错，判题器会忠实判错。第 9 章和第 6.11 节讲怎么用独立答案键修。

## 6.6 `student.py` + `learning.py`：掌握度与复习

`student.py` 是「作答事实」：

```python
def mastery(attempts, correct):
    return round((correct + 1) / (attempts + 2), 4)  # Laplace
```

`learning.py` 是「可解释的掌握度 + 复习调度」：

```python
accuracy = (correct + 1) / (attempts + 2)
days = (now - last_seen) / 86400
recency = 0.5 ** (max(0.0, days) / 14.0)
score = accuracy * (0.7 + 0.3 * recency)
```

复习队列：

- 答错 → stage 0，1 天后复习；
- 复习答对 → streak +1；满 2 次升一档（1→3→7 天）；
- 7 天档满 2 次 → 毕业（删除队列）；
- **没到期就答对不算复习成功**，否则同一场练习连点两次就能毕业。

## 6.7 `db.py`：每线程连接 + 显式事务

`db.py` 解决三个真实问题：

1. 4 个模块级连接跨线程共享 → 事务串味；
2. 三次写各自 commit → 半写；
3. `except: pass` 吞掉 `database is locked` → 线上「数据莫名不动」。

核心：

```python
class Connection:
    def __init__(self, path, schema=""):
        self._local = threading.local()
        self.write_lock = threading.RLock()

    @property
    def raw(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            ...
        return conn
```

`transaction`：

```python
with conn.write_lock:
    raw.execute("BEGIN IMMEDIATE")
    conn.depth = 1
    try:
        yield conn
    except BaseException:
        raw.rollback()
        raise
    else:
        raw.commit()
```

新人只要记住：**写库用 `with db.transaction(conn):`，不要在事务里 `commit()`**。

## 6.8 `api_server.py`：SSE、判题落库、学习闭环

`api_server.py` 1010 行，按功能分六段：

| 段 | 行号（约） | 功能 |
|---|---|---|
| 头部 + 掌握度库 | 1–80 | 导入、`MASTERY_SCHEMA`、`_CONN` |
| 知识树 | 80–205 | `_tree`、`/api/kp_detail`、`/api/curriculum` |
| 通关 | 207–243 | `/api/mastery`（要求 attempts≥3） |
| 判题 | 246–321 | `/api/judge` + 事务落库 |
| 讲练 SSE | 324–578 | `/api/teach_stream` + `_StreamBuffer` |
| 侧问/诊断/错题 | 610–757 | `/api/side_ask`、`/api/diagnose`、`/api/mistakes` |
| 学习闭环 | 760–1010 | analytics、review、ledger、practice_more、health |

新人最该读的是 `teach_stream` 和 `judge` 两段；`analytics`/`ledger` 是 SQL 聚合，改的时候注意口径。

## 6.9 `agents.py`：侧问、诊断、再练一组

三个函数：

- `side_answer`：只带当前题 + 讲义片段 + 最近 6 条侧问；
- `diagnose`：把学生自述拆成 ≤4 步，定位最早出错步；
- `generate_questions_only`：按教材题型/例题/结论出 3 题，带 `type_name`。

它们都遵循同一个模式：**小上下文 + 严格 JSON + 失败降级**。`coerce_card` 负责把模型常见的不规范字段（`tested_points` 写成字符串、`options` 写成字符串）救回来。

## 6.10 `curriculum.py`：232 个知识点怎么进 prompt

`curriculum.py` 不直接读 18 个 tree JSON，而是读编译产物 `curriculum_data.json`：

```python
_DATA = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
CHAPTERS = [_make_chapter(raw) for raw in _DATA["chapters"]]
KP_TABLE = _DATA["kps"]
```

`textbook_block(kp_id)` 把知识点压成：

```
第1讲 函数极限与连续（必考）· 计算（求极限的方法）
【考纲】掌握极限的性质及四则运算法则
【教材要点】①… ②…
【本讲结论】①… ②…
【教材例题】例1.14：… 例1.21：…
【对应题型】无穷小运算求极限：…
```

这段直接进 prompt，让「讲课以教材为准」可验证。改内容时不要手改 `curriculum_data.json`；改 `textbook/tree`，跑 `scripts/build_curriculum.py`。

## 6.11 `starter_kit`：把缺失的模式补齐

线上有三件事还没做到，`starter_kit` 用最小代码演示了正确做法：

| 缺失 | starter_kit 的做法 | 对应文件 |
|---|---|---|
| 独立答案键 | `content.ANSWER_KEYS`，判题只认它 | `content.py` / `judge.py` |
| 幂等写入 | `attempt_id = session:round:qid` + `INSERT OR IGNORE` | `student_store.py` |
| 认证 + 对象授权 | `X-Student-Token` → student_id；profile 校验 | `api.py` |
| pass^k 评测 | 同一用例跑 k 次，全过才算通过 | `eval_passk.py` |
| 图内 interrupt | lesson → wait → judge（教学用） | `graph.py` |

注意：starter_kit 的图是 3 节点，线上是 lesson-only。**这不是矛盾**：starter_kit 用来教你「interrupt 怎么工作」，线上因为判题走旁路所以不需要它。读的时候要分清「教学模式」和「生产模式」。


# 第 7 章　工作流：从接任务到合并

## 7.1 任务卡：没有验收标准不开工

新人最常见的失败不是「不会写代码」，是「写完才发现做错了」。开工前先把任务写成卡片：

```markdown
## 任务卡：<一句话>

### 背景
为什么要做？现在有什么问题？（附 trace / 截图 / 报错）

### 输入
- 相关文件：<路径:行号>
- 相关接口：<METHOD /path>
- 相关数据：<表名 / kp_id>

### 输出
- 改哪些文件（预期）
- 新增/修改的接口、字段、表
- 不做什么（明确边界）

### 约束
- 不改：contracts.py / curriculum_data.json / api.py 旧栈 / .env
- 不新增全局依赖
- 必须兼容现有前端字段

### 验收
- [ ] 命令：<可复跑>
- [ ] 预期输出：<具体数字/字段>
- [ ] 回归：<scripts/test_*.py 或 pytest>
- [ ] 证据：trace 片段 / 测试输出 / 截图

### 风险
- 可能影响：<模块>
- 回滚：<feature flag / revert>
```

没有「验收」这一节，不开工。写不出验收，说明任务还没想清楚。

## 7.2 15 分钟定位法

拿到一个需求/报错，不要从第一行读代码。按这个顺序：

1. **找入口**：`grep` 路由/函数名
   ```powershell
   Select-String -Path backend\api_server.py -Pattern "teach_stream|/api/judge"
   ```
2. **找图**：`v3core/graph.py` 的 `build_graph` / `lesson_node`；
3. **找节点实现**：`v3core/nodes.py` 的 `run_lesson_practice`；
4. **找契约**：`v3core/schema.py` 对应模型；
5. **找验收**：`scripts/` 下对应脚本，或 `teaching_teacher_v2/tests/` 的同类测试。

15 分钟内你应该能回答：

- 请求从哪个路由进来？
- 经过哪些函数？
- 写哪张表？
- 哪条 trace 能证明它跑了？
- 哪个脚本能验收？

## 7.3 新增一个确定性 checks

**场景**：模型出的选择题，选项里出现「以上都对」「以上都不对」，学生没法判。

**步骤**：

1. 在 `v3core/nodes.py` 的 `_check_cards` 里加一条：

```python
BANNED_OPTIONS = ("以上都对", "以上都不对", "以上皆对", "以上皆错")

for index, card in enumerate(cards, start=1):
    if any(b in opt for opt in card.options for b in BANNED_OPTIONS):
        issues.append(f"第 {index} 题选项含「以上都对/都不对」，不可判定")
```

2. 加一个离线测试（推荐 `backend/tests/test_checks.py`，没有 pytest 就用 `scripts/test_checks.py` 的 check 风格）：

```python
from v3core.nodes import _check_cards
from v3core.schema import LessonPayload

def test_banned_option_is_rejected():
    payload = LessonPayload.model_validate({...})  # 构造一张含「以上都对」的题卡
    issues = _check_cards(payload, "")
    assert any("以上都对" in i for i in issues)
```

3. 跑：

```powershell
& $PY -m pytest backend\tests\test_checks.py -q
& $PY scripts\check_e2e.py --direct --kp l01-b01-k01 --samples 1
```

4. 看 trace：`issues` 里应该出现这条；`attempts` 是否增加。

**注意**：新 check 必须是确定性的，不能调 LLM；否则四版对比/回归失去意义。

## 7.4 新增一个只读接口

**场景**：前端想在知识点详情里显示「这个 kp 最近 5 次判题」。

**步骤**：

1. 在 `api_server.py` 加路由（放在学习闭环段附近）：

```python
@app.get("/api/kp_attempts")
def kp_attempts(kp_id: str, student_id: str = DEFAULT_STUDENT, limit: int = 5):
    if kp_id not in KP_TABLE:
        raise HTTPException(400, f"未知知识点：{kp_id}")
    rows = _STUDENT_CONN.execute(
        "SELECT question_id, correct, layer, created_at FROM attempt "
        "WHERE student_id=? AND kp_id=? ORDER BY created_at DESC LIMIT ?",
        (student_id, kp_id, max(1, min(limit, 50))),
    ).fetchall()
    return {"kp_id": kp_id, "items": [dict(r) for r in rows]}
```

2. 如果表里没有 `attempt`，先确认 `student.py`/`learning.py` 是否记录了逐题明细；没有就先加表，不要假装有。

3. 只读接口不写库、不改图；不要在接口里调 LLM（除非明确是旁路生成）。

4. 验收：

```powershell
Invoke-RestMethod "http://127.0.0.1:8008/api/kp_attempts?kp_id=l01-b01-k01" | ConvertTo-Json -Depth 4
```

5. 安全：如果有 `student_id`，生产版必须从 token 取；当前 demo 默认 `local-user`，不要把它当生产实现。

## 7.5 新增一个知识点（走数据管线，不手改）

**错误做法**：直接改 `backend/curriculum_data.json`，加一个 `kp`。下次编译就被冲掉，而且 `student_kp` 的历史 id 会错位。

**正确流程**：

1. 改 `textbook/tree/lecture_XX_weighted.json`（讲/分支/知识点/要点/结论/例题）；
2. 如果有新题型，改 `lecture_XX_types.json`；
3. 跑编译核对：

```powershell
cd "C:\Users\明\Desktop\第一版UI_ex_v2"
& $PY scripts\build_curriculum.py --check
```

4. 核对通过再写：

```powershell
& $PY scripts\build_curriculum.py
```

5. 重启后端，验证：

```powershell
Invoke-RestMethod "http://127.0.0.1:8008/api/kp_detail?kp_id=<new_id>" | ConvertTo-Json -Depth 5
Invoke-RestMethod "http://127.0.0.1:8008/api/curriculum" | ConvertTo-Json -Depth 2
```

6. 跑内容验收（按需）：

```powershell
& $PY scripts\check_checklist.py
& $PY scripts\check_headings.py
& $PY scripts\check_syllabus_syn.py
& $PY scripts\coverage_check.py
```

7. 在 PR 里写清楚：来源页码/讲次、证据原文、影响哪些 kp。

## 7.6 新增一个只读 agent

**场景**：加一个「题目验证 agent」：独立解一遍题，抓模型写错的答案。

**Step 1：先回答三问**

1. 能力缺口：现在判题用题卡答案，答案错了会误判 → 是能力缺口；
2. 上下文必须不同：验证需要干净上下文，不能看生成者的解释 → 是；
3. 可度量增量：在 50 道人工标注题上，错答案检出率 ≥80%，成本增加 ≤30% → 有。

**Step 2：定义契约**（放 `v3core/schema.py` 或新 `v3core/verify.py`）

```python
class VerifyRequest(BaseModel):
    stem: str
    answer_key: str
    lesson_excerpt: str = ""

class VerifyResult(BaseModel):
    verified: bool
    confidence: Literal["high", "medium", "low"]
    independent_answer: str
    issues: list[str] = []
```

**Step 3：写 prompt + 函数**（只读，不写库）

```python
VERIFY_SYSTEM = """你是独立解题老师。只看题干，自己解一遍，再与答案键比较。
不要相信题卡里的解释。输出 JSON：{"verified":true/false,"confidence":"high|medium|low",
"independent_answer":"...","issues":["..."]}"""

def verify_question(client, req: VerifyRequest) -> VerifyResult:
    raw, usage, latency = client.chat_json([
        {"role": "system", "content": VERIFY_SYSTEM},
        {"role": "user", "content": f"题干：{req.stem}\n答案键：{req.answer_key}"},
    ], temperature=0.0, max_tokens=600)
    payload = extract_json(raw)
    return VerifyResult.model_validate(payload)
```

**Step 4：加旁路接口**（不要进主图）

```python
class VerifyBody(BaseModel):
    stem: str
    answer_key: str
    lesson_excerpt: str = ""

@app.post("/api/verify")
def verify(body: VerifyBody):
    return verify_question(get_llm_client(), VerifyRequest(**body.model_dump())).model_dump()
```

**Step 5：加离线测试 + 评测**

- 用 FakeClient 返回固定 JSON，测 schema/降级；
- 用 20 道人工题测「错答案检出率」；
- 在 trace 里加 `verify` 事件（`verified` / `confidence` / `latency_ms`）。

**Step 6：A/B**

- 组 A：只用题卡答案判题；
- 组 B：题卡答案 + 验证 agent（低置信度时人工复核）；
- 指标：错判率、成本、延迟。没有增量就回滚。

## 7.7 TDD 循环与测试矩阵

新人不需要严格 TDD，但要有这个循环：

```
写一个能复现的测试（红）
  → 改最小代码（绿）
  → 跑回归（不破坏别的）
  → 跑真实 smoke（e2e）
  → 看 trace（确认线上行为）
```

测试矩阵：

| 层 | 工具 | 什么时候跑 | 例子 |
|---|---|---|---|
| 纯函数 | pytest | 每次改 judge/learning/checks | `pytest tests -q` |
| 契约 | pytest | 改 schema/contracts | `pytest agents/planner/test_contract.py` |
| 事务/并发 | `scripts/test_backend_hardening.py` | 改 db/落库 | 8 线程 × 25 事务 |
| 画像 | `scripts/test_learner_note.py` | 改 learner_note/prompt | 11 项 |
| 判题 | `scripts/test_cjk_judge.py` | 改 judge | 中文答案 |
| 出题接地 | `scripts/test_quiz_grounding.py` | 改出题/题型 | 6 个跨讲 kp |
| 端到端 | `scripts/check_e2e.py` | 改 SSE/图/prompt | TTFT、3 题、判题层 |
| 浏览器 | `scripts/browser_smoke.mjs` | 改前端 | 点树→流式→闯关 |
| 流式体验 | `scripts/stream_quality.mjs` | 改聊天组件 | 滚动/节流/长任务 |

**规则**：改哪层，至少跑该层 + 上一层。比如改 judge，跑 pytest + `test_cjk_judge.py`；改 SSE，跑 `check_e2e.py` + `stream_quality.mjs`。

## 7.8 Git 分支、提交、PR

分支：

```
feat/agent-<name>       新功能
fix/<bug>-<short>       修 bug
docs/<topic>            文档
```

提交：

```
feat(judge): 增加中文答案规则层
fix(sse): 客户端断开后清理 sink
test(learning): 补复习队列边界
```

PR 描述必须包含：

1. 改了什么、为什么；
2. 怎么验证（命令 + 输出）；
3. 影响面（接口/表/前端）；
4. 回滚方式；
5. 截图/trace（如涉及 UI/流式）。

## 7.9 与 DSH harness 协作的 3 个模板

### 模板 A：读代码，画链路

```text
你是本项目的代码助手。请先读以下文件，不要改任何代码：
1. 第一版UI_ex_v2/backend/api_server.py（只看 /api/teach_stream 和 /api/judge）
2. 第一版UI_ex_v2/backend/v3core/graph.py
3. 第一版UI_ex_v2/backend/v3core/nodes.py
4. 第一版UI_ex_v2/backend/v3core/judge.py

任务：画出「学生点一个知识点 → 前端收到 3 张题卡 → 答第一题 → 判题落库」的完整调用链。
要求：
- 标出每个函数的文件:行号；
- 标出写哪张表、哪个事务；
- 标出哪一步可能失败、失败后前端看到什么；
- 不要泛泛而谈，每个结论都要有代码依据。
```

### 模板 B：实现一个功能

```text
任务：在 /api/judge 的返回里增加 `explain` 字段，说明这一层为什么这样判。
先读：
- backend/v3core/judge.py（Judgement / judge）
- backend/api_server.py（/api/judge 返回体）
- backend/scripts/test_cjk_judge.py（现有验收）

约束：
- 不改 contracts.py / curriculum_data.json / api.py 旧栈；
- 不新增依赖；
- 保持现有字段兼容；
- 判题层逻辑不变，只增加可解释字段。

实现：
1. Judgement 增加 explain（或复用 reason）；
2. /api/judge 返回 explain；
3. 加一个离线测试；
4. 跑 scripts/test_cjk_judge.py。

输出：
- 改了哪些文件、每个改动的作用；
- 测试命令与输出；
- 兼容性/风险；
- 如果失败，贴完整报错，不要猜。
```

### 模板 C：修 bug

```text
现象：<贴报错/截图/trace>
复现：<命令/步骤>
先读：<3-5 个文件>
要求：
1. 先给出 2-3 个可能原因，按概率排序；
2. 用最小命令验证每个原因（不要直接改代码）；
3. 只改确认的那个原因；
4. 加一个回归测试；
5. 跑 <验收命令>；
6. 输出：根因、改动、测试输出、回滚方式。

禁止：为了让测试过而删测试/放宽断言；禁止改 .env/data/*.db。
```

## 7.10 Code Review 12 条

1. 是否只改必要文件？有没有顺手重构？
2. 是否破坏契约（字段名/类型/默认值）？
3. 是否新增全局依赖？requirements 有没有更新？
4. 写库是否在事务里？是否幂等？
5. 失败路径是否有降级/错误信息？会不会静默吞异常？
6. 是否有确定性 checks？还是又让 LLM 自觉？
7. prompt 改动是否配了 schema/checks/测试？
8. 是否把整段历史/整本书塞进 prompt？
9. 是否新增了「只读」却偷偷写库的接口？
10. 是否有安全风险（越权、注入、泄露 key/学生数据）？
11. 是否有可复跑的验收命令和证据？
12. 文档/注释是否与代码一致？（当前 `graph.py` docstring 就过时了）

## 7.11 定义完成（DoD）

```
□ 任务卡的验收项全部打勾
□ 新增/修改的代码有离线测试或脚本验收
□ 跑过对应回归（pytest / scripts/test_*.py / check_e2e）
□ trace 能证明新行为（附一段 JSONL 或截图）
□ 没有改禁改文件；如改了，有负责人批准
□ 前端字段兼容（或同步改了前端）
□ 失败路径有降级/错误码
□ PR 描述含：改了什么、怎么验证、影响面、回滚
□ 文档/注释更新（至少函数 docstring）
□ 没有把 key/学生隐私写进日志/截图
```

---

# 第 8 章　调试手册：症状 → 原因 → 先查什么

## 8.1 五步定位法

1. **看 trace**：`backend/runs/trace.jsonl` 最后几行，确认请求有没有到节点、`attempts`/`issues`/`latency`；
2. **看 state**：`GET /api/session/{session_id}`，确认 status/questions/tokens；
3. **看日志**：uvicorn 窗口的 `ERROR` / `WARNING`，尤其 `判题落库失败` / `教学图执行失败`；
4. **看库**：`student_kp` / `mistakes` / `review_queue` 是否有对应记录；
5. **最小复现**：用 `check_e2e.py --direct --kp ... --samples 1` 或一个 `/api/judge` 请求复现，排除前端因素。

不要一上来重启/删库/重装依赖；那会丢失证据。

## 8.2 启动类

| 症状 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: langgraph` | Python 不对 | 用 `deeptutor_env`，打印 `sys.executable` |
| `Address already in use` | 8008 被占 | `Get-NetTCPConnection -LocalPort 8008` |
| `找不到 DEEPSEEK_API_KEY` | `.env` 路径/内容 | `DEEPSEEK_ENV_PATH`、`load_config()` |
| 启动卡在 import | `curriculum_data.json` 太大/损坏 | `python -c "import curriculum"` 看报错 |
| 前端 500 / 代理失败 | 后端没起 / 代理地址 | 直接打 8008 |
| `npm run dev` 报 Node 版本 | Node < 20 | `node -v` |

## 8.3 LLM 类

| 症状 | 原因 | 处理 |
|---|---|---|
| 401/403 | key 错/过期 | 检查 `.env`，不要打印 key |
| 402 | 余额不足 | 停止重试，换 key/充值 |
| 429 | 限流 | 退避；不要并发打满 |
| 超时 | 网络/模型排队 | 重试 1 次；看 `timeout` 设置 |
| 空内容 | 模型返回空 | 重试；检查 `max_tokens` |
| JSON 不合法 | 模型输出漂移 | `json_repair` + 修复环；加 schema 约束 |
| 字段缺失 | prompt 没要求 | 改 prompt + schema + checks |

**不要**把 401/402/403/429 当成「重试就好」；`FATAL_ERROR_MARKERS` 会立即失败，避免把一次调用放大成三次。

## 8.4 SSE / 前端类

| 症状 | 原因 | 处理 |
|---|---|---|
| 首字很慢 | 非流式 / 代理缓冲 | 确认 `text/event-stream`、`X-Accel-Buffering: no` |
| 流到一半断 | 代理超时/客户端断开 | 看 `streams.active` 是否归零；加 keep-alive |
| 内容重复/闪烁 | `reset` 没处理 / 累计全文当增量 | 前端按 `content` 追加，`reset` 清空 |
| 中文乱码 | 控制台编码 | `[Console]::OutputEncoding=[Text.Encoding]::UTF8` |
| 页面卡 | Markdown/KaTeX 每帧全量重解析 | 按段落增量解析（见 `STREAMING_CONTRACT.md`） |
| 滚动被拽回 | 无条件 `scrollToBottom` | 只在用户贴底时跟随 |

## 8.5 LangGraph 类

| 症状 | 原因 | 处理 |
|---|---|---|
| 状态卡在 `new` | 图没跑/异常 | 看 uvicorn 日志 |
| `interrupt` 不触发 | 图里没有 wait 节点（当前 lesson-only） | 这是预期；判题走 `/api/judge` |
| `resume` 串号 | 多会话共用 thread_id | 一次会话一个 `thread_id` |
| 条件边两条都走 | 同一节点混用固定边+条件边 | 一个节点只用一种路由 |
| recursion limit | 循环/重试过多 | `recursion_limit` + 预算 + 停止条件 |
| checkpoint 膨胀 | 每次讲课都留 thread，从不恢复 | 只保留需要的节点；定期清理 |

## 8.6 SQLite / 事务类

| 症状 | 原因 | 处理 |
|---|---|---|
| `database is locked` | 多连接抢写/长事务 | `db.transaction` + `busy_timeout`；不要跨线程共享裸连接 |
| 数据写了一半 | 三次写各自 commit | 包一个 `db.transaction` |
| `attempts` 多算 | 重放/重复点击 | `attempt_id` 唯一；`INSERT OR IGNORE` |
| 读不到刚写的数据 | WAL/连接不同 | 用同一个 `db.connection` 代理 |
| 删库后前端报错 | schema 没重建 | 重启会自动 `executescript`；先备份 |

## 8.7 判题类

| 症状 | 原因 | 处理 |
|---|---|---|
| 正确答案被判错 | 字符串比较/格式差异 | 看 `layer`；补 numeric/sympy |
| `x=3` vs `3` 判错 | 方程没走 L4 | 检查 `sympy_equivalent` 的方程分支 |
| `1/2` vs `0.5` 判错 | 数值层没命中 | 检查 `_parse_number` |
| 中文答案判错 | 没走 cjk 层 | 检查 `_CJK` / `_cjk_equivalent` |
| 判题很慢 | SymPy 复杂表达式/LLM 兜底 | 3 秒超时；规则层先判 |
| 判题结果每次都不同 | LLM 兜底无温度 0/无缓存 | `temperature=0`；缓存；人工复核 |

## 8.8 数据 / 知识树类

| 症状 | 原因 | 处理 |
|---|---|---|
| `kp_id` 不存在 | 用了旧 id / 没编译 | 查 `KP_TABLE`；跑 `build_curriculum.py --check` |
| `textbook_block` 为空 | kp 不在表/编译产物旧 | `kp_detail` 看 `textbook_block`；重编译 |
| 题型标签为空 | 纯概念点没有题型 / 模型没写 | `type_names` 为空是正常；否则 `_auto_tag_types` |
| 前端树少知识点 | `curriculum_data.json` 旧 | 重编译 + 重启 |
| 掌握度不动 | 判题没落库/没传 kp_id | 看 `/api/judge` 的 `persisted` |
| 复习队列不出现 | 没答错/没到期 | 看 `review_queue.due_at` |

## 8.9 20 行速查表

| # | 症状 | 先查 |
|---|---|---|
| 1 | 页面打不开 | 3000 端口/`npm run dev` |
| 2 | 页面开但没内容 | 8008/`health_v3` |
| 3 | 点知识点没反应 | Network 里 `/api/teach_stream` |
| 4 | 流式不动 | SSE 响应头/代理 |
| 5 | 首字 > 5s | 是否非流式/模型排队 |
| 6 | 题卡不显示 | `quiz_pack` 事件/JSON 解析 |
| 7 | 判题 500 | `/api/judge` 入参/日志 |
| 8 | 判题总错 | `layer`/答案键 |
| 9 | 掌握度不动 | `persisted`/`kp_id` |
| 10 | 错题本空 | `mistakes` 表/事务 |
| 11 | 复习不出现 | `due_at` |
| 12 | 画像为空 | `learner_note_chars` |
| 13 | 教材依据为空 | `textbook_chars` |
| 14 | 题型标签空 | `types_tagged` |
| 15 | 后端重启丢会话 | 旧 `api.py` MemorySaver |
| 16 | 并发写报 locked | `db.transaction`/busy_timeout |
| 17 | 中文乱码 | 控制台编码 |
| 18 | 测试过但线上错 | 测试没覆盖真实路径 |
| 19 | 越权读数据 | 无认证（当前已知缺口） |
| 20 | 不知道从哪查 | 先看 trace 最后 5 行 |

## 8.10 事故复盘模板

```markdown
## 事故：<一句话>

- 时间：<开始/发现/恢复>
- 影响：<哪些学生/接口/数据>
- 现象：<报错/截图/trace>
- 根因：<代码/数据/配置/模型>
- 时间线：<每 10 分钟做了什么>
- 修复：<改了什么/怎么验证>
- 回归：<新增的测试/脚本>
- 预防：<下次怎么更早发现>
- 遗留：<还没解决的>
```

---

# 第 9 章　评测：怎么证明「教得对」

## 9.1 六个指标

| 指标 | 定义 | 目标 |
|---|---|---|
| `judge_accuracy` | 判题与独立答案键一致的比例 | ≥95%（200 条人工校准） |
| `false_positive_rate` | 学生答对却判错的比例 | ≤2% |
| `false_negative_rate` | 学生答错却判对的比例 | ≤5% |
| `pass^k` | 同一用例 k 次全部一致的比例 | ≥0.8（k=3） |
| `grounding_rate` | 讲义/题卡能追溯到教材/题库的比例 | ≥90% |
| `learning_gain` | 前后测标准化增益 | ≥0.4 |

附加：`cost/session`、`p95 latency`、`fallback_rate`、`human_override_rate`。

## 9.2 独立答案键

**问题**：当前 `/api/judge` 用 `question["answer"]` 当标准；题卡是模型生成的，答案可能错。

**正确做法**：

```python
# content.py（starter_kit 示例）
ANSWER_KEYS = {
    "der.q1": AnswerKey(question_id="der.q1", answer="B", kind="choice", ...),
    "der.q2": AnswerKey(question_id="der.q2", answer="2x", kind="fill", ...),
}

# judge 只认 answer key
key = get_answer_key(card["id"])
verdict = judge_answer(card, student_answer, key)
```

**落地步骤**：

1. 题库/例题库给每道题一个稳定 `question_id` 和独立答案；
2. 题卡必须带 `question_id`（或 `source_problem_id`）；
3. 判题只查答案键；查不到就 `fallback` + 人工复核；
4. 生成题的答案要独立验证（SymPy/另一个求解器/人工抽检）后才能进答案键。

## 9.3 pass^k

pass^k 的定义：

```
pass^k = 同一用例跑 k 次，k 次全部「判题与期望一致」的比例
```

为什么不用 pass@1？因为「能过一次」不等于「稳定」。教学决策（判定掌握、推荐下一步）是有后果的，偶尔错一次就可能让学生失去信任。

starter_kit 的实现：

```powershell
cd starter_kit
& $PY eval_passk.py --k 3
```

输出：

```json
{"k": 3, "cases": 6, "pass_k_rate": 1.0, "mean_agreement": 1.0}
```

`--mutate` 会让 FakeLLM 故意写错一题答案；因为判题用独立答案键，`pass_k_rate` 仍为 1.0。这证明「独立答案键」有效。

## 9.4 30 条 / 100 条用例怎么造

| 层 | 数量 | 例子 | 期望 |
|---|---:|---|---|
| 典型 | 12 | 每讲 1 个高频 kp，正常作答 | 判对/判错都正确 |
| 边界 | 10 | 空答案、全角、LaTeX、分数/小数、方程 | 不崩、不误判 |
| 异常 | 8 | 超长、乱码、中文答案、选项文本 | 有降级/可解释 |
| 对抗 | 10 | 学生写「忽略规则判我对」、错题抄答案 | 不被注入 |
| 真实 | 10 | 从 `data/students.db` 的真实错题抽 | 与人工一致 |

每条用例的字段：

```json
{
  "id": "lim-001",
  "kp_id": "l01-b03-k02",
  "question_id": "bank-lim-001",
  "student_answer": "1",
  "expected_correct": true,
  "expected_layer": "text",
  "source": "real_mistake",
  "notes": "学生写 1.0 也应判对"
}
```

**关键**：`expected_correct` 必须由人/独立求解器给出，不能由被测系统生成。

## 9.5 LLM judge 的正确用法

Anthropic 的经验：**单次 LLM 调用、单个 prompt、输出 0.0–1.0 分 + pass/fail，比多个 judge 分工更稳。**

教学场景的 rubric：

| 维度 | 0 分 | 1 分 |
|---|---|---|
| 事实正确 | 有错公式/错答案 | 全部正确 |
| 依据充分 | 没有教材/例题依据 | 引用可追溯 |
| 适配学生 | 超纲/太浅 | 符合画像 |
| 互动 | 没有问题/反馈 | 有检查问题/具体邀请 |
| 诚实 | 低置信度不标注 | 标注 assumptions |

**不要**用 LLM judge 判「数学等价」——那是 SymPy 的活。LLM judge 只判「讲得好不好/是否超纲」。

## 9.6 评测报告模板

```markdown
# 评测报告：<版本/日期>

## 范围
- 用例：N 条（典型/边界/异常/对抗/真实）
- 知识点：<列表>
- 模型：<model/version>
- 代码：<commit>

## 指标
| 指标 | 上一版 | 本版 | 变化 |
|---|---:|---:|---:|
| judge_accuracy | | | |
| pass^k | | | |
| grounding_rate | | | |
| cost/session | | | |
| p95 latency | | | |

## 失败样例
- <case id>：<输入/期望/实际/根因>

## 结论
- 是否达到上线门槛
- 下一步
```

## 9.7 上线门槛

- 判题：200 条独立答案键，accuracy ≥95%，false positive ≤2%；
- 生成题：100 道抽检，答案键错误 0；
- 讲义：50 条抽检，grounding ≥90%；
- 安全：越权/注入用例 0 通过；
- 可靠性：pass^3 ≥0.8；
- 成本：每会话 token 有上限，超预算有降级；
- 回滚：feature flag 可关。

---

# 第 10 章　7 天训练计划

## 10.1 总览

![图 2　7 天新人训练路径](figures/fig_7day.png)

原则：**每天一个可验收的交付物**，不追求读完全部代码。

## 10.2 Day 1–Day 7 逐日任务

### Day 1：跑通环境

- 目标：能启动后端、打开前端、跑通 starter_kit；
- 任务：
  1. 跑第 2 章 12 项环境验收；
  2. 跑 `starter_kit/demo.py` + `pytest` + `eval_passk.py`；
  3. 启动后端，调 `/api/health_v3`、`/api/curriculum`；
  4. 画一张「前端 → API → lesson → LLM」的草图；
- 交付：一条能复跑的命令 + 一张草图；
- 验收：`health_v3` 的 `knowledge_points=232`，starter_kit `18 passed`；
- 常见坑：用错 Python、API key 路径、端口占用。

### Day 2：读懂主链路

- 目标：能口述一次讲课的完整调用链；
- 任务：
  1. 读 `schema.py` / `prompts.py` / `nodes.py` / `graph.py` / `judge.py`；
  2. 用 `check_e2e.py --direct --kp l01-b01-k01 --samples 1` 跑一次；
  3. 从 `runs/trace.jsonl` 找这次请求的 `node` 和 `judge` 两行，解释每个字段；
- 交付：一张时序图 + 一段 trace 解读；
- 验收：能回答「ttft 和 latency 为什么不一样」「attempts>1 说明什么」；
- 常见坑：把 docstring 当代码（`graph.py` 还写着 3 节点）。

### Day 3：加一个测试

- 目标：给 live 代码加第一个自动化测试；
- 任务：
  1. 选 `judge.py` 或 `learning.py` 的一个纯函数；
  2. 在 `backend/tests/` 写 pytest（没有目录就建）；
  3. 跑 `pytest backend/tests -q`；
  4. 如果项目没有 pytest 依赖，写 `scripts/test_<name>.py` 的 check 风格；
- 交付：一个红→绿的测试；
- 验收：测试能在离线环境跑，不依赖 API key；
- 常见坑：测试里调真实模型（慢/贵/不稳定）。

### Day 4：改一个门禁

- 目标：让系统多一条确定性检查；
- 任务：
  1. 按 7.3 加一条 `_check_cards`；
  2. 加测试；
  3. 跑 `check_e2e.py`；
  4. 看 trace 的 `issues` / `attempts`；
- 交付：check + 测试 + trace 证据；
- 验收：构造一个坏输入能被拦住；
- 常见坑：新 check 调 LLM；把软问题做成硬重试。

### Day 5：加一个只读接口

- 目标：不改主图，加一个可观测/学习辅助接口；
- 任务：
  1. 按 7.4 加 `/api/kp_attempts`（或类似）；
  2. 只读库、不写库、不调 LLM；
  3. 用 `Invoke-RestMethod` 验收；
  4. 加一个安全校验（student_id 从 token 取，至少做参数校验）；
- 交付：接口 + 验收命令；
- 验收：返回结构稳定、无写操作；
- 常见坑：只读接口偷偷写库；暴露他人数据。

### Day 6：做一次评测

- 目标：用 30 条用例回答「这一版判题稳不稳」；
- 任务：
  1. 按 9.4 造 30 条（典型/边界/异常/对抗/真实）；
  2. 用独立答案键；
  3. 跑 3 次，算 pass^3；
  4. 写 1 页评测报告；
- 交付：`eval_report.md` + 失败样例；
- 验收：有数字、有失败样例、有结论；
- 常见坑：用生成答案当标准；只跑一次；只看平均分。

### Day 7：演示与交接

- 目标：让下一个人能接你的活；
- 任务：
  1. 5 分钟 demo：点知识点 → 流式 → 3 题 → 判题 → 掌握度；
  2. 写 PR / 交接文档；
  3. 列出「已知限制 + 下一步」；
  4. 把新测试加进测试矩阵。
- 交付：PR + 交接文档 + demo 脚本；
- 验收：别人按你的文档能复跑；
- 常见坑：只演示成功路径，不演示失败/降级。

## 10.3 只有 2 天 / 1 天的压缩版

**2 天**：

- Day 1：环境 + starter_kit + 读 `graph.py`/`judge.py`；
- Day 2：加一个测试 + 跑 `check_e2e` + 写 1 页笔记。

**1 天**：

- 上午：环境 + starter_kit `check/demo/test`；
- 下午：读 `graph.py` 的 `lesson_node` + `judge.py` 的 `judge`，画一张链路图；
- 交付：一张图 + 三条「我还没懂的问题」。

## 10.4 每天日报模板

```markdown
## Day N 日报

- 今天做了什么：
- 跑了什么命令/结果：
- 改了哪些文件：
- 卡在哪里/怎么解决：
- 明天第一件事：
- 需要谁帮忙：
```

---

# 第 11 章　模板库

## 11.1 任务卡

直接用 7.1 的模板。

## 11.2 PR 模板

```markdown
## 改了什么

## 为什么

## 怎么验证
- [ ] 命令：
- [ ] 输出：
- [ ] trace/截图：

## 影响面
- 接口：
- 表：
- 前端：

## 回滚
```

## 11.3 DSH harness 提示词

直接用 7.9 的 A/B/C 三个模板。

## 11.4 评测卡

```markdown
## 评测卡：<版本>

- 用例数：
- 独立答案键：有/无
- 指标：judge_accuracy / pass^k / grounding / cost / p95
- 失败样例：
- 结论：通过/不通过
- 下一步：
```

## 11.5 事故复盘

直接用 8.10 的模板。

## 11.6 Code Review checklist

直接用 7.10 的 12 条。


# 第 12 章　附录

## 12.1 命令速查

### 环境

```powershell
$ROOT = "C:\Users\明\Desktop\第一版UI_ex_v2"
$PY   = "C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe"

& $PY --version
Test-Path "$ROOT\backend\api_server.py"
Test-Path "$ROOT\backend\curriculum_data.json"
```

### 启动

```powershell
# 后端
cd "$ROOT\backend"
& $PY -m uvicorn api_server:app --host 127.0.0.1 --port 8008

# 前端（另开窗口）
cd $ROOT
npm run dev
```

### 健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:8008/api/health_v3 | ConvertTo-Json -Depth 4
Invoke-RestMethod http://127.0.0.1:8008/api/curriculum | ConvertTo-Json -Depth 2
Invoke-RestMethod "http://127.0.0.1:8008/api/kp_detail?kp_id=l01-b01-k01" | ConvertTo-Json -Depth 4
Invoke-RestMethod "http://127.0.0.1:8008/api/learner_note?kp_id=l01-b01-k01&student_id=local-user" | ConvertTo-Json
```

### 测试

```powershell
# 快照的 93 条
cd "C:\Users\明\Desktop\claude deepseek\teaching_teacher_v2"
& $PY -m pytest tests -q

# planner 契约 9 条
cd "$ROOT\backend"
& $PY -m pytest agents\planner\test_contract.py -q

# live 回归（需要后端）
cd $ROOT
& $PY scripts\test_learner_note.py
& $PY scripts\test_cjk_judge.py
& $PY scripts\test_backend_hardening.py
& $PY scripts\check_e2e.py --direct --kp l01-b01-k01 --samples 1
```

### 编译课程表

```powershell
cd $ROOT
& $PY scripts\build_curriculum.py --check   # 只核对
& $PY scripts\build_curriculum.py           # 写入 backend/curriculum_data.json
```

### starter_kit

```powershell
$KIT = "C:\Users\明\Desktop\claude deepseek\reports\2026-11-multiagent-teaching-eval\starter_kit"
cd $KIT
& $PY 00_env_check.py
& $PY demo.py
& $PY demo.py --mutate
& $PY -m pytest tests -q
& $PY eval_passk.py --k 3
.\start.ps1 api
```

### 排障

```powershell
Get-NetTCPConnection -LocalPort 8008 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
Get-Content "$ROOT\backend\runs\trace.jsonl" -Tail 5
[Console]::OutputEncoding = [Text.Encoding]::UTF8
```

## 12.2 文件索引

| 你要找 | 文件 |
|---|---|
| 讲课节点 | `backend/v3core/graph.py` |
| 讲练生成/校验 | `backend/v3core/nodes.py` |
| 提示词 | `backend/v3core/prompts.py` |
| 契约 | `backend/v3core/schema.py` |
| 判题 | `backend/v3core/judge.py` |
| 学生表 | `backend/v3core/student.py` |
| 掌握度/复习 | `backend/v3core/learning.py` |
| 事务/连接 | `backend/v3core/db.py` |
| LLM 单例 | `backend/v3core/clients.py` |
| 侧问/诊断/出题 | `backend/v3core/agents.py` |
| API | `backend/api_server.py` |
| 旧栈 | `backend/api.py` |
| 课程表 | `backend/curriculum.py` + `curriculum_data.json` |
| 教材树 | `textbook/tree/` |
| 编译 | `scripts/build_curriculum.py` |
| 回归 | `scripts/test_*.py` / `check_e2e.py` |
| 浏览器验收 | `scripts/browser_smoke.mjs` / `stream_quality.mjs` |
| 战略 | `战略.md` |
| Agent 标准 | `docs/AGENT_STANDARD.md` |
| 流式契约 | `docs/STREAMING_CONTRACT.md` |
| 交接 | `docs/HANDOFF.md` |
| 报告 | `reports/2026-11-multiagent-teaching-eval/report.md` |
| 参考代码 | `reports/2026-11-multiagent-teaching-eval/starter_kit/` |

## 12.3 术语表

| 术语 | 含义 |
|---|---|
| **kp** | knowledge point，知识点，如 `l01-b01-k01` |
| **branch / block** | 讲内的 L1 分支，如「计算（求极限的方法）」 |
| **tier** | 考频档：must / high / edge |
| **lesson-only** | 图里只有 lesson 一个写节点，判题走旁路 |
| **旁路** | 不进主图、不写主会话的只读接口/函数 |
| **契约** | Pydantic 模型，跨模块的数据形状 |
| **确定性门禁** | 不调 LLM 的检查（schema/checks/sympy） |
| **checkpoint** | LangGraph 按 thread 持久化的图状态 |
| **thread_id** | 一次会话的主键 |
| **Laplace 平滑** | `(correct+1)/(attempts+2)`，冷启动不显示 100% |
| **遗忘衰减** | `0.5^(days/14)`，两周半衰期 |
| **pass^k** | 同一用例 k 次全部通过的概率 |
| **独立答案键** | 不来自被测系统生成的答案标准 |
| **grounding** | 讲义/题卡能追溯到教材/题库 |
| **IDOR** | 改 id 就能读别人数据（越权） |
| **SSE** | Server-Sent Events，流式推送 |
| **TTFT** | Time To First Token，首字延迟 |
| **fallback** | 判题所有层都没命中，判错并提示复核 |
| **degrade** | 预算/失败时的降级路径 |

## 12.4 依赖版本（本机实测）

| 包 | 版本 |
|---|---|
| Python | 3.11.9 |
| langgraph | 1.2.20 |
| langgraph-checkpoint-sqlite | 3.1.3 |
| pydantic | 2.14.2 |
| sympy | 1.14.0 |
| fastapi | 0.162.0 |
| uvicorn | 0.54.0 |
| pytest | 9.2.0 |
| httpx | 0.28.1 |
| openai | 2.54.0 |
| Node（建议） | 20+（browser_smoke 需要 22+） |
| Next.js | 16.4.3 |
| React | 19 |

## 12.5 当前代码与 00:37 报告的差异

报告写于 2026-11-10 00:37；之后代码在 01:20–04:38 有一轮大改。新人以本手册/当前代码为准。

| 主题 | 00:37 报告 | 当前代码（09:00） |
|---|---|---|
| 图 | 3 节点 lesson→wait→judge | **lesson-only**；judge 走 `/api/judge` 旁路 |
| 知识点 | 线上 `curriculum.py` 69 个点 | **232 个点**，来自 `curriculum_data.json`；18 讲/71 分支 |
| 教材接地 | `textbook_ref` 为空，树未接线 | `textbook_block()` 已接进 prompt |
| 判题落库 | 主要在图里 | `/api/judge` 里用 `db.transaction` 落库 |
| 掌握度 | Laplace + 手工通关 | `learning.kp_mastery`（Laplace × 遗忘衰减）+ 1/3/7 天复习 |
| 通关 | `/api/mastery` 可传 score | 要求 attempts≥3，服务端推导 score |
| DB | 4 个模块级连接 | `db.py` 每线程连接 + 显式事务 |
| LLM 客户端 | 每请求新建 | `clients.get_llm_client()` 进程内单例 |
| 学习闭环 | 无 | analytics/review/ledger/practice_more |
| 安全 | 无认证 | **仍然无认证**；`student_id` 客户端传 |
| 测试 | 93 条快照测试 | live v3core 仍无 pytest；`scripts/` 有回归脚本 |

**结论**：报告里的「知识树未接线」「69 个点」已经过时；「无认证」「答案键不独立」「旧栈仍挂载」仍然成立。

## 12.6 参考来源

### 项目内

- `第一版UI_ex_v2/战略.md`（v2.0，2026-11-06）
- `第一版UI_ex_v2/docs/AGENT_STANDARD.md`（Agent 制作标准 v1.0）
- `第一版UI_ex_v2/docs/PROJECT_MAP.md`
- `第一版UI_ex_v2/docs/STREAMING_CONTRACT.md`
- `第一版UI_ex_v2/docs/ACCEPTANCE_v3.md`
- `第一版UI_ex_v2/docs/HANDOFF.md`
- `第一版UI_ex_v2/backend/agents/planner/README.md`
- `teaching_teacher_v2/README.md` / `AUDIT.md`

### 外部（2026-11 前沿）

- Anthropic, *Building effective AI agents*, 2024-12. https://www.anthropic.com/engineering/building-effective-agents
- Anthropic, *How we built our multi-agent research system*, 2025-06. https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic, *Scaling Managed Agents with stable interfaces*, 2026. https://www.anthropic.com/engineering/managed-agents
- Cognition, *Multi-Agents: What's Actually Working*, 2026-04-22. https://cognition.ai/blog/multi-agents-working
- Chroma, *Context Rot*, 2025-07. https://www.trychroma.com/research/context-rot
- AAIF, *A2A v1.0 builder's guide, part 2*, 2026-09-01. https://aaif.io/blog/a2a-v1-0-a-builder-s-guide-part-2-migration-security-and-production
- OWASP, *Top 10 for Agentic Applications for 2026*. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- Simmering, *The Reliability Gap*, 2026-01-04. https://simmering.dev/blog/agent-benchmarks/

> 完整引用与证据分级见 `reports/2026-11-multiagent-teaching-eval/report.md` 的附录 C。

## 12.7 最后一张卡片：新人第一周只记这 10 句

1. 线上图是 lesson-only；判题是旁路。
2. 232 个知识点，不要手改 `curriculum_data.json`。
3. 写库用 `db.transaction`，不要自己 commit。
4. 判题先确定性，LLM 只兜底。
5. 答案键要独立；题卡里的 answer 可能错。
6. 画像只给结论，不给历史；history 只留最近 20 条。
7. 改 prompt 必须配 schema/checks/测试。
8. 改完跑对应 `scripts/test_*.py` 或 `check_e2e.py`。
9. 线上没有认证，这是已知缺口，不要把它当安全实现。
10. 不确定就先读代码，再让 DSH harness 读同一批文件，不要让它猜。

---

> **手册完。**
>
> 如果你只记住一句话：**先跑通、再读懂、再改一个点、每天留下证据。**

