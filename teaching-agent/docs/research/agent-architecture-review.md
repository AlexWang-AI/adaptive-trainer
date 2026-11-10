# 考研数学 AI 私教 · LangGraph 五节点方案架构评审

> 评审对象：第六届厦大 AI 挑战赛「自航智学 · 自主学习规划系统」设计方案（赛道二 Agent 创新赛）
> 评审时间：2026-11-01 ｜ 证据口径：LangChain / Anthropic / OpenAI / Microsoft 官方文档 + Cognition 工程博客 + Chroma 受控实验
> 配套文件：`multi-agent-2026-research.md`（行业范式与框架选型调研，含全部 star/版本实测）

---

## 一、结论先行

| # | 判断 | 一句话理由 |
|---|---|---|
| 1 | 「5 个角色做成 5 个节点」没问题；**叫它们 5 个 agent 是概念错位** | 这是 Anthropic 定义里的 **workflow**（预定义代码路径），不是 agent。当成 agent 才引出后面一堆过度设计 |
| 2 | 「先做节点 → 再分层子图 + 上下文隔离」方向可以，但**顺序讲反了** | 2026 共识是「先单图跑到好用，再因为**测得出来**的理由拆分」 |
| 3 | **上下文隔离在教育场景会伤害效果**——伤害来自「隔离 + 没有跨会话的显式学生模型」 | 子图默认 per-invocation 不记忆；教育恰恰是跨会话遗忘最贵的场景 |
| 4 | 最该删：auditor 的 agent 身份、90 分 LLM 打分、现在做 subgraph、「MAX_CYCLES 自研熔断」 | 见第五节 |
| 5 | 最该补：显式学生模型（Store）、确定性题库 + 知识点图、第 1 周接 trace、20~30 条真实错题评测集、熔断后的降级路径 | 5 周里这些决定成败，架构不决定 |
| 6 | 替代方案中最省力：(a) workflow-first；其次 (b) Deep Agents；(c)(d)(e)(f) 不建议 | 见第三节 |

**最需要先改变的一句话**：5 周的真正瓶颈是**题库、判分标准、学生模型**这三件「数据 + 确定性逻辑」的事。五个节点、子图、上下文隔离，都发生在瓶颈之外。

---

## 二、哪里对、哪里险、哪里过度

### ✅ 真正对的（三条）

1. **固定边的主链路是对的。** 教育主流程本质确定：诊断→教→练→反馈→验收。用确定性边而非 LLM 自主路由，可预期、可演示、可评测（官方 workflow 模式：prompt chaining / routing / evaluator-optimizer）。
2. **「节点只返回增量状态」是对的**，且是 LangGraph 官方语义（返回 update 由 reducer 合并），不是你们的发明。
3. **「诊断→练习→未达标回炉」是标准 evaluator-optimizer 模式**（生成器 + 评估器 + 条件边回退）。

### ⚠️ 有风险（按严重度）

**风险 1：`dialogue_history` 放 State 会持续膨胀。**
checkpointer 默认在**每个 super-step 把每个 channel 的完整值写一遍**，官方明确警告长线程会造成显著存储增长；缓解手段 `DeltaChannel` 仍是 beta。你们的意图（不把整段对话反复塞进 prompt）对了一半——省了 token，没省 checkpoint。真正解法是 `trim_messages` / 摘要 + 长期信息挪到 Store。

**风险 2：固定边 + 条件边混用在同一个节点上，是官方明令禁止的坑。**
> "For each node, choose one routing mechanism … **Do not mix** normal edges and dynamic routing from the same node, because both paths can execute."

你们的「教学→练习→反馈→验收」是固定边，「未达标回到教学或练习」是条件边。若写在同一个节点出口上，**两条边都会跑**。这是演示前一周最典型的 bug。

