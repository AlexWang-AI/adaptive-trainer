# 知识树流水线：从扫描版 PDF 到可教学的知识图谱

> 本文是从两份交接材料里反向还原出来的**完整技术路线**：
> - 桌面 `知识树日志.zip`（18 MB 事件流日志，6607 条事件 / 897 条助手消息 / 856 次工具调用）
> - 桌面 `知识树战略图谱.md`（战略快照）
> - 以及仓库里**仍然存在**的 41 个 `tools/*.py`、5 个 `tools/*.ps1`
>
> 结论先说：**这套流程本身已经是泛化的**。第 3 讲之后的导图就是「从教材正文标题自动推导」的，
> 不是人工画的。所以线代 / 概率可以直接复用同一条路线 —— 前提是先把 PDF 变成文本。

---

## 一、全景（五段 + 三道门禁）

```
① 解析   MinerU（CPU / basic-ONNX）分批 → textbook/chunks/*.md
          ↓  教训：GPU(DirectML) 在第 241 页之后静默崩溃；30 页/批 + 40 分钟超时；幂等跳过
② 清洗   textbook_postprocess.py / load_body()
          ↓  教训：GBK 反转乱码（新版→鏂扮増）、base64 图片行、>800 字符长行
③ 建树   mindmap_lectureNN.json（L1 白名单）
            → build_tree_v2.py 逐 L1 块：填 L2 / L3 / 结论 / 例题，每条必须带**逐字 evidence**
          ↓  硬门禁：evidence 不在原文 → 先在原文里搜一句替换 → 搜不到就丢弃并计数
④ 校验   coverage_check.py（例题/定义/定理/方法总结覆盖率）
          check_headings.py（教材二级标题覆盖率）
          audit_all.py / check_checklist.py / check_syllabus*.py / purge_irrelevant.py
          critic_tree.py（红队找漏找错）→ apply_critique.py（只收 evidence 能命中的）
          ↓  教训：红队不收敛，最终用**确定性覆盖率**当验收尺子，红队只做抽查
⑤ 挂接   extract_examples.py（抽例题原文）→ map_examples.py（题→点）→ attach_orphans.py（点→题）
          build_types.py / build_types_extra.py（题型层 144） / build_extras.py（提速层 124）
          ↓
⑥ 交付   lecture_XX_weighted.json（唯一事实源）→ 运行时由 build_curriculum.py 编译
```

## 二、① 解析：MinerU 的确切用法

本来这台机器上就有 `.venv-mineru`（mineru 4.x，含 `mineru-kit.exe`），模型在 `C:\mineru_models`（ONNX）。

```powershell
# 实际的调用（tools/parse_with_timeout.ps1 / tools/run_mineru.ps1）
$env:MINERU_MODEL_SOURCE = 'modelscope'
mineru-kit parse "<pdf>" --pages 241-270 --output "textbook/chunks/p241_270.md" --tier basic
```

关键参数与理由（都来自日志里踩过的坑）：

| 点 | 值 | 理由 |
|---|---|---|
| 档位 | `--tier basic`（纯 ONNX） | standard 档的 llama.cpp 在本机中文路径下初始化崩溃 |
| 设备 | `cpu`（`~/.mineru/config.yaml: onnx_device: cpu`） | GPU 走 DirectML，241 页之后**无报错直接退出**，stderr 无 traceback |
| 批大小 | 15~30 页 | 30 页在「极限计算 + 大量例题」段必崩；15 页最稳，30 页最快 |
| 单批超时 | 15~40 分钟 | 超时即杀、记 FAIL、继续下一批；不让一页坏页拖死整本 |
| 幂等 | 目标 md 存在就 `continue` | 中断后重跑自动续跑，这是能跑完 586 页的前提 |
| 输出 | 一个 chunk 一个 `.md` | 后续所有脚本按 lecture→chunk 映射取原文 |

实测速度：早期 38 秒/页（586 页 ≈ 6 小时），本轮线代 4 页冒烟 38 秒（含模型加载）≈ 3~8 秒/页，
说明模型已缓存、且公式密度低于高数的重页面。

## 三、② 清洗：三个必须处理的脏

1. **GBK 反转乱码**：MinerU 在中文 Windows 上输出的中文是「UTF-8 字节被当 GBK 解码」（新版 → 鏂扮増）。
   可逆：`line.encode("gbk").decode("utf-8")`，**必须在整行上做**，逐字做会丢字节。
   工具：`textbook_postprocess.py: fix_mojibake()` / `build_tree_v2.py: fix_line()`。
2. **base64 图片行**：`![](...)` 一行几万字符，直接剔除，否则 prompt 爆掉。
3. **超长行**：>800 字符的行（内嵌公式块 / 表格）也剔除。
   两者都在 `load_body()` 里，是 `pick_source()` 能正常工作的前提。

## 四、③ 建树：L1 白名单 + evidence 硬门禁

这是整套流程最核心的设计，也是「模型不许编知识点」的实现方式。

### 4.1 L1 从哪来：导图 → 之后改为教材标题

- 第 1、2 讲：`mindmap_lecture01/02.json` 是**按教材每讲开头的「基础知识结构」思维导图人工录入**的
  （桌面上那两张 `知识树图片/*.png` 就是这类导图页）。
- 第 3 讲起：日志里明确写着
  `"source": "教材正文标题自动推导（无人工导图，待用户校准）"` ——
  L1 分支从 OCR 出来的 `## 数字 标题` 推导，L2 由正文抽取。
- **这就是泛化的钥匙**：新书不需要画导图，只要有标题层级。

### 4.2 逐块填充（`build_tree_v2.py`）

对每个 L1 块：

