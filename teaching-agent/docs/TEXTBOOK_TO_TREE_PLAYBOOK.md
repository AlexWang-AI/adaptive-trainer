# 从一本教材到可教学知识树：完整复刻手册

> **这份文档的读者是另一个 AI agent（DeepSeek Harness / Codex / Claude Code 等），不是人。**
> 目标：拿到**任意一本**扫描版或文字版教材 PDF，按本文从零做出同样可直接被教学系统消费的知识树，
> 过程可复现、可自测、可迭代。
>
> 本手册来自一套真实跑通的生产线（《张宇基础30讲·高等数学》586 页 → 18 讲 / 71 分支 / 232 知识点 /
> 1068 要点 / 375 结论 / 581 例题挂接 / 144 题型 / 124 提速技巧），所有参数、门禁、事故都来自
> 那份工程的实际日志，不是设想。
>
> 配套：`docs/TREE_PIPELINE_PLAYBOOK.md`（那套工程的技术复盘）、`docs/CURRICULUM_ALIGNMENT.md`
> （怎么把树接进教学应用）。

---

## 0. 你会得到什么（先看验收标准，再动手）

一棵「可直接利用的知识树」= 一个 JSON 文件，满足：

| 维度 | 硬指标 | 为什么是这个数 |
|---|---|---|
| 层级 | 讲（L0）→ 分支（L1）→ 知识点（L2）→ 要点（L3），外加**结论层** | 只有两层时，模型讲不清「同一个知识点在不同题型下的差别」 |
| 覆盖率 | 教材例题覆盖率 **≥ 95%**（生产环境实测 99.5%） | 例题是教材里唯一「有限且可枚举」的集合，能算百分比 |
| 证据 | 每个 L1/L2/L3/结论**必须**带 `evidence`：从原文逐字复制的句子 | 没有 evidence 的节点 100% 是模型编的 |
| 粒度 | 每个 L2 至少 1 条 L3 要点；每个分支至少 1 条结论 | 否则这个知识点无法出题 |
| 例题 | 每个 L2 要么挂上例题号，要么显式标 `no_example: true` | 「没挂」和「本来就没有」必须能区分 |
| 结构缺陷 | 空结论分支 0、重复补点 0、截断文本 0、孤儿知识点 ≤ 5% | `audit_all.py` 可直接跑出来 |

不满足就不要进入下一阶段 —— 这是全流程唯一的原则。

### 0.1 如果你是接手 agent：照这个顺序敲（TL;DR）

```powershell
# 1) 侦察（自己写 10 行 pymupdf）：页数 / 有无文字层 / 讲数 / 例题编号风格
# 2) 冒烟解析 4 页
.\tools\parse_book.ps1 -Pdf "<book>.pdf" -Tag <tag> -Total <N> -StartPage 1 -EndPage 4 -Size 4 -TimeoutMin 15
# 3) 整本解析（幂等，断了就重跑）
.\tools\parse_book.ps1 -Pdf "<book>.pdf" -Tag <tag> -Total <N> -Size 30 -TimeoutMin 40
# 4) 分讲（先 --dry-run 看边界，人工确认后再跑）
python tools\split_book.py --tag <tag> --book "<书名>" --start-no <全局首讲号> --dry-run
python tools\split_book.py --tag <tag> --book "<书名>" --start-no <全局首讲号>
# 5) 每讲：白名单 → 建树 → 权重
python tools\derive_mindmap.py --lecture <NN> --file textbook\chunks\fixed\<tag>_lecture<NN>.md --title "<讲名>"
python tools\build_tree_v2.py  --lecture <NN> --file textbook\chunks\fixed\<tag>_lecture<NN>.md
python tools\weight_one.py     --lecture <NN>
# 6) 例题 / 题型 / 提速
python tools\extract_examples.py --lecture <NN>; python tools\map_examples.py --lecture <NN>
python tools\attach_orphans.py;                  python tools\resolve_orphans.py --lecture <NN>
python tools\build_types.py --lecture <NN>;      python tools\build_types_extra.py
python tools\build_extras.py --lecture <NN>;     python tools\add_missing_extras.py
# 7) 门禁（不绿就别继续）
python tools\coverage_check.py; python tools\check_headings.py; python tools\audit_all.py
python tools\purge_irrelevant.py --dry-run
# 8) 红队抽查
python tools\critic_tree.py --lecture <NN>; python tools\apply_critique.py --lecture <NN>
# 9) 人眼看图 + 编译进应用
python tools\render_tree_png.py --lecture <NN>; python scripts\build_curriculum.py
```

