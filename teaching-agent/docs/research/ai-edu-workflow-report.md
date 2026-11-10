<div class="toc-anchor"></div>

<div class="lead">

**这份报告要回答三个问题：**

1. 一台 AI 学习机，学生按下去之后，系统到底跑了哪些步骤？它的“智能体”工作流长什么样？
2. 它真正做对了什么、哪里在硬撑？技术债在哪里、能不能修？
3. 如果我们要复现，哪些能复现、哪些不能？最小可验证版本怎么搭？

主样本是科大讯飞 T90 / 星火 X2（2026 年 2 月发布，10 月 22 日又发了 X2.6），横向对照作业帮、学而思、小猿、豆包爱学、千问智学。**不讨论硬件参数**，只讨论 AI for Education 的调用链与产品工作流。

</div>

<div class="note">

**证据等级说明。** 本报告所有架构图都是“行为等价还原”，不是厂商内部实现图；不涉及破解固件、抓包或窃取商业机密。每条关键判断都标注了证据等级：

| 标记 | 含义 | 典型例子 |
|---|---|---|
| 已观察 | 公开产品行为、官方说明、用户实测可直接验证 | 拍照讲题、步骤批改、家长端报告 |
| 合理推断 | 根据行为与行业通用架构还原，厂商未确认 | 路由器、状态机、校验器、模型路由 |
| 厂商口径 | 官方宣传，未经独立复现 | “学会率 3.1 倍”“时间减少 64%” |
| 不可证实 | 内部实现细节、训练数据、判题算法 | 参数量、数据配比、具体 prompt |

</div>

# 0. 一页结论

<div class="keybox">

**三句话版本：**

1. **学习机的“智能体”不是自主 Agent，而是一条被产品流程写死的垂直工作流**：路由器 + 状态机 + 工具调用 + 大模型生成 + 校验器。它有多轮对话、工具调用和状态，但没有自主目标、开放工具使用、长期规划和可靠自检。
2. **能力上限由“感知 + 知识图谱 + 题库/考纲 + 校验器”决定，不由大模型决定。** 模型可以换：据报道，2025 年的 T30 用过“星火 + DeepSeek”双引擎；2026 年的 T90 换成星火 X2。内容和数据不能换。
3. **技术债集中在两处：感知债（手写/公式/图表识别）和校验债（步骤判题、答案一致性）。** 它们会级联：识别错 → 知识点错 → 路径错 → 批改错 → 家长不信任。

</div>

**五个可操作判断：**

- **体验的分水岭不在“讲得好不好”，而在“看不看得懂、判得对不对”。** 讲解是最后 20% 的体验，识别和判题是前 80% 的信任。
- **“个性化”真实存在，但只到题目级**：下一题做什么、下一节微课看什么；不是教学策略、动机、元认知层面的因材施教。
- **复现判定：工作流约 80% 可在 4—8 周内由 2—4 人小团队复现；产品护城河（内容/评测数据/渠道/品牌）约 20% 无法快速复现。** 复现一套“能跑的 AI 家教”不难，复现“敢让家长付 6000 元的可靠性”很难。
- **技术债的优先级：先修“能立刻提升信任”的（OCR 置信度门控、答案一致性、错题本清洗），不要先修“听起来最 AI”的（开放世界对话、情感陪伴）。**
- **验证方法：12 个黑盒探针，比看发布会更有效。** 同一道题拍三次、故意写非标准解、错误注入、跨章节综合题、开放追问——这四个就能把大多数产品的底摸清。

<div class="warnbox">

**一句话给决策者：** 如果你要进入这个方向，不要做“更会聊天的学习机”，要做“判得准、讲得对、可审计的垂直教辅工作流”。前者是模型能力，后者是产品能力；前者会贬值，后者会复利。

</div>

# 1. 体验层：学生实际经历的六个场景

先不谈架构。看学生按下按钮之后，屏幕上发生了什么。体验是工作流的外显；工作流是体验的内因。

<div class="diagram">

<div class="fig-title">图 1-1　AI 学习机的六个核心场景（行为示意，非真实截图）</div>

<div class="scene-grid">

<div class="scene-card">
<div class="scene-no">01</div>
<div class="scene-name">拍照讲题</div>
<div class="scene-line"><b>学生：</b>拍下手写作业题，或直接语音问“这题怎么做”。</div>
<div class="scene-line"><b>系统：</b>识别题目 → 分步提示 → 板书讲解 → 同类题。</div>
<div class="scene-pain">翻车点：识别错、讲解绕、不认非标准解。</div>
</div>

<div class="scene-card">
<div class="scene-no">02</div>
<div class="scene-name">精准学诊断</div>
<div class="scene-line"><b>学生：</b>选章节，做一组诊断题。</div>
<div class="scene-line"><b>系统：</b>定位薄弱点 → 生成路径 → 推微课和练习。</div>
<div class="scene-pain">翻车点：诊断题太少、标签错、跨章节弱。</div>
</div>

<div class="scene-card">
<div class="scene-no">03</div>
<div class="scene-name">作业批改</div>
<div class="scene-line"><b>学生：</b>整页拍照提交。</div>
<div class="scene-line"><b>系统：</b>判对错 → 标错因 → 收进错题本 → 推同类题。</div>
<div class="scene-pain">翻车点：对错颠倒、填空/手写失败、同一题结果漂移。</div>
</div>

<div class="scene-card">
<div class="scene-no">04</div>
<div class="scene-name">作文批改</div>
<div class="scene-line"><b>学生：</b>拍作文或输入文本。</div>
<div class="scene-line"><b>系统：</b>评分 → 评语 → 润色建议 → 范文。</div>
<div class="scene-pain">翻车点：主观、套话、评分不稳。</div>
</div>

<div class="scene-card">
<div class="scene-no">05</div>
<div class="scene-name">口语陪练</div>
<div class="scene-line"><b>学生：</b>跟读、对话、背单词。</div>
<div class="scene-line"><b>系统：</b>发音评分 → 纠音 → 对话练习。</div>
<div class="scene-pain">翻车点：方言/噪声误判，把自然缩略判成语法错。</div>
</div>

<div class="scene-card">
<div class="scene-no">06</div>
<div class="scene-name">家长报告</div>
<div class="scene-line"><b>家长：</b>打开手机家长端。</div>
<div class="scene-line"><b>系统：</b>学情、时长、薄弱点、错题、周报。</div>
<div class="scene-pain">翻车点：数据被错误批改污染、报告模板化。</div>
</div>

</div>
</div>

## 1.1 同一个动作，系统内部完全不同

<div class="table-note">表 1-1　六个场景的输入、输出与真实边界</div>

