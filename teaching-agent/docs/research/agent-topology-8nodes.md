# 七个 Agent 的拓扑与消息契约

> 适用项目：`第一版UI_ex_v2/backend`（现有 teach + quiz + wait + judge 四节点）
> 目标：把「每个人各做一个 agent，做完再连线」这件事变成**可并行的工程**，而不是后期返工。
> 时间：2026-11-01

---

## 0. 一句话范式

> **Hub-and-Spoke + 契约消息：主 agent（hub）独占会话状态与记忆；每个能力节点是 `输入契约 → 输出契约` 的纯函数；能力节点之间永不直连。**

这条范式解决了三个问题：
1. **连线不爆炸**：N 个 agent 不是 N² 条边，而是 N 条边全部指向 hub。
2. **可独立开发**：只要契约不变，5 个人可以并行做 5 个 agent，互不阻塞。
3. **上下文不串味**：每个 agent 只看到自己被允许看到的东西（你现在的 `_quiz_request` 就是这件事）。

---

## 1. 先判断「传什么」，再决定「怎么传」

所有 agent 之间的信息，只有三种形态：

| 形态 | 体积 | 例子 | 传法 |
|---|---|---|---|
| **A. 控制信号** | < 200 字 | 答对/答错、继续/结束、下一轮 | 直接放进 State 字段 |
| **B. 结构化产物** | 1–10 KB | 题目 JSON、错题条目、掌握度表、计划 | Pydantic 对象进 State；超过 50KB 存 artifact 传引用 |
| **C. 原始上下文** | 10 KB+ | 对话历史、教材原文、学生作答 | **永远不复制**：要么共享（同一 State），要么压成摘要，要么传 id |

**最容易犯的错是 C 当 B 传**：把 20 轮对话塞进 `student_message` 里交给下一个 agent。你现在没犯这个错（`_quiz_request` 的 `history=[]` 就是防线），扩到 7 个 agent 时要守住。

---

## 2. 八条技术路径（按耦合度从紧到松）

| # | 路径 | 机制 | 什么时候用 | 代价 |
|---|---|---|---|---|
| 1 | **纯函数调用** | `run_quiz_node(req, text, client)` | 90% 的场景。输入确定、输出确定 | 零成本，最好测 |
| 2 | **共享 State** | 同一张 `StateGraph` 的 `TutorState` | 主链路：teach → quiz → judge | State 会膨胀，需 reducer / trim |
| 3 | **子图 + private channel** | `add_node(compiled_subgraph)`，只桥接指定 key | 某个 agent 的中间过程很脏（多轮工具调用） | 调试看不见内部状态，interrupt 易错 |
| 4 | **agent-as-tool** | 把子 agent 包成 tool 给 LLM 调 | 让主 LLM 自己决定何时出题/何时复盘 | 不可预测（可能不调、可能连调） |
| 5 | **handoff（移交）** | `transfer_to_xxx`，控制权转移 | 客服式「分诊 → 专家」 | 默认**带走全部历史**，想隔离要显式 filter |
| 6 | **Send / map-reduce** | 条件边返回 `Send("judge", {...})` | 一次判 20 道题、并行生成 3 个难度档 | 只在真需要并行时用 |
| 7 | **队列 / 事件总线** | Redis Streams / Inngest / Celery | 跨进程、长任务、失败重试、削峰 | 引入运维；**5 周内不需要** |
| 8 | **网络协议** | MCP（agent→工具）、A2A（agent↔agent）、HTTP | 换机器、给第三方用、复用生态 | 跨进程才有意义 |

**你的情况该选哪条？** 1 + 2，个别地方用 6。3 和 5 现在不要碰，7 和 8 现在不要碰。

---

## 3. thread 到底是什么（这条必须纠正）

你现在写的是：

```python
config = {"configurable": {"thread_id": session_id}}
```

**这是对的**，但理解要改一下：

> `thread_id` 不是「agent 的记忆开关」，而是 **checkpoint 的隔离键**，也就是「一次会话」的主键。
> LangGraph 里所有 history / state / interrupt 恢复，都挂在这个键下面。