**风险 3：`MemorySaver`（现名 `InMemorySaver`）会在开发期反复害你们。**
官方定位：`InMemorySaver` 仅用于 experiment；SQLite 用于本地工作流；Postgres/Mongo 才谈生产。Streamlit 每次 rerun、每次热重载都会丢进程内存 → 学生状态全丢。**这不是「生产才换」，第 1 天就该换 `SqliteSaver`**（改 2 行）。

**风险 4：自研 `MAX_CYCLES=15` 不解决真问题。**
LangGraph 自带 `recursion_limit`（1.1.4 起默认 10,007）+ `RemainingSteps` + `GraphRecursionError`，官方给了 proactive（图内降级）与 reactive（外部 catch）两种模式。自研计数器数的是「循环次数」，不是「花了多少钱 / 多长」；而且**熔断之后走哪条路你们没写**——15 次之后学生看到什么？这是演示事故点。

### 🔴 过度设计（三条）

1. **auditor 做成独立 agent 是过度设计。** 「90 分验收」本质是**评测函数**。Anthropic 的经验：单次 LLM 调用 + rubric 分项打分（0.0–1.0）+ pass/fail，「最一致、最贴近人类判断」，多 judge 反而更差。
   → 而且「90 分」这个数字在教学上不可复现：同一份答案跑两次可能是 84 也可能是 93。应改成**分项 rubric + 二值门槛**（如：知识点覆盖 ≥3/4 且无计算错误 → pass）。
2. **「未来做分层子图」写进计划就是过度设计**——当前没有任何测出来的动机。官方列的三条 multi-agent 动机是：上下文管理、分布式开发（不同团队）、并行化。**5 人、5 周、单流程，一条都不占。**
3. **把「上下文隔离」当架构目标是过度设计。** 隔离是手段。Deep Agents 文档明确写了 subagents 的适用条件（多步任务把主上下文弄脏）与**不该用的场景**（单步任务、需要保留中间上下文、开销大于收益）。私教场景是「单学生 + 长会话 + 高依赖」，正落在「不要用」那一格。

### 🎯 上下文隔离在教育场景到底会不会伤效果？会，机制很具体

**第一层：官方默认行为就是「健忘」。**
| 子图编译参数 | 行为 | 教育含义 |
|---|---|---|
| `checkpointer=None`（默认） | 每次调用全新开始 | 讲完「极限」练完「导数」，下次进来不知道极限薄弱 |
| `checkpointer=True` | 同 thread 累积 | 只在一个 thread 内记得，换天/换会话就断 |
| `checkpointer=False` | 完全无 checkpoint | 无 interrupt、无恢复 |

**第二层：教育是跨会话问题，而 thread 是会话级的。**
LangGraph 的长期记忆必须用 **Store**（namespace 级、跨 thread），不是 checkpointer。
> **掌握度、错题、薄弱点放 checkpointer = 放错地方了。**

**第三层：反面证据更强。** Anthropic 明确说 multi-agent 只适合「广度优先、可并行、相互独立」的任务，而**「需要所有 agent 共享同一份上下文、或 agent 间依赖很多的领域不适合」**。Cognition 的原则更硬：共享完整 trace；动作携带隐式决策。Claude Code 的子 agent「从不与子 agent 并行工作，通常只被派去回答问题，不写代码」。

**教学正是「依赖极多、必须共享上下文」的领域**：老师讲的解法、学生犯的错、出题人意图、判分标准——四份上下文一旦被隔离进四个窗口，就会出现经典失败：讲的时候按洛必达，出题按泰勒，判分按等价无穷小，三份各自自洽，合起来是灾难。

**公平地说**：隔离有一种正确用法——**并行、无状态、一次性的重活**，如「一次给 20 道题打分」「并行生成 5 个难度档」。这类用 `Send` API 更合适，不需要子图。

**结论**：不要为「架构先进」做隔离，要为「上下文确实会脏」做隔离。你们的脏源只有一个——长对话历史，解法是摘要 + 外置记忆。

---