一讲的循环是 5→9，做完一讲再下一讲。**不要**先批量跑 18 讲的树再回头补门禁 ——
一旦白名单或分讲有问题，你要重跑全部。

---

## 1. 数据契约（下游所有脚本只认这四种文件）

### 1.1 `textbook/tree/lecture_NN_weighted.json` —— 主干（唯一事实源）

```jsonc
{
  "lecture": 1,
  "title": "函数极限与连续",
  "blocks": [                          // L1 分支
    {
      "name": "计算（求极限的方法）",
      "role": "重中之重",               // 教材导图上的角色标注
      "tier": "must",                  // must | high | edge（考频档，单独一轮打）
      "tier_reason": "……",
      "evidence": "教材原文里讲这一块的那句话",
      "nodes": [                       // L2 知识点
        {
          "name": "极限四则运算规则",
          "evidence": "……",
          "examples": ["例1.14", "例1.21"],
          "children": [                // L3 要点：题型 / 步骤 / 易错点
            { "name": "适用条件：各项极限均存在且分母极限不为零", "evidence": "……" }
          ]
        }
      ],
      "conclusions": [                 // 结论层
        { "level": "primary",   "statement": "极限的四则运算法则：……", "evidence": "……" },
        { "level": "secondary", "statement": "……",                     "evidence": "……" }
      ]
    }
  ]
}
```

### 1.2 `lecture_NN_types.json` —— 题型层

```jsonc
{ "lecture": 1, "title": "……",
  "types": [{ "name": "0/0 型未定式求极限", "feature": "分子分母同趋于 0……",
              "steps": ["先尝试等价无穷小替换", "检查洛必达条件", "泰勒展开"],
              "kps": ["洛必达法则", "泰勒公式"], "source": "method" }] }
```

### 1.3 `lecture_NN_extras.json` —— 提速层（教材没讲、考场能省时间的）

```jsonc
{ "lecture": 1, "items": [{ "name": "泰勒展开阶数速判", "type": "秒杀技巧",
    "when": "……", "how": "……", "risk": "……", "source": "external",
    "enhances": "泰勒公式应用时的展开原则" }] }
```

### 1.4 辅助文件

| 文件 | 内容 |
|---|---|
| `mindmap_lectureNN.json` | L1 白名单 `{lecture,title,source,l1:[{name,role,l2:[]}]}` |
| `examples_lecture_NN.json` | 例题原文 `{attached,total,unattached:[{id,text,line}]}` |
| `mapping_lecture_NN.json` | 例题→知识点 `{mapping:[{example,kps:[]}],attached,unknown_kp}` |
| `lecture_map_<tag>.json` | 分片→讲次映射 `{"01":{title,chunks,lines,chars}}` |
| `coverage_lecture_all.json` / `HEADING_GAP.md` / `AUDIT.md` / `SYLLABUS_GAP*.md` | 各门禁报告 |

---

## 2. 环境准备（Windows 实测，Linux 同理）

```powershell
$root = "C:\path\to\project"
$py   = "C:\...\Python311\python.exe"        # 主环境：跑 tools/*.py
$mpy  = "$root\.venv-mineru\Scripts\python.exe"  # 解析环境：只装 mineru
```

1. **MinerU**：`pip install mineru`，模型目录 `C:\mineru_models`（**不能有中文路径**，
   否则 llama.cpp 报 Unicode 错）。
2. `~/.mineru/config.yaml` 必须写死：
   ```yaml
   model:
     onnx_device: cpu        # ← GPU(DirectML) 会在第 241 页后静默退出，无 traceback
     base_dir: C:\mineru_models
   ```
3. 主环境依赖：`pymupdf`（探测页数/文字层）、`openai`（模型调用）、`python-docx`（可选）。
4. **PowerShell 脚本必须带 UTF-8 BOM**，否则 Windows PowerShell 5.1 按 GBK 解析，
   中文字符串会把引号吃掉 → `表达式或语句中包含意外的标记`。
   ```powershell
   $enc = New-Object System.Text.UTF8Encoding($true)
   [System.IO.File]::WriteAllText($path, $text, $enc)
   ```