| 场景 | 输入 | 系统输出 | 用户感知 | 常见翻车 |
|---|---|---|---|---|
| 拍照讲题 | 手写题照片、语音、圈画 | 分步提示、板书、同类题 | “像老师一样引导” | 识别错、讲解绕、非标准解不认 |
| 精准学 | 章节选择、诊断作答 | 薄弱点、路径、微课 | “只学不会的” | 诊断题少、标签错、跨章节弱 |
| 作业批改 | 整页拍照 | 对错、错因、错题本 | “省妈” | 对错颠倒、填空/手写失败 |
| 作文批改 | 作文照片/文本 | 评分、评语、范文 | “有反馈” | 主观、套话、评分漂移 |
| 口语陪练 | 跟读、对话 | 发音分、纠音 | “敢开口” | 方言/噪声误判 |
| 家长报告 | 自动汇总 | 学情、时长、周报 | “看得见” | 数据污染、模板化 |

<div class="keybox">

**体验的真相：** 用户以为自己在买“讲解”，实际上先买到的是“识别 + 判题”。识别错一道题，后面的讲解再流畅也会被判定为“不靠谱”；判错一道对题，家长会立刻怀疑整套系统。**讲解决定好感，判题决定信任；信任比好感贵一个数量级。**

</div>

# 2. 工作流拆解：一台学习机的“智能体”怎么跑

<div class="keybox">

**先定义清楚。** 本报告把“智能体（Agent）”定义为：能自主设定目标、规划步骤、调用工具、观察结果并重规划的 system。按这个标准，2026 年的消费级学习机**都不是 Agent**。它们更准确的名字是“agentic workflow”（有状态、有工具调用、有控制循环的垂直工作流）。下面为了叙述方便，仍称“智能体工作流”，但请记住这个区别。

</div>

## 2.1 七层行为等价架构

<div class="diagram">

<div class="fig-title">图 2-1　AI 学习机的七层行为等价架构（合理推断，非厂商内部图）</div>

<div class="layer-stack">

<div class="layer"><div class="lab">L1　交互层</div><div class="chips"><span class="chip">摄像头</span><span class="chip">麦克风/ASR</span><span class="chip">手写笔</span><span class="chip">触控/圈画</span><span class="chip">聊天框</span><span class="chip">白板</span></div></div>

<div class="layer"><div class="lab">L2　感知与结构化</div><div class="chips"><span class="chip">文档矫正</span><span class="chip">手写 OCR</span><span class="chip">公式识别</span><span class="chip">图表切分</span><span class="chip">题目切分</span><span class="chip">意图分类</span></div></div>

<div class="layer"><div class="lab">L3　学生模型与知识层</div><div class="chips"><span class="chip">知识图谱</span><span class="chip">先修边</span><span class="chip">掌握度向量</span><span class="chip">错因标签</span><span class="chip">本地考纲</span><span class="chip">教材版本</span></div></div>

<div class="layer accent"><div class="lab">L4　编排层</div><div class="chips"><span class="chip">路由器</span><span class="chip">状态机</span><span class="chip">工具调用</span><span class="chip">提示策略</span><span class="chip">模型路由</span><span class="chip">会话记忆</span><span class="chip">护栏</span></div></div>

<div class="layer"><div class="lab">L5　工具层</div><div class="chips"><span class="chip">教材/题库检索</span><span class="chip">符号求解</span><span class="chip">步骤校验</span><span class="chip">TTS</span><span class="chip">白板渲染</span><span class="chip">内容搜索</span><span class="chip">家长推送</span></div></div>

<div class="layer"><div class="lab">L6　生成层</div><div class="chips"><span class="chip">分步讲解</span><span class="chip">板书/图示</span><span class="chip">同类题</span><span class="chip">鼓励语</span><span class="chip">老师人设</span></div></div>

<div class="layer"><div class="lab">L7　校验与运营</div><div class="chips"><span class="chip">答案校验</span><span class="chip">置信度门控</span><span class="chip">日志/报错</span><span class="chip">内容运营</span><span class="chip">评测</span><span class="chip">人工抽检</span></div></div>

</div>
</div>

**每一层的关键问题：**

- L1—L2：**能不能看懂**。手写、公式、图表、多栏、反光、折角，都是长尾。
- L3：**知不知道自己不会**。知识图谱的粒度、先修边、本地考纲、学生历史，决定“个性化”是不是真的。
- L4：**会不会按流程走**。这是“智能体”最像智能体的地方，也是最容易被写死的地方。
- L5：**有没有真工具**。检索、符号求解、步骤校验，是“讲得对”的硬支撑。
- L6：**讲得像不像人**。人设、语气、板书、鼓励，决定好感，但不决定正确性。
- L7：**敢不敢承认不确定**。没有校验和置信度门控，前面所有层都会翻车。

## 2.2 讲题 Agent 的完整时序

这是整套系统最核心的一条链。下面 14 步是“行为等价还原”：每一步都能从产品行为中观察到或合理推断出来。

<div class="diagram">

<div class="fig-title">图 2-2　拍照讲题的 14 步时序（合理推断）</div>

<div class="seq">

<div class="seq-row"><div class="num">1</div><div class="seq-body"><b>输入</b>　拍照 / 语音 / 圈画；记录年级、教材版本、当前章节。</div></div>

<div class="seq-row"><div class="num">2</div><div class="seq-body"><b>图像预处理</b>　文档检测、透视矫正、去噪、增强；判断是否需要重拍。</div></div>

<div class="seq-row"><div class="num">3</div><div class="seq-body"><b>OCR / 公式识别</b>　手写文字 → 文本；公式 → LaTeX/MathML；图表 → 区域描述。<span class="seq-risk">最大误差源</span></div></div>

<div class="seq-row"><div class="num">4</div><div class="seq-body"><b>题目结构化</b>　切出题干、小问、选项、图、表；识别题型（计算/证明/选择/应用题）。</div></div>

<div class="seq-row"><div class="num">5</div><div class="seq-body"><b>意图路由</b>　讲这道题 / 批改 / 问概念 / 查词 / 口语 / 闲聊；选择不同工作流。</div></div>

<div class="seq-row"><div class="num">6</div><div class="seq-body"><b>学生状态注入</b>　年级、教材、章节、历史错题、掌握度、上次学习时间、本地考纲。</div></div>

<div class="seq-row"><div class="num">7</div><div class="seq-body"><b>知识标注</b>　题目 → 知识点、先修知识点、难度、常见错因；映射到知识图谱节点。</div></div>

<div class="seq-row"><div class="num">8</div><div class="seq-body"><b>检索</b>　从教材、例题、微课、题库中召回相关内容；rerank 后取 top-k。<span class="seq-risk">覆盖决定“对不对题”</span></div></div>

<div class="seq-row"><div class="num">9</div><div class="seq-body"><b>提示阶梯规划</b>　不直接给答案；按 hint level 1—4 设计“审题 → 方向 → 关键步 → 完整解”。</div></div>

<div class="seq-row"><div class="num">10</div><div class="seq-body"><b>生成第一层提示 + 板书</b>　文字 + 白板图/公式 + 语音；只问一个问题，等学生回应。</div></div>

<div class="seq-row"><div class="num">11</div><div class="seq-body"><b>学生回应</b>　文字、语音、圈画、手写；系统识别并更新会话状态。</div></div>

