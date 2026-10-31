# Adaptive Trainer

**基于 LangGraph 的模块化自主学习规划系统（多智能体自适应教育闭环）**

把学习从“靠意志力硬扛”变成“有路径、有反馈、有进度”的系统工程：先做标准化诊断，再由多智能体协同完成规划、讲解、练习、反馈与 90 分验收，让学习者从零开始也能清晰看到自己的位置和下一步。

---

## 1. 项目定位

Adaptive Trainer 是一个面向个人的闭环学习系统，不是普通的问答机器人。它强调三件事：

1. **先诊断再教学**：用标准化客观题测出真实起点，而不是让模型凭感觉给分。
2. **过程可审计**：每一轮教学、例题、纠错、审计都写入状态与对话历史，可回放、可复盘。
3. **达标才结业**：审计官按概念、推理、边界、迁移、修正五个维度打分，未达到 90 分必须打回重学。

当前 v1.0 测试原型已打通：

- LangGraph 动态工作流运行时 + V1.0 五节点参考流程
- 标准化摸底诊断卷（单选 + 填空，权重 20/25/30/25）
- 苏格拉底式教学与追问
- 概念陷阱变式题
- 错题本与思维模型沉淀
- 90 分终审审计
- Streamlit 高对比度工作台
- 本地 Whisper 语音转写与语音口误清洗

---

## 2. 核心原则：核心契约稳定，Agent 插件化

团队协作最重要的边界：**状态契约稳定，Agent 节点与业务流程可插拔。**

### 受保护的核心契约

| 文件 | 职责 | 修改规则 |
|---|---|---|
| `core/state.py` | `TrainerState` 全局状态、`MistakeEntry` 数据契约 | 修改需 PR review，并说明迁移影响 |
| `core/llm.py` | 模型接入与结构化输出 Schema | 修改需保持向后兼容，新增字段优先 |

### 动态工作流运行时（Agent 插座）

`core/graph.py` 是**动态工作流运行时**：负责可插拔节点插槽、Checkpoint 状态恢复与中断挂起机制。

它不是死板绑定 5 个固定节点的拓扑，而是一个**通用 Agent 插座**：

- 每个战役按需挂载节点或子图；第一期只挂载【基准测评】子图，不需要 teacher / practice / correction / auditor。
- 拓扑由 `builder.add_node(...)` 与边决定，运行时只负责状态、恢复、中断与路由。
- 新增 Agent 不需要改 `core/state.py`，也不需要修改所谓的“五节点列表”。

> **特别说明：当前仓库内的 `core/nodes.py`、`config/prompts.py` 和 `ui/app.py` 均为 V1.0 MVP 联调测试代码，仅用于验证全链路可跑通。除核心状态契约（`core/state.py`）与基础连接（`core/llm.py`）外，其他所有节点逻辑、提示词、题库与前端代码均属于测试脚手架，后续各战役中允许团队成员进行大幅删改、推倒重做或自由新增 Agent。**

### 可插拔、可推倒重构的模块

| 文件/目录 | 职责 | 协作方式 |
|---|---|---|
| `config/prompts.py` | V1.0 测试 Prompt | 可独立迭代，可整体重写 |
| `core/nodes.py` | V1.0 测试节点逻辑 | 可大幅删改或按战役重写 |
| `ui/app.py` | V1.0 调试工作台 | 可整体重做，但保留 `interrupt/resume` 契约 |
| `data/`（后续） | 题库、教材、错题资产 | 按战役新增，不污染核心状态 |
| `tests/`（后续） | 评测与回归用例 | 每个战役必须补齐 |
| `agents/`（建议） | 各战役新增 Agent | 独立文件 + `add_node` 挂载 |

**原则：**

- 先改 Prompt / 节点 / UI，不要先动核心状态契约；拓扑按战役自由组合。
- 新增能力优先通过独立 Agent 文件 + `add_node` 实现，不把逻辑堆进主图。
- 任何跨模块契约变更，必须在 PR 描述中写清楚：输入、输出、迁移方式、回滚方式。

### Agent 插拔协作范式（极简插头说明）

每个队员在独立文件中写一个节点函数：

```python
from core.state import TrainerState

def my_agent(state: TrainerState) -> dict:
    return {"current_task": "下一步任务"}
```

主图只需一行即可挂载：

```python
builder.add_node("my_agent", my_agent)
```

约束：输入 `TrainerState`，返回增量状态 `dict`；不直接修改其他字段；Prompt、模型、工具放在自己的文件/目录；新增节点不需要修改核心状态契约。

---

## 3. 五期演进战役

### 第一期：基准测评与诊断引擎

**目标：** 把摸底做成可复用、可扩展的标准化测评引擎。

