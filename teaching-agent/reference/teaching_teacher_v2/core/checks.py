from __future__ import annotations

import re

from core.schema import TeachingRequest, TeachingTurn

FORBIDDEN_PHRASES = ["显然", "众所周知", "易得", "同理", "不难看出"]
FORBIDDEN_TOC = [
    "目录", "章节", "第一章", "第二章", "第1章", "第2章",
    "本课大纲", "学习计划", "课程安排", "本课分",
]

JARGON_TERMS = [
    "函数", "变量", "导数", "积分", "极限", "概率", "矩阵", "向量",
    "方程", "系数", "对数", "分数", "小数", "负数", "相反数",
    "绝对值", "平方根", "因式分解", "斜率", "面积", "体积",
    "瞬时", "平均速度", "变化率",
]

INLINE_EXPLAIN_MARKERS = ["就是", "意思是", "指的是", "可以理解为", "换句话说", "好比", "相当于"]
INVITE_MARKERS = ["问", "告诉", "卡", "好奇", "想", "发我", "贴", "原题", "哪一步", "具体"]
GENERIC_INVITES = ["还有问题吗", "有问题吗", "是否明白", "听懂了吗", "明白了吗"]


def _has_inline_explanation(text: str, term: str) -> bool:
    start = 0
    while True:
        index = text.find(term, start)
        if index == -1:
            return False
        window = text[index : index + 18]
        if any(marker in window for marker in INLINE_EXPLAIN_MARKERS):
            return True
        start = index + len(term)
    return False


def check_turn(resp: TeachingTurn, req: TeachingRequest) -> list[str]:
    issues: list[str] = []
    text = resp.reply_markdown

    length = len(text)
    if length < 250:
        issues.append(f"reply_markdown 只有 {length} 字，讲得太少，学生可能没听懂")
    if length > 1500:
        issues.append(f"reply_markdown 有 {length} 字，太长；这一轮只讲一层")

    for marker in FORBIDDEN_TOC:
        if marker in text:
            issues.append(f"出现“{marker}”，像课程目录/章节；本节点不排目录")

    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            issues.append(f"出现跳步词“{phrase}”")

    for line in text.splitlines():
        for sentence in re.split(r"[。！？!?；;]", line):
            sentence = sentence.strip(" -*#\t")
            if len(sentence) > 120:
                issues.append("有一句超过 120 字，初学者读起来会累")

    known_text = " ".join(turn.content for turn in req.history if turn.role == "teacher")
    jargon_names = {item.term for item in resp.jargon}
    for term in JARGON_TERMS:
        if term in known_text:
            continue
        # 只出现一次的多半是顺带提一句，不算「没解释就抛术语」；出现两次以上才算真问题
        if text.count(term) >= 2 and term not in jargon_names and not _has_inline_explanation(text, term):
            issues.append(f"术语“{term}”出现了，但既没有列入 jargon，也没有就近解释")

    if any(generic in resp.invite_question for generic in GENERIC_INVITES):
        issues.append("invite_question 太笼统，要给学生一个具体的提问方向")
    elif len(resp.invite_question) < 12 and not any(
        marker in resp.invite_question for marker in INVITE_MARKERS
    ):
        issues.append("invite_question 不够具体，不像在邀请学生提问")

    if len(re.findall(r"[。；;]", resp.next_step)) > 1:
        issues.append("next_step 应只给一个很小的下一步，不要列 2 条以上")

    if resp.confidence == "low" and not resp.assumptions:
        issues.append("confidence=low 但没有写 assumptions，学生不知道哪里不确定")

    return list(dict.fromkeys(issues))