<div class="seq-row"><div class="num">12</div><div class="seq-body"><b>回应判定</b>　对 / 部分对 / 错 / 卡住；判断卡在哪一步、属于哪类错因。<span class="seq-risk">LLM 自评不可靠</span></div></div>

<div class="seq-row"><div class="num">13</div><div class="seq-body"><b>策略选择</b>　下一层提示 / 换一种讲法 / 降维举例 / 给完整解；多数产品这里是固定规则。<span class="seq-risk">策略是写死的</span></div></div>

<div class="seq-row"><div class="num">14</div><div class="seq-body"><b>收尾</b>　总结方法 → 推同类题 → 更新错题本/掌握度 → 生成家长报告。</div></div>

</div>
</div>

### 四个真正的断点

<div class="diagram">

<div class="fig-title">图 2-3　讲题链路上的四个断点（技术债的源头）</div>

<div class="break-grid">

<div class="break-card">
<div class="break-tag">断点 1</div>
<div class="break-title">第 3 步：OCR</div>
<div class="break-desc">手写连笔、公式分式、根号、图表、反光——识别错一个符号，整道题就错了。后面讲得再顺，也是错题。</div>
<div class="break-fix">可修性：中。加置信度门控、让用户重拍、公式用专用模型。</div>
</div>

<div class="break-card">
<div class="break-tag">断点 2</div>
<div class="break-title">第 8 步：检索</div>
<div class="break-desc">题库里没有同类题、教材版本不匹配、微课不对题，系统就会“硬讲”。这就是用户说的“答非所问”。</div>
<div class="break-fix">可修性：中。靠内容覆盖和 rerank，不是靠模型。</div>
</div>

<div class="break-card">
<div class="break-tag">断点 3</div>
<div class="break-title">第 12 步：判定</div>
<div class="break-desc">学生写对了但方法不同，判错；学生写错了但答案碰巧对，判对。LLM 自评没有可靠的数学证明能力。</div>
<div class="break-fix">可修性：中低。符号等价 + 数值代入 + 多解匹配，能覆盖计算题；应用题/证明题仍难。</div>
</div>

<div class="break-card">
<div class="break-tag">断点 4</div>
<div class="break-title">第 13 步：策略</div>
<div class="break-desc">“换个思路讲”听起来很智能，实际多数产品只有固定提示阶梯；学生一卡住，就退化成“车轱辘话”。</div>
<div class="break-fix">可修性：低。真策略需要教学理论和长期学生模型，不是 prompt 能解决。</div>
</div>

</div>
</div>

### 一个“行为等价”的伪 prompt

下面不是厂商的真实 prompt，而是从产品行为反推出来的策略骨架。它说明“AI 一对一”的智能程度：**真正决定体验的是 policy，而不是那句 system prompt。**

<div class="codebox">

```
system:
  你是 {grade} 的 {subject} 老师。
  不要直接给最终答案；按 hint_level 1-4 给提示。
  每次只问一个问题；结合 {textbook_version} 和 {local_exam}。
  不确定时明确说不确定，不要编。

context:
  题目 = {structured_question}
  知识点 = {knowledge_points}
  先修 = {prerequisites}
  学生掌握度 = {mastery_vector}
  历史错因 = {error_tags}
  可用例题/微课 = {retrieved_items}

policy:
  if 学生答案 == 正确:
      总结方法 + 推同类题 + 更新掌握度
  elif 部分正确:
      指出缺失的那一步 + 追问
  elif 错误:
      定位错因（概念/计算/审题/方法/粗心）+ 给一层提示
  elif 卡住:
      hint_level += 1
      if hint_level > 4: 给完整解 + 标注关键步
  每轮只做一件事；不重复上一轮的话。
```

</div>

<div class="warnbox">

**关键洞察：** 这套伪代码里，最难的不是 `system`，是 `policy` 和 `context`。`policy` 需要教学法，`context` 需要知识图谱和题库。大模型只负责“把话说出来”；说得对不对，取决于前面给它的结构化信息。**这就是为什么“换个更强的模型”不会自动让学习机变好。**

</div>

## 2.3 精准学闭环：个性化真正发生的地方

<div class="diagram">

<div class="fig-title">图 2-4　精准学的五步闭环（合理推断）</div>

<div class="loop">

<div class="loop-step"><div class="loop-no">1</div><div class="loop-name">诊断测</div><div class="loop-desc">少量题，自适应选题；目标是用最少题量定位薄弱点。</div></div>

<div class="loop-step"><div class="loop-no">2</div><div class="loop-name">掌握度向量</div><div class="loop-desc">每个知识点一个掌握概率；BKT/IRT/DKT 类模型 + 规则修正。</div></div>

<div class="loop-step"><div class="loop-no">3</div><div class="loop-name">先修追溯 / 路径规划</div><div class="loop-desc">知识图谱拓扑 + 本地考纲权重 + 时间预算 + 最近发展区。</div></div>

<div class="loop-step"><div class="loop-no">4</div><div class="loop-name">微课 + 练习</div><div class="loop-desc">2 分钟短课 + 同类题；错题回流。</div></div>

<div class="loop-step"><div class="loop-no">5</div><div class="loop-name">复测</div><div class="loop-desc">更新掌握度；决定下一轮路径。</div></div>

</div>

<div class="return">← 复测结果回写掌握度，形成闭环；但“回写”的前提是判定准确，否则错题会污染画像</div>

</div>

<div class="keybox">

**个性化发生在哪里？** 不在聊天里，在这张图里。系统真正个性化的是“下一题做什么、下一节微课看什么、先补哪个先修点”。这是一种**题目级自适应**，不是“理解这个孩子”的教学个性化。前者是数据问题，后者是教育问题；前者 2026 年已经成熟，后者还没有。

</div>

### 自适应选题的三种做法

| 做法 | 原理 | 优点 | 缺点 | 谁最可能用 |
|---|---|---|---|---|
| 规则分层 | 按章节/难度/错题标签直接推 | 便宜、可控 | 不精确、易重复 | 多数中端产品 |
| IRT/项目反应理论 | 估计能力参数，按信息量选题 | 题量少、可解释 | 需要题目标定 | 有题库积累的厂商 |
| BKT/DKT 知识追踪 | 逐知识点估计掌握概率 | 细粒度、可更新 | 需要学习序列数据 | 头部厂商/研究团队 |

## 2.4 批改流水线：最容易被低估的硬活

<div class="diagram">

<div class="fig-title">图 2-5　作业批改的六步流水线（合理推断）</div>

<div class="flow">

<div class="step"><b>整页拍照</b><br>多页/多栏/反光</div>
<div class="step"><b>版面分析</b><br>题目切分/区域检测</div>
<div class="step"><b>答案抽取</b><br>手写/公式/选项</div>
<div class="step"><b>步骤比对</b><br>符号等价/数值代入</div>
<div class="step"><b>判对错 + 错因</b><br>概念/计算/审题/方法</div>
<div class="step"><b>错题本 + 同类题</b><br>回流精准学/家长报告</div>

