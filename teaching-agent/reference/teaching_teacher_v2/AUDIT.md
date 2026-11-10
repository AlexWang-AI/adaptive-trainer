# 讲课 Agent v1 代码审计报告

- **审计对象**：`C:\Users\明\Desktop\teaching_teacher_agent`（21 个 Python 文件 + 6.4 KB 提示词原文，约 2.9k 行）
- **审计时间**：2026-11-07
- **审计方式**：逐文件通读 + 静态走查 + 构造复现用例（见 `tests/`）
- **产出**：`teaching_agent_v2/`（同一份代码的可运行升级版）

---

## 一、结论摘要

| 严重度 | 数量 | 含义 |
|---|---|---|
| **P0 阻断** | 4 | 会在真实使用中直接产生错误结果或让服务不可用 |
| **P1 重要** | 5 | 不影响「跑通」，但决定它是不是一个能用的产品 |
| **P2 工程** | 6 | 体验、成本、可维护性 |

**一句话结论**：v1 的**提示词工程做得相当好**（四版对照、确定性检查、修复重试，这套在 2026 年仍然是正确做法），
但它停在了「一个能跑的单节点 demo」——**缺的是把 LLM 之外的工程补齐**：持久化、显式学生模型、可解释判题、质量量化、可观测性、失败路由。

这正好对应 138 份工业落地报告的共同结论：**决定 agent 能否上生产的 80% 不在提示词，在外围工程。**

---

## 二、P0 级发现

### A1 · 判题用字符串相等，正确答案会被判错

**位置**：`api.py:83-105` `_judge()`

```python
if quiz.kind == "choice":
    correct = answer.strip().upper()[:1] == quiz.answer.strip().upper()
else:
    correct = _norm(answer) == _norm(quiz.answer)
```

**现象**：填空题只做「去空格 + 小写」比较。以下都是数学上正确、但会被判错的答案：

| 标准答案 | 学生答案 | v1 判定 | 是否正确 |
|---|---|---|---|
| `0.5` | `1/2` | ❌ 错 | ✅ 对 |
| `0.5` | `50%` | ❌ 错 | ✅ 对 |
| `x=3` | `3` | ❌ 错 | ✅ 对 |
| `√2` | `1.414` | ❌ 错 | ✅ 对 |
| `A` | `选A` | ❌ 错 | ✅ 对 |
| `3` | `$3$` | ❌ 错 | ✅ 对 |

**为什么这是 P0**：教学产品里「答对了被判错」比「答错没被发现」更伤——学生会直接失去信任。

**修法**：`judge.py` 改为五层判定（选项字母 → 归一化文本 → 数值等价 → LLM 语义等价 → 兜底），
每层结果写进 `Judgement.layer` 便于统计。实测见 `tests/test_judge.py`（17 个用例）。

### A2 · 会话存在内存里，重启即丢

**位置**：`api.py:219` `graph.compile(checkpointer=MemorySaver())`

**现象**：`MemorySaver` 是官方定位为「仅实验用」的实现。FastAPI 一重启、机器一休眠，全部会话丢失；
`README.md:80` 自己写了这一点但没有修。

**修法**：`graph.py` 改用 `SqliteSaver`（`data/checkpoints.sqlite`），并加了一个「换实例仍能读到同一 thread」的回归测试
（`tests/test_graph_flow.py::test_state_is_persisted_across_graph_instances`）。

### A3 · 教学失败后仍被固定边推下去，前端收到「空题」

**位置**：`api.py:208-219` 的建图逻辑

```python
graph.add_edge("teach", "quiz")     # 无条件边
graph.add_edge("quiz", "wait")
```

**现象**：`teach_node` 失败时返回 `{"status": "error"}`，但固定边不关心 status，图继续走到 `quiz`（也失败）→ `wait` → **在当前状态下触发 interrupt**。
前端拿到的不是错误，而是一个 `quiz: null` 的「请作答」——学生面对一道空题，且没有任何报错。

**修法**：`graph.py` 在 teach/quiz 之后都改成条件边，错误直接路由到 `END` 并带上结构化 `error`；
另加 `degrade` 节点处理预算耗尽。测试：`test_teaching_failure_routes_to_end_not_to_interrupt`。

### A4 · LLM 异常会抛穿整条链

**位置**：`node.py:82-83`、`quiz_node.py:112-113`

```python
for attempt in range(1, max_repairs + 2):
    raw, usage, latency_ms = client.chat_json(messages, temperature=temperature)
```

**现象**：`client.chat_json` 内部虽然重试 3 次，但最终仍会 `raise LLMError`。这一行没有 try/except，
异常直接冒到 FastAPI 层，500 且没有降级路径；图状态停在半途。

**修法**：`node.py` / `quiz_node.py` 把调用包进 try/except，转成结构化失败并计入重试；
耗尽后返回 `NodeResult(response=None)`，由图的错误边收口。

---

## 三、P1 级发现

### B1 · 没有显式学生模型，跨会话等于失忆

**位置**：`api.py:21` `MAX_HISTORY_TURNS = 20`、`TutorState.history`

**现象**：学生的全部状态就是 20 条对话文本。换一天、换一个 thread，系统不知道这个学生哪里薄弱、错过什么题。
而 checkpointer 是 **thread 级**的，天生不跨会话。