## 三、LangGraph 官方用法与已知坑

### subgraph

两条通信路径：**节点内调用子图**（父子 state schema 不同 key，需手写 wrapper）／**把子图当节点加入**（共享 key）。

已知坑（均出自官方文档）：
1. **namespace 按调用顺序分配** —— 重排调用顺序会串状态。修法：每个 subagent 包独立 `StateGraph` 并给唯一 node name。
2. **per-thread 子图不支持并行工具调用** —— LLM 并行调同一个子图工具会造成 checkpoint 冲突，必须显式禁用。
3. **子图状态可视化有前提** —— 必须能静态发现子图；「在工具函数里调用子图」时**看不到内部状态**。对 5 周团队这是致命的可观测性损失。
4. `Command(graph=Command.PARENT)` 跨层跳转时，共享 key 必须在父图定义 reducer。

### checkpointer

- `thread_id` 是主键，不传无法持久化、无法 resume interrupt。
- 三种 durability：`exit` / `async`（默认）/ `sync`。任何模式下**首个 checkpoint 落盘前崩溃，线程视作从未调用**。
- `update_state` 会走 reducer，对 `operator.add` 的 channel「清空」无效，必须用 `Overwrite` —— 错题本 / 错误缓冲区最容易踩这个。

### interrupt（你们最该用但没提的机制）

| 规则 | 说明 |
|---|---|
| 节点**从头重跑** | resume 不是从 `interrupt()` 那行继续，而是整节点重执行 |
| **不要** try/except 包 `interrupt()` | 它靠抛异常暂停，会被吞掉 |
| resume 值按**索引**匹配 | 多次 `interrupt()` 必须顺序稳定，条件跳过会错位 |
| **禁止** `while True` + `interrupt()` | 第 n 次 resume 会重放 n 次迭代，用条件边重入 |
| interrupt 前的副作用必须**幂等** | 否则每次 resume 插一条重复记录 |
| `Command(resume=...)` 是唯一该传给 `invoke()` 的 Command | 传 `update=` 会「resume 到最后 checkpoint」，图看起来卡死 |

**给 Streamlit 前端的捷径**：`response_schema` 可让 Studio 渲染带类型的输入表单；interrupt + 子图是官方 issue 高发区（如 #4523、#2870）——**用 interrupt，但别在子图里用**。

### Send API

用于动态 fan-out / map-reduce。对你们：❌ 不用来拆 5 个角色；✅ 用来「一次 20 道题并行判分」「同知识点并行生成 3 个难度档」。这是唯一真正需要并行的地方。

### 共享大 State vs 每节点独立 State

| 维度 | 共享大 State | 独立 State（subgraph / private schema） |
|---|---|---|
| 上手成本 | 低 | 高 |
| 可观测性 | 高（`get_state` 一把梭） | 低（需 `subgraphs=True`，工具内调用不可见） |
| 接口清晰度 | 低 | 高 |
| 并行安全 | 需 reducer | 天然隔离 |
| 流式泄漏 | private channel 不会自动隐藏，需 `output_keys` | 天然不外泄 |
| interrupt 语义 | 简单 | 易错 |

**建议**：一张共享 State + 少量 private channel + 显式 reducer。你们 5 周内接口一定会变，而子图同时拿走可观测性和 interrupt 的简单性——这两样在演示前一周价值最高。

---

## 四、替代方案取舍