1. `pick_source(body, [L1名] + L1候选L2名, budget=26000)`：按名字在原文里定位片段（每条命中行 ±3/+90 行）；
2. 提示词要求模型只做填空：
   - L1 名称逐字使用给定 L1（`data["name"] = l1["name"]` 强制覆盖）；
   - L2 优先用清单里的名字，清单没有的才允许新增；
   - L3 = 具体题型/步骤/易错点 1~4 条；
   - 结论分 `primary`（定理/公式本体）/`secondary`（推论/变形/秒杀）；
   - **每条都要 evidence：从原文逐字复制 6~120 字**；
   - examples 写教材例题编号（`例1.3`）。
3. 确定性门禁 `keep()`：
   - `norm(evidence) in norm(source)`（去 LaTeX 命令、空白、标点后比对）；
   - 且 `_relevant(name, evidence)`（节点名按 2 字片段至少命中一次，防止拿无关句子凑数）；
   - 不满足 → 用 `_search_evidence()` 在原文里按名字搜一句替代 → 还不行就**丢弃并计数**
     （日志里常见「丢弃证据不实 23 条」）。

### 4.3 建树实测规模（高数 18 讲）

| 指标 | 数值 |
|---|---|
| L1 分支 | 71 |
| L2 知识点 | 232 |
| L3 要点 | 1068 |
| 结论 | 375（primary 208 / secondary 167） |
| 教材例题挂接 | 581 处 |
| 题型 | 144 个（挂载 309 次） |
| 提速技巧/陷阱 | 124 条（挂载 118 次） |

## 五、④ 校验：三道确定性门禁 + 一个红队

| 工具 | 尺子 | 阈值 / 结果 |
|---|---|---|
| `coverage_check.py` | 原文「例 X.Y」「定义 N」「定理 N」「方法总结」是否都能在树里找到 | 例题覆盖率 **99.5%**（9 讲 100%，第1讲 95%） |
| `check_headings.py` | 教材二级标题 vs 树节点（2 字片段命中即覆盖） | 产出 `HEADING_GAP.md` |
| `check_checklist.py` | 88 条必会清单（`docs/EXAM_CHECKLIST.md`）是否被树覆盖 | 产出 `CHECKLIST_GAP.md` |
| `check_syllabus*.py` | 考纲条目 vs 树（字面 / 语义 / 同义三版） | 产出 `SYLLABUS_GAP*.md` |
| `critic_tree.py` → `apply_critique.py` | 红队只报 missing/wrong/incomplete，每条必须带 evidence；修复脚本只收 evidence 能命中的 | 第一轮 279 条，补进 251 条，28 条待裁决 |

**战略结论（日志里反复出现的教训）**：红队永远不会收敛（第二轮仍能挑 30+ 条），
所以验收改用覆盖率这种「有限集合上的比对」，红队降级为质量抽查。这是这套流水线能收尾的原因。

## 六、⑤ 挂接：例题 / 题型 / 提速层

| 脚本 | 作用 |
|---|---|
| `extract_examples.py` | 从原文抽例题原文 → `examples_lecture_XX.json`，并写回 `node.examples` |
| `map_examples.py` | 例题 → 知识点（按例号所在段落命中的 L2 名） |
| `attach_orphans.py` / `resolve_orphans.py` | 知识点 → 例题（反向补挂），孤儿节点 17 → 10 |
| `build_types.py` + `build_types_extra.py` | 题型层：feature / steps / 关联 kps |
| `build_extras.py` + `add_missing_extras.py` | 提速层：秒杀技巧 / 陷阱，`enhances` 指向教材知识点 |
| `render_tree_png.py` / `render_overview.py` | 每讲一图 + 总览图（人眼验收用） |

## 七、泛化到线代 / 概率：要改的只有三处

| 环节 | 高数现状 | 线代/概率需要 |
|---|---|---|
| 解析 | `parse_with_timeout.ps1` 写死路径/586 页 | 已新增 `tools/parse_book.ps1`（参数化：`-Pdf -Tag -Total -Size -TimeoutMin`，带幂等） |
| 讲次→原文映射 | `_tree_common.py: LECTURE_SRC` 写死 18 讲 + 高数页范围 | 新增 `LECTURE_SRC_XIANDAI` / `_GAILV`，页范围从 OCR 出来的「第 N 讲」标题行定位 |
| L1 白名单 | `mindmap_lectureNN.json`（前 2 讲人工，其余标题推导） | **从标题推导**，产出后用人工/规则校准 |

其余（build_tree_v2 的提示词与门禁、coverage、critic、types/extras、编译进课程表）**完全复用，不改一行**。

## 八、本轮已执行

1. 读完两份材料 + 41 个工具脚本，还原出上面这条线；
2. 4 页冒烟：MinerU 在线代 PDF 上正常出文（标题、公式、正文都可读）；
3. 起后台任务跑 **线代 213 页 + 概率 173 页**（30 页/批、40 分钟超时、幂等续跑），
   日志 `work/parse_xiandai.log`、`work/parse_gailv.log`；
4. 下一步（OCR 完成后）：按「第 N 讲」标题切分 → 生成 mindmap → 跑 build_tree_v2 → 三道门禁 → 编译进 `curriculum_data.json` 的第 19~30 讲。

## 九、风险与口径

- **页范围靠标题定位**：OCR 若有整页丢失，讲次切分会错位，需要用 `check_headings.py` 反查；
- **线代/概率的「基础知识结构」页**：如果每讲开头的导图页被 MinerU 当成图片，L1 只能从标题推导，
  与高数第 3 讲之后的做法一致，可接受，但要人工抽 1~2 讲核对；
- **教材例题编号**：线代用「例 1.1」同构，概率可能用「例 1.1」或「例1-1」，正则要兼容；
- **权重档（must/high/edge）**：高数是人工按考频打的，线代/概率需要同样打一遍（按考纲要求 + 真题频次）。
