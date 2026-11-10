"""确定性评分测试：同样的输入必须得到同样的分数。"""

from __future__ import annotations

from core.schema import TeachingRequest, TeachingTurn
from core.scoring import score_teaching

GOOD = dict(
    reply_markdown="甲" * 600,
    core_idea="导数是把一段的平均变化缩到一点后逼近的那个数。",
    order_rationale="学生只会背公式，所以先用开车场景建立一段与一点的区别。",
    analogy="速度表",
    example="10 分钟 5 公里",
    jargon=[{"term": "导数", "plain_explanation": "缩到一点时逼近的那个数。"}],
    check_question="2 分钟走 1 公里，平均速度是多少？",
    invite_question="你是卡在一段与一点的区别上，还是卡在具体怎么算？",
    next_step="自己举一个一段路变短的例子。",
    assumptions=["学生会算除法"],
    confidence="high",
)

REQ = TeachingRequest(topic="什么是导数", level="高中", subject="数学")


def test_clean_turn_scores_high():
    card = score_teaching(TeachingTurn(**GOOD), REQ, issues=[], attempts=1)
    assert card.total >= 90
    assert card.passed is True
    assert card.grade == "A"


def test_missing_example_and_analogy_deducts():
    data = dict(GOOD, example="", analogy="")
    card = score_teaching(TeachingTurn(**data), REQ, issues=[], attempts=1)
    assert card.breakdown["例子具体"] == 0
    assert card.total < 90


def test_critical_issue_fails_even_if_long():
    card = score_teaching(
        TeachingTurn(**GOOD),
        REQ,
        issues=["出现“目录”，像课程目录/章节；本节点不排目录"],
        attempts=1,
    )
    assert card.breakdown["结构合规"] == 0
    assert card.passed is False


def test_retries_are_penalised():
    one = score_teaching(TeachingTurn(**GOOD), REQ, issues=[], attempts=1)
    three = score_teaching(TeachingTurn(**GOOD), REQ, issues=[], attempts=3)
    assert three.total < one.total


def test_scoring_is_deterministic():
    a = score_teaching(TeachingTurn(**GOOD), REQ, issues=["x"], attempts=1)
    b = score_teaching(TeachingTurn(**GOOD), REQ, issues=["x"], attempts=1)
    assert a.as_dict() == b.as_dict()