- **只跑测评子图**：第一期只挂载 `START → diagnostic（含客观判分）→ END`，不启动 teacher / practice / correction / auditor。
- 客观题/梯度题 JSON Schema 标准化
- 单选、填空、多步计算的稳定判卷
- 真实权重计分，杜绝虚假 0 分
- 错题知识点精确回填 `knowledge_gaps`
- 拍照卷面 / 多模态 OCR 分析（后续接入）
- 题库版本化与难度分层

### 第二期：鼓励式苏格拉底教学与对抗教练

**目标：** 从“讲答案”升级为“让学生自己讲出因果”。

- 鼓励式追问策略，避免把学生问崩
- 对抗教练：专门攻击学生的概念边界与反例
- 费曼复述检查
- 教学策略路由：概念不清 / 推理跳步 / 迁移失败分别处理
- 语音口误清洗与教学容错

### 第三期：权威教材与真题库工程化挂载

**目标：** 让每个追问都能落到权威材料与真题上。

- 教材/真题结构化入库
- RAG 检索与引用溯源
- 题目难度、考点、题型标签
- 题库去重、版本管理、质量抽检
- 教材段落与知识点映射

### 第四期：90 分通关审计与错题本资产化

**目标：** 把“错题本”从列表升级为个人认知资产。

- 五维审计评分与证据链
- 错题归因：概念 / 推理 / 边界 / 表达 / 熟练度
- 错题复现与间隔复习
- 个人思维模型库
- 结业报告与能力雷达

### 第五期：双栏工作台前端重构与终极交付

**目标：** 面向真实使用场景的最终工作台。

- 左侧学习路径 / 知识点树 / 错题本，右侧专注教学对话
- 双栏联动与键盘快捷操作
- 语音、拍照、公式输入多模态
- 性能、可访问性、移动端适配
- 打包、部署、团队交付文档

---

## 4. V1.0 参考流程（测试原型，不是固定拓扑）

> `core/graph.py` 是动态工作流运行时（Agent 插座）。下图是 V1.0 MVP 的全链路参考，不是所有战役必须背负的固定拓扑。

第一期测评子图：

```text
START → diagnostic（含客观判分）→ END
```

V1.0 全链路参考：

```text
START
  │
  ▼
diagnostic ── 生成标准化摸底卷 + interrupt 收卷
  │            客观判分：单选字母比对 / 填空等价判断
  ▼
teacher ───── 苏格拉底式教学、追问、语音口误还原
  │
  ▼
practice ──── 概念陷阱变式题
  │
  ▼
correction ── 逐句纠错、错题本、思维模型
  │
  ▼
auditor ───── 五维审计、90 分硬门槛、轮次熔断
  │
  ├── pass ──────────────► END
  ├── re_teach ──────────► teacher
  ├── re_practice ───────► practice
  └── MAX_CYCLES ────────► END
```

其他战役可以只挂载当前子图；新增 Agent 通过 `builder.add_node` 接入，不需要改核心状态。

核心状态由 `TrainerState` 承载，包含：

- `benchmark_paper` / `benchmark_score`
- `current_score` / `target_score`
- `knowledge_gaps` / `learning_plan`
- `dialogue_history` / `current_task` / `human_response`
- `mistake_book` / `audit_feedback`
- `iteration_count` / `next_agent`

---

## 5. 目录结构

```text
adaptive_trainer/
├── .env.example              # 环境变量模板（可提交）
├── .env                      # 真实 Key（禁止提交）
├── .streamlit/
│   └── config.toml           # 强制浅色高对比度主题
├── config/
│   ├── __init__.py
│   └── prompts.py            # V1.0 测试 Prompt（可重构）
├── core/
│   ├── __init__.py
│   ├── graph.py              # 动态工作流运行时 / Agent 插座
│   ├── llm.py                # 基础连接与结构化输出（受保护）
│   ├── nodes.py              # V1.0 测试节点（可重构）
│   └── state.py              # 全局状态契约（受保护）
├── agents/                   # 后续新增 Agent（建议，独立文件挂载）
├── ui/
│   ├── __init__.py
│   └── app.py                # V1.0 调试工作台（可重做）
├── requirements.txt
├── run.bat                   # Windows 一键启动
└── README.md
```

---

## 6. 团队本地极速启动

### 6.1 克隆仓库

```bash
git clone git@github.com:AlexWang-AI/adaptive-trainer.git
cd adaptive-trainer
```

> 如果尚未配置 GitHub SSH，请先把自己的 SSH public key 加到 GitHub 账号。

### 6.2 安装依赖

Windows `cmd` / PowerShell：

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Git Bash：

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

### 6.3 配置 API Key

```bat
copy .env.example .env
```

编辑 `.env`，至少填入：

```env
OPENAI_API_KEY=your_deepseek_or_openai_api_key_here
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-flash
STRUCTURED_OUTPUT_METHOD=json_mode
TARGET_SCORE=90
MAX_CYCLES=15
```