5. 模型调用统一走 `backend/config.py:load_config()` + `backend/llm.py:LLMClient` + `backend/runner.py:extract_json`。
   **不要**在每个脚本里自己拼 HTTP。

---

## 3. 总流程（12 步，每步都有门禁）

```
S0 侦察    页数 / 有无文字层 / 讲数 / 例题编号风格 / 目录
S1 解析    MinerU 分批 → textbook/chunks/<tag>_XXX_YYY.md
S2 清洗    去 base64 / 去超长行 / GBK 反转 → fixed/
S3 分讲    按「基础知识结构」锚点切 → <tag>_lectureNN.md + lecture_map.json
S4 白名单  导图（有人工）或 derive_mindmap（标题推导）→ mindmap_lectureNN.json
S5 建树    build_tree_v2 → lecture_NN_v2.json（带 evidence 硬门禁）
S6 权重    weight_one → lecture_NN_weighted.json（must/high/edge，单独跑）
S7 例题    extract_examples → map_examples → attach_orphans → resolve_orphans
S8 题型    build_types → build_types_extra
S9 提速    build_extras → add_missing_extras
S10 门禁   coverage_check / check_headings / check_syllabus×3 / audit_all /
           purge_irrelevant / reevidence / evidence_fallback
S11 红队   critic_tree → apply_critique（只收 evidence 能命中的）
S12 交付   render_tree_png / render_overview / 编译进应用（build_curriculum.py）
```

---

## 4. 逐步操作手册

### S0 侦察（10 分钟，别跳）

```python
import fitz
doc = fitz.open(pdf)
print("pages", doc.page_count, "toc", len(doc.get_toc()))
chars = sum(len(doc.load_page(i).get_text("text").strip()) for i in range(min(8, doc.page_count)))
print("前 8 页字符数", chars)   # 0 → 纯扫描件，必须走 MinerU
```

要记下四件事，后面都要用：

| 记录项 | 用途 | 张宇30讲·高数的实际值 |
|---|---|---|
| 页数 | 分批总数 | 586 |
| 有无文字层 | 决定是否必须 MinerU | 无（扫描版），另有一份 OCR 版 |
| 讲数 | 树的 L0 数量 | 18（线代 6 / 概率 6 是另两册） |
| 例题编号风格 | 覆盖率正则 | `例1.14`（`例\s*(\d+)\.(\d+)`） |
| 目录页区间 | 切讲时要跳过 | 前 ~30 页是目录/序/出版信息 |

### S1 解析（MinerU，不用传统 OCR）

MinerU 是**版面感知**解析（文档版式 + 公式 + 表格 + 阅读顺序），不是 Tesseract 那种逐行 OCR。
输出 markdown（公式保留 LaTeX）。

```powershell
# 先 4 页冒烟，确认出文再整本
.\tools\parse_book.ps1 -Pdf "<book>.pdf" -Tag <tag> -Total <N> -StartPage 1 -EndPage 4 -Size 4 -TimeoutMin 15
# 整本（幂等：目标文件存在就跳过，中断后重跑自动续跑）
.\tools\parse_book.ps1 -Pdf "<book>.pdf" -Tag <tag> -Total <N> -Size 30 -TimeoutMin 40
```

| 参数 | 建议值 | 依据 |
|---|---|---|
| `--tier` | `basic`（纯 ONNX） | standard 档的 llama.cpp 在中文路径下初始化崩溃 |
| 设备 | `cpu` | GPU 会在重内容页（241 页后）**无报错直接消失** |
| 批大小 | 30 页（稳一点用 15） | 30 页最快；公式密集段 30 页会崩 → 降到 15 |
| 单批超时 | 40 分钟 | 超时杀掉、记 FAIL、继续下一批；坏页不许拖死整本 |
| 幂等 | 目标 `.md` 存在则跳过 | 这是能跑完 586 页的前提 |

**实测速率**：约 10~15 秒/页（本机 CPU，模型已缓存）。586 页 ≈ 2~2.5 小时；386 页（线代+概率）≈ 1.2~1.6 小时。

产物：`textbook/chunks/<tag>_001_030.md`… + `log_/err_` 日志。

### S2 清洗（三个必须处理的脏）

