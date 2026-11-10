# 多智能体（Multi-Agent / Agentic AI）开发在 2026 年的工业化现状

**调研时间：2026 年 11 月 1 日**
**方法**：所有版本号经 PyPI / npm / GitHub Releases atom 实测；所有 star 数经 GitHub REST API 实测（2026-11-01）；所有引用 URL 均做过可达性校验（HTTP 200/308）。

### 可信度标注约定

| 标记 | 含义 |
|---|---|
| **[实测]** | 我在 2026-11-01 直接调用 API 读取的数字（star / 版本 / 许可证） |
| **[原文]** | 我完整抓取并阅读了一手文章/README |
| **未确认** | 查不到可靠一手来源，明确不猜 |

> ⚠️ 关于「2026 年业界公认」这类说法：本报告只陈述**有出处**的判断。凡属厂商自述（如 Anthropic 说 MCP 有 1 万个 server），我会标明它是厂商声明而非第三方审计。

---

## 1. 标准流程 / 范式

### 1.1 底层坐标系：workflow vs agent（2024-12 提出，2026 仍是默认起点）

Anthropic 把 agentic system 分成两类：**workflow**（LLM 与工具由预定义代码路径编排）与 **agent**（LLM 自主决定流程与工具使用）。核心建议是「先用最简单的方案，只在可证明有效时才加复杂度」。
来源：[Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)（2024-12）

值得注意：该文顶部 2026 年已加了一条**免责声明式更新**，说明「文中描述的工具体系已过时，当前做法见 Managed Agents」。这本身就是 2026 年的重要信号——**范式没变，但「谁来托管这套循环」变了**。

文中五个 workflow 模式及适用/失效场景：

| 模式 | 适用 | 已知失效 |
|---|---|---|
| Prompt chaining 提示链 | 任务可干净拆成固定子步骤，用延迟换准确率 | 子步骤间需要动态回退时，链式结构无法回跳 |
| Routing 路由 | 输入有明确类别且分类准确 | 分类器错则整条链路错，且错误不可见 |
| Parallelization 并行（分段/投票） | 子任务独立可并行；或多视角提升置信度 | 投票对**相关错误**无效——同一模型重复采样会一起错 |
| Orchestrator-workers 编排者-工作者 | 子任务数量无法预先确定（改多文件代码、多源检索） | 编排者给的子任务描述含糊 → 子 agent 重复劳动或漏做（Anthropic 自己踩过） |
| Evaluator-optimizer 评估者-优化者 | 有明确评价标准且迭代能带来可测收益 | 无客观标准时退化为「自我表扬循环」 |

来源同上 [原文]。

### 1.2 Orchestrator-worker：唯一被大规模验证的多 agent 形态

Anthropic 的 Research 系统是这个范式的公开最强证据：
- 多 agent（Opus 4 主 + Sonnet 4 子）比单 agent Opus 4 在内部 research eval 上**高 90.2%** [原文]
- 性能差异的 **80% 可由 token 用量单独解释**，加上工具调用次数与模型选择共解释 **95%**（BrowseComp）[原文]
- 成本代价：agent 比 chat 多约 **4×** token，多 agent 系统多约 **15×** token [原文]

失效场景（Anthropic 自己列出）：**需要所有 agent 共享同一上下文、或 agent 间依赖很强的领域不适合**；「大多数编码任务真正可并行的子任务比研究少」；「LLM agent 还不擅长实时协调与委派」[原文]。
另有两个工程性失效：**同步执行造成瓶颈**（主 agent 无法中途纠偏子 agent，一个子 agent 卡住全阻塞），以及**部署期间 agent 处于流程任意位置**（它们用 rainbow deployment 解决）。
来源：[How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)（2025-06）

### 1.3 Cognition 的转折：从「别做多 agent」到「写入必须单线程」

**2025-06**：《Don't Build Multi-Agents》提出两条原则——
1. 共享上下文，且共享**完整 agent trace** 而非单条消息；
2. **动作携带隐式决策**（actions carry implicit decisions），冲突的隐式决策导致坏结果。
结论：默认排除不满足这两条的架构，用**单线程线性 agent**，长上下文靠「专职压缩模型」解决。
来源：[Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents)（2025-06-12）[原文]

**2026-04**：同一作者发布后续《Multi-Agents: What's Actually Working》，这是本次调研中**信息密度最高**的一篇。核心结论修正为：

> **多 agent 系统今天能跑通的形态是：写入保持单线程，其余 agent 只贡献「智能」而非「动作」。**

具体三种已验证形态：

| 形态 | 机制 | 实测效果 / 关键发现 |
|---|---|---|
| **Generator-verifier（代码评审循环）** | 写代码 agent 与评审 agent **完全不共享上下文** | Devin Review 平均每 PR 抓 **2 个 bug，其中约 58% 为严重级**（逻辑错误、漏边界、安全漏洞）。反直觉点：评审 agent 上下文越干净效果越好，因为绕开了 Context Rot |
| **Smart Friend（弱模型调用强模型工具）** | 小模型把大模型当工具调用，**fork 全量上下文**过去 | 跨前沿模型（Claude + GPT 同时上）已在生产跑通并有实效；但「弱主模型→强辅助」失败——SWE-1.5 太弱，**不知道何时该升级咨询**。结论：这是训练问题，不是提示词问题 |
| **Map-reduce-and-manage（manager + 子 agent）** | manager 拆任务、spawn 子 Devin、通过内部 MCP 协调 | 已在 Devin 生产可用。踩的坑：「管理者默认过度指令化」「子 agent 以为和父 agent 共享状态」「子 agent 不会主动向上汇报」 |

明确否定的方向：**「无结构 swarm（任意 agent 网络互相协商）基本是干扰项」**。
来源：[Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working)（2026-04-22）[原文]

> 这两篇文章放一起看，才是 2026 年的真实共识：**并行的「读」可以放开，「写」必须串行**。这与 2025 年「一律别做多 agent」相比是实质性修正，但和「agent swarm 自由协作」的营销叙事完全相反。

### 1.4 Deep agents / subagents：2026 年最主流的「产品化形态」

