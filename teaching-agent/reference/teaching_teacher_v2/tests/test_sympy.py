"""SymPy 符号等价测试：这些用例对应真实考研高数的答案形态。

规则：每条都必须是「学生写法」与「标准答案」在数学上等价/不等价，
而字符串比较一定判不出来——这正是引入 SymPy 的理由。
"""

from __future__ import annotations

import pytest

from core.judge import judge, sympy_equivalent
from core.schema import QuestionCard


def make(question: str, answer: str, kind: str = "fill") -> QuestionCard:
    return QuestionCard(
        kind=kind,
        stem=question,
        options=[],
        answer=answer,
        explanation="由题意直接计算可得。",
        tested_points=["求导"],
        difficulty="medium",
        why_this_question="这一轮讲的就是这个动作，直接检验学生有没有掌握。",
        source_quote="",
        confidence="high",
    )


EQUIVALENT = [
    # 求导结果的不同写法
    ("2x", "2*x"),
    ("2x", "x*2"),
    # 展开 / 因式分解
    ("(x+1)^2", "x^2+2x+1"),
    ("x^2-1", "(x-1)(x+1)"),
    # 三角恒等式
    ("sin(x)^2+cos(x)^2", "1"),
    ("tan(x)", "sin(x)/cos(x)"),
    # 学生常用的简写（不带括号/乘号）
    ("sinx", "sin(x)"),
    ("cos2x", "cos(2*x)"),
    ("sin^2x+cos^2x", "1"),
    ("sin²x+cos²x", "1"),
    ("sinx^2", "sin(x^2)"),
    ("2xy", "2*x*y"),
    ("arcsinx", "arcsin(x)"),
    # 对数写法
    ("ln(x)", "log(x)"),
    # 幂与根式
    ("1/sqrt(2)", "sqrt(2)/2"),
    ("√2/2", "sqrt(2)/2"),
    ("2√2", "sqrt(8)"),
    ("x^(-1)", "1/x"),
    ("x⁵", "x^5"),
    # 常数与近似值
    ("e^(i*pi)", "-1"),
    ("3π", "9.4248"),
    ("π/2", "1.5708"),
    ("ln(2)", "0.6931"),
    ("5!", "120"),
    # 带分数
    ("1 1/2", "1.5"),
    ("-1 1/2", "-1.5"),
    # 方程等价
    ("2x=6", "x=3"),
    ("x=3", "3"),
]

NOT_EQUIVALENT = [
    ("2x+1", "2x-1"),
    ("x^2", "x^3"),
    ("sin(x)", "cos(x)"),
    ("x=3", "x=4"),
    ("1/2", "1/3"),
    # 只给一个根不算完整解
    ("x^2=4", "2"),
    # 11/2 不能被当成带分数 1 1/2
    ("11/2", "1.5"),
    ("5!", "5"),
]


@pytest.mark.parametrize("student,answer", EQUIVALENT)
def test_sympy_accepts_equivalent_forms(student, answer):
    equivalent, detail = sympy_equivalent(student, answer)
    assert equivalent is True, f"{student} 与 {answer} 应判等价，实际：{equivalent} / {detail}"


@pytest.mark.parametrize("student,answer", NOT_EQUIVALENT)
def test_sympy_rejects_different_forms(student, answer):
    equivalent, detail = sympy_equivalent(student, answer)
    assert equivalent is False, f"{student} 与 {answer} 应判不等价，实际：{equivalent} / {detail}"


def test_judge_uses_sympy_layer_before_llm():
    card = make("求 f(x)=(x+1)^2 的导数", "2x+2")

    class Boom:
        def chat_json(self, *a, **k):  # 如果调用到 LLM 就失败
            raise AssertionError("不该走到 LLM 兜底")

    verdict = judge(card, "2(x+1)", client=Boom())
    assert verdict.correct is True
    assert verdict.layer == "sympy"


def test_judge_rejects_wrong_derivative_without_llm():
    card = make("求 f(x)=x^2 的导数", "2x")

    class Boom:
        def chat_json(self, *a, **k):
            raise AssertionError("判错不该依赖 LLM")

    verdict = judge(card, "x^2", client=Boom())
    assert verdict.correct is False
    assert verdict.layer == "sympy"


def test_open_ended_answer_falls_through_to_llm():
    card = make("用自己的话说，导数是什么", "把一段的平均变化缩到一点")

    class Stub:
        def __init__(self):
            self.called = 0

        def chat_json(self, *a, **k):
            self.called += 1
            return '{"equivalent": true, "reason": "意思一致"}', {}, 5

    stub = Stub()
    verdict = judge(card, "让区间不断缩小后逼近的那个变化率", client=stub)
    assert verdict.correct is True
    assert verdict.layer == "llm"
    assert stub.called == 1


def test_malicious_expression_is_not_executed():
    # parse_expr 走 eval 路径，这里验证没有把 builtins 暴露出去
    equivalent, detail = sympy_equivalent('__import__("os").system("echo hacked")', "1")
    assert equivalent is None
    assert "无法解析" in detail or "异常" in detail or "超时" in detail


def test_plus_minus_covers_all_roots():
    equivalent, detail = sympy_equivalent("x^2=4", "±2")
    assert equivalent is True, detail


def test_unparsed_shorthand_defers_to_next_layer():
    # sinxy 无法确定是 sin(x)*y 还是 sin(x*y)，不能硬判错
    equivalent, detail = sympy_equivalent("sinxy", "sin(x*y)")
    assert equivalent is None
    assert "简写" in detail


def test_resource_bomb_is_skipped():
    for expr in ("9**9**9", "100000!"):
        equivalent, detail = sympy_equivalent(expr, "1")
        assert equivalent is None, f"{expr} 不应进入符号计算"
        assert "复杂" in detail