```python
def clean(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("![]("):      # base64 图片行，一行几万字符
        return None
    if len(line) > 800:                          # 内嵌公式块 / 表格
        return None
    try:
        line = line.encode("gbk").decode("utf-8")  # GBK 反转乱码（新版→鏂扮増），必须整行做
    except Exception:
        pass
    return line
```

**为什么必须做**：不去 base64，24k 字符的 prompt 窗口一张图就吃光；不做 GBK 反转，
后面 evidence 逐字比对会全部失败（模型看到的是乱码）。

### S3 分讲

```powershell
python tools\split_book.py --tag <tag> --book "<书名>" --glob "<tag>*_*.md" --dry-run  # 先看边界
python tools\split_book.py --tag <tag> --book "<书名>"
```

判据优先级：
1. **`基础知识结构`**（每讲开头都有一页导图页）—— 最稳的锚点；
2. 锚点往回 60 行找 `第N讲` 取讲次，标题行优先；
3. 找不到就按顺序补号。

**线代/概率特有的两个参数**（它们的开头有一讲「第0讲 零基础课」，不算在 30 讲里）：

```powershell
python tools\split_book.py --tag xiandai --book 线性代数 --start-no 19 --skip-first 1 `
       --titles "行列式,矩阵,向量组,线性方程组,特征值与特征向量,二次型"
```

`--skip-first 1` 丢掉第0讲那个锚点，`--titles` 直接从**目录页**抄（OCR 出来的目录很准，
比从正文猜讲名可靠得多）。

**必须人工核对一遍**：打印出来的「第N讲 / 讲名 / 行数 / 字数」表里，
字数 < 3000 的讲次基本是切错了（目录被当成正文、或两讲黏在一起）。
目录页里的「第1讲 ……1」这种行**不能**当锚点 —— 否则整本目录会被算成第 1 讲（真实踩过）。

### S4 L1 白名单（树的骨架，决定后面一切）

两个来源，按优先级：

1. **教材有导图页**（每讲开头「基础知识结构」那种思维导图）→ 人工/模型录入
   `mindmap_lectureNN.json`。这是最理想的，因为 L1 就是教材作者的分块。
2. **没有导图** → `tools/derive_mindmap.py` 从正文标题推导：

```powershell
python tools\derive_mindmap.py --lecture 19 --file textbook\chunks\fixed\xiandai_lecture19.md `
       --title "行列式" --book "线性代数" [--dry-run]
```

硬门禁（脚本内置）：L1 名字 2~14 字、不含「注/解/例/习题/答案/基础知识结构」这类版式词、
且**必须在原文里命中至少一个 2 字片段**；L2 同规则。命不中的直接丢并打印。

**为什么必须有白名单**：v1 让模型自由切块，切出了「第1讲」「基础知识结构」这种伪分支，
整棵树作废（`extract_tree.py` 的教训）。

### S5 建树（核心步骤）

```powershell
python tools\build_tree_v2.py --lecture 19 --file textbook\chunks\fixed\xiandai_lecture19.md
```

它做的事：

1. `pick_source(body, [L1] + L1的候选L2, budget=26000)`：按名字在原文里定位片段（命中行 ±3/+90 行）；
2. 一次模型调用填一个 L1 块（**L1 名字强制覆盖成白名单里的**）；
3. 每条 evidence 过两道门禁：
   - **逐字存在**：`norm(evidence) in norm(source)`（norm = 去 LaTeX 命令/花括号/美元符/空白/标点）；
   - **相关性**：节点名切 2 字片段，至少一个出现在 evidence 里（防止拿无关句子凑数）；
   - 不过 → `_search_evidence()` 按名字在原文搜一句替代 → 还不过 → **丢弃并计数**。
4. 产物：`lecture_NN_v2.json` + `.md`（人眼可读版）。

**正常输出**：每讲丢弃 2~46 条证据（日志实测）。丢弃 0 条反而可疑 —— 说明门禁没生效。
丢弃 > 60 条说明原文片段选得不对（`budget` 太小或讲次切错）。

### S6 权重（必须单独跑，不许在建树时顺便判）

```powershell
python tools\weight_one.py --lecture 19     # 读 _v2.json → 写 _weighted.json
```

三档：`must`（几乎每年必考/大题高频）、`high`（常考，小题或组合）、`edge`（低频/纯概念）。

**为什么单独跑**：建树时让模型「顺便」判权重，它会把重要章节判成次要 ——
生产环境里「反常积分」就是这么被埋掉的。