LangChain 把 deepagents 定义为「batteries-included agent harness」，内置：子 agent（隔离上下文窗口）、文件系统（本地/沙箱/远端可插拔）、上下文管理（长会话摘要 + 工具输出落盘）、shell、持久记忆、human-in-the-loop。
来源：[deepagents README](https://github.com/langchain-ai/deepagents) · [官方文档](https://docs.langchain.com/oss/python/deepagents/overview) [实测：30,841 star，v0.7.32，MIT]

这套「上下文落盘 + 子 agent 隔离」的配方与 Anthropic 的建议高度一致——Anthropic 明确推荐「子 agent 把产物写到文件系统，只回传轻量引用，以减少『传话游戏』式的信息损失」[原文，multi-agent-research-system 附录]。

### 1.5 Durable execution 成为一等公民

Anthropic 的表述值得整段引用：「agent 是有状态的且错误会累积……我们不能从头重启：重启昂贵且让用户沮丧。所以我们构建了能从出错处恢复的系统。」他们同时用**模型自身智能**（告诉 agent 某工具在失败，让它自己适应）+ **确定性保险**（重试逻辑 + 定期 checkpoint），并区分二者职责。
来源：[multi-agent-research-system](https://www.anthropic.com/engineering/multi-agent-research-system) [原文]

### 1.6 2026 年的新范式：Managed Agents（会话 / harness / 沙箱三者虚拟化）

Anthropic 在 2026 年发布了 Managed Agents，这是**范式层面**最重要的新东西，也是「单 agent + 托管 harness」路线的最强表态：

- 把 agent 拆成三个可独立替换的接口：**session**（append-only 事件日志）、**harness**（调用模型、路由工具调用的循环）、**sandbox**（执行环境）
- 起因是「养宠物」问题：早期把三者塞进一个容器，容器挂 = 会话丢；且凭证与模型生成的代码同处一容器，**一次 prompt injection 就能读到自己的 token**
- 结构化解法：**token 永不进入沙箱**。Git 用初始化时 clone + 写入 local remote；自定义工具走 MCP + 专用 proxy，harness 全程不知道凭证
- 性能收益：harness 移出容器后，**p50 TTFT 降约 60%，p95 降超 90%**
- 一个漂亮的实证：Sonnet 4.5 会在接近上下文上限时「提前收尾」（context anxiety），他们加了 context reset；**换到 Opus 4.5 后该行为消失，reset 变成死代码**

来源：[Scaling Managed Agents with stable interfaces](https://www.anthropic.com/engineering/managed-agents) · [文档](https://platform.claude.com/docs/en/managed-agents/overview)（2026）[原文]

> 这条的启示对做产品的人很关键：**harness 里的每个 workaround 都是对「当前模型能力」的假设，模型一升级就变成技术债**。Anthropic 自己的对策是把假设关进可替换的接口。

相关前作（Anthropic 官方博客，我只验证了链接可达、未逐段精读，标注为参考）：
[Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) ·
[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

---

## 2. 主流框架现状（2026-11）

### 2.1 一览表（star / 版本 / 许可证均为 2026-11-01 实测）

| 框架 | Star [实测] | 最新版 [实测] | 许可证 | 生产就绪度 |
|---|---|---|---|---|
| [LangChain](https://github.com/langchain-ai/langchain) | 148,799 | 1.4.7 | MIT | 高（1.x，承诺 2.0 前不破坏） |
| [LangGraph](https://github.com/langchain-ai/langgraph) | 44,250 | **1.2.19**（2026-10-30） | MIT | 高（1.0 于 2025-10-22 发布） |
| [deepagents](https://github.com/langchain-ai/deepagents) | 30,841 | 0.7.32（2026-10-23） | MIT | 中（仍 0.x） |
| [OpenAI Agents SDK (py)](https://github.com/openai/openai-agents-python) | 30,428 | **0.24.0**（2026-10-15） | MIT | 中（一年后**仍 0.x**） |
| [OpenAI Agents SDK (js)](https://github.com/openai/openai-agents-js) | 3,956 | 0.21.0 | MIT | 中 |
| [Claude Agent SDK (py)](https://github.com/anthropics/claude-agent-sdk-python) | 8,396 | **0.2.176**（2026-10-31） | MIT | 中（0.x，但日更） |
| [Claude Code](https://github.com/anthropics/claude-code) | 154,103 | 持续发版 | **无 LICENSE 文件** | 商业产品 |
| [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) | 14,458 | **1.24.0**（2026-10-30） | MIT | 高（1.0 GA，官方支持） |
| [AutoGen](https://github.com/microsoft/autogen) | 61,660 | python-v0.7.5（**2025-09-30**） | CC-BY-4.0 | **已归档/不维护** |
| [Semantic Kernel](https://github.com/microsoft/semantic-kernel) | 28,724 | 持续发版 | MIT | **已被 MAF 取代** |
| [Google ADK (py)](https://github.com/google/adk-python) | 22,067 | **2.13.0**（2026-10-23） | Apache-2.0 | 高（2.0 线） |
| [Google ADK (java)](https://github.com/google/adk-java) | 1,760 | 持续发版 | Apache-2.0 | 中 |
| [CrewAI](https://github.com/crewAIInc/crewAI) | 60,361 | 1.15.33（2026-10-29） | MIT | 中高 |
| [LlamaIndex](https://github.com/run-llama/llama_index) | 52,765 | 0.14.25 | MIT | 中（core 仍 0.x） |
| LlamaIndex Workflows | 同上仓 | **2.26.1**（2026-10-21） | MIT | 中高（已独立 2.x） |
| [Agno](https://github.com/agno-agi/agno) | 43,001 | 3.1.12（2026-10-29） | Apache-2.0 | 中高 |
| [Pydantic AI](https://github.com/pydantic/pydantic-ai) | 20,975 | 2.64.0（2026-10-31） | MIT | 中高 |
| [Mastra (TS)](https://github.com/mastra-ai/mastra) | 29,244 | **@mastra/core 1.81.0** | ⚠️ 含 `ee/` 目录，非纯 OSS | 中 |

### 2.2 逐项要点

**LangGraph 1.2.x** — 唯一「明确宣称是 durable agent framework 且发了 1.0」的项目。1.0 三大卖点：durable state、built-in persistence、human-in-the-loop。官方说法：「这是 durable agent framework 领域第一个稳定大版本」，并承诺 **1.x 不破坏、直到 2.0**。
来源：[LangChain 与 LangGraph 达 v1.0](https://www.langchain.com/blog/langchain-langgraph-1dot0)（2025-10-22）[原文] · [LangGraph v1 发布说明](https://docs.langchain.com/oss/python/releases/langgraph-v1)
⚠️ 已知摩擦点：`langgraph.prebuilt` 被弃用、功能迁到 `langchain.agents`；1.0 同时把旧功能挪进 `langchain-classic`——**生态教程大量过时**。

**LangChain 1.4.7** — 定位「最快搭 agent」，核心是 `create_agent` + **middleware**（HITL、摘要压缩、PII 脱敏、自定义 hook）。官方罕见地承认历史问题：「抽象有时太重、包面过大、开发者想要对循环更多控制」。这是**自我批评 + 收窄 API 面**的一年。

**deepagents** — 「batteries-included harness」，建立在 LangGraph 之上，因此白拿 streaming/persistence/checkpointing + LangSmith 追踪。缺点是**仍是 0.x**，API 会变。

**OpenAI Agents SDK 0.24.0** — 定位轻量多 agent 框架，核心概念：Agents、**Sandbox agents**（预配置容器、面向长周期任务）、Realtime/voice agents、agents-as-tools、handoffs、guardrails。**是本次调研中最刺眼的版本号**：距离 2025 年初从 Swarm 演进以来已一年多，仍在 0.x。

**Claude Agent SDK 0.2.176** — 同样 0.x 但日更（2026-10-31 仍在发）。它的价值不在 SDK 抽象，而在**harness 本身**（Claude Code 那套循环 + 工具 + 权限模型）。2026 年 10 月 Anthropic 把 **Agent Skills 标准捐给 AAIF**，Skills / subagents 因此成为跨厂商概念，而不只是 Claude 特性。
来源：[Donating Agent Skills to the Agentic AI Foundation](https://www.anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation)（2026-10-22）· [Simon Willison 的解读](https://simonwillison.net/2026/Oct/22/donating-agent-skills/)

**Microsoft Agent Framework 1.24.0** — 这是 2026 年**结构性变化最大**的一家。已确认：
- Semantic Kernel README 首行：「Semantic Kernel is now Microsoft Agent Framework!」MAF 是 SK 的「enterprise-ready successor」，**1.0 生产就绪、承诺长期支持**
- AutoGen README：「**AutoGen is now archived and no longer maintained by Microsoft**」，并明确「继续建议不要用于生产」，新项目应直接用 MAF，附 [AutoGen → MAF 迁移指南](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/)
- MAF 同时提供 **Python / .NET / Go** 三语言（Go 在独立仓 `microsoft/agent-framework-go`），并宣称通过 **A2A 与 MCP** 实现跨运行时互操作

来源：[microsoft/agent-framework README](https://github.com/microsoft/agent-framework) · [microsoft/autogen README](https://github.com/microsoft/autogen) · [microsoft/semantic-kernel README](https://github.com/microsoft/semantic-kernel) [均为原文]
⚠️ **一处需要说明的矛盾**：AutoGen README 已写「已归档」，但 GitHub API 在 2026-11-01 返回 `archived: false`。可能是归档流程未完成、或文字先行。**结论：把 AutoGen 当停止维护对待是安全的，但「archived 标记」这个具体事实未确认。**

**Google ADK 2.13.0** — README 标题已是「Agent Development Kit (ADK) **2.0**」，code-first、强调 testability 与 versioning，Apache-2.0，另有 Java 版。

**CrewAI 1.15.33** — 角色扮演式多 agent 编排，是「概念最讨喜、也最容易过度设计」的一个。star 60k 说明传播力强，但其 role-playing 抽象正好落在 Cognition 第 2 条原则（动作携带隐式决策）的雷区，**适合演示、需谨慎上生产**。

**LlamaIndex** — 定位已明显漂移：仓库描述现在是「the document processing platform for AI」，即重心从「agent 框架」转向「文档/数据层」。独立的 llama-index-workflows 已到 2.26.1，比 core（0.14.x）版本号更成熟。

**Agno 3.1.12** / **Pydantic AI 2.64.0** — 前者自我定位「self-driving agent platform」，后者主打「typed end to end」，两者都已进入 2.x/3.x，迭代极快。Pydantic AI 对**类型安全 + 结构化输出**的强调，在 5 人小团队里性价比很高。

**Mastra** — TypeScript 阵营最活跃者（@mastra/core 1.81.0）。⚠️ **许可证要注意**：`LICENSE.md` 显示存在 `ee/` 企业目录（如 `@mastra/core/auth/ee`、`agent-builder/ee`），即**开源核心 + 商业模块**的混合模式，不是纯 OSI 开源。

---

## 3. 工业化的关键配套

判断标准：**这些才是决定 agent 能不能上生产的东西，框架本身反而不是瓶颈**。

### 3.1 持久化 / 耐久执行

| 方案 | Star [实测] | 许可证 | 定位与取舍 |
|---|---|---|---|
| [Temporal](https://github.com/temporalio/temporal) | 24,109 | MIT | 最成熟的工作流引擎，Python SDK 1.35.0（2026-10-28）。官方有 AI agent 叙事：[Of course you can build dynamic AI agents with Temporal](https://temporal.io/blog/of-course-you-can-build-dynamic-ai-agents-with-temporal)。**取舍：确定性重放约束会把你的代码结构「掰」成 workflow/activity 两段，学习曲线真实存在；跑基础设施本身有运维成本** |
| [Restate](https://github.com/restatedev/restate) | 4,633 | ⚠️ **BSL 1.1** | 单二进制、轻量，SDK 1.2.0（2026-10-28）。**取舍：BSL 不是 OSI 开源，商业使用需读附加授权条款** |
| [Inngest](https://github.com/inngest/inngest) | 6,005 | ⚠️ **SSPL 1.0**（附 Apache-2.0 未来许可） | step function 风格，serverless/edge 友好。**取舍：SSPL 对 SaaS 转售有实质限制；Python SDK 0.5.19 最后发版 2026-06，明显落后于 npm 端 4.26.2** |
| [DBOS](https://github.com/dbos-inc/dbos-transact-py) | 1,660 | MIT | 「DB-backed durable workflows」，直接把状态放 Postgres，**不需要额外基础设施**——对 5 人团队这是最大优势。3.4.0（2026-10-28） |
| LangGraph checkpointer | — | MIT | 内建，零额外运维，与图执行模型天然贴合。**取舍：它是「持久化 + 恢复」，不等于通用 durable execution——跨系统事务、外部副作用重试仍需你自己兜**。文档：<https://docs.langchain.com/oss/python/langgraph/persistence> |

**我的判断**：LangGraph 项目直接用自带 checkpointer；非 LangGraph 栈想要「无新增基础设施」选 DBOS；已经有 Kafka/微服务重度运维能力的团队才值得上 Temporal。

### 3.2 可观测与评测

| 方案 | Star [实测] | 开源/许可 | 2026 关键事实 |
|---|---|---|---|
| [Langfuse](https://github.com/langfuse/langfuse) | 36,814 | MIT + `ee/` | **已被 ClickHouse 收购**（ClickHouse $400M D 轮同时宣布收购）——见 [ClickHouse 公告](https://clickhouse.com/blog/clickhouse-raises-400-million-series-d-acquires-langfuse-launches-postgres)。LICENSE 版权行已改为「Copyright (c) 2023-2026 **ClickHouse, Inc.**」[实测]。v4.72.0 / Python SDK 5.1.0 |
| LangSmith | — | 闭源商业 | LangChain 官方平台，2026 年产品面已从「观测」扩到 **Engine / Observability / Evaluation / Deployment / Sandboxes / LLM Gateway / Fleet**（见官网导航）。**取舍：与 LangChain 生态耦合最深、体验最顺，但也是最强锁定** |
| [Opik](https://github.com/comet-ml/opik) | 23,076 | Apache-2.0 | Comet 出品，2.2.137。**Apache-2.0 是它相对 Langfuse 的差异点**（Langfuse 有 ee 目录） |
| [Phoenix](https://github.com/Arize-ai/phoenix) | 12,087 | ⚠️ **Elastic License 2.0 (ELv2)** | Arize 出品。**ELv2 禁止把产品作为托管服务提供**，自用无碍 |
| Braintrust | — | 闭源商业 | PyPI/npm SDK 开源（`braintrust-sdk-javascript` 仅 29 star），核心平台闭源。具体定价**未确认**（未抓取） |

**评测这件事的实证结论**（引用 Anthropic 原文，比任何工具宣传都实用）：
- **立刻用小样本开评**。早期改动 effect size 极大（30%→80%），20 条真实 query 就能看出差异；「等有了几百条用例再做 eval」是错误且常见的拖延借口
- **LLM-as-judge 要单次单 prompt 输出 0.0–1.0 分 + pass/fail**，比多 judge 分工更稳定、更贴人类判断
- 评判维度建议：事实准确性、引文准确性、完整性、来源质量、工具效率
- **有副作用/改变状态的 agent 要用 end-state evaluation**（判终态对不对，不判路径），复杂流程拆成离散 checkpoint
- **人工测试不可省**：他们的人工测试发现 agent 系统性偏好 SEO 内容农场而放弃权威 PDF

来源：[multi-agent-research-system](https://www.anthropic.com/engineering/multi-agent-research-system) [原文]

### 3.3 沙箱

| 方案 | Star [实测] | 许可 | 备注 |
|---|---|---|---|
| [E2B](https://github.com/e2b-dev/E2B) | 14,642 | Apache-2.0 | 面向 agent 的代码执行环境，SDK `e2b` 2.62.0。定位最贴「给 agent 用的沙箱」 |
| [Daytona](https://github.com/daytonaio/daytona) | 71,412 | 无 LICENSE | ⚠️ **主仓库已归档（archived），最后推送 2026-07-24**。高 star 但**当前状态不可用于新项目**；是否迁到新仓库/新产品形态**未确认** |
| [Firecracker](https://github.com/firecracker-microvm/firecracker) | 37,758 | Apache-2.0 | microVM，隔离强度最高，但**你要自己写编排层**——它不是产品，是积木 |

**取舍总结**：E2B/Daytona 类 = 冷启动快、开箱即用、按秒计费，但要信任第三方；Firecracker = 隔离最强、可控性最高，但工程量大到不适合 5 周项目。Anthropic 在 Managed Agents 里给出的原则比工具选择更重要：**凭证永远不要和模型生成的代码同处一个沙箱**（否则一次 prompt injection 就全泄）[原文]。

### 3.4 工具协议：2026 年最大的结构性新闻

**MCP：从 Anthropic 项目变成 Linux Foundation 标准。**
- 已捐赠给 **Agentic AI Foundation (AAIF)**，这是 **Linux Foundation 下的定向基金**，由 **Anthropic、Block、OpenAI 共同创立**，Google、Microsoft、AWS、Cloudflare、Bloomberg 支持
- AAIF 创始项目：**MCP、Block 的 goose、OpenAI 的 AGENTS.md**
- 治理模型不变（原 maintainer 继续、社区输入优先）
- 厂商声明数字：**10,000+ 活跃公共 MCP server**；ChatGPT、Cursor、Gemini、Microsoft Copilot、VS Code 均已采纳；Python+TypeScript SDK **月下载 9700 万+**；有官方 [Registry](https://github.com/modelcontextprotocol/registry)；2025-11-25 spec 引入异步操作、无状态化、server identity、官方扩展

来源：[Donating MCP to the Agentic AI Foundation](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation) · [MCP 一周年 spec 博客](https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/) · [modelcontextprotocol.io](https://modelcontextprotocol.io) [原文]
> ⚠️ 上述 10,000 / 9700 万是 **Anthropic 自述**，非第三方审计，请当厂商声明看。

**A2A：从 Google 项目变成 Linux Foundation 标准，并且和 MCP 归到同一个基金会。**
- 起源于 Google，已捐给 Linux Foundation；**v1.0 稳定规范于 2026-03** 发布
- 2026-08-27 被 AAIF 接纳为 **Growth Stage 项目**
- 定位分工讲得很清楚：**MCP 是「垂直」集成层（agent → 工具/数据库），A2A 是「水平」协议（agent ↔ agent 对等协作）**
- 采纳：**150+ 组织**；Google Cloud、**AWS Bedrock AgentCore Runtime**、**Azure AI Foundry** 原生支持；ServiceNow、Salesforce、Atlassian、SAP 在用；框架侧 LangGraph、CrewAI、Pydantic AI、AG2、IBM BeeAI 支持

来源：[A New Chapter for A2A: Joining the AAIF](https://a2a-protocol.org/latest/blog/2026/08/27/a-new-chapter-for-a2a-joining-the-agentic-ai-foundation/) · [AAIF 公告](https://aaif.io/blog/a2a-joins-aaif) · [a2a-protocol.org](https://a2a-protocol.org/) · [A2A GitHub](https://github.com/a2aproject/A2A) [实测 26,367 star, Apache-2.0]

**ADK / MAF 双双向 A2A+MCP 靠拢**（MAF README 明确写「cross-runtime interoperability via A2A and MCP」）——这说明 2026 年协议层已经收敛，**协议之争基本结束，剩下的是实现质量之争**。

> 诚实的保留：A2A 的「150+ 组织」和「生产跑通」也都是**协议方自述**。我在公开检索中没找到独立的、可量化的「A2A 跨厂商互操作实际调用量」数据。**跨组织 agent 互调在 2026 年是否真的普遍，未确认。**

### 3.5 Guardrails / 权限

- [NeMo Guardrails](https://github.com/NVIDIA-NeMo/Guardrails)：7,404 star，可编程护栏，**但它是对话系统护栏，不等于 agent 权限系统**
- 真正有效的权限实践来自 harness 层，Anthropic 的表述最具体：**把 token 放在沙箱之外**（Git 用初始化期 clone + local remote；自定义工具走 MCP + vault proxy，harness 不知道凭证）[原文，managed-agents]
- LangChain 1.0 把 **HITL middleware**（审批/编辑/拒绝工具调用）+ **PII 脱敏 middleware** 做成了内建能力 [原文]

**关于 prompt injection，本次调研最硬的一条证据**是 Langflow 的 CVE 序列（见 4.2），它说明：agent 平台常在网络可达端点上做**无沙箱的 `exec()`**，这是架构级问题，打补丁只是临时手段。

---

## 4. 可直接部署的开源项目 / 平台

### 4.1 总表（star / 版本 / 许可证全部 2026-11-01 实测）

| 项目 | Star | 最新版 | 许可证 | 定位 | 部署难度 | 结论 |
|---|---|---|---|---|---|---|
| [n8n](https://github.com/n8n-io/n8n) | **209,232** | 1.123.91 | ⚠️ **Sustainable Use License**（非 OSI） | 通用工作流自动化 + AI 节点 | 低（Docker） | 集成强、agent 弱 |
| [Dify](https://github.com/langgenius/dify) | **160,131** | 1.18.0 | ⚠️ Apache-2.0 **+ 附加条件** | LLM 应用/agent 平台（可视化 + RAG） | 中（compose 多组件） | 做 demo 首选之一 |
| [Open WebUI](https://github.com/open-webui/open-webui) | 157,433 | 0.12.5 | ⚠️ 自定义（含品牌条款，保留所有权利） | 自托管 Chat UI | 低 | 只是前端，不是 agent 平台 |
| [Langflow](https://github.com/langflow-ai/langflow) | 156,214 | 1.14.0.dev12 | MIT | 可视化 agent/flow 构建器 | 低 | ⚠️ **安全记录严重** |
| [RAGFlow](https://github.com/infiniflow/ragflow) | 93,278 | nightly | Apache-2.0 | RAG 引擎 + agent | 高（重，要 GPU/资源） | RAG 强、重 |
| [OpenHands](https://github.com/OpenHands/OpenHands) | 92,388 | 1.23.0-r3 | MIT | 自主软件开发 agent | 中高（要容器+沙箱） | 真能跑，运维重 |
| [CrewAI](https://github.com/crewAIInc/crewAI) | 60,361 | 1.15.33 | MIT | 角色扮演多 agent | 低 | 演示友好 |
| [LibreChat](https://github.com/LibreChat-AI/LibreChat) | 46,589 | 日更 | MIT | 多模型 Chat 前端 | 低 | 稳定、活跃 |
| [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 30,410 | 持续 | Apache-2.0 | 深度研究 agent | 低 | 单一职责，好参考 |
| [Sim](https://github.com/simstudioai/sim) | 29,953 | 0.9.38 | Apache-2.0 | 协作式 agent 工作区 | 中 | 0.x，快但抖 |
| [FastGPT](https://github.com/labring/FastGPT) | 29,964 | 4.17.2 | ⚠️ Apache-2.0 **+ 附加条件** | 知识库问答平台 | 中高 | 中文场景实用 |
| [Coze Studio](https://github.com/coze-dev/coze-studio) | 21,791 | **V0.5.1（2026-02-05）** | Apache-2.0（`LICENSE-APACHE`） | 字节系可视化 agent 平台 | 中高 | ⚠️ **版本停滞** |
| [Suna](https://github.com/kortix-ai/suna) | 20,342 | dev-latest | ⚠️ **Elastic License 2.0** | 「通用 AI 员工」（现改名 Kortix CompanyOS） | 中 | ⚠️ **许可已收紧** |
| AutoGen Studio | 随 AutoGen | — | — | 多 agent 低代码 GUI | — | ❌ **随 AutoGen 一起进入归档** |

### 4.2 逐项：真实口碑与被吐槽的点（带出处）

**n8n** — 分发能力最强（209k star、400+ 集成），但**许可证不是开源**：`LICENSE.md` 明确写着 **Sustainable Use License**，且 `.ee` 文件/目录不在该许可内——这是典型的 **fair-code**，不是 OSI 开源 [实测 LICENSE 原文]。
AI Agent 节点的真实问题（GitHub issue，均为实测存在的 URL）：
- [Issue #27342](https://github.com/n8n-io/n8n/issues/27342)：**「AI Agent Node Validation & Error Handling is Unreliable」** —— 校验与错误处理不可靠
- [Issue #23185](https://github.com/n8n-io/n8n/issues/23185)：**「AI Agent V3 breaks multi-turn tool calling with OpenAI-compatible providers (Regression from V2)」** —— 升级引入回归，多轮工具调用直接坏
- [Issue #24042](https://github.com/n8n-io/n8n/issues/24042)：**「Tool node errors fail workflow instead of returning error to agent for handling」** —— 工具报错把整个 workflow 打挂，而不是把错误交回 agent 处理
> 第二条和第三条最有信息量：它们暴露的是**架构问题**——n8n 的引擎语义是「工作流」，而 agent 需要「把错误当输入继续循环」。用它做 agent 是在和工作流引擎的语义对抗。

**Dify** — 160k star、**部署文档自己就有 troubleshooting 专区**（[Common Issues](https://docs.dify.ai/en/self-host/deploy/troubleshooting/common-issues)、[Docker Issues](https://docs.dify.ai/en/self-host/deploy/troubleshooting/docker-issues)），这其实是很诚实的信号：自托管摩擦点很多。
许可证是真正的坑：`LICENSE` 明确写「**Dify 在修改版 Apache 2.0 下授权，附加条件**」——(a) **不得用于多租户服务**（除非书面授权，一个 workspace = 一个 tenant）；(b) **不得移除控制台/应用中的 LOGO 与版权信息**（不涉及前端的使用不受此限）[实测 LICENSE 原文]。
> **「看起来唬人但难用」的具体证据**：Dify 的可视化编排在 demo 时很漂亮，但一旦要**版本管理 + 多人协作 + 私有化二次开发**，社区的主要反馈是必须锁版本、别跟 main 分支（例：[Dify 二次开发避坑：为什么直接使用 main 分支是隐形炸弹？](https://blog.csdn.net/WANGJUNAIJIAO/article/details/153721272)，中文博客，权威性一般，作为社区经验参考）。另有高互动 open issue [#39151](https://github.com/langgenius/dify/issues/39151)（61 条评论）反映**并行 fail-fast 导致连带节点失败无法归因**——这正是「可视化工作流 + 并发」组合的典型调试困境。

**Coze Studio** — 最值得注意的不是功能而是**节奏**：最新 release **V0.5.1 停在 2026-02-05**，仓库最后推送 2026-07-29，**距调研日已 3 个月无 release** [实测]。许可证是干净的 Apache-2.0（`LICENSE-APACHE`，标准全文，10174 字符）[实测]，我之前预期的限制性条款**在 LICENSE 文件中并不存在**——这点必须纠正，README 层的商标附加条款**未确认**。
真实部署摩擦（中文 issue，评论量真实）：
- [#805 代码节点 sandbox 模式运行报错](https://github.com/coze-dev/coze-studio/issues/805)
- [#500 NAS 部署出现这个是什么问题？](https://github.com/coze-dev/coze-studio/issues/500)
- [#2353 知识库写入节点 authentication failed: missing session_key in cookie](https://github.com/coze-dev/coze-studio/issues/2353)
- [#749 本地 Embedding 模型（openai 协议）数据处理失败 code=105000004](https://github.com/coze-dev/coze-studio/issues/749)
> 这些清一色是「本地化/国产化环境的集成摩擦」，不是模型能力问题。**Coze Studio 的定位更接近「字节商业版的试用装」，而非持续演进的开源基础设施。**

**Langflow** — 本次调研中**最需要警告**的项目。它是 MIT 许可、156k star、上手最快的可视化 agent 构建器，但：
- **CVE-2026-9198**（CVSS 9.8，未授权 RCE，2026-07-17 披露），IBM 同日发 1.10.1 修复
- 这是 **18 个月内第 7 个 critical CVE**，同类根因反复出现：`/api/v1/auto_login` 铸造 SUPERUSER token → `/api/v1/validate/code` 通过 `exec()` 执行任意 Python，**无需认证**
- 已被 **CISA 加入 KEV 目录（2026-08-04）**，联邦修复期限 2026-08-07（已过）
- 约 **7,000 个互联网暴露实例**；**JadePuffer 勒索活动**（Sysdig 于 2026-07 记录）正是利用 CVE-2025-3248 打掉一个公网 Langflow，dump 了 Postgres、收割 LLM/云/数据库凭证并横向移动到生产 MySQL 与 Nacos
- 作者的核心论断（我认可）：**架构即漏洞——在网络可达端点上做无沙箱动态代码执行，打补丁只是临时措施**

来源：[Seven Critical CVEs in 18 Months: Langflow's Architecture Is the Vulnerability](https://forkast.news/seven-critical-cves-in-18-months-langflows-architecture-is-the-vulnerability/)（2026-08-09）[原文]
> 说明：文中「IBM Langflow」指 Langflow 现属 IBM；文中引用的 NVD 与 CISA 链接我**未能直接抓取**（站点对本次请求返回错误），故上述 CVE 编号与 KEV 状态均**转引自该文**，属二手。

**Open WebUI** — 157k star，但**许可证要仔细读**：`LICENSE` 开头是「**Open WebUI License / Copyright (c) 2023- Open WebUI Inc. / All rights reserved.**」，基于 BSD 但**附加了品牌保留条件**（v0.6.x 起引入）。官方有专门的[许可证 FAQ](https://docs.openwebui.com/license/)解释「个人/商业/教学仍可自由使用」。**不是 OSI 开源**。定位上它只是 Chat UI 前端，**不是多 agent 平台**——把它当 agent 平台是常见误解。

**OpenHands** — 92k star、MIT、v1.23.0-r3，是目前最「真能干活」的开源自主开发 agent。但运维成本真实存在：话题度最高的 open issue 是 [#17546「detect ports automatically instead of always using 3001」](https://github.com/OpenHands/OpenHands/issues/17546)（**204 条评论**）——一个端口硬编码问题能堆到 204 条评论，说明**部署环境适配是它的主要摩擦面**。另有 587 个 open issue。
> 关于 SWE-bench 类基准的可信度，值得并列参考 ICSE 2026 论文 [Are "Solved Issues" in SWE-bench Really Solved Correctly?](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/59/Are-Solved-Issues-in-SWE-bench-Really-Solved-Correctly-An-Empirical-Study)——即「排行榜分数」和「真实可用」之间有系统性偏差。这是对**所有** coding agent 的通用警告。

**Suna** — 曾经的「通用 AI 员工」明星项目，2026 年两处实质变化 [实测]：**许可证已从宽松许可改为 Elastic License 2.0**（禁止作为托管服务转售），仓库描述改为「**Kortix CompanyOS** – the open-source operating system for your company」。**ESL 2.0 不是 OSI 开源**。另外 `kortix-ai/suna` 的 **open issue 数为 0**，是本次调研中唯一的异常值——issue 极可能被关闭或分流到别处，**具体原因未确认**，但「0 open issue」本身就不该被读作「没问题」。

**RAGFlow** — 93,278 star、Apache-2.0、**902 个 open issue**。部署重（解析要 GPU/大量内存），真实吐槽集中在解析卡住：
- [#3022 Hanging at parsing files](https://github.com/infiniflow/ragflow/issues/3022)
- [#5598 解析加速需要什么型号/多少块 GPU](https://github.com/infiniflow/ragflow/issues/5598)
- [#7881 知识库检索时 ollama CPU 占用过高](https://github.com/infiniflow/ragflow/issues/7881)
> 它的强项（深度文档解析）和它的槽点（深度解析很吃资源）是同一件事。

**FastGPT** — 29,964 star、v4.17.2、中文知识库场景实用。许可证同样是 **Apache-2.0 + 附加条件**（`LICENSE` 原文：不得用于「类似 FastGPT 的多租户 SaaS」、不得移除 LOGO）。issue 区大量是**部署/接口细节**（如 [#6922 rocky8.4 部署 v4.14.19 报错](https://github.com/labring/FastGPT/issues/6922)、[#6567 知识库接口上传 base64 图片转换](https://github.com/labring/FastGPT/issues/6567)），说明**主要成本在运维而非能力**。

**Sim** — 29,953 star、Apache-2.0、0.9.38（**仍 0.x**）。issue 区是典型的「第三方集成授权」摩擦：[#5704 Unable to authorize Zoom integration](https://github.com/simstudioai/sim/issues/5704)（45 条评论）、[#860 Google Sheets Authentication Error](https://github.com/simstudioai/sim/issues/860)。定位清晰、迭代快，但 0.x 意味着 API/行为会变。

**gpt-researcher** — 30,410 star、Apache-2.0，单一职责（深度研究），是**读代码学多 agent 编排的好样本**（比读一个 20 万 star 的平台高效得多）。

**AutoGen Studio** — ❌ 直接排除。AutoGen README 已写「archived and no longer maintained by Microsoft」、「继续建议不要用于生产」，Studio 作为其 GUI 一并失去维护 [原文]。

---

## 5. 踩坑清单（2026 年被广泛报道的失败模式）

### 5.1 Context rot（上下文腐化）—— 有最硬的实证

**现象**：模型并非均匀使用上下文，输入越长性能越不稳。Chroma 用 **18 个模型**（含 GPT-4.1、Claude 4、Gemini 2.5、Qwen3）在**受控任务**（隔离输入长度这一个变量）上验证：
- 所有实验里性能**随输入长度一致下降**
- needle-question 相似度越低，下降越快
- **只要一个 distractor 就掉性能**，4 个 distractor 进一步叠加；distractor 影响**不均匀**
- LongMemEval 上，聚焦输入（~300 token）显著优于全量输入（~113k token）
- 反直觉：**结构连贯的 haystack 反而比打乱的更差**——「去掉局部连贯性一致地提升表现」
- Claude 系最保守（不确定就弃答，幻觉率最低），GPT 系在 distractor 在场时幻觉率最高

来源：[Context Rot: How Increasing Input Tokens Impacts LLM Performance](https://www.trychroma.com/research/context-rot)（Chroma 技术报告，2025-07-14）[原文]

**成熟对策**：
1. 子 agent 用**干净上下文**做验证（Cognition 的 generator-verifier 就是靠这个拿到每 PR 2 个 bug）
2. 子 agent 产物**落盘**、只回传轻量引用（Anthropic 明确推荐）
3. 长会话做**阶段摘要 + 外部记忆**，接近上限时 spawn 干净上下文的新子 agent 接力
4. ⚠️ **注意对策会过期**：Anthropic 发现 Sonnet 4.5 的「context anxiety」在 Opus 4.5 上**消失了**，为它加的 context reset 变成死代码 [managed-agents 原文]。**所有 context workaround 都要标注「基于哪个模型」并定期复审。**

### 5.2 成本爆炸 —— 有具体倍数

- agent 约 chat 的 **4×** token，multi-agent 约 **15×**（Anthropic 实测）
- 反直觉的因果：**性能提升主要来自「花更多 token」**——token 用量单独解释 BrowseComp 上 80% 的方差
- 结论：**multi-agent 只在「任务价值足够高、能付得起这个倍数」时经济上成立**。Cognition 也把「成本爆炸催生多 agent 需求」列为 2026 的 push 因素

来源：[multi-agent-research-system](https://www.anthropic.com/engineering/multi-agent-research-system) · [multi-agents-working](https://cognition.com/blog/multi-agents-working)

**对策**：按查询复杂度**显式写死 effort 分级**（Anthropic：简单事实查证 1 个 agent + 3–10 次工具调用；直接对比 2–4 个子 agent × 10–15 次；复杂研究 >10 个子 agent）。原文承认：「agent 很难自己判断该花多少力气，所以我们把 scaling 规则嵌进 prompt」。

### 5.3 无限循环 / 无法收敛

真实症状（Anthropic 自述早期版本）：
- **简单查询 spawn 50 个子 agent**
- **无休止地搜索不存在的来源**
- **agent 之间用过多更新互相干扰**
- 已经拿到足够结果还继续（「agents continuing when they already had sufficient results」）
- 子 agent 重复劳动：一个去查 2021 汽车芯片危机，另两个重复查 2025 供应链

来源：[multi-agent-research-system](https://www.anthropic.com/engineering/multi-agent-research-system) [原文]

Cognition 侧的同构问题：review 循环「会多轮迭代，每轮都能发现新 bug——这不总是好事，因为很慢」，所以**coding agent 与 review agent 之间的「通信桥」**（谁决定哪些 bug 值得修）是防循环的关键 [原文]。

**对策**：max iterations 停止条件 + 显式 effort 预算 + **verifier 的反馈要经过主 agent 的上下文过滤**，不能直接灌进循环。

### 5.4 多 agent 上下文丢失 / 状态不一致

这是 Cognition 两篇文章的主轴，具体失败点：
- 子 agent 之间**看不到彼此的隐式决策**，产出风格/边界处理冲突（Flappy Bird 例子：一个做了马里奥背景，一个做了不像游戏素材的鸟）
- 子 agent **误以为和父 agent 共享状态**（实际不共享）
- 子 agent **不会主动向上汇报**能让兄弟 agent 改计划的发现——「因为模型没在需要它的环境里被训练过」
- manager **在小范围委派上训练过度，默认过度指令化**，在缺乏代码库上下文时反而坏事

**对策（Cognition 的验证过的顺序）**：宁可单线程；要并行就让**读并行、写串行**；必须共享时传**完整 trace 而非消息摘要**。

### 5.5 评测缺失 / 评测方法错

失败模式：
- 以为 eval 必须几百条才能开始 → 永远不开始（Anthropic 明确反对）
- 用 step-level 断言评有副作用的 agent → 必然误判（应改 end-state evaluation）
- 只靠自动 eval → 漏掉系统性偏差（如偏好 SEO 内容农场）
- 相信排行榜分数 ≈ 可用性（见 ICSE 2026 SWE-bench 论文）

### 5.6 安全边界失效（2026 年最严重的一类）

- **凭证与模型生成代码同处一个沙箱** → 一次 prompt injection 即取得 token，且攻击者能用该 token **开新会话、再委派任务**（Anthropic 描述的 escalation 路径）[managed-agents 原文]
- **网络可达端点上的无沙箱 `exec()`** → Langflow 18 个月 7 个 critical CVE、KEV、真实勒索事件 [forkast]
- **升级即回归**：n8n AI Agent V3 破坏多轮工具调用 [#23185](https://github.com/n8n-io/n8n/issues/23185)

**对策**：token 永不进沙箱（Git 用初始化 clone、工具走 vault proxy）；网络可达面收敛；把 prompt injection 当**必然发生**来设计而不是当可防。

### 5.7 部署期状态撕裂

Anthropic 的原话值得抄进你的 runbook：agent 系统是「高度有状态的 prompt/工具/执行逻辑之网，几乎连续运行」，**部署更新时 agent 可能停在任何一步**，因此需要 **rainbow deployment**（新旧版本并行、逐步切流），不能一次性全量替换 [原文]。

### 5.8 harness 假设过期（2026 年新增的一类）

**「你为弥补模型缺陷加的每一个 workaround，都是一条会过期的假设。」** Anthropic 用 context reset 的例子亲自演示了这一点，并把它上升为架构原则：**对「接口」有观点，对「实现」无观点**，这样实现可随模型能力替换 [managed-agents 原文]。

---

## 6. 如果你要在一个 5 人学生团队、5 周内做出能演示的多智能体系统

### ✅ 推荐（按优先级）

| 选择 | 理由 |
|---|---|
| **架构：单线程主 agent + 2–3 个只读子 agent** | 这是 2026 年唯一被两家具名公司同时验证的形态。写入串行，避免 Cognition 的隐式决策冲突。演示效果足够「多智能体」，风险最低 |
| **必加一个 generator-verifier 循环** | 性价比最高的「多 agent」卖点：分工清晰、可量化（统计抓到多少问题）、几乎不会失控。注意**评审 agent 要用干净上下文** |
| **框架：LangGraph 1.2.x（+ 需要时 deepagents）** | 唯一发了 1.0 且承诺不破坏的 durable agent runtime；checkpointer + HITL 白送。5 周内「能恢复状态」是演示加分项 |
| **或：OpenAI Agents SDK（若团队已重度用 OpenAI）** | 概念最简洁（agents / handoffs / guardrails），学习成本最低。代价：仍 0.24.x，要有「API 会变」的心理准备 |
| **或：Pydantic AI 2.64（若团队偏类型安全/Python 原生）** | typed end-to-end，小团队心智负担低，2.x 稳定线 |
| **持久化：LangGraph checkpointer** | 零额外基础设施。别在 5 周里上 Temporal |
| **可观测：Langfuse 自托管（Apache/MIT 核心）或直接用 LangSmith 免费层** | 一定要有 trace，否则演示失败时你无法解释为什么。LangSmith 与 LangChain 栈最顺；注意 Langfuse 已被 ClickHouse 收购、有 `ee/` 目录 |
| **工具接入：MCP** | 协议已归 Linux Foundation，ChatGPT/Cursor/VS Code 都支持——**写 MCP server 是可复用资产**，而且演示时「接第三方工具」非常直观 |
| **评测：20 条真实 query + LLM-as-judge（单 prompt 0–1 分 + pass/fail）** | Anthropic 明确说 20 条就够看出差异。5 周里这是能做完的规模 |
| **代码执行隔离：E2B（云）或干脆不要代码执行** | 5 周内自建 Firecracker 不现实。实在要跑代码就用 E2B；能不做就不做 |
| **前端/交付：LibreChat（MIT、日更）或 gpt-researcher 式精简 Web UI** | 不要为了「有个漂亮界面」去自托管 Dify/Langflow |

### ❌ 不推荐（及原因）

| 不要做 | 原因 |
|---|---|
| **不要做「agent swarm / 自由协商」** | Cognition 2026 明确定性为「mostly a distraction」 |
| **不要用 AutoGen / AutoGen Studio** | README 已写归档、不维护、不建议生产 |
| **不要用 Semantic Kernel 新建项目** | README 首行即「Semantic Kernel is now Microsoft Agent Framework」，等于宣告迁移 |
| **不要选 Langflow 做任何联网部署** | 18 个月 7 个 critical CVE、CISA KEV、真实勒索事件；架构级问题 |
| **不要把 Open WebUI 当 agent 平台** | 它只是 Chat UI；且许可是「All rights reserved + 品牌条款」，非 OSI |
| **不要用 n8n 做核心 agent 循环** | 工作流引擎语义与 agent 循环语义冲突（见 #24042、#23185）；且 Sustainable Use License 非开源 |
| **不要用 Coze Studio 作为演进基础** | release 停在 2026-02-05，3 个月无版本推进 |
| **不要用 Suna** | 许可证已收紧为 Elastic License 2.0（禁托管转售），且 issue 数为 0 属异常 |
| **不要在 5 周内自建 durable execution / 沙箱 / 观测平台** | Temporal、Firecracker、Langfuse 都是「买/用」而非「造」的东西 |
| **不要追求 >3 个子 agent** | 每个子 agent 都在放大成本和上下文丢失风险；Anthropic 建议复杂研究才 >10 个，且那是 15× 成本的场景 |
| **不要用 main 分支跑 Dify/Coze 做演示** | 演示前一天被上游改崩是最经典的翻车方式；锁 tag |

### 5 周排期建议（务实版）

- **W1**：定形态（单线程主 + 只读子 agent + verifier），跑通 1 个 agent 循环 + trace（LangSmith/Langfuse 二选一，别两套都上）
- **W2**：接 MCP 工具 2–3 个；加 checkpointer；建 20 条 eval 集
- **W3**：加子 agent（限只读）+ generator-verifier；开始跑 eval，记录 pass rate 与 token 成本
- **W4**：加 HITL 审批点（演示里「人类随时叫停」是极强叙事）+ 成本/延迟看板
- **W5**：只做稳定性与演示脚本；**禁止加新 agent**。准备一个「故意失败」的 demo（展示 verifier 抓到 bug），比全程顺利更有说服力

### 最后一句诚实的提醒

本次调研能确认的是：**协议层（MCP/A2A）已经收敛、单线程+只读子 agent 已成共识、durable execution 与可观测是真正的分水岭**。不能确认的是：A2A 的跨组织实际调用规模、各商业观测平台的具体定价、以及 Daytona 归档后的替代方案走向。做技术选型时，**把「框架」的权重调低、把「trace + eval + 状态恢复 + 凭证隔离」的权重调高**，这个判断在 2026 年的证据里是最稳的。
