# 指挥官 Agent 设计蓝图 v2（功能先行）

> 状态：**待评审，未实现**
> 前提：教材/教辅资料是**固定资产**，不是模型现场发挥；指挥官负责「管进程」，不负责「产内容」。
> 工程路线：路线 1（LangGraph 图 + 工具 + Store + 检查点）

---

## 0. 一句话定位

> **指挥官 = 一个不说话的调度器。它手里有一张穷举过的知识点清单和一套真实题目，负责决定「现在学哪一个、学完没有、下一步给谁」，并把进度算出来给界面看。**

三条铁律：

1. **指挥官不生成任何自然语言**，只发结构化指令。
2. **知识点是穷举的、固定的**，不允许模型自己增删。
3. **学生只看到进度**，看不到"每周/每天做什么"这种计划文本。

---

## 1. 数据资产（先有资产，才有 agent）

三份固定资产，全部来自教材 + 人工校准，**不由 LLM 现场生成**。

### 1.1 `kp_tree.json` —— 知识点清单（穷举）

```json
{
  "textbook": "张宇基础30讲（高数）",
  "lectures": [
    {
      "lecture": 1,
      "title": "函数、极限、连续",
      "sections": [
        {
          "id": "lim.basic",
          "title": "极限的定义与性质",
          "kps": [
            {"id": "lim.definition", "name": "极限定义", "exam_weight": 4, "page": 12}
          ]
        }
      ]
    }
  ]
}
```

**穷尽标准**：以教材「讲 → 节 → 知识点」三级为准，一个讲下面的节必须全到，一个节下面的知识点必须全到。
缺一个，指挥官就不会放行这一讲。

### 1.2 `problems.jsonl` —— 题目库（拆解后的）

```json
{"id":"p0123","lecture":1,"section":"lim.basic","kp_ids":["lim.definition"],
 "type":"example","stem":"...","options":[],"answer":"2","solution":"...",
 "difficulty":2,"source_page":14,"variant_of":null}
```

- `type`: `example`（例题）/ `exercise`（习题）/ `variant`（生成变式）
- `variant_of`: 变式题必须指回母题 id
- **拆解要求**：一道题要标出它考了哪几个 kp（可多标），这是「题 ↔ 知识点」双向索引的基础

### 1.3 `kp_index.json` —— 索引（供 agent 查，不用读全书）

```json
{"lim.definition": {"examples": ["p0123","p0124"], "exercises": ["p0131","p0132"], "gap": false}}
```

**资料缺口**：某个 kp 的例题 <2 或习题 <2，标 `gap: true`，界面提示「本知识点题量不足」。

---

## 2. 六个角色：功能切割与上下文边界

| 角色 | 唯一职责（一句话） | 输入 | 输出 | 绝不看 | 产文本 |
|---|---|---|---|---|---|
| **commander** | 管进度、派活、打勾 | 知识树 + 学生状态 + 题库索引 | `Task(给谁/给什么)` | **学生原话、讲解正文、题目正文** | ❌ |
| **teach** | 把一个知识点讲透，并判定这一步是否讲完 | 1 个 kp 结构 + 学生近 3 轮 | `TeachingTurn` + `KpCovered` | 别的 kp、全局进度、其他单元 | ✅ 只出讲解 |
| **quiz** | 针对当前 kp 出一题（原题或变式） | kp + 本轮讲解摘要 + 该 kp 题库候选 | `QuizItem` | 学生历史、其他单元 | ✅ 只出题 |
| **judge** | 判对错（纯函数） | 题 + 学生答案 | `Verdict` | 讲解、历史 | ❌ |
| **sideqa** | 支线答疑并归档 | 支线问题 + 当前 kp 一句话摘要 | `SideAnswer` + `ArchiveCard` | 主干对话全文 | ✅ 只答支线 |
| **arsenal/exam** | 单元收尾出综合卷 | 单元 kp 集合 | `Paper` | 单轮对话 | ✅ 只出卷 |

**为什么这么切**：指挥官的上下文里**只有结构化字段**（kp_id、状态、计数），永远不装自然语言正文——这是「不污染上下文」的物理保证，不是靠提示词约束。

---

## 3. 指挥官的状态机（路线 1 落地形态)

