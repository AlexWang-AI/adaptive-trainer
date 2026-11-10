from __future__ import annotations

import json

from core.schema import TeachingRequest, TeachingTurn

QUIZ_SCHEMA = """{
  "kind": "choice 或 fill",
  "stem": "题干；只出一道题；数学用 LaTeX $...$",
  "options": ["选择题必须正好 4 个选项；填空题必须是空数组"],
  "answer": "选择题填 A/B/C/D；填空题填标准答案",
  "explanation": "为什么是这个答案；一到三句话",
  "tested_points": ["这道题只测的 1-3 个点"],
  "difficulty": "easy|medium|hard",
  "why_this_question": "为什么现在出这道题：对准学生这一轮卡住的哪句话/哪个动作",
  "source_quote": "从教学节点 reply_markdown 里摘一句原文，证明题目有依据",
  "confidence": "high|medium|low"
}"""


def build_quiz_system_prompt(req: TeachingRequest) -> str:
    prior = req.prior_knowledge.strip() or "未提供"
    misconceptions = req.misconceptions.strip() or "未提供"
    return f"""你是“出题节点”，不是教学节点。你的唯一任务：根据上一轮教学节点的回复，出一道题，检查学生是否真的掌握了刚才那一层。

【学生画像】
- 主题：{req.topic}
- 学段：{req.level}
- 学科：{req.subject}
- 已有基础：{prior}
- 常见误解：{misconceptions}

【硬性规则】
1. 只出一道题，不要出第二道；不要写“第 1 题/第 2 题”。
2. 题型只能是 choice（单选）或 fill（填空），以选择题为主；选择题必须正好 4 个选项，只有一个正确；填空题 options 必须是空数组。options 里只写选项内容，不要自带 A/B/C/D 前缀（程序会自动加字母）。
3. 题目必须严格基于 <teaching_turn> 里刚刚讲过的这一层；不能引入没讲过的新概念，不能超纲，不能考整章。
4. 题目必须对准 <student_message> 暴露的卡点：
   - 学生说“还是不懂/有点跳/没听懂” → 出 easy，只测刚才那一个动作/一个符号。
   - 学生说“懂了/大概明白” → 出 medium，测刚才的 check_question 或 next_step。
   - 学生问“为什么/什么时候用/变式” → 出 medium 或 hard，但仍然只测一个点。
5. 选择题不要出“以下哪些/多选/以上都对/以上都不对”；干扰项要像真的会犯的错，不要靠文字游戏。
6. 填空题答案要短、唯一、可判定；不要出需要长计算或含糊表述的填空。
7. why_this_question 必须具体说明“学生这一轮卡在哪句话/哪个动作，所以出这道题”，不要写空话。
8. source_quote 必须从 <teaching_turn> 的 reply_markdown 里原样摘一句（不改写），证明题目有依据。
9. 只输出 JSON，不要 markdown 代码块；公式用 LaTeX。

【JSON 结构】
{QUIZ_SCHEMA}
"""


def build_quiz_user_prompt(req: TeachingRequest, teaching: TeachingTurn) -> str:
    teaching_json = json.dumps(teaching.model_dump(), ensure_ascii=False, indent=2)
    current = req.student_message.strip() or "（第一轮，从学习主题开始）"
    history = "\n".join(
        f"{'学生' if turn.role == 'student' else '老师'}：{turn.content}"
        for turn in req.history[-8:]
    ) or "（无历史）"
    return f"""【学生这一轮说】
{current}

【最近对话】
{history}

<teaching_turn>
{teaching_json}
</teaching_turn>

请严格根据上面这一轮教学，只出一道题。输出完整 JSON。"""


def build_quiz_repair_prompt(issues: list[str]) -> str:
    lines = "\n".join(f"- {issue}" for issue in issues[:8])
    return f"""你上一次出的题没有通过校验：
{lines}

请保持题目考点不变，只修复这些问题；重新输出完整 JSON，不要解释，不要 markdown 代码块。"""
