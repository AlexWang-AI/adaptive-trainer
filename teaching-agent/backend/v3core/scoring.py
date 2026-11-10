"""确定性教学评分（rubric），替代「90 分」这种拍脑袋门槛。

为什么不用 LLM 打总分？
    LLM 打 0-100 的分数不可复现：同一份回答两次可能 84 也可能 93，
    学生追问「为什么差一分」时无法解释。这里改成**可解释的分项 rubric**：
    每一项都有明确的判定规则，扣分能指到具体句子，总分只是分项之和。

维度（满分 100）：
    结构合规 30   —— schema/确定性检查是否通过
    长度得当 15   —— 250~1500 字之间
    术语友好 20   —— 术语要么进 jargon 表，要么就近解释
    例子具体 15   —— 有 example 和 analogy
    互动设计 10   —— 检查问题 + 具体邀请问题
    诚实标注 10   —— 低置信度时给出 assumptions

通过门槛：总分 ≥ 75 且没有 critical 问题（目录化/跳步词/无检查问题）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from v3core.schema import TeachingRequest, TeachingTurn

CRITICAL_PREFIXES = ("出现“目录", "出现“章节", "出现跳步词")


@dataclass
class ScoreCard:
    total: int
    grade: str
    passed: bool
    breakdown: dict[str, int] = field(default_factory=dict)
    deductions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "grade": self.grade,
            "passed": self.passed,
            "breakdown": self.breakdown,
            "deductions": self.deductions,
        }


def _grade(total: int) -> str:
    if total >= 90:
        return "A"
    if total >= 80:
        return "B"
    if total >= 75:
        return "C"
    return "D"


def score_teaching(
    turn: TeachingTurn,
    req: TeachingRequest,
    *,
    issues: list[str] | None = None,
    attempts: int = 1,
) -> ScoreCard:
    issues = issues or []
    breakdown: dict[str, int] = {}
    deductions: list[str] = []

    critical = [i for i in issues if i.startswith(CRITICAL_PREFIXES)]

    # 1. 结构合规 30
    # critical（目录化、跳步词）直接清零；普通的术语/措辞问题每次只扣 3 分、最多扣 15，
    # 否则一条软问题就能把 30 分吃掉，出现过「内容不错但分数 60」的误伤。
    if not issues:
        breakdown["结构合规"] = 30
    elif critical:
        breakdown["结构合规"] = 0
        deductions.append("存在 critical 问题：" + critical[0])
    else:
        penalty = min(15, 3 * len(issues))
        breakdown["结构合规"] = 30 - penalty
        deductions.append(f"{len(issues)} 条软问题，扣 {penalty}")

    # 2. 长度 15
    length = len(turn.reply_markdown)
    if 250 <= length <= 1200:
        breakdown["长度得当"] = 15
    elif 250 <= length <= 1500:
        breakdown["长度得当"] = 10
        deductions.append(f"篇幅 {length} 字偏长，扣 5")
    else:
        breakdown["长度得当"] = 5
        deductions.append(f"篇幅 {length} 字不在 250~1500 区间，扣 10")

    # 3. 术语友好 20
    jargon_terms = {item.term for item in turn.jargon}
    jargon_score = 20
    if any(i.startswith("术语“") for i in issues):
        jargon_score -= 10
        deductions.append("有术语既未列入 jargon 表也未就近解释，扣 10")
    if len(jargon_terms) < 1:
        jargon_score -= 5
        deductions.append("未给出任何术语解释，扣 5")
    breakdown["术语友好"] = max(0, jargon_score)

    # 4. 例子具体 15
    example_score = 0
    if turn.example.strip():
        example_score += 9
    else:
        deductions.append("缺少具体例子，扣 9")
    if turn.analogy.strip():
        example_score += 6
    else:
        deductions.append("缺少生活类比，扣 6")
    breakdown["例子具体"] = example_score

    # 5. 互动设计 10
    interaction = 0
    if turn.check_question.strip():
        interaction += 5
    else:
        deductions.append("缺少检查问题，扣 5")
    if len(turn.invite_question.strip()) >= 8 and not any(
        g in turn.invite_question for g in ("还有问题吗", "有问题吗", "听懂了吗", "明白了吗")
    ):
        interaction += 5
    else:
        deductions.append("邀请提问过于笼统，扣 5")
    breakdown["互动设计"] = interaction

    # 6. 诚实标注 10
    honest = 10
    if turn.confidence == "low" and not turn.assumptions:
        honest = 0
        deductions.append("置信度 low 但没写 assumptions，扣 10")
    elif turn.confidence == "medium" and not turn.assumptions:
        honest = 7
    breakdown["诚实标注"] = honest

    # 修复惩罚：第 2 次以上重试说明一次写对的能力不足
    if attempts > 1:
        extra = min(10, (attempts - 1) * 5)
        breakdown["结构合规"] = max(0, breakdown["结构合规"] - extra)
        deductions.append(f"重试 {attempts - 1} 次，扣 {extra}")

    total = max(0, min(100, sum(breakdown.values())))
    passed = total >= 75 and not critical
    return ScoreCard(total=total, grade=_grade(total), passed=passed,
                     breakdown=breakdown, deductions=deductions)