```
START
  │
  ▼
pick_next_kp ──(还有未掌握的 kp)──► dispatch_teach ──► await_student ──► dispatch_quiz
  │                                                                          │
  │(全部掌握)                                                                ▼
  ▼                                                                     await_answer
 END                                                                         │
  ▲                                                                          ▼
  │                                                                       judge (确定性)
  │                                                                          │
  │◄──────────── not_mastered：回 dispatch_teach（补强，最多 N 次）◄────────┤
  │                                                                          │
  │◄── mastered：tick_kp（打勾+记录证据）────────────────────────────────────┤
  │                                                                          │
  └──────────────────── progress_update ──────────────────────────────────────┘
```

节点职责：

| 节点 | 类型 | 干什么 | 是否调 LLM |
|---|---|---|---|
| `pick_next_kp` | 规则 | 按知识树顺序 + 掌握度挑下一个 | ❌ |
| `dispatch_teach` | 规则 | 组装 `Task{teach, kp, 素材, 约束}` | ❌ |
| `await_student` | interrupt | 等学生输入/作答 | ❌ |
| `dispatch_quiz` | 规则 | 从题库挑候选交给 quiz | ❌ |
| `judge` | 纯函数 | 判对错 | ❌ |
| `tick_kp` | 规则 | 掌握就写 Store + 打勾 | ❌ |
| `progress_update` | 规则 | 算进度，推给前端 | ❌ |

**结论：指挥官这一圈节点，一个 LLM 都不调。** 它靠数据和规则运转，LLM 只在 teach/quiz/sideqa/exam 里面。

---

## 4. 打勾机制：只能由结构化信号触发

```python
class KpCovered(BaseModel):
    """teach 讲完一个 kp 的信号。"""
    kp_id: str
    covered: bool
    evidence: list[str]          # 本轮讲到了哪几个要点（引用知识树里的要点 id）
    open_questions: list[str]    # 学生还没消化的点

class MasterySignal(BaseModel):
    """掌握判定：必须挂在 judge 的结构化结果上。"""
    kp_id: str
    mastered: bool
    reason: str
    judge_verdict_ids: list[str]  # ← 必须能对上真实判分记录，否则不成立
```

指挥官只认这两个对象。**它不看 teach 说了什么话**，只看 `covered=True` 且 `judge_verdict_ids` 达标。

这是防「模型自说自话」的关键：**打勾的证据必须是可回溯的判分记录**。

---

## 5. 学生只看到进度条

### 5.1 UI 拿到的唯一数据结构

```json
{
  "chapter": "第1讲 函数、极限、连续",
  "kp_total": 6,
  "kp_done": 2,
  "percent": 33,
  "current_kp": {"id": "lim.lhopital", "name": "洛必达法则", "state": "teaching"},
  "remaining_rounds": 7,
  "eta_minutes": 280,
  "gaps": []
}
```

### 5.2 明确不给学生看的

- 「本周目标」「今日任务」这类计划文本
- 指挥官的任何决策理由
- 单元划分、课时估算

> 计划是**内部数据**，进度是**外部表现**。学生只关心"还剩多少"。

---

## 6. 上下文隔离（写死，不靠提示词）

| 角色 | 能进上下文的 | 字符上限 | 隔离手段 |
|---|---|---|---|
| commander | 只读结构化字段（kp_id / 状态 / 计数） | 无自然语言 | 类型系统：State 里不放 `str` 正文 |
| teach | 1 个 kp + 该 kp 的 ≤2 道例题 + 近 3 轮对话 | ≤4000 字 | 组装时裁剪 |
| quiz | 本轮讲解摘要（≤300 字）+ 该 kp 候选题 ≤6 道 | ≤2500 字 | 摘要而非全文 |
| judge | 题干 + 标准答案 + 学生答案 | ≤1500 字 | 纯函数 |
| sideqa | 支线问题 + 当前 kp 一句话 | ≤1200 字 | 只给摘要 |

**每个 agent 一个独立的 prompt 组装函数，输入只有上表允许的字段**——接口层面就传不进多余的东西。

---

## 7. 结构化输出契约（这是上一版最缺的）

### 7.1 每个 agent 的 schema 大纲

