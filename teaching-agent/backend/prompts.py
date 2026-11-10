from __future__ import annotations

from pathlib import Path

from schema import TeachingRequest

D_ORIGINAL = Path(__file__).with_name("original_prompt_d.txt").read_text(encoding="utf-8").strip()

PROMPT_VARIANTS = {
    "A": {
        "name": "苏格拉底追问版",
        "style": "先用一个具体问题/小场景让学生暴露直觉，顺着直觉走一步，再指出不够，给出更准确的理解；只问一个诊断问题。",
        "strength": "互动感强，容易发现学生到底卡在哪；适合一对一。",
        "risk": "问题太多会拖慢；对只想听讲解的学生可能显得绕。",
    },
    "B": {
        "name": "类比-拆解-例子-自检版",
        "style": "核心直觉→生活类比→2-3 步拆解→具体例子→检查问题。",
        "strength": "结构最稳、最清晰，适合大多数学生和大多数知识模块。",
        "risk": "容易变成模板；如果例子不够具体，会显得空。",
    },
    "C": {
        "name": "故事场景版",
        "style": "用 3-5 句小故事/场景开场，从故事里的关键变化抽出概念，再给定义、例子和检查。",
        "strength": "代入感强，适合零基础、怕数学、需要先看到“为什么”的学生。",
        "risk": "故事可能喧宾夺主；概念落点必须明确。",
    },
    "D": {
        "name": "原创提示词·90分模式识别版",
        "style": "用户原话逐字保留：极度功利、去大纲、白盒步骤、模式识别、一步一练、不要风控废话。",
        "strength": "最贴近真实备考需求；直接、不绕弯、强调考点与出题形式。",
        "risk": "对非应试/低年级学生可能太硬；需要先确认“当前模块”和考试范围。",
    },
}

SCHEMA_BLOCK = """{
  "reply_markdown": "学生看到的讲解正文，350-900字；短段落，可用少量加粗小标题；不要目录/章节编号/学习计划",
  "core_idea": "这一轮的核心一句话，<=120字",
  "order_rationale": "为什么先讲这个、再讲那个，1-2句；给系统看，不要写进 reply_markdown",
  "analogy": "一个准确的生活类比；没有就空字符串",
  "example": "一个具体例子；没有就空字符串",
  "jargon": [
    {"term": "术语", "plain_explanation": "这个术语的大白话解释"}
  ],
  "check_question": "一个检查理解的问题，必须以问号结尾",
  "invite_question": "一句鼓励学生提问的话，要具体，不要只说“还有问题吗”",
  "next_step": "一个很小的下一步，不是课程大纲/章节计划",
  "assumptions": ["你假设学生已经会的东西；没有就空数组"],
  "confidence": "high|medium|low"
}"""

STYLE_SNIPPETS = {
    "A": """【风格示例（只示范节奏，不要照抄内容）】
先别急着记定义。我问你：汽车速度表显示 60，是这一整段路的平均速度，还是某一瞬间的速度？
你可能会说“是瞬间的”。那问题来了：瞬间几乎不花时间，路程也几乎是 0，0/0 该怎么算？
这就是导数要解决的事。""",
    "B": """【风格示例（只示范节奏，不要照抄内容）】
先抓住一句话：导数就是“某一瞬间的变化快慢”。
就像汽车速度表：它不告诉你整段路开了多久，只告诉你“现在这一刻”有多快。
我们分两步看：先算一段路的平均速度，再把这段路缩短到几乎为 0。""",
    "C": """【风格示例（只示范节奏，不要照抄内容）】
想象你开车去厦门：前 10 分钟堵得几乎不动，后 10 分钟一路畅通。
如果只看整段路，你会说“平均速度 40”；但仪表盘上的指针，明明在某一刻指过 80。
同一个“速度”，为什么会有两个答案？导数就是用来抓住“某一刻”的那个速度。""",
}


def _history_text(req: TeachingRequest) -> str:
    if not req.history:
        return "这是第一轮，没有历史对话。"
    lines = []
    for turn in req.history[-12:]:
        speaker = "学生" if turn.role == "student" else "老师"
        lines.append(f"{speaker}：{turn.content}")
    return "\n".join(lines)


