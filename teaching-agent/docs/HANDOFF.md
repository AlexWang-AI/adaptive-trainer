# 交接文档（给下一个 Harness）

> 生成时间：2026-11-09
> 项目：考研数学一「张宇基础30讲」全量知识图谱
> 状态：18 讲全部建成，三层结构（教材树 / 提速层 / 题型层），六道门禁全绿

---

## 一、项目根目录

```
C:\Users\明\Desktop\第一版UI_ex_v2
```

**先读这份，别先读代码**：

| 文件 | 作用 |
|---|---|
| `战略.md`（241 行） | 战略基线 v2.0，**只增不改，AI 无权修改**，每轮动手前必读 |
| `docs/ACCEPTANCE_v3.md` | 验收报告（三层结构 + 六道门禁 + 四把尺子） |
| `docs/BLINDSPOT_ROUND3_FINAL.md` | 第三次扫盲结项：漏项四类原因 + 修复清单 |
| `docs/PROJECT_MAP.md` | 项目全貌（早期版本，部分内容已过时） |
| `docs/EXAM_CHECKLIST.md` | 88 条必会清单（防漏用的靶子） |

---

## 二、核心资产：`textbook/tree/`

### 2.1 三层数据（18 讲 × 3 套 = 54 个文件）

| 文件模式 | 数量 | 内容 | 层 |
|---|---|---|---|
| `lecture_XX_weighted.json` | 18 | **教材知识树**：L1 分支 / L2 知识点 / L3 要点 / 结论 / 例题 / 权重 | 教材层 |
| `lecture_XX_extras.json` | 18 | **外部提速层**：124 条秒杀技巧与特殊结论（`source: external`，含 `enhances` 指向强化的教材知识点） | 提速层 |
| `lecture_XX_types.json` | 18 | **题型层**：144 个题型（特征 / 步骤 / 关联知识点） | 题型层 |

### 2.2 汇总与索引

| 文件 | 内容 |
|---|---|
| `index.json` | 18 讲总索引（讲次、标题、分支数、知识点数、结论数） |
| `overview.png` | 全书三层总览图 |
| `lecture_XX_tree.png` | 每讲一张图（教材树 + 紫提速 + 青题型） |
| `MISTAKES.md` + `mistakes.json` | **易错点索引 175 条**（考前只看这一页） |
| `AUDIT.md` / `audit_all.json` | 结构体检报告 |
| `coverage_lecture_all.json` | 每讲例题覆盖率 |
| `HEADING_GAP.md` | 教材标题覆盖缺口（未覆盖 7，全为 OCR 乱码） |
| `SYLLABUS_GAP_SYN.md` | 教材考纲覆盖缺口（未覆盖 4，全为仅数三） |
| `CHECKLIST_GAP.md` | 必会清单缺口（0） |

### 2.3 中间产物（可忽略，勿当作数据源）

- `lecture_XX_v2.json`（18）：建树原始输出，已被 weighted 取代
- `critique_*.json` / `applied_*.json`（各 28）：红队审计记录与补入变更单
- `purge_report.json`、`EVIDENCE_REVIEW.md`：证据清理记录

---

## 三、原始数据：`textbook/chunks/`

| 路径 | 内容 |
|---|---|
| `chunks/*.md`（33 个） | MinerU 解析出的分片原文（p001–p240 为 30 页/批，q241–q586 为 15 页/批） |
| `chunks/fixed/*.md`（29 个） | 编码修复后的原文（GBK→UTF-8 逐行反转），**建树用的是这些** |

**修复编码的方法**（必须知道）：
```python
def fix(line):
    try:    return line.encode("gbk").decode("utf-8")
    except: return line
```

---

## 四、工具链：`tools/`

### 4.1 建树与内容

