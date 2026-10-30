# Adaptive Trainer

**基于 LangGraph 的模块化自适应特训系统（AI 反向人类特训）**

把“听懂了”逼成“真的会”：系统先做标准化摸底，再由教学启发官用苏格拉底式追问逼你重建逻辑，课后例题官设置概念陷阱，纠错官沉淀错题本，终审审计官以 90 分为硬门槛决定是否结业。

---

## 1. 项目定位

Adaptive Trainer 是一个面向个人的闭环学习系统，不是普通的问答机器人。它强调三件事：

1. **先诊断再教学**：用标准化客观题测出真实起点，而不是让模型凭感觉给分。
2. **过程可审计**：每一轮教学、例题、纠错、审计都写入状态与对话历史，可回放、可复盘。
3. **达标才结业**：审计官按概念、推理、边界、迁移、修正五个维度打分，未达到 90 分必须打回重学。

当前 v1.0 已打通的底座包括：

- LangGraph 五节点闭环状态机
- 标准化摸底诊断卷（单选 + 填空，权重 20/25/30/25）
- 苏格拉底式教学与追问
- 概念陷阱变式题
- 错题本与思维模型沉淀
- 90 分终审审计
- Streamlit 高对比度工作台
- 本地 Whisper 语音转写与语音口误清洗

---

## 2. 核心原则：动静分离

团队协作最重要的边界：**主底座稳定，业务模块可插拔。**

### 受保护的主底座

以下文件是全员共享的契约，不应随单个功能需求随意改动：

| 文件 | 职责 | 修改规则 |
|---|---|---|
| `core/state.py` | `TrainerState` 全局状态、`MistakeEntry` 数据契约 | 修改需 PR review，并说明迁移影响 |
| `core/graph.py` | 五节点拓扑、`audit_router` 路由、checkpointer | 修改需 PR review，禁止破坏节点边界 |
| `core/llm.py` | 模型接入与结构化输出 Schema | 修改需保持向后兼容，新增字段优先 |

### 可插拔、可推倒重构的模块

| 文件/目录 | 职责 | 协作方式 |
|---|---|---|
| `config/prompts.py` | 各 Agent 的 System Prompt | 可独立迭代，建议按 Agent 分 PR |
| `core/nodes.py` | 五个 Agent 节点的业务逻辑 | 可在既有输入/输出契约内重构 |
| `ui/app.py` | Streamlit 工作台 | 可整体重做，但必须保留 `interrupt/resume` 契约 |
| `data/`（后续） | 题库、教材、错题资产 | 按阶段新增，不污染主状态 |
| `tests/`（后续） | 评测与回归用例 | 每期战役必须补齐 |

**原则：**

- 先改 Prompt / 节点 / UI，不要先动状态与拓扑。
- 新增能力优先通过新字段、新工具、新节点内部逻辑实现，避免破坏已有链路。
- 任何跨模块契约变更，必须在 PR 描述中写清楚：输入、输出、迁移方式、回滚方式。

---

## 3. 五期演进战役

### 第一期：基准测评与诊断引擎

**目标：** 把摸底做成可复用、可扩展的标准化测评引擎。

- 客观题/梯度题 JSON Schema 标准化
- 单选、填空、多步计算的稳定判卷
- 真实权重计分，杜绝虚假 0 分
- 错题知识点精确回填 `knowledge_gaps`
- 拍照卷面 / 多模态 OCR 分析（后续接入）
- 题库版本化与难度分层

### 第二期：鼓励式苏格拉底教学与对抗教练

**目标：** 从“讲答案”升级为“逼学生自己讲出因果”。

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

## 4. 系统架构

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
│   └── prompts.py            # 五个 Agent 的 System Prompt
├── core/
│   ├── __init__.py
│   ├── graph.py              # 五节点拓扑与条件路由（受保护）
│   ├── llm.py                # 模型接入与结构化输出模型
│   ├── nodes.py              # 五个 Agent 节点逻辑
│   └── state.py              # 全局状态与错题结构（受保护）
├── ui/
│   ├── __init__.py
│   └── app.py                # Streamlit 工作台
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
main                      受保护的稳定底座
feat/phase1-benchmark     第一期功能分支
feat/phase2-socratic      第二期功能分支
fix/...                   缺陷修复
docs/...                  文档
```

- 不直接在 `main` 上开发。
- 每个 PR 只做一件事，标题写清“改了什么 + 为什么”。
- 合并前至少 1 名队友 review。
- 修改 `core/state.py` 或 `core/graph.py` 需要额外说明迁移与回滚方案。

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

## 8. 4 人协作建议

| 角色 | 主要责任 | 对应战役 |
|---|---|---|
| 测评与数据工程 | 题库 Schema、判卷、统计与难度分层 | 第一期 |
| 教学 Agent 工程 | 苏格拉底追问、对抗教练、语音容错 | 第二期 |
| 教材与检索工程 | 教材/真题入库、RAG、引用溯源 | 第三期 |
| 前端与交付 | 双栏工作台、审计报告、部署与文档 | 第四、五期 |

每期结束统一做一次集成回归，确保：

- 主底座状态字段没有被破坏；
- 五节点拓扑仍然可编译；
- 真实 API 能跑通至少一条完整链路；
- 新增模块有最小测试与使用说明。

---

## 9. 当前里程碑

**v1.0 core chassis 已完成：**

- 五节点 LangGraph 状态机
- 真实 DeepSeek API 接入
- 标准化摸底测评与真实权重计分
- Streamlit 高对比度 UI
- 本地 Whisper 语音转写
- 语音口误清洗与纠偏
- 错题本、思维模型、审计报告

下一阶段从 **第一期：基准测评与诊断引擎** 继续推进。

---

## 10. 安全与许可

- 本项目为私有团队项目，未经允许请勿公开仓库或分发内部题库。
- 所有模型调用费用由各自 API Key 承担。
- 生产环境如需多人使用，请把 `MemorySaver` 替换为持久化 checkpointer（SQLite/Postgres），并为每个用户分配独立 `thread_id`。