### S7 例题抽取与挂接（覆盖率的分母）

```powershell
python tools\extract_examples.py --lecture 19   # 抽原文「例X.Y」→ examples_lecture_NN.json + node.examples
python tools\map_examples.py    --lecture 19   # 例题 → 知识点（LLM，只许从本讲清单里逐字选）
python tools\attach_orphans.py                 # 反向：给没例题的知识点挑最匹配的例题
python tools\resolve_orphans.py --lecture 19   # 定性：真没有例题 → 标 no_example
```

生产结果：孤儿节点 17 → 10；例题覆盖率 22% → 99.5%。

**注意**：`map_examples` 允许「判断不了就写空数组」，所以覆盖率里要区分
「没挂」（缺陷）和「本来就没有」（标 `no_example`）。

### S8 题型层 / S9 提速层

```powershell
python tools\build_types.py --lecture 19        # 4~6 个题型/讲：name/feature/steps/kps
python tools\build_types_extra.py               # 给「没有任何题型覆盖」的知识点补题型
python tools\build_extras.py --lecture 19       # 4~6 条秒杀技巧/特殊结论/陷阱
python tools\add_missing_extras.py              # 按必会清单补齐漏网的技巧
```

判断标准：题型必须能落到 `kps` 里的具体知识点（逐字选），落不到的就是凑数。

### S10 质量门禁（五把尺子，全是确定性代码）

```powershell
python tools\coverage_check.py                   # 例题/定义/定理/方法总结覆盖率
python tools\check_headings.py                   # 教材二级标题 vs 树节点（→ HEADING_GAP.md）
python tools\check_syllabus.py                   # 考纲/考点表 字面版
python tools\check_syllabus_syn.py               # 同义版
python tools\check_syllabus_semantic.py          # 语义版（模型判断，仅作参考）
python tools\check_checklist.py                  # 88 条必会清单（→ CHECKLIST_GAP.md）
python tools\audit_all.py                        # 结构体检（→ AUDIT.md）
python tools\purge_irrelevant.py [--dry-run]     # 证据与节点无关 → 删
python tools\reevidence.py --lecture 19          # 证据可疑 → 回原文重找
python tools\evidence_fallback.py                # 还缺 → 确定性兜底
```

每把尺子的判定逻辑（必须照抄，否则口径不一致）：

| 门禁 | 逻辑 | 通过线 |
|---|---|---|
| `coverage_check` | 原文所有 `例 X.Y` 是否能在树的 `examples` 或节点名里找到；`定义 N`/`定理 N` 计数；`方法总结` 条数 | 例题 ≥95%（实测 99.5%） |
| `check_headings` | 讲内每个 `##` 标题，取 2 字片段在树里检索，命中 ≥1 即覆盖 | 未覆盖 ≤10% |
| `check_checklist` | 88 条必会清单逐条在「树 + 提速层」里检索 | 全部命中或人工裁定 |
| `audit_all` | 空结论分支 / 重复补点 / 截断（以「根号/当且/，如」结尾）/ 无例题 | 前三项 0 |
| `purge_irrelevant` | 节点名 2 字片段是否命中 evidence | 命中率 100% |

### S11 红队与回填（只做抽查，不做收敛判据）

```powershell
python tools\critic_tree.py --lecture 19     # → critique_lecture_19.json
python tools\apply_critique.py --lecture 19  # 只补 evidence 能命中的；其余记待裁决
```

红队提示词只让报三类问题：`missing`（原文有树里没有，尤其「N 种/N 类」被截断）、
`wrong`（条件/层级/张冠李戴）、`incomplete`（要点不足以做题）。每条必须带 evidence。

**生产结果**：第一轮 279 条 → 补进 251 条 → 28 条待裁决。
**第二轮仍能挑出 30+ 条** —— 所以红队**不是**收敛判据，覆盖率才是。

### S12 可视化 + 交付

```powershell
python tools\render_tree_png.py --lecture 19    # 每讲一张结构图（人眼验收）
python tools\render_overview.py                 # 全书总览（每讲一行）
python scripts\build_curriculum.py              # 编译成运行时课程表（接进教学应用）
```

编译这一步（本工程新增）把树压成 `backend/curriculum_data.json`，运行时只读它：
id 在这里定死（`l19-b02-k03`），前端/后端不用再碰 `textbook/`。

