"""判题器：SymPy 符号等价为核心的分层判定。

为什么必须上 SymPy
------------------
v2 的判题只在「数值」这一层做得不错，一到考研高数就崩：
    d/dx(x^2)      学生写 2x        → 字符串不等
    ∫2x dx         学生写 x^2+C     → 字符串不等
    sin^2+cos^2    学生写 1         → 字符串不等
    (x+1)^2        学生写 x^2+2x+1  → 字符串不等
这些不是「写法不同」，是同一个数学对象的两种表达。只有符号计算能判。

分层顺序（每层都可解释、可观测，命中即返回）
--------------------------------------------
    L1 choice   选择题：字母 / 选项全文
    L2 text     归一化后完全一致（全半角、空格、标点、$...$）
    L3 numeric  数值等价（分数/小数/百分数/根号/π）
    L4 sympy    符号等价（化简差为 0；等价方程按比例判定）
    L5 llm      语义兜底（开放题，如「用自己的话说」）
    L6 fallback 判错，但反馈邀请学生重述

安全说明：parse_expr 走的是 eval 路径，所以 global_dict 只给空 builtins，
local_dict 只给白名单符号与函数；再叠一个 3 秒超时，防止病态表达式挂死。
"""

from __future__ import annotations

import math
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

try:
    import sympy
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    SYMPY_AVAILABLE = True
except Exception:  # pragma: no cover - sympy 缺失时自动降级
    sympy = None  # type: ignore[assignment]
    SYMPY_AVAILABLE = False

_OPTION_LETTER = re.compile(r"(?:^|[^A-Za-z])([A-Da-d])(?![A-Za-z])")
_PREFIX = re.compile(r"^(?:答案是|正确答案是|正确选项是|正确的是|应该选|我选|答案|选|答)\s*[:：]?\s*")
_TRAILING = "。．.，,；;：:！!？?、 \t\n"
_LATEX_WRAPPERS = ("\\left", "\\right", "\\,", "\\;", "\\!", "\\quad", "\\qquad", "\\displaystyle")

_SUPERSCRIPT = str.maketrans({"²": "**2", "³": "**3", "⁴": "**4"})
_SUPERSCRIPT_MULTI = {"⁻¹": "**-1", "⁻²": "**-2", "½": "(1/2)", "¼": "(1/4)"}
_UNICODE_MATH = {
    "√": "sqrt", "π": "pi", "θ": "theta", "α": "alpha", "β": "beta",
    "−": "-", "–": "-", "—": "-", "×": "*", "·": "*", "÷": "/",
    "≤": "<=", "≥": ">=", "≠": "!=", "∞": "oo", "∫": "Integral",
}


def normalize(text: str) -> str:
    """文本归一化：全半角、大小写、空白、常见符号、LaTeX 外壳、答案前缀。"""
    t = unicodedata.normalize("NFKC", str(text or ""))
    t = t.replace("$", "")
    for wrapper in _LATEX_WRAPPERS:
        t = t.replace(wrapper, "")
    t = t.replace("−", "-").replace("–", "-").replace("—", "-")
    t = t.replace("×", "*").replace("·", "*").replace("÷", "/")
    t = t.replace("＝", "=").replace("≈", "=")
    t = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\text\{([^{}]*)\}", r"\1", t)
    t = _PREFIX.sub("", t.strip())
    t = re.sub(r"\s+", "", t)
    t = t.lower()
    return t.strip(_TRAILING)


# ---------------------------------------------------------------------------
# L3 数值
# ---------------------------------------------------------------------------
def _parse_number(text: str) -> float | Fraction | None:
    t = normalize(text)
    if not t:
        return None
    while len(t) >= 2 and (t[0], t[-1]) in {("(", ")"), ("[", "]"), ("{", "}")}:
        t = t[1:-1]
    if not t:
        return None

    t = t.replace("pi", "π")
    percent = t.endswith("%")
    if percent:
        t = t[:-1]

    if "√" in t or "sqrt" in t:
        m = re.fullmatch(r"([+-]?\d*\.?\d*)(?:√|sqrt\()([+-]?\d*\.?\d*)\)?", t)
        if m:
            coeff, radicand = m.group(1), m.group(2)
            try:
                c = 1.0 if coeff in ("", "+") else float(coeff)
                r = 2.0 if radicand in ("", "+") else float(radicand)
                if r < 0:
                    return None
                value = c * math.sqrt(r)
                return value / 100 if percent else value
            except ValueError:
                return None

    if t in ("π", "-π", "2π", "-2π"):
        mult = {"π": 1.0, "-π": -1.0, "2π": 2.0, "-2π": -2.0}[t]
        return math.pi * mult

    if "=" in t:
        t = t.split("=")[-1]

    try:
        if "/" in t and t.count("/") == 1:
            num, den = t.split("/")
            value = Fraction(num) / Fraction(den)
        else:
            value = Fraction(t)
        return value / 100 if percent else value
    except (ValueError, ZeroDivisionError):
        pass

    try:
        value = float(t)
        return value / 100 if percent else value
    except ValueError:
        return None


