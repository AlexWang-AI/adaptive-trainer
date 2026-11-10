# Agent 制作标准（v1.0）

> 适用对象：本项目所有 Agent 的设计者（含用 Codex / Claude Code / 其他 harness 写代码的同学）
> 维护者：王子骞（`contracts.py` 唯一守门人）
> 参考实现：`backend/agents/planner/`（路线规划 agent，已完成 4 版对比）
> 最后更新：2026-11-01

---

## 0. 一句话范式

> **Hub-and-Spoke + 契约消息：主 agent（hub）独占会话状态与记忆；每个能力节点是 `输入契约 → 输出契约` 的纯函数；能力节点之间永不直连。**

三条推论，违反任何一条都要回退重做：

1. **能力节点不互相调用**。`quiz` 不调 `teach`，`teach` 不读 `quiz`。所有信息经 hub 中转。
2. **节点之间只传结构化对象**，不传自由文本、不传整段对话。
3. **记忆只有三处**：`thread`（会话）、`Store/DB`（学生档案）、`State`（本轮工作区）。除此之外任何"agent 自己记着"都是 bug。

---

## 1. 目录结构（照抄，不要自创）

```
backend/
├── contracts.py              # 跨 agent 契约（全项目唯一，改它要 review）
├── curriculum.py             # 知识点底座（唯一权威，agent 不许发明 id）
├── runner.py                 # run_structured：LLM+JSON+校验+修复环（不要重写）
├── llm.py                    # DeepSeek 客户端（不要重写）
├── config.py                 # 读 key/base_url/model
├── agents/
│   └── <agent_name>/
│       ├── __init__.py
│       ├── schema.py         # 本 agent 的输入/输出模型
│       ├── prompts.py        # V1~V4 的 prompt 构造函数
│       ├── checks.py         # 确定性校验 + 量化打分（必须有）
│       ├── variants.py       # V1~V4 的实现
│       ├── cases.jsonl       # 评测用例（≥6 条，含边界）
│       └── test_contract.py  # pytest 契约测试（≥8 条）
└── eval/
    └── <agent_name>_eval.py  # 四版对比跑分
```

**命名规则**：agent 名字用英文小写，`teach` / `quiz` / `planner` / `sideqa` / `exam`。中文名只在 `AgentSpec.name` 里出现。

---

## 2. 五条硬规矩

| # | 规矩 | 违反后的后果 |
|---|---|---|
| 1 | 输入/输出必须是 Pydantic 模型，字段带 `description` 和长度约束 | LLM 输出漂移，无法自动校验 |
| 2 | `kp_ids` 只能来自 `curriculum.py` 白名单 | 出现"lim.某不存在的知识点"，计划无法执行 |
| 3 | 必须写 `checks.py`，且 checks 是**确定性**的（不调 LLM） | 四版对比失去公平性，无法回归 |
| 4 | 每个 agent 必须能单独跑：`run_<agent>(client, request)` | 只能联调，出问题无法定位 |
| 5 | 不新增依赖到全局 Python，新依赖写进 `requirements.txt` | 组员环境不一致 |

---

## 3. Agent 之间传什么（技术路径选择表）

先判断信息形态，再选路径。**90% 的场景应该选第 1 条。**

| 信息形态 | 例子 | 用什么 | 明确不要用 |
|---|---|---|---|
| A 控制信号（<200 字） | 答对/答错、继续/结束、下一单元 | State 字段 | 建消息队列 |
| B 结构化产物（1–10 KB） | 题目 JSON、计划、错题条目 | Pydantic 对象经 hub | 塞进 prompt 自由文本 |
| C 原始上下文（10 KB+） | 对话历史、教材原文 | 共享 State / 摘要 / 传 id | 复制粘贴进别的 agent |

八条路径与适用边界：

| # | 路径 | 用不用 | 说明 |
|---|---|---|---|
| 1 | 纯函数调用 | ✅ 默认 | `run_quiz_node(req, text)` 形式 |
| 2 | 共享 State（一张图） | ✅ 主链路 | 注意 reducer 与 trim |
| 3 | 子图 + private channel | ⏸ 暂不用 | 调试看不见内部状态 |
| 4 | agent-as-tool | ⏸ 暂不用 | 让 LLM 自己决定调用，不可预测 |
| 5 | handoff 移交 | ❌ | 默认带走全部历史，与本项目隔离设计冲突 |
| 6 | Send / map-reduce | ⭕ 少数场景 | 并行判 20 道题时用 |
| 7 | 队列/事件总线 | ❌ 5 周内不用 | 运维成本 > 收益 |
| 8 | MCP / A2A / HTTP | ❌ 暂不用 | 跨进程才有意义 |

### `thread` 到底是什么

`thread_id` 是 **checkpoint 的隔离键 = 一次会话的主键**，不是"agent 的记忆开关"。

- 一次辅导会话 = 一个 `thread_id`。
- 出题 agent 不需要记忆 → **不给它 checkpointer，它就是纯函数**，不要"开个临时 thread 再丢掉"。
- 跨会话的掌握度/错题 → 进 `Store`/`student` 表，**绝不进 checkpoint**。

---

## 4. 四版对比协议（每个 agent 必须做）

每个 agent 做一个 V1~V4，**共用同一套 schema 和同一套 checks**，只在策略上不同。递进关系固定：

| 版本 | 策略 | 目的 |
|---|---|---|
| **V1** | 一次性直出，不做修复 | 基线：测「模型裸能力」 |
| **V2** | 两段式（先骨架再细化） | 测「任务拆解」是否有用 |
| **V3** | 白名单强约束 + 修复环 | 测「约束 + 自愈」的收益 |
| **V4** | V3 + 自评再修订 | 测「多花一次调用」值不值 |