### 多册合并的编号约定（做第二、第三册时必看）

| 约定 | 值 | 说明 |
|---|---|---|
| 全局讲次 | 高数 1–18、线代 19–24、概率 25–30 | 三册合成 30 讲，前端不区分册也能排序 |
| 切讲 | `split_book.py --tag xiandai --start-no 19 --skip-first 1 --titles "…"` | 产物 `chunks/fixed/xiandai_lecture19.md`，映射表键是**全局讲次** |
| 树文件 | **统一** `lecture_{全局讲次:02d}_weighted.json` | `build_tree_v2 --lecture 19` → `lecture_19_v2.json` → `weight_one` → `lecture_19_weighted.json`，三册同一个命名，编译器不用分册名 |
| 编译清单 | `scripts/build_curriculum.py` 的 `BOOKS` | `{key, start, count, short, label}`，缺文件的讲自动跳过 |
| 分册信息 | `chapters[].book` / `kps[].book_name` | 前端可据此显示「线代 / 概率」徽标 |
| 试编译 | `build_curriculum.py --out work/test.json` | 不覆盖线上 `backend/curriculum_data.json`，草稿讲次先试编 |

**一册没做完不影响另一册**：编译器按「文件存在才编」工作，
所以可以先交付高数，线代/概率陆续补，课程表随之从 18 讲长到 30 讲。

---

## 5. 自测协议（每做完一讲就跑一遍，别攒到最后）

```markdown
□ 1. 结构：lecture_NN_weighted.json 里 blocks ≥ 2，每个 block 有 conclusions，每个 node 有 children
□ 2. 证据：随机抽 5 条 evidence，手动在原文里 grep，必须能原样搜到
□ 3. 丢弃数：2~46 条属正常；0 条或 >60 条都要查
□ 4. 覆盖率：coverage_check 单讲 ≥95%
□ 5. 标题：check_headings 单讲未覆盖 ≤10%
□ 6. 体检：audit_all 该讲空结论 0 / 截断 0 / 无例题 ≤2
□ 7. 人眼：看 render_tree_png 出来的图，能不能看懂这一讲的结构（30 秒判断）
```

以上 7 项全绿才算这一讲完成。全书的完成条件是：**每一讲都绿 + 总览图能看出全书脉络**。

---

## 6. 迭代协议（这是整套方法最容易做错的地方）

**错误做法**：跑红队 → 修补 → 再跑红队 → 发现还有问题 → 无限循环。
生产环境两轮红队分别挑出 279 / 30+ 条，第三轮还能挑 —— **红队永不收敛**。

**正确做法**：

| 阶段 | 判据 | 什么时候停 |
|---|---|---|
| 建树 | evidence 门禁丢弃率、每讲节点数 | 一讲产出即停，进 S6 |
| 补全 | `coverage_check` 例题覆盖率、`check_headings` 未覆盖率 | 覆盖率 ≥95% 且未覆盖 ≤10% 即停 |
| 抽查 | 红队 issues 的**证据命中率** | 红队产出的条目「能落回原文」的比例 ≥90% 即停 |
| 收尾 | `audit_all` 三类结构缺陷 | 全 0 即停 |

也就是说：**用「有限集合的比对」（例题/标题/清单/考纲条目）当收敛判据，
用红队做质量抽查**。这条是那套工程最重要的方法论。

---

## 7. 通用化矩阵：换一本书要改什么

| 环节 | 通用？ | 换书要改的地方 | 怎么自动判定 |
|---|---|---|---|
| S1 解析 | ✅ 完全通用 | 只换 `-Pdf` / `-Total` / `-Tag` | `fitz` 读页数 |
| S2 清洗 | ✅ 完全通用 | 无 | — |
| S3 分讲 | ⚠️ 半通用 | 锚点词（`基础知识结构`）、讲次正则（`第N讲`） | 先 `--dry-run` 打表，人工核边界 |
| S4 白名单 | ✅ 通用（走 derive_mindmap） | 无（有导图就用导图） | L1 命中率 ≥90% |
| S5 建树 | ✅ 完全通用 | 无（提示词是学科中立的「教研员」角色） | 丢弃率 2~46 条 |
| S6 权重 | ✅ 通用 | 三档定义按考试类型微调 | 每讲 must 占比 40%~60% |
| S7 例题 | ⚠️ 半通用 | 例题编号正则（`例1.1` / `例 1-1` / `Exercise 1.1`） | 在 S0 侦察里抽样看 |
| S8/S9 题型/提速 | ⚠️ 半通用 | 提示词里的学科示例（数学一 140 分档） | 每讲 4~6 个题型 |
| S10 门禁 | ⚠️ 半通用 | `check_syllabus`/`check_checklist` 的「考纲/必会清单」要换成本学科的 | 报告文件生成即生效 |
| S11 红队 | ✅ 完全通用 | 无 | — |
| S12 编译 | ✅ 通用（本工程新写的） | 无 | 编译后 KP 数 = 树里节点数 |