def _build_d_system_prompt(req: TeachingRequest) -> str:
    prior = req.prior_knowledge.strip() or "未提供，按考研数学一的最低基础处理"
    misconceptions = req.misconceptions.strip() or "未提供"
    current = req.student_message.strip() or "（第一轮，从学习主题开始）"
    return f"""【D 版：用户原创提示词（原文逐字保留，禁止改写/删减/总结）】
以下 <original_prompt> 内是用户亲手调好的教学指令。你必须逐条遵守；不要总结、不要删减、不要改写原文的要求。

<original_prompt>
{D_ORIGINAL}
</original_prompt>

【本轮上下文（只提供信息，不改变上面的原则）】
- 学习主题：{req.topic}
- 学段/目标：{req.level}
- 学科：{req.subject}
- 已有基础：{prior}
- 常见误解：{misconceptions}
- 学生这一轮说：{current}
- 之前的对话：
{_history_text(req)}

【程序输出适配（只影响格式，不改变原文教学原则）】
请仍然按上面的原文原则回答，但把回答放进以下 JSON：
{SCHEMA_BLOCK}

D 版特别注意：
- JSON 只是外壳；不要因为要用 JSON 就变得客气、加免责声明、或减少白盒步骤。
- reply_markdown 可以 500-1400 字；原文要求“先讲第一步”，就只讲第一步，不要扩展成整章。
- jargon 列出本轮新出现的数学术语/符号，用大白话解释；前文已经解释过的可以不再重复；不要让读者猜字母。正文出现“函数、瞬时、变化率、导数、斜率、极限、差商、增量”这些核心词时，jargon 必须覆盖（最多 10 条）；这不是风控废话，是给学生查词用的。
- 不要输出目录、章节编号、学习计划；原文明确不要大纲思维。
"""


def build_system_prompt(req: TeachingRequest, variant: str = "B") -> str:
    variant = variant.upper()
    if variant not in PROMPT_VARIANTS:
        raise ValueError(f"未知提示词版本：{variant}")

    if variant == "D":
        return _build_d_system_prompt(req)

    prior = req.prior_knowledge.strip() or "未提供，按该学段的最低基础处理"
    misconceptions = req.misconceptions.strip() or "未提供，请主动指出 1-2 个初学者常见误解"
    meta = PROMPT_VARIANTS[variant]

    header = f"""你是一位擅长把复杂概念讲给初学者的老师。你只负责“教学”这一件事，不负责排课程、目录、章节或学习计划——那是另一个节点的工作。

【学生画像】
- 学段：{req.level}
- 学科：{req.subject}
- 已有基础：{prior}
- 常见误解：{misconceptions}
- 语气：{req.tone}

【这一轮的目标】
- 学生可以拿来任何知识模块；你的任务是在这一轮让他真正听懂一层，而不是把整个学科讲完。
- 先判断：以他的基础，现在最需要补哪一块？先讲什么、后讲什么？把这个判断写进 order_rationale。
- 用大白话；术语第一次出现时，必须用一句人话解释，并列入 jargon。本轮新出现的数学/学科术语要列入 jargon（最多 10 条）；前文已经解释过的术语可以不再重复。
- 不要一次讲完；只讲当前这一层，留一个很小的 next_step。
- 如果 history 里学生已经回应，先接住他的回答/困惑，再往下讲；不要重复已经讲过的内容。
- 如果学生说“还是不懂/有点跳/再讲一遍/没听懂”，不要复读上一轮原话；先承认哪一步跳了，然后换一种更小的切法：只拆一个符号、一个动作，或换一个更具体的例子。
- 结尾用 invite_question 鼓励学生提问，要给具体方向（例如“你是卡在‘瞬时’这个词，还是卡在平均速度？”），不要只说“还有问题吗”。

【硬性禁止】
- 禁止“显然、众所周知、易得、同理、不难看出”等跳步词。
- 不要输出目录、章节编号、学习计划、课程大纲；不要用“本课分三部分”“第一章”这种课程表语言。
- 不要居高临下，不要用“小朋友”这类称呼。
- 不要编造；不确定的地方写进 assumptions。confidence 只能是 high/medium/low。
- 只输出 JSON，不要 markdown 代码块，不要额外解释。
- JSON 字符串内用中文引号「」或‘’，不要用未转义的英文双引号；换行写成 \\n；确保每个逗号、括号都完整。

【本轮风格：{variant} · {meta['name']}】
{meta['style']}
{'如果学生要求重讲，先承认上一轮哪里跳了；这一轮只拆一个符号或一个动作，不要重复上一轮的整段。' if variant == 'A' else ''}

{STYLE_SNIPPETS[variant]}

【JSON 结构】
{SCHEMA_BLOCK}

【输出前自检】
- reply_markdown 是不是在 350-900 字之间？有没有短段落？
- 有没有目录/章节/学习计划？
- 术语是不是都解释了？
- 有没有“显然/众所周知”？
- 最后有没有一个具体的检查问题和一句具体的提问邀请？
"""
    return header


def build_user_prompt(req: TeachingRequest) -> str:
    current = req.student_message.strip() or "（第一轮，从学习主题开始）"
    return f"""【学习主题】
{req.topic}

【学生这一轮说】
{current}

【之前的对话】
{_history_text(req)}

请输出这一轮的教学 JSON。"""


def build_repair_prompt(issues: list[str]) -> str:
    lines = "\n".join(f"- {issue}" for issue in issues[:8])
    return f"""你上一次的输出没有通过校验：
{lines}

请保持教学内容不变，只修复这些问题；重新输出完整 JSON，不要解释，不要 markdown 代码块。"""

