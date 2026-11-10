from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.quiz_node import check_quiz  # noqa: E402
from core.quiz_schema import QuizQuestion  # noqa: E402
from core.schema import TeachingRequest, TeachingTurn  # noqa: E402

TEACHING = TeachingTurn(
    reply_markdown=(
        "把区间不断缩短到几乎为 0 时，平均变化率逼近的那个数就是该点的导数。"
        "先算一段的平均变化率，再把这一段缩到几乎为零，看它稳定地靠近哪个数；"
        "这个靠近的数就是该点的瞬时变化率。速度表上的读数就是这样一个例子，"
        "它不是整段路的平均速度，而是某一瞬间的速度。"
        "如果你只盯着整段路的平均速度，就会把“段”和“点”混在一起；"
        "所以第一步永远是先把一段缩短，再观察它靠向哪个数，这就是导数的直觉。"
    ),
    core_idea="导数是瞬时变化率。",
    order_rationale="先讲平均，再缩短到一点。",
    analogy="速度表。",
    example="x=1 附近。",
    jargon=[],
    check_question="这是在描述一段还是一个点？",
    invite_question="你卡在哪一步？",
    next_step="只写一个差商式子。",
    assumptions=[],
    confidence="high",
)

VALID = {
    "kind": "choice",
    "stem": "这个越来越靠近 2 的过程，主要描述什么？",
    "options": ["一整段平均", "某一点瞬时", "函数值等于 2", "终点越远越稳"],
    "answer": "B",
    "explanation": "缩短到一点后逼近的是该点瞬时变化率。",
    "tested_points": ["平均变化率与瞬时变化率的区别"],
    "difficulty": "easy",
    "why_this_question": "学生这一轮卡在一段还是一个点，所以只测这个区分。",
    "source_quote": "平均变化率逼近的那个数就是该点的导数",
    "confidence": "high",
}


class QuizSchemaTests(unittest.TestCase):
    def test_valid_choice(self):
        quiz = QuizQuestion.model_validate(VALID)
        issues = check_quiz(quiz, TEACHING, TeachingRequest(topic="导数", level="高中"))
        self.assertEqual(issues, [])

    def test_choice_needs_four_options(self):
        payload = deepcopy(VALID)
        payload["options"] = ["A", "B", "C"]
        with self.assertRaises(ValidationError):
            QuizQuestion.model_validate(payload)

    def test_fill_needs_empty_options(self):
        payload = deepcopy(VALID)
        payload["kind"] = "fill"
        payload["answer"] = "2"
        with self.assertRaises(ValidationError):
            QuizQuestion.model_validate(payload)

    def test_source_quote_must_be_grounded(self):
        payload = deepcopy(VALID)
        payload["source_quote"] = "这句话不在教学回复里"
        quiz = QuizQuestion.model_validate(payload)
        issues = check_quiz(quiz, TEACHING, TeachingRequest(topic="导数", level="高中"))
        self.assertTrue(any("source_quote" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