def _numbers_equal(a: float | Fraction, b: float | Fraction) -> bool:
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return a == b
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-3, abs_tol=1e-6)
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# L4 SymPy 符号等价
# ---------------------------------------------------------------------------
_ALLOWED_NAMES = {
    "sqrt": sympy.sqrt if SYMPY_AVAILABLE else None,
    "sin": sympy.sin if SYMPY_AVAILABLE else None,
    "cos": sympy.cos if SYMPY_AVAILABLE else None,
    "tan": sympy.tan if SYMPY_AVAILABLE else None,
    "cot": sympy.cot if SYMPY_AVAILABLE else None,
    "sec": sympy.sec if SYMPY_AVAILABLE else None,
    "csc": sympy.csc if SYMPY_AVAILABLE else None,
    "asin": sympy.asin if SYMPY_AVAILABLE else None,
    "acos": sympy.acos if SYMPY_AVAILABLE else None,
    "atan": sympy.atan if SYMPY_AVAILABLE else None,
    "log": sympy.log if SYMPY_AVAILABLE else None,
    "exp": sympy.exp if SYMPY_AVAILABLE else None,
    "abs": sympy.Abs if SYMPY_AVAILABLE else None,
    "pi": sympy.pi if SYMPY_AVAILABLE else None,
    "e": sympy.E if SYMPY_AVAILABLE else None,
    "oo": sympy.oo if SYMPY_AVAILABLE else None,
    "E": sympy.E if SYMPY_AVAILABLE else None,
    "i": sympy.I if SYMPY_AVAILABLE else None,
}
_TRANSFORMS = (
    standard_transformations + (implicit_multiplication_application, convert_xor)
) if SYMPY_AVAILABLE else ()

# parse_expr 的 eval 环境：只给构造 AST 必需的几个名字，__builtins__ 清空。
# （缺 Symbol/Integer 会导致 auto_symbol 变换直接 NameError，这是踩过的坑）
_PARSE_GLOBALS: dict[str, Any] = (
    {
        "__builtins__": {},
        "Symbol": sympy.Symbol,
        "Integer": sympy.Integer,
        "Float": sympy.Float,
        "Rational": sympy.Rational,
        "Function": sympy.Function,
    }
    if SYMPY_AVAILABLE
    else {}
)

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sympy-judge")


def _latex_to_python(text: str) -> str:
    t = text
    # \frac{a}{b} → (a)/(b)
    for _ in range(3):
        t = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"((\1)/(\2))", t)
    # \sqrt[n]{x} → (x)**(1/n)；\sqrt{x} → sqrt(x)
    t = re.sub(r"\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}", r"((\2)**(1/(\1)))", t)
    t = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", t)
    t = re.sub(r"\\(sin|cos|tan|cot|sec|csc|log|ln|exp|arcsin|arccos|arctan)\b", r"\1", t)
    t = t.replace("\\pi", "pi").replace("\\cdot", "*").replace("\\times", "*")
    t = t.replace("\\infty", "oo").replace("\\left", "").replace("\\right", "")
    t = t.replace("\\", "")
    return t


def _to_python_math(text: str) -> str:
    """把学生/标答的各种写法收敛成 sympy 能 parse 的表达式。"""
    t = unicodedata.normalize("NFKC", str(text or ""))
    t = _PREFIX.sub("", t.strip())
    t = _latex_to_python(t)
    for src, dst in _SUPERSCRIPT_MULTI.items():
        t = t.replace(src, dst)
    t = t.translate(_SUPERSCRIPT)
    for src, dst in _UNICODE_MATH.items():
        t = t.replace(src, dst)
    t = t.replace("＝", "=").replace("≈", "=")
    t = re.sub(r"\bln\b", "log", t)
    t = re.sub(r"\s+", "", t)
    return t.strip(_TRAILING)