**修法**：`student.py` 建独立 SQLite 表（`student_kp` + `mistakes`），
掌握度用 Laplace 平滑（0 次尝试 = 50%，不是 100%），答错自动入错题本、答对自动销账；
`graph.py` 把「最薄弱的三个知识点 + 最近错题」压成一句 `learner_note` 注入提示词——
**给模型的是结论，不是历史**。

### B2 · 没有质量量化，「跑通了」被当成「教得好」

**位置**：只有 `checks.py`（确定性问题清单），没有打分

**现象**：`eval.py` 的 PASS 定义是「有输出且无 issue」，这是一个 0/1 信号；无法回答「这一版比上一版好多少」，
也无法在演示时给学生一个可信的掌握度反馈。

**修法**：`scoring.py` 用 6 维确定性 rubric（结构合规 30 / 长度 15 / 术语友好 20 / 例子具体 15 / 互动设计 10 / 诚实标注 10，
重试额外扣分），分数可复现、扣分能指到具体句子。测试：`tests/test_scoring.py`。

### B3 · 没有可观测性

**现象**：token、延迟只 `print` 到 stdout，落在 `runs/*.json` 里但没有汇总；
线上出问题时无法回答「哪一步慢、哪个用例总在重试」。

**修法**：`trace.py` 每节点一行 JSONL（node / attempts / tokens / latency / issues），
`aggregate()` 直接产出 p50/p95、重试数、判题分层分布；`/api/stats` 暴露。

### B4 · 没有成本上限

**现象**：`max_rounds` 只限轮数，不限 token。一轮 2 次调用、每次 2k token，10 轮就是 4 万；
一旦进入「重试风暴」没有任何刹车。

**修法**：`token_budget` 进入 state，teach 与 judge 都检查；耗尽时走 `degrade` 节点给出小结与下一步，
而不是抛错或静默中断。

### B5 · `/api/teach_turn` 不幂等

**现象**：同一个 `session_id` 再调一次，会用初始 state 重新 `invoke`，把正在等作答的会话打回第一轮。
前端重试一次就丢进度。

**修法**：`api_v2.py` 先 `get_state`，若 `status == "awaiting_answer"` 直接返回当前状态；
`teach_answer` 也加了状态校验（非 `awaiting_answer` 返回 409）。

---

## 四、P2 级发现

| ID | 位置 | 现象 | 修法 |
|---|---|---|---|
| C1 | `api.py:43-44` | 每个节点都 `LLMClient(load_config())`，每次新建连接池 | `graph.py` 用 `lru_cache` 复用单例 |
| C2 | `node.py:104-110` | 修复消息不断 append，重试越改越长 | 保留，但 `max_repairs` 默认 2 且新增 token 预算兜底 |
| C3 | `api.py` | 无流式，前端干等 12~20 s | 预留 `/api/stats`；流式留待 v2.1 |
| C4 | `api.py:317-324` | `reset` 是空实现，返回 "ignored" | 明确文档化：换 session_id；数据留在 sqlite |
| C5 | `checks.py:64-68` | 术语检查会**误报**：`JARGON_TERMS` 里的词只要出现在正文、又不在 `jargon` 表就报错，模型被迫整段重写 | v2 在评分里把这条从「阻断」降为「扣 10 分」，不再强制重试 |
| C6 | `tests/` | 只测 schema，判题/评分/图流程零覆盖 | 新增 43 个用例（判题 17 / 评分 5 / 学生模型 4 / 图流程 6 + 原 11） |

**C5 的实测证据**：在构造测试用提示词时，仅仅因为正文出现了「瞬时」二字，`check_turn` 连续 3 次判失败，
`run_teaching_node` 跑了 3 次调用才罢休——**一次本可避免的 3 倍成本**。这类「检查器制造的重试」是长尾成本的主要来源。

---

## 五、能力对照

| 能力 | v1 | v2 |
|---|---|---|
| 四版教学模式（A/B/C/D） | ✅ | ✅ 保留 |
| 确定性检查 + 修复重试 | ✅ | ✅ 保留 |
| 会话持久化 | ❌ 内存 | ✅ SQLite |
| 跨会话学生模型 | ❌ | ✅ 掌握度 + 错题本 |
| 判题 | 字符串相等 | 五层等价（含数值/LLM 兜底） |
| 质量分数 | ❌ | ✅ 6 维 rubric |
| 结构化追踪 | ❌ | ✅ JSONL + 聚合 |
| 成本上限 | ❌ | ✅ token 预算 + 降级 |
| 失败路由 | ❌ 固定边 | ✅ 条件边 + 结构化错误 |
| 幂等 | ❌ | ✅ |
| 测试覆盖 | 11 个（仅 schema） | 43 个（含图流程） |
| 前端接口 | 3 个 | 3 个兼容 + 3 个新增 |

---

## 六、保留判断

以下是我**没有改**的地方，以及理由：

1. **四个教学模式保留**。A/B/C/D 是产品差异化的来源，不该在架构升级中被削平。
2. **不加子图、不加多 agent**。5 周内、一个人维护，子图只会同时拿走可观测性和 interrupt 的简单性；
   教学流程本身是确定的，属 Anthropic 定义的 workflow，用确定性边是对的。
3. **不用 Dify/Coze 重构**。它们能白送前端，但做不出「知识点掌握度 + 自适应出题」，
   而且 DeepSeek 结构化输出在 Dify 上有已知回归（discussion #36000）。
4. **暂时不做流式**。Streamlit/Next 前端改动面大，收益排在「判题正确率」之后。