</div>
</div>

| 题型 | 判题方法 | 可靠性 | 主要失败模式 |
|---|---|---|---|
| 计算题 | 符号等价（SymPy）+ 数值代入 | 较高 | 多解、等价变形、手写识别错 |
| 选择题/填空 | 答案匹配 + 规则 | 高 | 手写 OCR、单位/格式 |
| 应用题 | LLM 判步骤 + 关键结果校验 | 中 | 建模不同、步骤省略、单位 |
| 证明题 | LLM + 人工 rubric | 低—中 | 逻辑跳跃、非标准证法 |
| 作文 | rubric + LLM judge | 中 | 主观、评分漂移、套话 |
| 口语 | 专用发音评测 | 高 | 方言、噪声、自然缩略 |

<div class="warnbox">

**一致性比准确率更致命。** 同一道题拍三次，如果三次结果不同，用户不会认为“AI 有 90% 准确率”，只会认为“这机器不靠谱”。很多投诉不是“判错了”，而是“一会儿对一会儿错”。**判题系统的第一指标应该是一致性，其次才是准确率。**

</div>

## 2.5 工具调用清单：一个“AI 家教”真正要接哪些工具

<div class="table-note">表 2-1　工具调用清单与可替代方案</div>

| 工具 | 触发时机 | 输入 → 输出 | 失败模式 | 开源/API 替代 |
|---|---|---|---|---|
| 文档矫正 / OCR | 拍照后 | 图像 → 文本 + 框 | 手写、反光、折角 | PaddleOCR、讯飞 OCR |
| 公式识别 | 数学题 | 图像 → LaTeX | 分式、根号、手写 | Mathpix、Texify、pix2tex |
| ASR | 语音提问/口语 | 音频 → 文本 + 音素 | 噪声、方言 | Whisper、FunASR |
| 题目切分 | OCR 后 | 文本 → 题干/小问 | 多栏、图表 | 规则 + LayoutLM |
| 意图路由 | 每次输入 | 文本 → 意图 | 模糊指令 | 小模型 + 规则 |
| 知识标注 | 题目入库 | 题目 → 知识点 | 标签噪声 | LLM + 人工 |
| 检索 | 讲题前 | query → 教材/例题/微课 | 召回不准 | BM25 + embedding + rerank |
| 符号求解 | 数学/物理 | 表达式 → 解 | 应用题建模 | SymPy、Wolfram |
| 步骤校验 | 学生作答 | 步骤 → 对/错/部分 | 非标准解 | 符号等价 + LLM judge |
| 白板渲染 | 讲解 | 讲解计划 → SVG/Canvas | 排版、遮挡 | 自研 |
| TTS / 人设 | 讲解 | 文本 → 语音 | 情感、口音 | edge-tts、Azure |
| 家长推送 | 学习结束 | 报告 → App | 数据污染 | 自研 |

<div class="keybox">

**工具层的真相：** 这些工具没有一个是“教育专属黑科技”。OCR、ASR、TTS、检索、符号求解都是通用件。学习机的难度不在“有没有工具”，而在**什么时候调用、调用哪个、结果怎么验证、失败怎么兜底**。这四件事属于编排层，不属于模型层。

</div>

## 2.6 三种编排模式：为什么教育产品不能做成“自由聊天”

<div class="diagram">

<div class="fig-title">图 2-6　三种编排模式的光谱</div>

<div class="spectrum">

<div class="spec-card">
<div class="spec-head">A. 固定状态机</div>
<div class="spec-sub">确定性优先</div>
<div class="spec-body">流程写死：诊断 → 讲题 → 练习 → 批改 → 报告。每一步有明确的输入/输出和失败兜底。</div>
<div class="spec-good">可控、可测、便宜、合规</div>
<div class="spec-bad">不灵活，遇到新题型容易“不会”</div>
<div class="spec-who">讯飞 / 学而思 / 作业帮的主线（推断）</div>
</div>

<div class="spec-card">
<div class="spec-head">B. LLM 路由器 + 工具调用</div>
<div class="spec-sub">灵活性与可控的折中</div>
<div class="spec-body">模型判断意图，选择工具链；允许一定程度的自主规划，但仍在护栏内。</div>
<div class="spec-good">能处理开放问、多工具组合</div>
<div class="spec-bad">难测试、易漂移、成本高</div>
<div class="spec-who">2025—2026 的“AI 答疑”增强功能</div>
</div>

<div class="spec-card">
<div class="spec-head">C. 自由聊天 Agent</div>
<div class="spec-sub">体验优先</div>
<div class="spec-body">以对话为中心，模型自由回答；没有强制的诊断/练习/批改闭环。</div>
<div class="spec-good">最自然、最灵活、迭代最快</div>
<div class="spec-bad">无结构化闭环、无家长管控、错误不可控</div>
<div class="spec-who">豆包爱学 / 千问智学 / 通用大模型</div>
</div>

</div>
</div>

<div class="warnbox">

**判断：** 教育产品的主线一定是 A，B 是增强，C 是入口。把 C 当卖点可以，把 C 当教学系统会翻车。因为家长买的不是“能聊”，是“能负责”。A 的价值是可审计、可复现、可兜底；B 的价值是覆盖长尾；C 的价值是拉新和免费流量。

</div>

## 2.7 模型路由与成本：293B MoE 不可能端侧跑

<div class="diagram">

<div class="fig-title">图 2-7　典型的模型路由（合理推断）</div>

<div class="route">

<div class="route-node">用户请求</div>
<div class="route-arrow">→</div>
<div class="route-node small">小模型/规则<br>意图、路由、OCR 后处理</div>
<div class="route-arrow">→</div>
<div class="route-node small">大模型<br>讲解、作文、开放问</div>
<div class="route-arrow">→</div>
<div class="route-node small">符号引擎<br>求解、步骤校验</div>
<div class="route-arrow">→</div>
<div class="route-node small">TTS/白板<br>多模态输出</div>

</div>
</div>

| 任务 | 模型规格 | 部署 | 延迟目标 | 成本敏感度 |
|---|---|---|---|---|
| OCR / ASR | 专用小模型 | 端/云 | < 1 s | 高 |
| 意图 / 路由 | 小模型/规则 | 端/云 | < 300 ms | 高 |
| 讲解生成 | 大模型（星火 X2 / DeepSeek / Qwen） | 云 | 1—3 s 首 token | 中 |
| 步骤校验 | 符号引擎 + 小模型 | 云 | < 2 s | 中 |
| 作文 / 口语 | 专用模型 + LLM | 云 | 2—5 s | 低 |

<div class="keybox">

**证据链：** 据报道，2025 年 T30 用“星火 + DeepSeek 双引擎”；2026 年 T90 用星火 X2；2026 年 10 月 22 日星火 X2.6 强调“端云一体”。这说明两件事：第一，**模型是可替换的**；第二，**端云分工是必然的**。293B MoE 的 X2 不可能在平板上跑，端侧只能做小模型和预处理，讲解和复杂判定必须上云。