_CJK = re.compile(r"[\u4e00-\u9fff]")

# 中文答案的等价词表（考研填空最常见的那几组）
# 只做「同义书写」归一，绝不做跨概念映射：
# 「收敛/发散」「存在/不存在」是相反概念，映射到一起会把错答判成对（踩过）。
_CJK_SYNONYMS = [
    ["充要", "充分必要", "充分且必要"],
    ["0/0型", "零比零型", "0比0型"],
    ["∞/∞型", "无穷比无穷型", "无穷大比无穷大型"],
    ["单调递增", "单调增"],
    ["单调递减", "单调减"],
]


def _cjk_equivalent(student: str, answer: str) -> tuple[bool | None, str]:
    """中文答案的规则层：先做同义词归一，再做包含关系判定（不含 LLM）。"""
    a = re.sub(r"[^\u4e00-\u9fffa-zA-Z0-9/]", "", str(student or ""))
    b = re.sub(r"[^\u4e00-\u9fffa-zA-Z0-9/]", "", str(answer or ""))
    if not a or not b:
        return None, "空答案"

    def canon(text: str) -> str:
        out = text
        for group in _CJK_SYNONYMS:
            for word in group[1:]:
                out = out.replace(word, group[0])
        return out

    ca, cb = canon(a), canon(b)
    if ca == cb:
        return True, "中文答案归一后一致"
    # 注意：「存在」是「不存在」的子串，直接做包含判断会把「收敛」判成「发散」。
    # 所以包含关系只对长短语生效（≥4 字），且双方都不能带否定词。
    if "不" in ca or "不" in cb:
        return False, "中文答案含否定，不做包含判定"
    # 前后缀关系（「发散（调和级数）」vs「发散」）可以放心判等；
    # 中间包含（「存在」在「不存在」里那种）一律交给 LLM，避免误判。
    if len(ca) >= 2 and len(cb) >= 2 and abs(len(ca) - len(cb)) <= 12:
        if ca.startswith(cb) or ca.endswith(cb) or cb.startswith(ca) or cb.endswith(ca):
            return True, "中文答案前后缀一致"
    # 完全不相干的短答案（没有任何公共字）直接判错，不必等 LLM
    if len(set(ca) & set(cb)) == 0:
        return False, "中文答案无公共字，判为不一致"
    return None, "中文答案需要语义判断"


def _safe_parse(expr_text: str):
    if not SYMPY_AVAILABLE or not expr_text:
        return None
    if len(expr_text) > 200:
        return None
    local_dict: dict[str, Any] = dict(_ALLOWED_NAMES)
    for name in re.findall(r"[A-Za-z]+", expr_text):
        if name not in local_dict:
            local_dict[name] = sympy.Symbol(name)
    try:
        return parse_expr(
            expr_text,
            local_dict=local_dict,
            global_dict=dict(_PARSE_GLOBALS),
            transformations=_TRANSFORMS,
            evaluate=True,
        )
    except Exception:  # noqa: BLE001
        return None


def _equation_diff(side: str):
    """把 "lhs=rhs" 变成 lhs-rhs 的 SymPy 表达式。"""
    parts = side.split("=")
    if len(parts) != 2:
        return None
    x, y = _safe_parse(parts[0]), _safe_parse(parts[1])
    if x is None or y is None:
        return None
    return sympy.simplify(x - y)