所以：

| 你想表达的 | ❌ 错误做法 | ✅ 正确做法 |
|---|---|---|
| 出题 agent 不需要记忆 | 给它单独开一个 thread，用完丢掉 | **不给它 checkpointer，它就是纯函数**（你现在就是这样） |
| 主 agent 要记住整个会话 | 把历史存在自己变量里 | 一个会话一个 `thread_id`，状态由 checkpointer 管 |
| 换个学生要重新开始 | 复用同一个 thread | 换 `thread_id` |

**「用完即消的 thread」是反模式**，会带来三个真实问题：
1. 每次调用都新建/删除 checkpoint，白付存储和延迟；
2. `interrupt` 的 resume 值绑定在 thread 上，容易串号（官方 issue 高发区）；
3. trace 会碎成 N 段，出问题时没法回放整条链。

**结论**：一个辅导会话 = 一个 thread。agent 记不记忆，由**你喂给它什么上下文**决定，不由 thread 决定。

---

## 4. 拓扑：8 个节点，全部绕 hub

```
                         ┌──────────────────────────┐
                         │   tutor（hub / 主 agent）  │
                         │   持有 thread + 学生档案    │
                         └────────────┬─────────────┘
                                      │  单向调用（输入契约 → 输出契约）
   ┌──────────┬──────────┬────────────┬──────────┬──────────┬──────────┐
   ▼          ▼          ▼            ▼          ▼          ▼          ▼
diagnose    plan       teach         quiz      judge      recap    summarize
(摸底)     (规划)      (讲)          (出题)     (判分)     (复盘)    (压缩)
   │          │          │            │          │          │          │
   └──────────┴──────────┴────────────┴──────────┴──────────┴──────────┘
                                      │
                                      ▼
                              formatter（卡片，确定性）
```

**铁律**：能力节点之间**没有边**。`quiz` 不知道 `teach` 的对话历史，`teach` 看不到题目和答案——它们各自只和 hub 交换契约。

### 节点清单

| # | 节点 | 类型 | 读什么（输入） | 产出（输出） | 需要记忆 |
|---|---|---|---|---|---|
| 1 | `tutor` | hub（编排） | 学生消息 + 会话 State | 路由决策 | ✅ 整个会话 |
| 2 | `diagnose` | LLM | topic / level / 探针作答 | `KpStatus[]` 初值 | ❌ |
| 3 | `plan` | LLM | `KpStatus[]` + 目标分数 | `PlanStep[]` | ❌ |
| 4 | `teach` | LLM | 主题 + 学段 + **画像摘要** + 近 3 轮 + 本轮学生话 | `TeachingTurn` | ⭕ 近 3 轮 |
| 5 | `quiz` | LLM | **当前教学正文** + 本轮学生话 | `QuizQuestion` | ❌（history=[]） |
| 6 | `judge` | 确定性 | `QuizQuestion` + 学生答案 | `Judgement` | ❌ |
| 7 | `recap` | LLM | 本轮错题 + 讲解要点 | `MistakeEntry[]` | ❌ |
| 8 | `summarize` | LLM | 长对话（>20 轮时触发） | `SessionSummary` | ❌ |
| — | `formatter` | 确定性 | `QuizQuestion` / `TeachingTurn` | UI 卡片结构 | ❌ |

**5 个 LLM 节点 + 3 个确定性节点**。判分、卡片、进度计算不要做成 agent——它们没有「判断」，只有「计算」。
（你现在的 `_judge` / `_quiz_card` 就是确定性函数，这是对的，别改。）

---

## 5. 消息契约（先定这个，再写 agent）

建议新建 `backend/contracts.py`，把「谁能给谁什么」写成类型。**契约是 5 个人并行的唯一接口**。

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