</div>

# 3. 横向对照：五类玩家的“工作流指纹”

<div class="diagram">

<div class="fig-title">图 3-1　五类玩家的入口与闭环（行为示意）</div>

<div class="brand-grid">

<div class="brand-card">
<div class="brand-name">科大讯飞</div>
<div class="brand-entry">入口：拍照 / 精准学诊断</div>
<div class="brand-loop">闭环：诊断 → 路径 → 微课 → 讲题 → 批改 → 报告</div>
<div class="brand-moat">核心资产：考试评测数据、本地考纲、渠道</div>
<div class="brand-weak">强项：步骤批改、口语；短板：跨章节、文科</div>
</div>

<div class="brand-card">
<div class="brand-name">作业帮</div>
<div class="brand-entry">入口：拍照搜题 / 作业</div>
<div class="brand-loop">闭环：搜题 → 题库匹配 → 讲解 → 练习</div>
<div class="brand-moat">核心资产：约 24 亿题库、搜题心智</div>
<div class="brand-weak">强项：搜题、理科；短板：课程体系、主动诊断</div>
</div>

<div class="brand-card">
<div class="brand-name">学而思</div>
<div class="brand-entry">入口：课程 / 学-练-测</div>
<div class="brand-loop">闭环：上课 → 练习 → 测评 → 精准学</div>
<div class="brand-moat">核心资产：约 1600 万分钟教研内容、培优体系</div>
<div class="brand-weak">强项：课程、培优；短板：主动诊断、普娃适配</div>
</div>

<div class="brand-card">
<div class="brand-name">小猿</div>
<div class="brand-entry">入口：拍试卷 / 作业诊断</div>
<div class="brand-loop">闭环：诊断 → 分层推题 → 错题 → 复练</div>
<div class="brand-moat">核心资产：约 20 亿题库、诊断闭环</div>
<div class="brand-weak">强项：诊断、性价比；短板：课程体系</div>
</div>

<div class="brand-card wide-card">
<div class="brand-name">豆包爱学 / 千问智学</div>
<div class="brand-entry">入口：聊天 / 拍照</div>
<div class="brand-loop">闭环：问答 → 讲解 →（千问）批改/错题/组卷</div>
<div class="brand-moat">核心资产：通用大模型、流量、免费策略</div>
<div class="brand-weak">强项：灵活、目前免费；短板：结构化内容、家长管控、硬件</div>
</div>

</div>
</div>

<div class="table-note">表 3-1　五类玩家的能力对照（基于公开产品行为与实测）</div>

| 维度 | 讯飞 | 作业帮 | 学而思 | 小猿 | 豆包/千问 |
|---|---|---|---|---|---|
| 入口 | 拍照/诊断 | 拍照搜题/作业 | 课程 | 拍试卷/诊断 | 聊天/拍照 |
| 诊断方式 | 少量题 + 知识图谱 | 先做题再诊断 | 课程中测 | 拍卷诊断 + 分层 | 无系统诊断 |
| 讲解策略 | 步骤级、错因点拨 | 题库解析 + 视频 | 课程 + 精准学 | 解析 + 推题 | 通用对话 |
| 批改强项 | 数学步骤/口语/作文 | 理科/搜题 | 课程作业 | 整页/错题 | 通用批改（千问强） |
| 闭环完整度 | 高 | 中高 | 高（课程侧） | 中高 | 低 |
| 内容壁垒 | 考试评测/本地考纲 | 24 亿题库 | 1600 万分钟课程 | 20 亿题库 | 模型/流量 |
| 真实短板 | 跨章节、文科 | 课程体系 | 主动诊断 | 课程体系 | 结构化/管控/硬件 |

<div class="keybox">

**工作流指纹：** 讯飞是**评测数据驱动**的，作业帮是**题库驱动**的，学而思是**课程驱动**的，小猿是**诊断驱动**的，豆包/千问是**模型驱动**的。五条路线没有谁全面领先，只有场景匹配。买学习机不是买“最强 AI”，是买“最匹配你家孩子学习路径的那条流水线”。

</div>

# 4. 技术债地图：它到底哪里在硬撑

## 4.1 十一类技术债

<div class="table-note">表 4-1　AI 学习机的技术债清单（严重度 1—5，5 最严重）</div>

<table class="heat wide">
<thead><tr><th>债务</th><th>具体表现</th><th>严重度</th><th>用户影响</th><th>可修性</th><th>证据</th></tr></thead>
<tbody>
<tr><td><b>感知债</b></td><td>手写连笔、公式、图表、反光、折角识别错</td><td class="sev5">5</td><td>整题错、讲解错、批改错</td><td>中</td><td>投诉/实测</td></tr>
<tr><td><b>结构化债</b></td><td>题目切分错、知识点标错、答案抽取错</td><td class="sev4">4</td><td>路径错、推题错</td><td>中</td><td>合理推断</td></tr>
<tr><td><b>策略债</b></td><td>提示阶梯写死、换讲法不会、车轱辘话</td><td class="sev4">4</td><td>讲不透、学生放弃</td><td>低</td><td>用户实测</td></tr>
<tr><td><b>校验债</b></td><td>步骤判题不稳、对错颠倒、同题结果漂移</td><td class="sev5">5</td><td>信任崩塌、退货</td><td>中低</td><td>黑猫/小红书</td></tr>
<tr><td><b>覆盖债</b></td><td>跨章节/综合题弱、文科弱、教材版本不全</td><td class="sev4">4</td><td>“关键时刻不会”</td><td>中</td><td>横评/评测</td></tr>
<tr><td><b>数据债</b></td><td>题库答案错、标签噪声、内容陈旧</td><td class="sev4">4</td><td>教错、误导</td><td>中</td><td>投诉/行业</td></tr>
<tr><td><b>评测债</b></td><td>只有厂商内部指标，无独立 RCT</td><td class="sev5">5</td><td>无法证明效果</td><td>低</td><td>公开资料</td></tr>
<tr><td><b>延迟/成本债</b></td><td>云端大模型延迟、并发成本、离线弱</td><td class="sev3">3</td><td>等待、卡顿</td><td>中</td><td>合理推断</td></tr>
<tr><td><b>合规/安全债</b></td><td>未成年人保护、考试时段限制、AI 备案、版权</td><td class="sev4">4</td><td>下架/处罚/诉讼</td><td>中</td><td>国标/监管</td></tr>
<tr><td><b>商业债</b></td><td>硬件周期、渠道加价、免费 AI 冲击、真人答疑成本</td><td class="sev4">4</td><td>增长不可持续</td><td>低</td><td>财报/市场</td></tr>
<tr><td><b>信任债</b></td><td>一次判错就失去信任；虚假宣传反噬</td><td class="sev5">5</td><td>退货、差评、口碑</td><td>低</td><td>投诉/报道</td></tr>
</tbody>
</table>

## 4.2 债务传导链：为什么“95% 准确率”不够