| 方案 | 何时更合适 | 对你们 | 迁移成本 |
|---|---|---|---|
| **(a) workflow-first：单图 + 工具 + 确定性流程** | 流程确定、要可演示可评测、团队小、时间短 | ⭐ 最合适 | **≈0.5–1 人日**（保留 5 节点，删 3 样东西，加 Store） |
| **(b) LangChain Deep Agents** | 想要现成 harness：planning / 虚拟文件系统 / subagents / skills / 摘要 / offload / HITL | ⭐ 次优，skills + memory 正好对应「教学方法库 + 学生档案」 | 中，≈3–5 人日 |
| (c) Claude Agent SDK subagents + skills | 全押 Anthropic、需要沙箱内执行 | ⚠️ 模型锁定 Claude，**你们用 DeepSeek 直接出局** | 高 |
| (d) OpenAI Agents SDK handoffs | 客服式分诊→专家、单 run 内交接 | ⚠️ 语义相反：handoff 默认**带走全部历史** | 中高 |
| (e) Microsoft Agent Framework graph | .NET / Azure / 类型化 executor + superstep | ⚠️ 与 LangGraph 高度同构，迁移是纯成本 | 高 |
| (f) Dify / Coze 低代码 | 演示优先、非技术人员维护 | ⚠️ 能做 demo，做不出「学生模型 + 自适应出题」 | 低上手 / 高天花板 |

**Deep Agents 的关键细节**：subagents 有 `mode: "isolated"`（只给任务描述）与 `mode: "fork"`（继承父对话，beta）。**教育场景里，判分 agent 适合 fork（要看到老师讲了什么），出题 agent 适合 isolated（不该被学生的话带偏）**——这比「全部隔离」精确得多。

---

## 五、可直接用的环境 / 插件

| 工具 | 解决什么 | 不解决什么 | 5 周内值不值 |
|---|---|---|---|
| **Langfuse**（自建或云） | 完整 trace：prompt / 响应 / token / 延迟 / 工具调用；异步上报不加延迟；自带 LLM-judge、prompt 管理、数据集实验 | 不解决「学生为什么学不会」；不替代自己的评测集 | ⭐⭐⭐ **第 1 周就接**（一个 decorator） |
| **MCP** | 工具生态标准（「AI 的 USB-C」），一份 server 到处接 | **不解决工具质量**：描述写得烂会把 agent 带沟里 | ⭐⭐ 少量用（题库 / 公式 / 计算器） |
| **LangGraph Agent Server**（原 Platform） | 现成后端：threads / runs / cron / durable queue / SSE；自动注入 checkpointer 与 store | 不解决产品逻辑；自建要 PG + Redis | ⭐ 演示前别碰 |
| **Deep Agents Code（`dcode`）** | 终端 coding agent，含 memory / skills / 子 agent / MCP / tracing / HITL 审批 | 是**给你们写代码用的**，不是产品运行时 | ⭐⭐ 团队开发加速器 |
| **vibe-kanban** | 「计划与评审 AI agent 工作」的看板，支持 Claude Code / Codex / Gemini CLI 等，可自建 | 只管代码 agent 编排，与产品运行时无关 | ⭐⭐ 5 人并行开发防 git 冲突 |
| **E2B / Daytona** | 云端沙箱，跑 agent 生成的代码 | 考研数学不跑学生代码 | ❌ **伪需求，删掉** |

---

## 六、5 周 / 5 人 / 要能演示的最小可行架构

```
Streamlit (chat)  ── thread_id = st.session_state["tid"]
        │  invoke / stream_events
        ▼
ONE StateGraph · SqliteSaver（Day 1 就换）· recursion_limit=25 · RemainingSteps 兜底
State（一张 TypedDict）
 ├─ messages:    Annotated[list, add_messages]   ← 只留近 N 轮 + 摘要
 ├─ student_id:  str                              ← Store 的 namespace key
 ├─ kp_status:   dict[kp -> {mastery, attempts, last}]
 ├─ wrong_book:  Annotated[list, add]             ← 去重靠 tool
 ├─ plan:        list[kp]                         ← 诊断产出
 ├─ current_item:{kp, difficulty, question, answer}
 ├─ grade:       {score, rubric{}, errors[]}
 └─ _scratch:    PrivateState（不进 stream，配 output_keys）

START → [① diagnostic 诊断/规划（LLM + 题库探针 ≤5 题）]
      → [② teacher 讲解（读 kp_status + 最近 2 轮）· interrupt()「懂了没？」]
      → [③ practice 取题（确定性：题库按 kp+difficulty 抽，可 Send 并行判分）]
      → [④ correction 判分 + 更新 kp_status + 错题本]
                └─ 唯一允许动态路由的节点：
                   pass(二值门槛) → END ｜ partial(换简单题) → practice ｜ fail(回炉) → teacher

外挂：Store（跨会话：掌握度历史 / 错题 + 根因 / 有效讲法偏好）
      Langfuse trace（第 1 周接）
      确定性题库 + 知识点图（JSON/SQLite，不是 LLM）
```