# ---------- 画像：跨会话，唯一允许长期存在的东西 ----------
class KpStatus(BaseModel):
    """单个知识点的掌握状态。确定性结构，LLM 只负责更新，不负责记住。"""
    kp: str = Field(..., description="知识点 id，如 'derivative/chain-rule'")
    mastery: float = Field(0.0, ge=0, le=1)
    attempts: int = 0
    last_seen: str = ""          # ISO 时间
    last_error: str = ""          # 最近一次错的根因（一句话）

class StudentProfile(BaseModel):
    student_id: str
    target_score: int = 90
    kp_status: dict[str, KpStatus] = {}
    # 刻意不放对话历史：历史属于 thread，不属于画像

# ---------- 节点间契约 ----------
class TeachIn(BaseModel):
    topic: str
    level: str
    profile_digest: str          # 画像压缩成 ≤300 字，不传整个 dict
    recent_turns: list[dict]     # 只传近 3 轮
    student_message: str

class TeachOut(BaseModel):
    reply_markdown: str
    core_idea: str
    check_question: str
    # 刻意不含 quiz 相关字段

class QuizIn(BaseModel):
    teaching_text: str           # 只读本轮正文
    student_message: str
    level: str
    weaker_points: list[str] = []  # hub 挑给它的薄弱点，不让它自己猜

class QuizOut(BaseModel):
    stem: str
    options: list[str] = []
    answer: str
    explanation: str
    source_quote: str            # 必须来自 teaching_text（你已有这条校验）
    difficulty: Literal["easy", "normal", "hard"] = "normal"

class JudgeIn(BaseModel):
    quiz: QuizOut
    answer: str

class Judgement(BaseModel):
    correct: bool
    correct_answer: str
    feedback: str
    error_type: Literal["concept", "computation", "misread", "skip"] | None = None
    kp: str | None = None

class RecapIn(BaseModel):
    judgement: Judgement
    teaching_text: str
    student_message: str

class MistakeEntry(BaseModel):
    concept: str
    user_flaw: str
    key_insight: str
    kp: str = ""
```

**hub 里唯一允许流转的东西**：

```python
class TutorState(TypedDict, total=False):
    # 会话层（checkpoint 里）
    session_id: str
    student_id: str
    round: int
    recent_turns: list[dict]        # 近 3 轮，不是全部
    teaching: TeachOut | None
    quiz: QuizOut | None
    judgement: Judgement | None
    pending_mistakes: list[MistakeEntry]
    # 只看不写（由 Store 提供，不进 checkpoint）
    profile_digest: str
```

**规则**：`teach` 不接受 `quiz`；`quiz` 不接受 `recent_turns`；`judge` 不接受 `topic`。
每加一条违反这条的边，就多一份「出题按泰勒、讲课按洛必达」的耦合。

---

## 6. 立刻能做的三步（每步都省后面的时间）

### 第 1 步：把两份重复代码抽成一个 node runner（半天）

`node.py:60-155` 和 `quiz_node.py:112-213` 结构 95% 相同：调 LLM → 抽 JSON → LaTeX 修复 → Pydantic 校验 → 跑 checks → 修复环。

```python
def run_structured_node(
    *,
    system_prompt: str,
    user_prompt: str,
    client: LLMClient,
    schema: type[BaseModel],
    checks: Callable[[BaseModel], list[str]] | None = None,
    preprocess: Callable[[dict], dict] | None = None,   # quiz 的 LaTeX 修复从这进
    max_repairs: int = 2,
    temperature: float = 0.3,
) -> NodeResult[BaseModel]: ...
```

新增第 3、4、5 个 agent 时，每个只需要写 **prompt 构造函数 + checks + schema**，约 60 行，而不是 200 行。

### 第 2 步：`MemorySaver` → `SqliteSaver`（10 分钟）

`api.py:13,263` 现在是 `MemorySaver()`：uvicorn 一重启，学生会话全丢——你做 UI 调试时一定踩过这个。

```python
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3, pathlib

