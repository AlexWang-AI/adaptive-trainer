import pytest
from pydantic import ValidationError

from content import get_questions
from contracts import LessonPayload, QuestionCard


def test_choice_needs_four_options():
    with pytest.raises(ValidationError):
        QuestionCard(
            id="x.q1", kind="choice", stem="题干够长了吗？", options=["A", "B"],
            answer="A", explanation="解析够长了吗？", tested_points=["x"],
        )


def test_fill_must_have_no_options():
    with pytest.raises(ValidationError):
        QuestionCard(
            id="x.q2", kind="fill", stem="题干够长了吗？", options=["A"],
            answer="1", explanation="解析够长了吗？", tested_points=["x"],
        )


def test_lesson_payload_unique_ids():
    q1 = get_questions("der.basic")[0]
    q2 = q1.model_copy(update={"stem": "另一道题够长了吗？"})
    with pytest.raises(ValidationError):
        LessonPayload(
            teaching={
                "reply_markdown": "这一轮讲一层。" * 20,
                "core_idea": "导数是瞬时变化率。",
                "check_question": "你懂了吗？",
            },
            questions=[q1, q2],
        )
