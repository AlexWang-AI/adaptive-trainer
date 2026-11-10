from content import get_answer_key, get_questions
from judge import judge_answer


def _judge(kp_id: str, index: int, student: str) -> tuple[bool, str]:
    card = get_questions(kp_id)[index]
    key = get_answer_key(card.id)
    verdict = judge_answer(card, student, key)
    return verdict.correct, verdict.layer


def test_choice_letter_and_option_text():
    assert _judge("der.basic", 0, "B") == (True, "choice")
    assert _judge("der.basic", 0, "选B") == (True, "choice")
    assert _judge("der.basic", 0, "4") == (True, "choice")
    assert _judge("der.basic", 0, "A")[0] is False


def test_fill_numeric_equivalence():
    assert _judge("lim.lhopital", 1, "1") == (True, "text")
    assert _judge("lim.lhopital", 1, "1.0")[0] is True
    assert _judge("lim.lhopital", 1, "0")[0] is False


def test_fill_symbolic_equivalence():
    assert _judge("der.basic", 1, "2*x") == (True, "sympy")
    assert _judge("der.basic", 1, "x^2")[0] is False


def test_integral_constant_matters():
    assert _judge("int.basic", 0, "x^2+C")[0] is True
    assert _judge("int.basic", 0, "x^2")[0] is False


def test_equation_solution():
    from contracts import AnswerKey, QuestionCard

    card = QuestionCard(
        id="eq.q1", kind="fill", stem="解方程 2x=6。", options=[],
        answer="x=3", explanation="两边同时除以 2，得到 x=3。", tested_points=["eq"],
    )
    key = AnswerKey(question_id="eq.q1", answer="x=3", kind="fill", explanation="")
    assert judge_answer(card, "3", key).correct is True
    assert judge_answer(card, "x=4", key).correct is False