<div class="diagram">

<div class="fig-title">图 4-1　一次识别错误的级联放大（合理推断）</div>

<div class="chain">

<div class="chain-node source">手写 OCR 错一个符号</div>
<div class="chain-arrow">↓</div>
<div class="chain-node">题目结构化错 → 知识点标错</div>
<div class="chain-arrow">↓</div>
<div class="chain-node">诊断结果错 → 学习路径推错</div>
<div class="chain-arrow">↓</div>
<div class="chain-node">讲解/批改错 → 错题本被污染</div>
<div class="chain-arrow">↓</div>
<div class="chain-node">家长报告错 → 家长不信任</div>
<div class="chain-arrow">↓</div>
<div class="chain-node end">退货 / 差评 / “智商税”</div>

</div>

<div class="chain-note">长链条里，单点 95% 准确率经过 5 个环节只剩约 77%；如果每次交互都涉及识别和判定，实际可用性会更低。可靠性不是“平均值”，是“最弱一环”。</div>

</div>

## 4.3 为什么难修

<div class="grid-2">

<div class="mini-card">
<div class="mini-title">长尾分布</div>
<div class="mini-body">手写、公式、图表、多栏、方言，每个 edge case 都要数据和标注；越到后面，边际成本越高。</div>
</div>

<div class="mini-card">
<div class="mini-title">校验比生成难</div>
<div class="mini-body">生成一个“看起来对”的解法很容易；判断一个非标准解法是否等价，需要符号推理和领域知识。</div>
</div>

<div class="mini-card">
<div class="mini-title">内容运营不是模型问题</div>
<div class="mini-body">题库答案错、标签噪声、教材版本更新，靠模型修不了，只能靠教研团队和流程。</div>
</div>

<div class="mini-card">
<div class="mini-title">评测缺 ground truth</div>
<div class="mini-body">学习效果需要长期跟踪/RCT；厂商只能用“使用时长、完成率、内部测试”替代，无法证明“学会”。</div>
</div>

<div class="mini-card">
<div class="mini-title">成本与延迟</div>
<div class="mini-body">大模型不能端侧跑；云端并发贵；离线场景弱。讲解要等 1—3 秒，孩子注意力已经跑了。</div>
</div>

<div class="mini-card">
<div class="mini-title">合规约束</div>
<div class="mini-body">未成年人保护、考试时段限制、生成式 AI 备案、版权；每一条都可能让功能下架或改版。</div>
</div>

</div>

## 4.4 修债优先级：先修“信任”，再修“智能”

<div class="diagram">

<div class="fig-title">图 4-2　技术债修复优先级矩阵</div>

<div class="priority">

<div class="pq high-fix">
<div class="pq-title">高影响 · 可修</div>
<div class="pq-body">OCR 置信度门控 / 重拍提示<br>答案一致性校验<br>错题本清洗 / 人工报错闭环<br>判题结果二次确认</div>
<div class="pq-tag">先做 · 4—8 周可见效</div>
</div>

<div class="pq high-hard">
<div class="pq-title">高影响 · 难修</div>
<div class="pq-body">步骤级判题（非标准解）<br>跨章节/综合题推理<br>文科主观题评分<br>长期学生模型</div>
<div class="pq-tag">长期投入 · 内容+研究</div>
</div>

<div class="pq low-fix">
<div class="pq-title">低影响 · 可修</div>
<div class="pq-body">报告模板 / UI 动效<br>首 token 延迟优化<br>家长端推送策略</div>
<div class="pq-tag">顺手做</div>
</div>

<div class="pq low-hard">
<div class="pq-title">低影响 · 难修</div>
<div class="pq-body">开放世界知识问答<br>情感陪伴 / 心理支持<br>全学科全学段覆盖</div>
<div class="pq-tag">不要先做</div>
</div>

</div>
</div>

<div class="keybox">

**反直觉结论：** 最该先修的不是“更聪明的讲解”，是“更可靠的识别和判题”。前者提升好感，后者决定信任；而家长付费的底层理由是信任。**先让机器“别教错”，再让它“教得好”。**

</div>

# 5. 可复现性判定：哪些能摸清，哪些摸不清

<div class="keybox">

**总判断：** 工作流约 **80% 可复现**；产品护城河约 **20% 不可快速复现**。换句话说，你可以用 4—8 周做出一个“能跑的 AI 家教”原型，但做不出一个“敢让家长付 6000 元”的产品。前者是工程问题，后者是内容、数据、渠道和信任问题。

</div>

## 5.1 复现矩阵

<div class="table-note">表 5-1　能力复现难度与建议</div>

| 能力 | 可复现度 | 4—8 周 MVP | 难点 | 建议 |
|---|---|---|---|---|
| 拍照 OCR / 公式 | 高 | 可以 | 手写长尾 | 先用云 API，不要自研 |
| 题目结构化 | 中 | 可以（单栏理科） | 图表、多栏 | 先做初中数学单栏 |
| 知识图谱 | 中 | 可以（一个教材版本） | 标注成本 | 手工 + LLM 标注 + 抽检 |
| 自适应诊断 | 高 | 可以 | 题目标定 | 先用简化 IRT/规则 |
| 讲题状态机 | 高 | 可以 | 讲解质量 | 先做 4 级提示阶梯 |
| 步骤级批改 | 中低 | 部分（计算题） | 非标准解 | SymPy + 数值代入 |
| 作文 / 口语 | 中 | 可以（英语口语） | 主观性 | 先做口语，再做作文 |
| 内容 / 题库 | 低 | 不可 | 版权、成本 | 采购/合作，不要全自建 |
| 考试评测数据 | 极低 | 不可 | 数据壁垒 | 学校/机构合作 |
| 渠道 / 品牌 / 售后 | 极低 | 不可 | 资本、时间 | 不做通用硬件 |

## 5.2 最小可复现架构（MVP）

<div class="diagram">

<div class="fig-title">图 5-1　一个 4—8 周可搭起来的 AI 家教 MVP（推荐栈）</div>

<div class="layer-stack mvp">

<div class="layer"><div class="lab">输入</div><div class="chips"><span class="chip">手机/平板拍照</span><span class="chip">语音</span><span class="chip">文本</span><span class="chip">圈画</span></div></div>

<div class="layer"><div class="lab">感知</div><div class="chips"><span class="chip">PaddleOCR</span><span class="chip">pix2tex / Texify</span><span class="chip">FunASR / Whisper</span><span class="chip">版面分析</span></div></div>

<div class="layer"><div class="lab">结构化</div><div class="chips"><span class="chip">LLM + 规则</span><span class="chip">题干/小问</span><span class="chip">知识点</span><span class="chip">难度</span></div></div>

<div class="layer accent"><div class="lab">编排</div><div class="chips"><span class="chip">FastAPI</span><span class="chip">状态机（LangGraph/自研）</span><span class="chip">路由器</span><span class="chip">会话记忆</span></div></div>

