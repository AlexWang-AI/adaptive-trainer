# teaching_teacher_v2 · 讲练合一的讲课 Agent（v3）

v1 的原始代码在 `C:\Users\明\Desktop\teaching_teacher_agent`（未改动），v2 的审计版在 `~teaching_agent_v2`。
这一版按三条要求重构：**讲练合一（单节点单调用）**、**SymPy 符号判题**、**可读的包结构**。

## 一、讲练合一：4 节点 → 3 节点，2 次调用 → 1 次

```
v2:  START → teach(讲) → quiz(出题) → wait → judge → ...
v3:  START → lesson(讲义 + 3 题卡，一次结构化调用) → wait → judge → ...
```

- 提示词要求模型一次输出 `{"teaching": {...}, "questions": [3 张题卡]}`；
- 题目与讲义同源，`source_quote` 必须能在讲义里原样找到——从结构上消灭「讲洛必达、考泰勒」；
- **字段顺序被写死**：`teaching.reply_markdown` 必须是 JSON 的第一个字段，
  这样 `MarkdownStreamExtractor` 能在第一个 token 到达时就开始渲染。

### 首屏为什么能进 3 秒

不是模型变快了，是**不再等整段生成完**：

| 指标 | v2 | v3 |
|---|---|---|
| 每轮 LLM 调用 | 2 次（teach + quiz） | **1 次** |
| 首屏（实测） | 等讲完全文 12~21 s | **TTFT 461~1883 ms（p50 1010 ms）** |
| 整轮耗时（实测） | 12~21 s | 7.2~9.2 s |
| 冷启动（CLI 新建连接） | — | 2.3~2.6 s |

首屏 = 第一个可渲染 token 到达的时间，由 `LLMClient.stream_json` 记录 `ttft_ms` 并写入 trace。

## 二、判题：字符串 → SymPy 符号等价

分层顺序（命中即返回，每层都可观测）：

```
L1 choice   选项字母 / 选项全文
L2 text     归一化文本（全半角、空格、标点、$…$）
L3 numeric  数值（分数/小数/百分数/根号/π）
L4 sympy    符号等价（化简差为 0；等价方程按常数比例；方程解与表达式互比）
L5 llm      语义兜底（开放题）
L6 fallback 判错并邀请重述
```

SymPy 层做的事：

- 解析前把 `\frac{}{}`、`\sqrt{}`、`π`、`√`、`×`、`^`、`²`、`ln` 等收敛成 Python 表达式；
- `simplify(a - b) == 0` 判等价，`a.equals(b)` 抽样兜底；
- 方程按 `lhs - rhs` 的常数倍判定（`2x=6` ≡ `x=3`）；方程对表达式时解方程再比；
- **3 秒超时**（线程池），超时交给下一层，不会挂死请求；
- 安全：`parse_expr` 的 `global_dict` 只给 `Symbol/Integer/Float/Rational/Function`，`__builtins__` 清空。

实测（`report/judge_benchmark.py`，24 例）：

| 组 | v1 字符串 | v3 分层+SymPy |
|---|---|---|
| 基础（0.5 / 1/2 / 选A …） | 62% | **100%** |
| 高数（求导、展开、三角恒等、方程） | 36% | **100%** |

## 三、目录

```
teaching_teacher_v2/
├── core/
│   ├ nodes.py       ← 讲练合一节点 + 流式解析 + 题卡校验（本次重点）
│   ├ judge.py       ← 五层判题，SymPy 符号等价（本次重点）
│   ├ graph.py       ← 3 节点状态机（lesson → wait → judge，3 题循环）
│   ├ schema.py      ← TeachingRequest / TeachingTurn / QuestionCard / LessonPayload
│   ├ prompts.py     ← 紧凑版讲练合一提示词（1401 字符 ≈ 860 token）
│   ├ llm.py         ← chat_json + stream_json（TTFT / usage / 立即失败）
│   ├ checks.py scoring.py student.py trace.py config.py
│   └ eval_cases.py
├── api_v2.py        ← FastAPI：teach_turn / teach_answer / teach_stream(SSE) / profile / stats
├── demo.py          ← CLI 流式演示，直接打印首屏毫秒
├── eval_v3.py       ← 端到端评测（真实模型，产出 TTFT/分数/判题指标）
├── tests/           ← 64 个用例（judge / sympy / scoring / student / graph）
├── report/          ← 判题基准 + 看板（dashboard_v3.html）
└── legacy/          ← v1 的旧实现（仅作对照，不参与运行）
```

## 四、跑起来

```bash
$PY = C:\Users\明\Desktop\deeptutor_env\Scripts\python.exe

%PY% -m pytest tests -q                 # 64 个单测，不联网
%PY% demo.py --topic "什么是导数"        # 流式演示，打印首屏毫秒
%PY% eval_v3.py --limit 4               # 端到端评测
%PY% report/judge_benchmark.py          # v1 vs v3 判题基准
%PY% -m uvicorn api_v2:app --port 8008  # 起服务
```

## 五、已知限制

- **首屏依赖流式**：非流式调用（`teach_turn`）仍然要等整段生成完（7~9 s）；
  要 3 秒内看到内容，必须用 `/api/teach_stream` 或 `demo.py`。
- **SymPy 只覆盖标量表达式**：区间、集合、矩阵、向量答案会落到 LLM 或 fallback。
- **`i` 被当作虚数单位**：学生用 `i` 当索引变量时可能误判（考研场景极少）。
- **额度**：评测中遇到过一次 DeepSeek 402（余额不足），已把 401/402/403/429 改为立即失败、不重试。