pathlib.Path("data").mkdir(exist_ok=True)
CONN = sqlite3.connect("data/checkpoints.db", check_same_thread=False)
GRAPH = builder.compile(checkpointer=SqliteSaver(CONN))
```

已在本机验证：`langgraph 1.2.6` + `langgraph-checkpoint-sqlite 3.1.3` 可用，thread 隔离正常（同一 db 两个 thread 互不影响）。

### 第 3 步：加学生档案表（半天）

```sql
CREATE TABLE IF NOT EXISTS student (
  student_id TEXT PRIMARY KEY,
  profile_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

`schema` 用上面的 `StudentProfile`。**掌握度、错题永远不进 checkpoint**——它在 thread 里，天生不跨会话；学生明天再来就什么都忘了，这是教育产品最贵的一种 bug。

---

## 7. 你现在的代码里，哪些已经是对的（别动）

| 位置 | 做法 | 为什么对 |
|---|---|---|
| `api.py:73-83` | `_quiz_request` 里 `history=[]` | 上下文隔离做对了：出题只看本轮正文 |
| `api.py:229-234` | judge 只回传「答对/答错」最小信号 | 防止出题/判分的隐式决策污染教学 |
| `api.py:202-210` + `482` | `interrupt()` + `Command(resume=...)` | HITL 用对了，这是很多团队做不出来的 |
| `node.py:82-144` | Pydantic 校验 + `json_repair` + 修复环 | 生产级结构化输出 |
| `quiz_node.py:44-76` | LaTeX 反斜杠修复 | 踩过坑才写得出来的代码 |
| `quiz_node.py:98-101` | `source_quote` 必须在教学正文里 | 防幻觉硬约束，很专业 |
| `quiz_node.py:83-109` | 出题质量 checks（多问句/多选/答案过长/low confidence） | 这就是「agent 只负责把自己的事做好」 |
| `api.py:374-436` | `/api/agents` 把每个 agent 的输入/输出/约束列出来 | 契约可视化的雏形，值得保留 |

## 8. 需要改的（按性价比排序）

| 优先级 | 位置 | 问题 | 改法 |
|---|---|---|---|
| P0 | `api.py:170-178` | 假打字机：整段生成完再 `time.sleep` 切片 | 真流式（LLM stream）+ 前端打字动画；否则首字延迟 = 全量生成时间，且同步 def 会占满线程池 |
| P0 | `api.py:13,263` | `MemorySaver` | `SqliteSaver` |
| P1 | `api.py:103-132` | `_judge` 只做字符串归一化 | `x=2` vs `2`、`\frac{1}{2}` vs `0.5` 会误判；用 sympy 做数学等价 |
| P1 | `teaching_history` 20 轮 ×1600 字 | 每轮全量传，成本线性涨 | `summarize` 节点：>8 轮压成摘要 |
| P2 | `_payload` / `_quiz_card` | UI 结构与业务逻辑混在一个文件 | 抽 `formatter`，前端只认卡片 schema |
| P2 | `AGENT_SPECS` 每次请求读磁盘源码 | 把源码暴露给前端 | 启动时读一次缓存；生产环境关掉 |

---

## 9. 怎么让 5 个人真的能并行

你现在已经有的资产：`compare.py` + `eval_cases.py` + 四版对照（variant B 胜出）。**这是整个项目最值钱的方法论**，把它变成制度：

1. 每个 agent 一个目录：`agents/teach/{prompt.py, node.py, checks.py, schema.py, cases.jsonl}`
2. `cases.jsonl` 是**验收标准**：10 条输入 + 期望的硬约束（不是期望的完整输出）
3. 每个 PR 必须跑 `pytest agents/<name>/test_contract.py`：schema 能构造、checks 能过、错误输入有正确兜底
4. 谁改契约，谁负责跑全量 `eval/`：`python -m eval.run --all`，输出 pass rate 与 token 成本
5. 契约（`contracts.py`）由一个人守门，任何改动都要 review——**这是 5 个人唯一会打架的地方**

---

## 10. 一句话总结

> 你现在的两个 agent 已经是**正确的范式**（hub + 契约 + 单向 + 隔离），只是还没起名字。
> 接下来不是「再写 5 个 agent」，而是**先把契约和 runner 抽出来**，让第 3～8 个 agent 各用半天就能长上去。