def _compare_equations(left: str, right: str, eq_a: bool, eq_b: bool) -> tuple[bool | None, str]:
    d1 = _equation_diff(left) if eq_a else _safe_parse(left)
    d2 = _equation_diff(right) if eq_b else _safe_parse(right)
    if d1 is None or d2 is None:
        return None, "方程解析失败"

    if eq_a and eq_b:
        if d1 == 0 and d2 == 0:
            return True, "两侧方程恒等"
        if d1 == 0 or d2 == 0:
            return False, "零解与非零解不等价"
        ratio = sympy.simplify(d1 / d2)
        if ratio.is_number and ratio != 0:
            return True, f"等价方程（相差常数倍 {ratio}）"
        return False, "方程不等价"

    # 一侧是方程、一侧是表达式：解方程，比解与表达式的值
    equation = d1 if eq_a else d2
    plain_text = right if eq_a else left
    plain = _safe_parse(plain_text)
    if plain is None:
        return None, "表达式解析失败"
    symbols = sorted(equation.free_symbols, key=str)
    if len(symbols) != 1:
        return False, "无法确定方程变量"
    try:
        solutions = sympy.solve(equation, symbols[0])
    except Exception:  # noqa: BLE001
        return None, "方程求解失败"
    if not solutions:
        return False, "方程无解"
    for sol in solutions:
        try:
            if sympy.simplify(sol - plain) == 0:
                return True, f"方程的解等于学生答案（{sympy.sstr(sol)}）"
        except Exception:  # noqa: BLE001
            continue
    return False, "方程的解与学生答案不一致"


def _compare_exprs(left: str, right: str) -> tuple[bool | None, str]:
    """核心比较：表达式差化简为 0，或等价方程按常数比例判定。"""
    eq_a, eq_b = "=" in left, "=" in right
    if eq_a or eq_b:
        return _compare_equations(left, right, eq_a, eq_b)

    a, b = _safe_parse(left), _safe_parse(right)
    if a is None or b is None:
        return None, "表达式无法解析"

    try:
        diff = sympy.simplify(a - b)
    except Exception:  # noqa: BLE001
        return None, "化简失败"

    if diff == 0:
        return True, "化简后差为 0"
    if diff.is_number:
        try:
            if abs(complex(diff.evalf())) < 1e-9:
                return True, "数值差为 0"
        except (TypeError, ValueError):
            pass
    # 采样法兜底：simplify 卡在形式上，但数值上处处相等
    try:
        if a.equals(b):
            return True, "抽样验证等价"
    except Exception:  # noqa: BLE001
        pass
    return False, "化简后不等价"


def sympy_equivalent(student: str, answer: str, timeout: float = 3.0) -> tuple[bool | None, str]:
    """带超时的符号等价判定；返回 None 表示判不了（交给下一层）。"""
    if not SYMPY_AVAILABLE:
        return None, "sympy 不可用"

    # 中文答案（“用自己的话说”）不是符号表达式，交给 LLM 层
    if _CJK.search(str(student) or "") or _CJK.search(str(answer) or ""):
        return None, "含自然语言，交给语义层"

    left = _to_python_math(student)
    right = _to_python_math(answer)
    if not left or not right:
        return None, "空表达式"

    # 纯数字：数值层已经判过相等，到这里说明不等；直接给结论，省一次化简。
    # 但方程（"2x=6"）不能走这条路——拆等号只取右端会得出错误的数。
    if "=" not in left and "=" not in right:
        num_left, num_right = _parse_number(student), _parse_number(answer)
        if num_left is not None and num_right is not None:
            if _numbers_equal(num_left, num_right):
                return True, "数值相等"
            return False, "数值不等"

    try:
        future = _EXECUTOR.submit(_compare_exprs, left, right)
        return future.result(timeout=timeout)
    except FuturesTimeout:
        return None, f"sympy 判定超时（>{timeout}s）"
    except Exception as exc:  # noqa: BLE001
        return None, f"sympy 异常：{type(exc).__name__}"


# ---------------------------------------------------------------------------
# L1 选项
# ---------------------------------------------------------------------------
def extract_choice_letter(text: str, options: list[str] | None = None) -> str | None:
    raw = str(text or "")
    match = _OPTION_LETTER.search(raw)
    if match:
        return match.group(1).upper()
    if options:
        norm = normalize(raw)
        for index, option in enumerate(options):
            if norm and norm == normalize(option):
                return chr(65 + index)
    return None


@dataclass
class Judgement:
    correct: bool
    layer: str
    normalized_student: str
    normalized_answer: str
    feedback: str
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "correct": self.correct,
            "layer": self.layer,
            "student_normalized": self.normalized_student,
            "answer_normalized": self.normalized_answer,
            "reason": self.reason,
        }


_LLM_JUDGE_SYSTEM = """你是数学判题助手。判断学生的答案与标准答案在数学上是否等价。
只输出 JSON：{"equivalent": true/false, "reason": "不超过 30 字的理由"}。
等价包括：同一数值的不同写法、同一表达式等价变形、带或不带变量名（如 x=3 与 3）、
分数小数百分数互化、等价方程（如 2x=6 与 x=3）。不要求书写格式一致。"""