```python
class TeachingTurn(BaseModel):
    kp_id: str                       # 必须等于派单里的 kp
    reply_markdown: str
    points_covered: list[str]        # 必须来自知识树里该 kp 的要点
    check_question: str
    next_hint: str

class QuizItem(BaseModel):
    kp_id: str
    mode: Literal["original", "variant"]
    source_problem_id: str | None    # mode=original 必填，且必须在题库里
    parent_problem_id: str | None    # mode=variant 必填，指回母题
    stem: str
    options: list[str]
    answer: str
    explanation: str

class Verdict(BaseModel):
    quiz_id: str
    correct: bool
    matched_rule: Literal["exact", "numeric", "symbolic", "llm_fallback"]
    detail: str

class KpCovered(BaseModel):
    kp_id: str
    covered: bool
    evidence: list[str]
    open_questions: list[str]

class MasterySignal(BaseModel):
    kp_id: str
    mastered: bool
    reason: str
    judge_verdict_ids: list[str]
```

### 7.2 校验规则（每条都要有对应的失败用例）

| 校验 | 规则 | 失败时 |
|---|---|---|
| kp 一致性 | `TeachingTurn.kp_id == Task.kp_id` | 驳回重做 |
| 要点合法性 | `points_covered ⊆ kp.points` | 驳回 |
| 原题必须真实 | `source_problem_id` 在题库 | 驳回 |
| 变式必须挂母题 | `parent_problem_id` 存在 | 驳回 |
| 打勾必须有证据 | `judge_verdict_ids` 全部可查 | 拒绝打勾 |

---

## 8. 工程结构（路线 1）

```
backend/
├── data/                          # 固定资产（由 MinerU 产出 + 人工校准）
│   ├── kp_tree.json
│   ├── problems.jsonl
│   └── kp_index.json
├── commander/
│   ├── graph.py                   # 状态机（第 3 节那张图）
│   ├── tools.py                   # 全是纯函数，不调 LLM
│   ├── state.py                   # CommanderState（不含自然语言）
│   └── progress.py                # 进度计算
├── agents/
│   ├── teach/  quiz/  judge/  sideqa/  exam/
└── store/
    └── student.py                 # 掌握度、错题、进度快照（跨会话）
```

工具清单（commander 专用，全部确定性）：

| 工具 | 作用 |
|---|---|
| `get_lecture_tree(lecture)` | 取某讲的知识点结构 |
| `get_next_kp(student_id, lecture)` | 下一个未掌握的 kp |
| `get_problems(kp_id, mode, n)` | 取候选题 |
| `tick_kp(student_id, kp_id, evidence)` | 打勾 + 落库 |
| `compute_progress(student_id)` | 算进度条数据 |
| `check_gaps(lecture)` | 查资料缺口 |

---

## 9. 与现有代码的关系

| 现有 | 处置 |
|---|---|
| `planner` 四版（V1~V4/V3R） | **保留作为历史对照**，但不再是主链路；它的「排 3-12 个单元」思路与「固定知识树 + 只出进度」冲突 |
| `contracts.py` | 复用类型骨架，新增 `KpCovered` / `MasterySignal` / `Verdict` |
| `curriculum.py` | 升级为 `kp_tree.json` 的代码化版本，补 `points`（要点）与 `page` |
| `runner.py` / `tracing.py` / LangSmith | 原样复用 |
| demo 里 teach/quiz/judge 四节点 | 保留思路，按第 2 节重新切边界 |

---

## 10. 分阶段与验收

| 阶段 | 交付 | 验收标准 |
|---|---|---|
| **P1** | `kp_tree.json` + `problems.jsonl` + `kp_index.json`（前 3 讲） | 知识点和题目能逐条对上教材页码 |
| **P2** | commander 图骨架 + 6 个纯函数工具 | 不调 LLM 也能跑出「下一个该学什么」 |
| **P3** | teach / quiz / judge 接进图里，四版对比 | kp 覆盖率、幻觉引用数、掌握判定可回溯 |
| **P4** | 进度条端到端 + Store 落库 | 关掉再开，进度不丢 |
| **P5** | sideqa + exam 挂进来 | 支线不污染主干 |

---

## 11. 待你拍板（5 个点）

1. **掌握判定归属**：由 teach 出结论（但必须引用 judge 证据），还是由 judge 直接出结论？
2. **quiz 由谁触发**：指挥官派发（我推荐，可控），还是 teach 自己叫？
3. **进度条粒度**：按知识点（最细）、按讲（最粗），还是双轨（讲为外圈、kp 为内圈）？
4. **穷尽标准**：按教材「讲-节」目录穷尽，还是按考纲考点穷尽（两者不完全重合）？
5. **资料缺口**：某 kp 题不足时，允许 quiz 生成变式顶上，还是必须在 UI 标红「资料不足」？
