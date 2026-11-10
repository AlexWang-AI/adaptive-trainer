"""五层判题：choice → text → numeric → sympy → fallback。

设计原则：
1. 能确定性判的，绝不问模型；
2. 每一层都写进 `Judgement.layer`，可统计、可解释；
3. 标准答案来自 `AnswerKey`（独立答案键），不是题卡里的 `answer`。
"""

from __future__ import annotations

import math
import re
import unicodedata
from fractions import Fraction
from typing import Any

from contracts import AnswerKey, Judgement, QuestionCard

try:
    import sympy
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    SYMPY_OK = True
except Exception:  # pragma: no cover
    sympy = None  # type: ignore
    SYMPY_OK = False

_OPTION_LETTER = re.compile(r"(?:^|[^A-Za-z])([A-Da-d])(?![A-Za-z])")
_PREFIX = re.compile(r"^(?:答案是|正确答案是|正确选项是|正确的是|应该选|我选|答案|选|答)\s*[:：]?\s*")
_TRAILING = "。．.，,；;：:！!？?、 \t\n$"
_UNICODE = {"π": "pi", "√": "sqrt", "×": "*", "·": "*", "÷": "/", "−": "-", "–": "-", "—": "-"}
_FUNCS = {
    "sin": "sin", "cos": "cos", "tan": "tan", "cot": "cot", "sec": "sec", "csc": "csc",
    "arcsin": "asin", "arccos": "acos", "arctan": "atan",
    "ln": "log", "log": "log", "exp": "exp", "sqrt": "sqrt", "abs": "Abs",
}


def normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", str(text or ""))
    for src, dst in _UNICODE.items():
        t = t.replace(src, dst)
    t = t.replace("$", "")
    t = _PREFIX.sub("", t.strip())
    t = t.strip(_TRAILING)
    t = re.sub(r"\s+", "", t)
    return t.lower()


def _choice_letter(card: QuestionCard, student: str) -> str | None:
    s = normalize_text(student)
    if len(s) == 1 and s.upper() in {"A", "B", "C", "D"}:
        return s.upper()
    m = _OPTION_LETTER.search(student)
    if m:
        return m.group(1).upper()
    for i, option in enumerate(card.options):
        if normalize_text(option) == s:
            return chr(65 + i)
    return None


def _parse_number(text: str) -> Any | None:
    s = normalize_text(text).replace("=", "")
    if not s:
        return None
    percent = s.endswith("%")
    if percent:
        s = s[:-1]
    try:
        value: Any = Fraction(s)
    except Exception:
        try:
            value = float(s)
        except Exception:
            if not SYMPY_OK:
                return None
            try:
                value = sympy.N(_parse_expr(s))
            except Exception:
                return None
    if percent:
        value = value / 100
    return value


def _parse_expr(text: str):
    if not SYMPY_OK:
        raise ValueError("sympy 不可用")
    s = normalize_text(text).replace("^", "**")
    s = re.sub(r"√\s*\(([^()]*)\)", r"sqrt(\1)", s)
    s = re.sub(r"√\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", s)
    for src, dst in _FUNCS.items():
        s = re.sub(rf"\b{src}\b", dst, s)
    local = {name: sympy.Symbol(name) for name in ("x", "y", "z", "t", "a", "b", "c", "C")}
    local.update({"pi": sympy.pi, "E": sympy.E})
    global_dict = {"__builtins__": {}}
    for name in ("Symbol", "Integer", "Float", "Rational", "sqrt", "sin", "cos", "tan", "cot",
                 "sec", "csc", "asin", "acos", "atan", "log", "exp", "Abs", "pi", "E"):
        if hasattr(sympy, name):
            global_dict[name] = getattr(sympy, name)
    return parse_expr(
        s,
        local_dict=local,
        global_dict=global_dict,
        transformations=standard_transformations + (implicit_multiplication_application, convert_xor),
        evaluate=True,
    )


def _sympy_equal(a_text: str, b_text: str) -> bool:
    try:
        a = _parse_expr(a_text)
        b = _parse_expr(b_text)
        if a is None or b is None:
            return False
        diff = sympy.simplify(a - b)
        if diff == 0:
            return True
        if diff.free_symbols == set():
            return abs(float(diff)) < 1e-9
        return bool(a.equals(b))
    except Exception:
        return False


def _equation_equal(key_text: str, student_text: str) -> bool:
    """标准答案是方程时：2x=6 与 x=3、x=3 与 3 都应判对。"""
    if not SYMPY_OK:
        return False
    try:
        key_lhs, key_rhs = [x.strip() for x in key_text.split("=", 1)]
        key_eq = sympy.Eq(_parse_expr(key_lhs), _parse_expr(key_rhs))
        if "=" in student_text:
            s_lhs, s_rhs = [x.strip() for x in student_text.split("=", 1)]
            s_expr = sympy.simplify(_parse_expr(s_lhs) - _parse_expr(s_rhs))
            k_expr = sympy.simplify(key_eq.lhs - key_eq.rhs)
            ratio = sympy.simplify(s_expr / k_expr) if k_expr != 0 else None
            return ratio is not None and ratio.free_symbols == set() and ratio != 0
        student_expr = _parse_expr(student_text)
        solutions = sympy.solve(key_eq, sympy.Symbol("x"))
        return any(sympy.simplify(student_expr - s) == 0 for s in solutions)
    except Exception:
        return False


def judge_answer(card: QuestionCard, student_answer: str, key: AnswerKey) -> Judgement:
    raw = str(student_answer or "").strip()
    if not raw:
        return Judgement(correct=False, layer="fallback", reason="空答案", correct_answer=key.answer)

    # L1 选择题
    if key.kind == "choice":
        student_letter = _choice_letter(card, raw)
        correct = student_letter == key.answer.strip().upper()
        return Judgement(
            correct=correct,
            layer="choice",
            reason=f"选项 {student_letter or '无法识别'} vs {key.answer}",
            correct_answer=key.answer,
        )

    # L2 文本完全一致
    if normalize_text(raw) == normalize_text(key.answer):
        return Judgement(correct=True, layer="text", reason="归一化后完全一致", correct_answer=key.answer)

    # L3 数值
    a, b = _parse_number(raw), _parse_number(key.answer)
    if a is not None and b is not None:
        try:
            equal = abs(float(a) - float(b)) <= 1e-3 * max(1.0, abs(float(b)))
        except Exception:
            equal = False
        if equal:
            return Judgement(correct=True, layer="numeric", reason="数值等价", correct_answer=key.answer)

    # L4 符号等价 / 方程
    if "=" in key.answer:
        if _equation_equal(key.answer, raw):
            return Judgement(correct=True, layer="sympy", reason="方程解等价", correct_answer=key.answer)
    elif _sympy_equal(key.answer, raw):
        return Judgement(correct=True, layer="sympy", reason="化简后差为 0", correct_answer=key.answer)

    # L5 fallback：开放题/无法判定，交人工或 LLM，但绝不静默判对
    return Judgement(
        correct=False,
        layer="fallback",
        reason="未命中任何确定性判定层，需人工复核",
        correct_answer=key.answer,
    )