可选语音转写配置：

```env
WHISPER_MODEL=base
WHISPER_LOCAL_ONLY=1
```

> `.env` 已被 `.gitignore` 严格忽略。**绝对不要**把真实 Key 写进 README、Issue、PR 或提交历史。

### 6.4 启动

双击项目根目录的 `run.bat`，或在终端运行：

```bat
C:\Users\你的用户名\AppData\Local\Programs\Python\Python311\python.exe -m streamlit run ui/app.py
```

`run.bat` 会自动：

1. 切换到项目根目录；
2. 若 `.env` 不存在，从 `.env.example` 复制；
3. 启动 Streamlit；
4. 自动打开 `http://localhost:8501`；
5. 报错时保留窗口，方便排查。

### 6.5 最小验证

```bash
python -m py_compile config/prompts.py core/*.py ui/app.py
python -m streamlit run ui/app.py
```

首次打开后，输入一个主题，例如：

```text
旋转体体积
```

应看到标准化摸底小卷；完成并提交后，应显示真实得分与薄弱知识点。

---

## 7. 协作规范

### 分支策略

```text
main                      稳定运行时与核心契约
feat/phase1-benchmark     第一期功能分支
feat/phase2-socratic      第二期功能分支
fix/...                   缺陷修复
docs/...                  文档
```

- 不直接在 `main` 上开发。
- 每个 PR 只做一件事，标题写清“改了什么 + 为什么”。
- 合并前至少 1 名队友 review。
- 修改 `core/state.py` 或 `core/graph.py` 的运行时契约需要额外说明迁移与回滚方案。

### 提交信息

```text
feat: 新增标准化摸底卷客观判分
fix: 修复填空题等价判断误判
docs: 补充第三期题库接入说明
refactor: 拆分 teacher 节点的追问策略
```

### 安全红线

- 禁止提交 `.env`、`*.env`、`*.docx`、音频文件、个人密钥目录。
- 禁止在 Issue / PR / 截图中出现真实 API Key。
- 一旦发现 Key 泄露，立即在对应平台轮换，并清理 Git 历史。
- 提交前执行：

```bash
git status --short
git diff --cached --name-only
```

确认没有 `.env` 或密钥文件进入暂存区。

### 测试门禁

每次 PR 至少通过：

```bash
python -m py_compile config/prompts.py core/*.py ui/app.py
```

涉及流程变更时，额外运行：

```bash
python -m streamlit run ui/app.py
```

并完整走一次：

```text
开局 → 摸底小卷 → 提交 → 教学 → 例题 → 纠错 → 审计
```

---

## 8. 协作方式：模块战役制（4 人核心 + 第 5 人弹性）

不按人永久分割模块；同一时间只打一个主战场，战役内做临时工作流分工与角色轮换。

| 战役 | 主攻模块 | 完成标准 |
|---|---|---|
| 战役 1 | 诊断 + 自主规划 + 主底座 | LangGraph 骨架、诊断/规划、真实计分、最小调试页 |
| 战役 2 | 知识底座、教辅、题库 | 考纲/教材/真题/题型入库、RAG、评测集 v1 |
| 战役 3 | 教学、练习、反馈、验收 | 教学/练习/反馈/验收闭环、进度三问、90 分验收、试点跑通 |
| 战役 4 | UI 与交付 | 双栏工作台、进度看板、演示视频、文档提交 |

战役内临时工作流：主攻/架构、内容/数据、Agent/教学、评测/交付；角色随战役轮换。当前核心 4 人；第 5 人弹性加入内容/题库/评测工作流，不新开独立模块。

每个战役结束做一次集成回归：

- 核心状态契约没有被破坏；
- 当前战役子图能编译/挂载；
- 真实 API 能跑通当前模块的完整链路；
- 新增 Agent 有最小测试与使用说明。

---

## 9. 当前里程碑

**v1.0 测试原型已完成（仅用于验证全链路）：**

- 动态工作流运行时 + V1.0 五节点参考流程
- 真实 DeepSeek API 接入
- 标准化摸底测评与真实权重计分
- Streamlit 高对比度 UI
- 本地 Whisper 语音转写
- 语音口误清洗与纠偏
- 错题本、思维模型、审计报告

以上均为测试原型，不代表最终产品形态；各战役可大幅替换 UI、Prompt 与节点逻辑。

下一阶段从 **第一期：基准测评与诊断引擎** 继续推进。

---

## 10. 安全与许可

- 本项目为私有团队项目，未经允许请勿公开仓库或分发内部题库。
- 所有模型调用费用由各自 API Key 承担。
- 生产环境如需多人使用，请把 `MemorySaver` 替换为持久化 checkpointer（SQLite/Postgres），并为每个用户分配独立 `thread_id`。