**换学科的实操顺序**：先用第 1 讲跑通 S1→S5，看树像不像样；像样了再批量跑；
不像样只改 S3/S4（分讲与白名单），不要改 S5 的提示词 —— 提示词一改，
evidence 门禁的统计基线就变了，你会分不清是书的问题还是提示词的问题。

---

## 8. 事故档案（每一条都真实发生过）

| # | 事故 | 症状 | 根因 | 修复 |
|---|---|---|---|---|
| 1 | GPU 解析静默崩溃 | 进程消失，stderr 无 traceback，卡在第 241 页 | DirectML 在重内容页挂掉 | 改 CPU |
| 2 | 中文乱码 | 「新版」变成「鏂扮増」 | MinerU 输出 UTF-8 被当 GBK 解码 | 整行 `encode("gbk").decode("utf-8")` |
| 3 | prompt 爆掉 | 单条消息几十万字符 | base64 图片行 | 剔除 `![](` 开头的行 |
| 4 | 伪分支 | L1 里出现「第1讲」「基础知识结构」 | v1 让模型自由切块 | L1 白名单 + 强制覆盖 |
| 5 | 证据造假 | 三条不同的知识点共用同一句「芝诺悖论」 | 只查「句子在原文存在」，不查「是否相关」 | 加相关性门禁（2 字片段命中） |
| 6 | 权重失真 | 反常积分被判成 edge | 建树时顺便判权重 | 单独跑 `weight_one.py` |
| 7 | 目录被当正文 | 第 1 讲吞了整本目录 | 用「第N讲」当切分锚点 | 改用「基础知识结构」当锚点 |
| 8 | 红队不收敛 | 第二轮仍 30+ 条，永远补不完 | 红队是「找茬」，没有有限集合 | 覆盖率当验收，红队降级为抽查 |
| 9 | PowerShell 语法错误 | `表达式或语句中包含意外的标记“OK”` | 脚本没有 UTF-8 BOM，PS5.1 按 GBK 解析 | 写文件时带 BOM |
| 10 | 批次超时拖死整本 | 一页坏页跑几小时 | 没有单批超时 | `Wait-Process -Timeout` + 杀进程 + 记 FAIL |
| 11 | 截断文本 | 节点名以「根号」「当且」「，如」结尾 | 模型输出被 max_tokens 截断 | `audit_all` 检出 → `reevidence` 重取 |
| 12 | 重复补点 | 同一 L2 下出现 2 个同名 L3 | 红队回填时没查重 | `apply_critique` 去重 + `audit_all` 复核 |
| 13 | 会话回收打断批处理 | 日志停在 `start xiandai 31-60`，没有 OK/FAIL；子进程还在跑但循环没了 | 长任务挂在会话后台任务上，会话侧被回收 | 改用 `tools/run_ocr_detached.ps1` 脱离会话启动（`Start-Process` + 日志），自己立刻返回 |
| 14 | 两个 MinerU 抢内存 | 空闲内存 327 MB，两个批次都变慢甚至一起被杀 | 同时跑两本书（或用户自己又开了一个） | **一次只跑一本**；启动前先 `Get-CimInstance Win32_OperatingSystem` 看空闲内存 ≥ 2 GB |
| 15 | 批次被杀后留空洞 | 31-60 的 md 没生成，但循环已经跑到 61 | 子进程被杀 → 脚本判 FAIL 继续下一批 | 幂等 + 事后按 `chunks` 列表核对连续性（缺哪段补哪段） |
| 16 | 第0讲打乱编号 | 线代/概率开头有「第0讲 零基础课」，按锚点顺序编号会把第1讲推后一位 | 按顺序补号 | `split_book.py --skip-first 1 --start-no 19`，讲名用 `--titles` 从目录抄 |