关键决定与理由：

| 决定 | 理由 |
|---|---|
| **4 个节点而非 5 个** | auditor 合并进 correction：判分 = 评估 + 归因 |
| 只有 correction 一个节点动态路由 | 规避「同一节点混用固定边 + 条件边」的官方警告 |
| `recursion_limit=25` + `RemainingSteps` 降级 | 用官方机制替代自研计数器，且**必须写出降级路径** |
| interrupt 放 teacher 而非 auditor | HITL 的价值在「学生卡住的那一刻」 |
| 判分 = rubric(LLM) + 确定性校验 | 纯 LLM 判分会漂移 |
| 掌握度进 Store 不进 checkpointer | thread 级记忆不跨会话 |
| 不做 subgraph / 不做上下文隔离 | 5 周引入子图会同时失去可观测性与 interrupt 的简单性 |
| messages 只留最近 N 轮 + 摘要 | 避免 checkpoint 膨胀 |

### 最该删的 5 样

1. auditor 的「agent」身份 → 变成 correction 里的 rubric 函数
2. 「90 分」→ 4 项 rubric + 二值门槛
3. 「未来分层子图 + 上下文隔离」这句话（至少从 5 周计划里删）
4. `MemorySaver` → 第 1 天换 `SqliteSaver`
5. 沙箱类计划（若方案里有）

### 最该补的 5 样

1. **显式学生模型**（最高优先级）：`kp_status` 用确定性结构，LLM 只负责「更新它」而不是「记住它」。**只要学生模型是显式、结构化、跨会话的，隔离就不伤害效果；反之隔离就是灾难。**
2. **确定性题库 + 知识点图**：LLM 不该是题目来源，只在题目上做讲解与批改。这决定产品「能不能教对」，比架构重要 10 倍。
3. **Langfuse 第 1 周接上**：一个 `@observe()` 看到每次判分的完整 prompt，5 周内唯一能救命的调试手段。
4. **20~30 条真实错题评测集 + 跑分表**：早期改动 effect size 巨大（30%→80%），20 条就够看出问题。
5. **熔断后的降级路径写死在代码里**：如 `RemainingSteps<=4` → 给标准解法 + 结束会话 + 写入「未掌握」。没有这条，演示当天必然卡死。

### 一个不客气的提醒：Streamlit

Streamlit 的「整脚本 rerun」与 `interrupt()` 的「暂停-恢复」语义冲突：中断状态活在 checkpoint 里，而 Streamlit 每次交互重跑整个脚本。demo 能糊过去（`st.session_state` 存 thread_id + `stream_events` 循环 + `stream.interrupted` 判断），但「学生答题中途暂停、第二天继续」会很难看。**V1 不做跨会话中断恢复，只做会话内 interrupt**；跨会话续接交给 Store（学生模型层）。

---

## 七、一句话交付建议

> **把「5 个 agent」改成「1 张图 + 4 个节点 + 1 个显式学生模型」，auditor 降级为 rubric，上下文隔离换成「摘要 + Store」，第 1 天换 SqliteSaver 并在第 1 周接 Langfuse，剩下 4 周全部投给题库和判分标准。**
> 架构没错，只是**在错误的地方追求了复杂度**——这个项目真正的复杂度在题目和评分标准里。