<div class="layer"><div class="lab">工具</div><div class="chips"><span class="chip">BM25 + embedding + rerank</span><span class="chip">SymPy</span><span class="chip">步骤校验</span><span class="chip">edge-tts</span><span class="chip">SVG 白板</span></div></div>

<div class="layer"><div class="lab">生成</div><div class="chips"><span class="chip">DeepSeek / Qwen / 星火 API</span><span class="chip">提示策略</span><span class="chip">同类题生成</span></div></div>

<div class="layer"><div class="lab">记忆</div><div class="chips"><span class="chip">SQLite / Postgres</span><span class="chip">pgvector</span><span class="chip">学生画像</span><span class="chip">错题本</span></div></div>

<div class="layer"><div class="lab">校验</div><div class="chips"><span class="chip">符号等价</span><span class="chip">数值代入</span><span class="chip">LLM judge</span><span class="chip">置信度门控</span></div></div>

<div class="layer"><div class="lab">UI / 评测</div><div class="chips"><span class="chip">Next.js / React</span><span class="chip">家长报告</span><span class="chip">1000 题 golden set</span><span class="chip">12 个黑盒探针</span></div></div>

</div>
</div>

<div class="keybox">

**最小闭环：** 拍照 → OCR → 结构化 → 检索 → 4 级提示 → 学生回应 → 符号校验 → 同类题 → 错题本。不要一上来做“全科全能”；先把**初中数学计算题**这一个窄场景做到“识别准、判得稳、讲得清”。

</div>

## 5.3 6—8 周构建路线

<div class="diagram">

<div class="fig-title">图 5-2　从 0 到可试用 MVP 的四周段路线</div>

<div class="timeline">

<div class="week-card">
<div class="week-head">W1—2</div>
<div class="week-title">能看懂题</div>
<div class="week-body">拍照上传、OCR、公式识别、题目切分；单栏初中数学；建立 200 题 golden set。</div>
<div class="week-check">验收：OCR 字符准确率、题目切分准确率</div>
</div>

<div class="week-card">
<div class="week-head">W3—4</div>
<div class="week-title">能诊断和讲</div>
<div class="week-body">知识图谱（一个教材版本）、检索、4 级提示状态机、白板输出。</div>
<div class="week-check">验收：提示对题率、一次解决率</div>
</div>

<div class="week-card">
<div class="week-head">W5—6</div>
<div class="week-title">能判和记</div>
<div class="week-body">SymPy 校验、错题本、同类题、家长报告；端到端打通。</div>
<div class="week-check">验收：判题一致率、错题归因准确率</div>
</div>

<div class="week-card">
<div class="week-head">W7—8</div>
<div class="week-title">能扛住真实用户</div>
<div class="week-body">12 个黑盒探针、100 名学生试用、失败案例复盘、修最痛的债。</div>
<div class="week-check">验收：7 日留存、家长信任度、退货意愿</div>
</div>

</div>
</div>

## 5.4 成本与指标

<div class="table-note">表 5-2　MVP 成本结构与验收指标</div>

| 项目 | MVP 估算 | 说明 |
|---|---|---|
| LLM API | 低 | 按 token；讲解、判定、作文 |
| OCR / ASR | 低—中 | 云 API 按次；自建 GPU 更高 |
| 内容 | 高 | 题库/教材/微课，最大成本 |
| 人力 | 2—4 人 × 6—8 周 | 后端、前端、算法、教研 |
| 硬件 | 不需要 | 先用手机/平板 |
| 评测 | 中 | 人工标注、教研抽检 |

**核心指标（按优先级）：**

1. **判题一致率**：同一题多次提交，结果一致的比例。
2. **识别到判定的端到端准确率**：不是单点 OCR 准确率。
3. **提示对题率**：提示是否指向当前题/当前错因。
4. **一次解决率**：不换题、不重开，能否在 4 层提示内解决。
5. **幻觉率**：不确定时是否承认不确定。
6. **首 token 延迟**：讲解开始等待时间。
7. **7 日留存 / 家长信任度**：产品层指标。

## 5.5 黑盒探针：不拆机也能摸清工作流

<div class="table-note">表 5-3　12 个黑盒探针（建议在线下店或 7 天退货期内做）</div>

| # | 探针 | 操作 | 通过说明 | 失败说明 | 揭示 |
|---|---|---|---|---|---|
| 1 | 一致性 | 同一题拍 3 次 | 结果一致 | 结果漂移 | OCR/判题不稳 |
| 2 | 非标准解 | 用老师方法但不同解法 | 判对并解释 | 判错 | 判题器只匹配标准解 |
| 3 | 错误注入 | 中间步骤故意写错 | 指出错误 | 只看最终答案 | 步骤校验缺失 |
| 4 | 跨章节 | 出一道综合题 | 追溯先修 | 只推当前章节 | 知识图谱浅 |
| 5 | 开放追问 | 问“为什么分类讨论” | 真解释 | 车轱辘话 | 策略模板化 |
| 6 | 超纲/冷门 | 奥数/大学题 | 承认不确定 | 胡编 | 幻觉/护栏 |
| 7 | 多轮记忆 | 3 轮后改条件 | 记得前文 | 重复问 | 会话记忆弱 |
| 8 | 手写退化 | 潦草/连笔 | 提示重拍 | 硬判 | OCR 门控缺失 |
| 9 | 文科主观 | 作文/阅读 | 有理有据 | 套话/漂移 | rubric 弱 |
| 10 | 考试模式 | 高考时段试用 | 阻断搜题 | 仍可搜 | 合规 |
| 11 | 延迟 | 首 token | < 3 s | > 5 s | 模型路由/端云 |
| 12 | 家长端 | 查看数据回传 | 报告可解释 | 只有时长 | 数据闭环 |

<div class="keybox">

**最省钱的验证顺序：** 先做 1、2、3、4、5。这五个探针能在 30 分钟内告诉你：这台机器的“智能”是真工作流，还是 prompt + 题库。**如果第 1 个探针就漂移，后面的讲解再惊艳也不要买。**

</div>

## 5.6 复现的边界：别把“能跑”当成“能卖”

- **可以复现：** 感知、检索、状态机、提示策略、符号校验、白板、TTS、错题本、家长报告。
- **不能快速复现：** 24 亿题库、1600 万分钟课程、中高考阅卷数据、教材版权、线下渠道、品牌信任、售后体系。
- **不要做：** 通用学习机、全科全学段、自建题库、AI 老师人设、不可验证的“3 倍提升”。
- **应该做：** 单科窄场景、可验证判题、B 端学校/机构、内容合作、可审计的 AI 教辅。

<div class="warnbox">

**给技术团队的一句话：** 这个产品的护城河不在“模型调得好”，在“数据闭环 + 内容版权 + 渠道 + 售后”。如果你只有模型能力，你适合做工具/API，不适合做整机品牌；如果你有内容和渠道，AI 只是把你的教辅重做一遍。

</div>

# 6. 结论：这台机器到底是什么

<div class="keybox">