---

## 9. 提示词模板（照抄，改学科时只改示例）

### 9.1 建树（`build_tree_v2.py`，这是最关键的一个）

```
你是考研数学教研员。给你一块教材原文和该块的【导图节点清单】，请把内容填进这些节点。
规则：
1. L1 名称必须逐字使用给定的 L1；L2 优先使用给定清单里的名字，清单没有的才可新增。
2. 每个 L2 下给出 L3：具体题型/步骤/易错点（1-4 条）。
3. conclusions：一级结论（定理/公式本体，level=primary）和二级结论（推论/常用变形/秒杀，level=secondary）。
4. 每条都要 evidence：从原文逐字复制的句子（6-120字），不许改写。
5. examples：原文出现的例题编号（例1.3 这种），没有就空数组。
只输出 JSON：{"name":"L1名","evidence":"…","nodes":[…],"conclusions":[…]}
```

### 9.2 红队（`critic_tree.py`）

```
你是考研数学教研组的**审校（红队）**。给你一棵知识点树的一个分支，以及教材原文。
你的任务不是夸它，而是**找它漏了什么、错了什么**。只报三类问题：
1. missing：原文里有、树里没有的知识点/方法/结论（尤其『N 种/N 类』这种枚举被截断）
2. wrong：树里的表述与原文不符（条件写错、层级放错、结论张冠李戴）
3. incomplete：知识点在，但要点（L3）不足以支撑做题（缺条件/缺易错点/缺步骤）
每条必须给 evidence：从原文逐字复制一句作为依据。没有依据的不要报。
宁可少报，不许编。
```

### 9.3 权重（`weight_one.py`）

```
给每个分支打考频权重：must（几乎每年必考/大题高频出处）、high（常考，小题或与别章组合）、
edge（低频/仅特定科目考/纯概念）。判断依据：考点频次与重要性，不要按分支在书里的顺序猜。
```

### 9.4 题型（`build_types.py`）与提速（`build_extras.py`）

见 §4 S8/S9。核心约束：题型必须挂到具体知识点（逐字选），提速技巧必须写「什么情况下会翻车」。

### 9.5 例题映射（`map_examples.py`）

```
给每道例题标注它主要考的知识点（1-2 个），只能从知识点清单里选，名字必须逐字一致。
判断依据：这道题在算什么、用了什么方法、卡在哪一步。不要按题号或章节猜。
```

---

## 10. 一页 checklist（打印贴墙）

```
□ 侦察：页数/文字层/讲数/例题编号/目录区间 记下来了
□ 冒烟：4 页解析出文，中文不乱码
□ 整本解析：分批 + 超时 + 幂等，失败批次单独重跑
□ 分讲：边界表人工核过，字数 <3000 的讲次已修正
□ 白名单：每讲 L1 2~6 个，全部能在原文命中
□ 建树：每讲丢弃证据 2~46 条，节点数合理
□ 权重：must 占比 40~60%，重要章节没被判成 edge
□ 例题：覆盖率 ≥95%，孤儿 ≤5% 或已标 no_example
□ 题型：每讲 4~6 个，全部挂到具体知识点
□ 提速：每讲 4~6 条，都写了失效条件
□ 门禁：audit_all 三类缺陷全 0；check_headings 未覆盖 ≤10%
□ 红队：一轮抽查，只收 evidence 命中的
□ 人眼：看 PNG 能 30 秒讲清这一讲结构
□ 编译：build_curriculum.py 通过，KP 数 = 树节点数
```

---

## 11. 这套方法为什么有效（给接手者的判断依据）

1. **把「模型会不会编」变成「能不能在原文里找到」** —— evidence 逐字校验是全流程的地基。
2. **把「够不够全」变成可计算的覆盖率** —— 例题、标题、清单都是有限集合。
3. **把「分块」交给教材自己的结构** —— L1 白名单要么来自导图，要么来自标题，不让模型自由发挥。
4. **把「权重」单独抽出来** —— 判断类任务混在生成任务里，一定会被生成任务带偏。
5. **每个环节都有可复跑的脚本和可读的报告** —— 所以另一台机器、另一个 agent 能接手。

按本文做完一本书，你得到的不是一份笔记，而是一份**能被教学系统直接消费、且每一条都能回溯到教材原文的知识图谱**。
