from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.checks import check_turn  # noqa: E402
from core.schema import TeachingRequest, TeachingTurn  # noqa: E402

VALID = {
    "reply_markdown": """**先看一个你熟悉的场景**
你开车去厦门，前 10 分钟堵得几乎不动，后 10 分钟一路畅通。整段路的平均速度可能只有 40，但仪表盘上的指针，在某一刻明明指过 80。

**为什么会有两个速度**
平均速度看的是“一整段路”，它把慢和快平均掉了。可我们经常想知道“现在这一刻有多快”，这就需要把时间间隔缩到很小。

**导数就是干这个的**
把一段时间缩到几乎为 0，平均速度就逼近某一瞬间的速度。这个“瞬时变化率”，数学上叫导数。它不是另一个世界来的公式，它就是速度表指针背后的那个数。

所以，导数不是让你多背一个符号，而是让你能描述“这一刻正在怎么变”。""",
    "core_idea": "导数就是某一瞬间的变化快慢。",
    "order_rationale": "先讲平均速度，因为学生已经会；再把时间缩短引出瞬时速度，最后命名导数。",
    "analogy": "汽车速度表：它不告诉你整段路开了多久，只告诉你现在这一刻有多快。",
    "example": "前 10 分钟堵、后 10 分钟畅通，整段平均速度和某一刻的表盘读数不同。",
    "jargon": [
        {"term": "平均速度", "plain_explanation": "一整段路的总路程除以总时间，把快慢平均掉。"},
        {"term": "瞬时", "plain_explanation": "某一刻，时间间隔几乎为 0 的那一瞬间。"},
        {"term": "变化率", "plain_explanation": "一个量相对另一个量变化得有多快。"},
        {"term": "导数", "plain_explanation": "某一瞬间的变化率，也就是瞬时速度的数学名字。"},
    ],
    "check_question": "如果把时间间隔从 10 分钟缩短到 0.001 秒，平均速度会接近什么？",
    "invite_question": "你是卡在“瞬时”这个词，还是卡在“平均速度怎么算”？告诉我，我们从你卡住的地方往下讲。",
    "next_step": "下一步只做一件事：把 10 分钟缩短到 1 秒，看看平均速度怎么变。",
    "assumptions": ["学生会算平均速度"],
    "confidence": "high",
}


class SchemaTests(unittest.TestCase):
    def test_valid_turn(self):
        response = TeachingTurn.model_validate(VALID)
        req = TeachingRequest(topic="什么是导数？", level="高中")
        self.assertEqual(check_turn(response, req), [])

    def test_question_mark_required(self):
        payload = deepcopy(VALID)
        payload["check_question"] = "这是一个没有问号的问题"
        with self.assertRaises(ValidationError):
            TeachingTurn.model_validate(payload)

    def test_reply_too_short(self):
        payload = deepcopy(VALID)
        payload["reply_markdown"] = "太短了。"
        with self.assertRaises(ValidationError):
            TeachingTurn.model_validate(payload)

    def test_toc_is_rejected(self):
        payload = deepcopy(VALID)
        payload["reply_markdown"] += "\n\n本课分三部分，下面是目录。"
        response = TeachingTurn.model_validate(payload)
        issues = check_turn(response, TeachingRequest(topic="什么是导数？", level="高中"))
        self.assertTrue(any("目录" in issue or "章节" in issue or "本课分" in issue for issue in issues))

    def test_missing_jargon_is_flagged(self):
        payload = deepcopy(VALID)
        payload["jargon"] = []
        response = TeachingTurn.model_validate(payload)
        issues = check_turn(response, TeachingRequest(topic="什么是导数？", level="高中"))
        self.assertTrue(any("术语" in issue for issue in issues))

    def test_generic_invite_is_flagged(self):
        payload = deepcopy(VALID)
        payload["invite_question"] = "还有问题吗？"
        response = TeachingTurn.model_validate(payload)
        issues = check_turn(response, TeachingRequest(topic="什么是导数？", level="高中"))
        self.assertTrue(any("太笼统" in issue for issue in issues))

    def test_next_step_should_be_single(self):
        payload = deepcopy(VALID)
        payload["next_step"] = "先复习平均速度。再预习瞬时速度。"
        response = TeachingTurn.model_validate(payload)
        issues = check_turn(response, TeachingRequest(topic="什么是导数？", level="高中"))
        self.assertTrue(any("next_step" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