**一句话：** 它是一套“感知 → 结构化 → 诊断 → 规划 → 讲题 → 批改 → 报告”的垂直工作流，外面套了一个“AI 老师”的人设。它不是智能体，是智能教辅；不是因材施教，是题目级自适应；不是模型能力，是内容 + 数据 + 工程 + 渠道的复合体。

</div>

**它擅长：**

- 结构化理科：数学计算、物理计算、英语口语、教材同步。
- 重复练习：错题归集、同类题、精准学路径。
- 家长管控：时长、应用、报告、护眼。
- 规模化：一个老师带一个班，一台机器带一个孩子。

**它不擅长：**

- 开放题、跨章节综合题、文科主观题。
- 真正的教学策略、学习动机、元认知、长期成长画像。
- 承认“我不会”；大多数产品的默认行为是“硬讲”。
- 替代老师；它最多替代“重复讲解”和“作业检查”。

**它的护城河：**

- 内容：题库、教材、课程、微课。
- 数据：考试评测、阅卷、口语、错题。
- 渠道：线下门店、经销商、售后。
- 品牌：家长信任、NPS、高端心智。
- 不是模型：模型可换，且正在被免费通用模型商品化。

**它的技术债：**

- 感知债：看懂题。
- 校验债：判对错。
- 评测债：证明有效。
- 信任债：一次错误就崩塌。

<div class="diagram">

<div class="fig-title">图 6-1　如果只记住一张图，记这张</div>

<div class="chain">

<div class="chain-node source">识别不准</div>
<div class="chain-arrow">→</div>
<div class="chain-node">标签错 / 路径错</div>
<div class="chain-arrow">→</div>
<div class="chain-node">讲解错 / 批改错</div>
<div class="chain-arrow">→</div>
<div class="chain-node">错题本污染</div>
<div class="chain-arrow">→</div>
<div class="chain-node end">家长不信任</div>

</div>

<div class="chain-note">AI 学习机的竞争，最终不是“谁更会聊”，而是“谁更少犯错、谁能让家长看见它没犯错”。</div>

</div>

# 附录 A　证据表

| 判断 | 证据 | 等级 | 时间 |
|---|---|---|---|
| T90 的 AI 1 对 1 / 晓悦 / 步骤批改 | 讯飞官方发布 | 厂商口径 | 2026-02 / 03 |
| 星火 X2：293B MoE、全国产算力 | 官方 / IT之家 | 厂商口径 | 2026-02-11 |
| 星火 X2.6：端云一体、智能体能力 | 官方 / 电子技术应用 | 厂商口径 | 2026-10-22 |
| 学习平板 2026 Q3 销量 -30.8% | 洛图科技 | 硬数据 | 2026-10-23 |
| 2026 H1 讯飞智能硬件收入 -15.96% | 半年报 / 证券时报 | 硬数据 | 2026-08 |
| 讯飞 AI 作业诊断暂未上线家长端 | 讯飞投资者问答 | 官方口径 | 2024-05 |
| 批改错误、对错颠倒 | 黑猫 / 小红书 / 新浪投诉 | 用户侧个案 | 2025—2026 |
| 豆包爱学 / 千问智学免费讲题批改 | 公开产品实测 | 已观察 | 2026 |
| GB/T 46348-2025 新国标 | 国标 / 新京报 | 硬数据 | 2025-10 发布 / 2026-05 实施 |
| 学习机投诉 9300+ 条 | 黑猫 / 上游新闻 | 媒体统计 | 2025-12 |
| T30 星火 + DeepSeek 双引擎 | 报道 / 用户晒单 | 厂商/媒体 | 2025 |
| 整机 BOM 约 1800—2300 元 | 行业拆解 | 估算 | 2024—2026 |

# 附录 B　术语表

| 术语 | 含义 |
|---|---|
| OCR | 光学字符识别；把图片里的文字转成文本 |
| ASR | 自动语音识别 |
| 知识图谱（KG） | 知识点 + 先修关系 + 题目关联的结构化网络 |
| BKT / IRT / DKT | 三种学生掌握度建模方法：贝叶斯知识追踪 / 项目反应理论 / 深度知识追踪 |
| RAG | 检索增强生成；先检索资料再让模型回答 |
| MoE | 混合专家模型；参数量大但每次只激活一部分 |
| 步骤校验 | 判断学生解题步骤是否正确，而不只看最终答案 |
| 提示阶梯 | 从“审题”到“完整解”的分层提示策略 |
| 置信度门控 | 置信度低于阈值时拒绝作答/要求重拍，而不是硬编 |
| Rubric | 评分量规；作文/主观题的分项标准 |

# 附录 C　主要来源

- [科大讯飞 T90 系列发布（官方）](https://edu.iflytek.com/about-us/news/company-news/2665.html)
- [星火 X2 发布（IT之家）](https://www.ithome.com/0/921/060.htm)
- [星火 X2.6 端云一体（电子技术应用）](http://chinaaet.cn/article/3000181254)
- [洛图科技 2026Q3 学习平板季报](https://display.m.ofweek.com/2026-10/ART-8321304-8420-30708503.html)
- [科大讯飞 2026 半年报解读（证券时报）](https://www.stcn.com/article/detail/4095569.html)
- [讯飞 AI 学（家长端）应用页](https://sj.qq.com/appdetail/com.iflytek.aistudyclient.parentcontrol)
- [讯飞官方：AI 作业诊断暂未上线家长端（2024）](https://stock.stockstar.com/IG2024051300000233.shtml)
- [AI 学习机投诉与新国标调查（上游新闻）](https://www.cqcb.com/news/16/2025-12-18/6032003.html)
- [学而思“真人答疑”争议与投诉数据](https://post.smzdm.com/p/a70q7v5d/)
- [AI 学习机全产业链拆解（搜狐）](https://www.sohu.com/a/1053901267_122257688)
- [2025 五机 45 天横评（知乎）](https://zhuanlan.zhihu.com/p/15679723319)
- [豆包爱学 × 千问智学 2026 使用手记](https://zhuanlan.zhihu.com/p/2059029108542137146)
- [免费 AI 攻入教育（蓝鲸财经）](https://www.lanjinger.com/d/1785840588543313348)
- [GB/T 46348-2025 新国标报道（新京报）](https://www.bjnews.com.cn/detail-1763117814168588.html)

# 附录 D　免责声明

1. 本报告的架构图为**行为等价还原**，基于公开产品行为、官方发布、用户实测和行业通用架构推断，不代表厂商内部实现；不涉及破解固件、抓包或窃取商业机密。
2. 厂商未公开模型参数量、训练数据、判题算法、prompt、路由策略；本报告中的伪代码仅用于说明工作流，不是真实代码。
3. 用户投诉和实测为个案，不能代表整体质量；硬数据以洛图科技、财报、国标为准。
4. 数据截至 **2026-10-29**；AI 产品和模型迭代快，具体功能以实机/官方最新说明为准。
5. 本报告不构成购买建议或投资建议；购买前请用第 5.5 节的黑盒探针实机验证。
