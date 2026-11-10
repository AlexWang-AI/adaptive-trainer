# planner · 路线规划 agent（总指挥 / 锚点）

**职责**：把「两周把极限学扎实」这种目标，拆成**可执行、可验收、可量化**的单元序列。
它不讲课、不出题、不判分。

## 输入 / 输出

```python
from agents.planner.schema import PlannerRequest, StudyPlan
from agents.planner.variants import run_auto

request = PlannerRequest(
    goal="两周把极限这一讲学扎实",
    scope=["lim"],              # 章节 id（lim/der/app/int/mv/di/ode/ser）或 kp id
    days=14,
    hours_per_day=2,
    level="大学低年级",
    profile_digest="暂无历史，按零基础处理",
)
run = run_auto(client, request)   # client = LLMClient(load_config())
plan: StudyPlan | None = run.plan
run.issues                        # 空列表 = 通过全部确定性校验
```

输出片段：

```
U01 order=1 sessions=3 | 极限的定义与性质
   kps: ['lim.definition']
   验收: 独立做出 ≥2 道原题 + 1 道变式，且步骤无卡顿
U02 order=2 sessions=3 | 无穷小与无穷大、等价无穷小
...
```

## 四版对比（6 条用例，deepseek-v4-flash，2026-11-01）

| 版本 | 通过 | 综合分 | 覆盖率 | 幻觉率 | 平均调用 | tokens | 耗时 | 策略 |
|---|---|---|---|---|---|---|---|---|
| V1 | 0/6 | 0.464 | 0.293 | **0.77** | 1 | 2,666 | 9.2s | 一次性直出，无白名单、无修复 |
| V2 | 5/6 | 0.996 | 0.986 | 0 | 2 | 7,493 | 14.8s | 两段式：先排骨架再补验收 |
| V3 | 5/6 | 1.000 | 1.000 | 0 | 1 | 4,314 | 9.5s | 白名单 + 修复环 |
| V4 | **6/6** | 0.998 | 0.994 | 0 | 3 | 16,360 | 28.8s | V3 + 教研自评 + 修订 |
| **V3R** | **6/6** | **1.000** | **1.000** | **0** | **1** | **4,195** | **10.5s** | **V3 + 确定性规整（选定）** |

### 结论：线上用 V3R

1. **V1 证明白名单是刚需**：不给 id 白名单，模型会发明 `lim.discontinuity`、`di.cartesian_swap`、`mv.chain_rule` 这类不存在但很像的 id，幻觉率 77%。
2. **V4 的自评确实能救回 6/6，但代价是 4 倍 tokens 和 3 倍耗时**；而 `normalize.py` 用**确定性拓扑排序 + 补漏 + 重编号**，一次 LLM 都不用，把同样的问题全修掉了。
   → **能确定性修的问题，不要多花一次 LLM 调用。**
3. c5（60 天 / 8 章 / 56 个知识点）是最难的用例：V2、V3 都栽在这里（漏知识点 / 前置顺序错），V3R 靠代码规整通过。

## 文件说明

| 文件 | 作用 |
|---|---|
| `schema.py` | `PlannerRequest` / `StudyPlan` / `Unit` / `ExitTest` |
| `prompts.py` | V1~V4 的 prompt 构造函数（共用 `COMMON_RULES`） |
| `checks.py` | 8 条确定性校验 + `evaluate_plan()` 量化打分 |
| `variants.py` | V1 / V2 / V3 / V4 / V3R / AUTO 六个入口 |
| `normalize.py` | 确定性后处理：补漏 → 拓扑排序 → 重编号 → 重算轮次 |
| `cases.jsonl` | 6 条评测用例（含 8 章大范围、单点定向补差） |
| `test_contract.py` | 9 条契约测试（离线，不打 API） |

## 已知限制

1. **教材页码为空**：`curriculum.py` 的 `textbook_ref` 还没回填（PDF 是扫描件，需 OCR），所以 `must_solve` 里只能写「第1讲 例题1-3」这种**讲次级**引用，还不能精确到页码。
2. **单元数没有硬上限**：大范围计划会拆到 16~23 个单元（60 天场景其实合理），但 UI 上需要分页展示。
3. **没有考虑学生已完成的部分**：`profile_digest` 只是文本摘要，还没接 `KpState` 结构化输入——接上之后可以直接跳过已掌握的单元。

## 复跑

```bash
cd backend
python -m pytest agents/planner/test_contract.py -q
python -m eval.planner_eval --variants V3R --workers 3
```