| 脚本 | 作用 |
|---|---|
| `build_tree_v2.py --lecture N --file <原文>` | 从原文抽 L1/L2/L3/结论/证据（含证据逐字校验 + 相关性校验 + 兜底搜索） |
| `critic_tree.py --lecture N` | 红队审计：找 missing / wrong / incomplete |
| `apply_critique.py --lecture N` | 回填红队意见（只收证据能命中原文的） |
| `fill_conclusions.py` | 补空结论分支 |
| `extract_examples.py` / `map_examples.py` | 抽例题 + 题→知识点挂接 |
| `resolve_orphans.py` / `attach_orphans.py` | 给无例题的知识点补挂或标注 |
| `reevidence.py` / `evidence_fallback.py` / `purge_irrelevant.py` | 证据修复三件套 |
| `build_extras.py` / `add_missing_extras.py` | 生成·补齐提速层 |
| `build_types.py` / `build_types_extra.py` | 生成·补齐题型层 |
| `build_mistakes.py` | 生成易错点索引 |

### 4.2 检查（四把尺子 + 体检）

| 脚本 | 依据 | 当前结果 |
|---|---|---|
| `check_checklist.py` | 88 条必会清单 | 88/88 命中 |
| `check_headings.py` | 教材 272 个章节标题 | 未覆盖 7（OCR 乱码） |
| `check_syllabus_syn.py` | 教材 145 条考点表 + 同义词 | 未覆盖 4（仅数三） |
| `audit_all.py` | 结构完整性 | 空结论/重复/截断/无例题 全 0 |
| `coverage_check.py` | 例题覆盖 | 99.1%（16/18 讲 100%） |

### 4.3 渲染

```
python tools/render_tree_png.py --lecture N   # 单讲三层图（需 Pillow + 微软雅黑）
python tools/render_overview.py               # 全书三层总览
```

---

## 五、当前规模（可复核）

```
教材知识树   232 知识点 / 376 结论 / 1074 条要点 / 363 道例题挂接
外部提速层   124 条（118 条已关联到教材知识点）
题型层       144 个（知识点覆盖 100%，0 孤儿）
易错点       175 条
```

---

## 六、质量门禁与已知限制

**六道门禁全绿**：空结论 0 / 重复 0 / 截断 0 / 无例题 0 / 脏证据 0 / 例题覆盖 99.1%

**已知限制（不要当 bug 修）**：
1. 例 14.10 原书解析后只剩题号，无名干，无法挂接
2. 讲 16 有 2 道例题（例16.11/16.12）挂接位置靠推断
3. 第 2–18 讲的 L1 来自正文标题推导，只有第 1 讲用了用户手绘导图
4. 提速层 124 条与题型层 144 个为模型生成 + 人工核对，公式已验，「该不该考/顺序」未经用户逐条确认
5. 数二 / 数三版本**未做**（用户指令只做数一）
6. `check_syllabus_semantic.py`（模型语义对照）**过度报告，已弃用**，不要拿它的结果当依据

---

## 七、复跑全部检查（一条命令）

```powershell
cd C:\Users\明\Desktop\第一版UI_ex_v2
$py = "C:\Users\明\AppData\Local\Programs\Python\Python311\python.exe"
& $py tools\audit_all.py
& $py tools\purge_irrelevant.py --dry-run
& $py tools\check_checklist.py
& $py tools\check_headings.py
& $py tools\check_syllabus_syn.py
& $py tools\coverage_check.py
```

**Python 环境**：`C:\Users\明\AppData\Local\Programs\Python\Python311\python.exe`（有 openai / pydantic / python-dotenv）
渲染用 DSH 自带 Python：`C:\Users\明\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（有 Pillow）

---

## 八、LLM 与追踪

- 配置在 `backend/.env`（含 `OPENAI_API_KEY`、`LANGSMITH_API_KEY`）
- LangSmith 项目：`mathneuron-planner`
- 主 agent（teach V5 两步法）在 `backend/agents/teach/`，选型结论见 `docs/teach-variant-decision.md`

---

## 九、接手建议（按顺序）

1. 读 `战略.md` 和 `docs/ACCEPTANCE_v3.md`，了解约束与现状
2. 跑一遍第七节的全部检查，确认数字与本文一致
3. 打开 `textbook/tree/overview.png` 和任意 `lecture_XX_tree.png` 看清结构
4. 若要继续补内容：先改 `docs/EXAM_CHECKLIST.md` 加条目，再跑 `check_checklist.py` 找缺口，最后补数据
5. **不要重跑 `build_tree_v2.py` 覆盖现有树**——现有数据经过多轮人工修订，重建会丢修订
