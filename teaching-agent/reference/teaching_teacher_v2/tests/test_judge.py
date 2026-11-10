"""判题器回归测试：这些用例就是 v1 会判错的真实场景。"""

from __future__ import annotations

import pytest

from core.judge import extract_choice_letter, judge, normalize
from core.quiz_schema import QuizQuestion


def make_quiz(kind: str = "fill", answer: str = "0.5", options: list[str] | None = None) -> QuizQuestion:
    return QuizQuestion(
        kind=kind,
        stem="一辆车 2 分钟走了 1 公里，平均速度是多少？",
        options=options or (["0.5 公里每分钟", "2 公里每分钟", "1 公里每分钟", "0.2 公里每分钟"] if kind == "choice" else []),
        answer=answer,
        explanation="平均速度等于总距离除以总时间，1 除以 2 等于 0.5。",
        tested_points=["平均速度"],
        difficulty="easy",
        why_this_question="刚才讲的第一步就是这个卡点。",
        source_quote="如果一辆车 2 分钟走了 1 公里",
        confidence="high",
    )


@pytest.mark.parametrize(
    "answer,expected_layer",
    [
        ("0.5", "text"),
        ("1/2", "numeric"),
        ("0.50", "numeric"),
        ("50%", "numeric"),
        (" 0.5 ", "text"),
        ("０.５", "text"),  # 全角
    ],
)
def test_equivalent_numeric_answers_pass(answer, expected_layer):
    verdict = judge(make_quiz(), answer)
    assert verdict.correct is True
    assert verdict.layer == expected_layer


@pytest.mark.parametrize("answer", ["3", "0.4", "", "不知道"])
def test_wrong_answers_fail(answer):
    verdict = judge(make_quiz(), answer)
    assert verdict.correct is False


def test_choice_letter_variants():
    quiz = make_quiz(kind="choice", answer="A")
    for answer in ["A", "a", "选A", "答案是A", "A. 0.5 公里每分钟", "0.5 公里每分钟"]:
        assert judge(quiz, answer).correct is True, answer

    for wrong in ["B", "选D", "2 公里每分钟"]:
        assert judge(quiz, wrong).correct is False, wrong


def test_choice_letter_extraction_edge_cases():
    assert extract_choice_letter("选A") == "A"
    assert extract_choice_letter("我选 C 吧") == "C"
    assert extract_choice_letter("A") == "A"
    assert extract_choice_letter("因为所以") is None


def test_x_equals_three_equals_three():
    quiz = make_quiz(kind="fill", answer="x=3")
    assert judge(quiz, "3").correct is True
    assert judge(quiz, "x = 3").correct is True
    assert judge(quiz, "4").correct is False


def test_sqrt_equivalence():
    quiz = make_quiz(kind="fill", answer="√2")
    assert judge(quiz, "1.414").correct is True
    assert judge(quiz, "1.5").correct is False


def test_latex_wrapped_answer():
    quiz = make_quiz(kind="fill", answer="3")
    assert judge(quiz, r"$3$").correct is True
    assert judge(quiz, r"\left(3\right)").correct is True


def test_normalize_strips_prefixes_and_punctuation():
    assert normalize("答案是：A。") == "a"
    assert normalize("　1 / 2　") == "1/2"


def test_llm_fallback_only_when_layers_fail():
    class StubClient:
        def __init__(self):
            self.called = 0

        def chat_json(self, messages, **_):
            self.called += 1
            return '{"equivalent": true, "reason": "同一结论的不同表述"}', {}, 10

    client = StubClient()
    quiz = make_quiz(kind="fill", answer="把一段缩到一点")

    # 前三层能判出来时，不应该调用 LLM
    judge(quiz, "把一段缩到一点", client=client)
    assert client.called == 0

    # 判不出来时，走 LLM 兜底
    verdict = judge(quiz, "无限接近某一点时得到的值", client=client)
    assert client.called == 1
    assert verdict.correct is True
    assert verdict.layer == "llm"


def test_choice_full_text_wins_over_letter_inside_text():
    quiz = make_quiz(kind="choice", answer="B", options=["xx", "a cat", "yy", "zz"])
    assert judge(quiz, "a cat", allow_llm=False).correct is True
    assert judge(quiz, "xx", allow_llm=False).correct is False


def test_choice_answer_key_may_be_full_text():
    quiz = {"kind": "choice", "answer": "a cat", "options": ["xx", "a cat", "yy", "zz"], "stem": "pick"}
    assert judge(quiz, "B", allow_llm=False).correct is True


def test_mixed_number_is_not_glued_into_wrong_integer():
    quiz = make_quiz(kind="fill", answer="1.5")
    assert judge(quiz, "1 1/2", allow_llm=False).correct is True
    assert judge(quiz, "11/2", allow_llm=False).correct is False


def test_pi_multiple_is_numeric_equivalent():
    quiz = make_quiz(kind="fill", answer="3π")
    verdict = judge(quiz, "9.4248", allow_llm=False)
    assert verdict.correct is True
    assert verdict.layer == "numeric"


def test_incomplete_equation_roots_are_wrong():
    quiz = make_quiz(kind="fill", answer="x^2=4")
    assert judge(quiz, "2", allow_llm=False).correct is False
    assert judge(quiz, "±2", allow_llm=False).correct is True


def test_function_shorthand_is_equivalent():
    assert judge(make_quiz(kind="fill", answer="sin(x)"), "sinx", allow_llm=False).correct is True
    assert judge(make_quiz(kind="fill", answer="2*x*y"), "2xy", allow_llm=False).correct is True
    assert judge(make_quiz(kind="fill", answer="sqrt(2)/2"), "√2/2", allow_llm=False).correct is True


class _BadLLM:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    def chat_json(self, *args, **kwargs):
        return self.raw, {}, 1


def test_llm_failure_marks_uncertain_not_confident_wrong():
    quiz = make_quiz(kind="fill", answer="把一段缩到一点")

    verdict = judge(quiz, "无限接近某一点时得到的值", client=_BadLLM('{"equivalent": "no"}'))
    assert verdict.correct is False
    assert verdict.uncertain is True

    class Boom:
        def chat_json(self, *args, **kwargs):
            raise RuntimeError("network down")

    verdict = judge(quiz, "无限接近某一点时得到的值", client=Boom())
    assert verdict.correct is False
    assert verdict.uncertain is True
    assert "LLM" in verdict.reason