def _llm_equivalent(client, question: str, answer: str, student: str) -> tuple[bool, str]:
    messages = [
        {"role": "system", "content": _LLM_JUDGE_SYSTEM},
        {"role": "user", "content": f"题目：{question}\n标准答案：{answer}\n学生答案：{student}"},
    ]
    try:
        raw, _usage, _latency = client.chat_json(messages, temperature=0.0, max_tokens=200)
    except Exception as exc:  # noqa: BLE001
        return False, f"LLM 判题失败：{type(exc).__name__}"

    import json

    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return False, "LLM 返回非 JSON"
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return False, "LLM 返回 JSON 解析失败"
    return bool(payload.get("equivalent")), str(payload.get("reason", ""))[:60]


def _field(question, name: str, default=None):
    """同时支持 pydantic 模型与 dict（图里存的是 dict）。"""
    if isinstance(question, dict):
        return question.get(name, default)
    return getattr(question, name, default)


def judge(
    question,
    answer: str,
    *,
    client=None,
    allow_llm: bool = True,
    allow_sympy: bool = True,
    sympy_timeout: float = 3.0,
    answer_key: str | None = None,
) -> Judgement:
    """分层判定。`question` 可以是 QuizQuestion / QuestionCard，也可以是等价 dict。

    `answer_key` 是独立答案键：传入时优先于 `question["answer"]`。
    这样题库/验证器可以给标准答案，不必相信模型生成题卡里的 answer。
    """
    student_raw = str(answer or "")
    student_norm = normalize(student_raw)
    key_text = str(answer_key if answer_key is not None else _field(question, "answer", "") or "")
    answer_norm = normalize(key_text)
    options = list(_field(question, "options", []) or [])

    # L1 选择题
    if _field(question, "kind", "") == "choice":
        expected = extract_choice_letter(key_text, options)
        got = extract_choice_letter(student_raw, options)
        if expected and got:
            return Judgement(got == expected, "choice", got, expected, "", f"选择题 {got} vs {expected}")

    # L2 归一化文本
    if student_norm and student_norm == answer_norm:
        return Judgement(True, "text", student_norm, answer_norm, "", "归一化后完全一致")

    # L3 数值（方程形如 "x=3" 不在这里处理，交给 L4）
    if "=" not in student_norm and "=" not in answer_norm:
        a, b = _parse_number(student_raw), _parse_number(key_text)
        if a is not None and b is not None and _numbers_equal(a, b):
            return Judgement(True, "numeric", student_norm, answer_norm, "", f"数值等价：{a} ≈ {b}")

    # L4 SymPy 符号等价
    if allow_sympy:
        equivalent, detail = sympy_equivalent(student_raw, key_text, timeout=sympy_timeout)
        if equivalent is True:
            return Judgement(True, "sympy", student_norm, answer_norm, "", detail)
        if equivalent is False:
            # 符号层明确判不等的，直接返回，不再浪费一次 LLM 调用
            return Judgement(False, "sympy", student_norm, answer_norm, "", detail)

    # L4.5 中文答案（填空常见：发散/不存在、充分/必要）
    if _CJK.search(student_raw) or _CJK.search(key_text):
        cjk_ok, cjk_detail = _cjk_equivalent(student_raw, key_text)
        if cjk_ok is True:
            return Judgement(True, "cjk", student_norm, answer_norm, "", cjk_detail)
        if cjk_ok is False:
            # 规则层给出确定的「不等」就直接返回，不再花 2~4 秒等 LLM（红队 P1-2 的延迟代价）
            return Judgement(False, "cjk", student_norm, answer_norm, "", cjk_detail)

    # L5 LLM 语义兜底
    if allow_llm and client is not None and len(student_norm) >= 2:
        equivalent, reason = _llm_equivalent(
            client, str(_field(question, "stem", "") or ""), key_text, student_raw
        )
        if equivalent:
            return Judgement(True, "llm", student_norm, answer_norm, "", reason)
        return Judgement(False, "llm", student_norm, answer_norm, "", reason)

    return Judgement(False, "fallback", student_norm, answer_norm, "", "未命中任何判定层")