**判定"最好"的口径**（不许拍脑袋）：

1. 先看**硬指标**：通过率（checks 全过）→ 覆盖率 → 幻觉率 → 顺序/轮次一致性。
2. 硬指标打平时看**成本**：调用数、tokens、耗时。
3. 硬指标相同、成本接近时，才用人工看 3 条样例做主观裁决。

> 参考实现里的 `evaluate_plan()` 就是一个可抄的打分函数。

### 允许出现第五档：V3R（代码规整）

planner 的实测结论值得写进范式：**V4（自评 + 修订）做到 6/6，但花了 3 次调用 / 16k tokens；V3R（V3 + 确定性后处理）同样 6/6，只花 1 次调用 / 4.2k tokens。**

规则：

- 凡是**不变量**（顺序、编号、去重、求和、格式），一律用代码保证，不要问模型。
- 只有当问题是**语义性**的（讲得对不对、难度合不合适）时，才值得再花一次 LLM 调用。
- 新增 agent 时，先做 V1~V4；如果 V3 与 V4 差距只在"不变量"上，就加一个 `V3R` 用代码补，别让 V4 上线。

---

## 5. 评测协议（cases.jsonl）

每个 agent 至少 6 条用例，必须覆盖：

- **典型场景** 2 条（正常输入）
- **边界场景** 2 条（超大范围 / 极小范围、时间极紧、零基础）
- **异常场景** 2 条（信息缺失、自相矛盾、学生画像很差）

每条用例的字段与 agent 的输入模型一一对应，例如 planner 的 `{"id","goal","scope","days","hours_per_day","level","profile_digest","style"}`。

跑法：

```bash
cd backend
python -m eval.planner_eval --workers 3
# 或只跑部分
python -m eval.planner_eval --cases c1 c6 --variants V1 V3
```

输出：`eval/results/<agent>_<时间戳>.json`（明细）+ `.md`（对比表）。

---

## 6. 定义完成（DoD，缺一条不算交付）

```
□ schema.py 覆盖输入/输出，字段都有 description 与长度约束
□ checks.py 有 ≥5 条确定性校验，每条都能被测试触发
□ V1~V4 四个版本都能跑通，且 V1 的通过率明显低于 V3/V4（否则说明约束没用）
□ cases.jsonl ≥6 条，含边界与异常
□ test_contract.py ≥8 条，pytest 全绿（离线，不打 API）
□ eval 跑完，产生了对比表，并写下「选第几版、为什么」
□ 在 AgentManifest 注册：id / name / role / owner / version / input_model / output_model / memory
□ README 里补一段：输入样例、输出样例、已知限制
```

---

## 7. 怎么把它交给 Codex / 其他 harness（复制这段）

> 你要实现的 agent 是 **<agent 名>**，位于 `backend/agents/<agent 名>/`。
>
> 严格按 `docs/AGENT_STANDARD.md` 的结构建文件：`schema.py` / `prompts.py` / `checks.py` / `variants.py` / `cases.jsonl` / `test_contract.py`。
>
> 约束：
> 1. 只能 import `contracts.py`、`curriculum.py`、`runner.py`、`llm.py`、`config.py`，不许重复实现 LLM 调用、JSON 解析、重试。
> 2. 知识点 id 只能来自 `curriculum.py`，禁止发明。
> 3. 做 V1~V4 四个版本，共用 schema 与 checks，只在 `prompts.py` 与 `variants.py` 里区分。
> 4. `checks.py` 必须是确定性校验，不调 LLM。
> 5. 写完后跑 `python -m pytest agents/<agent 名>/test_contract.py -q`，必须全绿。
> 6. 再跑 `python -m eval.<agent 名>_eval --workers 3`，把对比表贴回 PR。
>
> 参考实现：`backend/agents/planner/`（路线规划 agent，可以直接对照着抄结构）。
>
> 不要改：`contracts.py`、`curriculum.py`、`runner.py`、`llm.py`、`config.py`、`api.py`。

---

## 8. 分工与协作

| 内容 | 谁负责 | 规则 |
|---|---|---|
| `contracts.py` | 队长 | 任何改动必须 PR + review |
| `curriculum.py` | 队长 + 内容组 | 新增知识点要写来源（OCR 页码/大纲条目） |
| 各自的 `agents/<name>/` | 各人 | 一个 agent 一个目录，互不越界 |
| `api.py` 集成 | 队长 | 各人只提供 `run_<agent>()`，不直接改 api |

Git 习惯：

- 分支：`feat/agent-<name>`；每个 agent 一条分支，不长期挂。
- 提交信息：`agent(<name>): <做了什么>`。
- 合并前：`pytest` 全绿 + eval 对比表贴在 PR 描述里。

---

## 9. 常见错误清单（照着自查）

| 错误 | 症状 | 正确做法 |
|---|---|---|
| 把整段对话塞给下一个 agent | token 暴涨、答非所问 | 传摘要或只传本轮正文 |
| 每个 agent 复制一份重试逻辑 | 5 份代码，改一处漏四处 | 统一用 `runner.run_structured` |
| 让 LLM 判分 | 同一份答案两次打分不同 | 判分用确定性函数（字符串/数值/sympy） |
| 用 `MemorySaver` 跑真实会话 | 服务一重启学生状态全丢 | `SqliteSaver` + `data/checkpoints.db` |
| 把掌握度放 State | thread 内有效，跨会话丢 | 放 `student` 表 / Store |
| 子 agent 里用 `interrupt()` | resume 串号、卡死 | interrupt 只放主图 |
| 一个节点同时接固定边和条件边 | 两条路都会执行 | 一个节点只用一种路由方式 |
| 不写 checks 就上线 | 无法回归，改 prompt 全靠感觉 | checks 是 agent 的单元测试 |
