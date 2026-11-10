"""知识点包 + 独立题库。

为什么答案键不放在题卡里？
- 题卡是 LLM 生成的，`answer` 可能是错的；
- 判题器如果拿题卡的 answer 当标准，就是「自己判自己」；
- 所以这里维护一份独立 `ANSWER_KEYS`，判题只认它。

真实项目里这份数据来自 `textbook/tree/*.json` + 例题库；
starter_kit 只放 3 个知识点，方便读完。
"""

from __future__ import annotations

from contracts import AnswerKey, KpPack, QuestionCard

KP_PACKS: dict[str, KpPack] = {
    "der.basic": KpPack(
        kp_id="der.basic",
        name="导数的定义与几何意义",
        points=[
            "导数是「瞬时变化率」，不是「整段平均变化率」。",
            "几何上，f'(x0) 是曲线在 x0 处切线的斜率。",
            "求导可以先算差商，再让 Δx 趋于 0。",
        ],
        example="一辆车 2 分钟走了 1 公里，平均速度是 0.5 公里/分钟；速度表指针指的是某一刻的瞬时速度，那才是导数。",
        misconceptions=[
            "把平均速度当成瞬时速度。",
            "以为 f'(2) 就是把 x=2 代进 f(x)。",
        ],
    ),
    "lim.lhopital": KpPack(
        kp_id="lim.lhopital",
        name="洛必达法则",
        points=[
            "只适用于 0/0 或 ∞/∞ 型未定式。",
            "分子分母分别求导，再求极限。",
            "求导后如果还是未定式，可以再用一次；但每次都要先验证条件。",
        ],
        example="lim(x→0) sin x / x 是 0/0 型，分子分母分别求导得 cos x / 1，代入 x=0 得 1。",
        misconceptions=[
            "对 1/0 这种「不是未定式」的极限也用洛必达。",
            "把「分子分母分别求导」写成「整个分式求导」。",
        ],
    ),
    "int.basic": KpPack(
        kp_id="int.basic",
        name="不定积分基本公式",
        points=[
            "不定积分是求导的逆运算，结果要加常数 C。",
            "∫x^n dx = x^(n+1)/(n+1)+C（n≠-1）。",
            "先凑基本公式，再积分；不要一上来就硬套。",
        ],
        example="∫2x dx = x² + C，因为 (x²+C)' = 2x。",
        misconceptions=[
            "忘记写 +C。",
            "把 ∫2x dx 写成 2x²/2 后不再化简。",
        ],
    ),
}

QUESTION_BANK: dict[str, list[QuestionCard]] = {
    "der.basic": [
        QuestionCard(
            id="der.q1",
            kind="choice",
            stem="设 f(x)=x²，则 f'(2) 等于多少？",
            options=["2", "4", "8", "1"],
            answer="B",
            explanation="f'(x)=2x，代入 x=2 得 4。",
            tested_points=["der.basic"],
            difficulty="easy",
            source_quote="导数是「瞬时变化率」",
            confidence="high",
        ),
        QuestionCard(
            id="der.q2",
            kind="fill",
            stem="设 f(x)=x²，则 f'(x)=？只填表达式。",
            options=[],
            answer="2x",
            explanation="用幂函数求导公式：(x²)'=2x。",
            tested_points=["der.basic"],
            difficulty="medium",
            source_quote="求导可以先算差商，再让 Δx 趋于 0",
            variant_of="der.q1",
            confidence="high",
        ),
    ],
    "lim.lhopital": [
        QuestionCard(
            id="lim.q1",
            kind="choice",
            stem="lim(x→0) sin x / x 等于多少？",
            options=["0", "1", "∞", "不存在"],
            answer="B",
            explanation="0/0 型，用洛必达：cos x / 1，代入 0 得 1。",
            tested_points=["lim.lhopital"],
            difficulty="easy",
            source_quote="只适用于 0/0 或 ∞/∞ 型未定式",
            confidence="high",
        ),
        QuestionCard(
            id="lim.q2",
            kind="fill",
            stem="lim(x→0) (eˣ-1)/x =？只填数字。",
            options=[],
            answer="1",
            explanation="0/0 型，洛必达后得 eˣ/1，代入 0 得 1；等价无穷小 eˣ-1 ~ x 也得到 1。",
            tested_points=["lim.lhopital"],
            difficulty="medium",
            source_quote="分子分母分别求导，再求极限",
            variant_of="lim.q1",
            confidence="high",
        ),
    ],
    "int.basic": [
        QuestionCard(
            id="int.q1",
            kind="fill",
            stem="∫2x dx =？只填带常数 C 的结果。",
            options=[],
            answer="x^2+C",
            explanation="2x 的原函数是 x²，所以结果是 x²+C。",
            tested_points=["int.basic"],
            difficulty="easy",
            source_quote="不定积分是求导的逆运算，结果要加常数 C",
            confidence="high",
        ),
        QuestionCard(
            id="int.q2",
            kind="choice",
            stem="∫cos x dx 等于多少？",
            options=["sin x + C", "-sin x + C", "cos x + C", "-cos x + C"],
            answer="A",
            explanation="sin x 的导数是 cos x，所以 ∫cos x dx = sin x + C。",
            tested_points=["int.basic"],
            difficulty="medium",
            source_quote="先凑基本公式，再积分",
            variant_of="int.q1",
            confidence="high",
        ),
    ],
}

ANSWER_KEYS: dict[str, AnswerKey] = {
    q.id: AnswerKey(question_id=q.id, answer=q.answer, kind=q.kind, explanation=q.explanation)
    for cards in QUESTION_BANK.values()
    for q in cards
}

DEMO_ANSWERS: dict[str, list[str]] = {
    "der.basic": ["B", "2x"],
    "lim.lhopital": ["B", "1"],
    "int.basic": ["x^2+C", "A"],
}

# 评测用例：answers 与 QUESTION_BANK 的顺序一一对应，expected 是「独立答案键」判定结果。
EVAL_CASES = [
    {"id": "der-all-correct", "kp_id": "der.basic", "answers": ["B", "2x"], "expected": [True, True]},
    {"id": "der-first-wrong", "kp_id": "der.basic", "answers": ["A", "2x"], "expected": [False, True]},
    {"id": "lim-all-correct", "kp_id": "lim.lhopital", "answers": ["B", "1"], "expected": [True, True]},
    {"id": "lim-second-wrong", "kp_id": "lim.lhopital", "answers": ["B", "0"], "expected": [True, False]},
    {"id": "int-all-correct", "kp_id": "int.basic", "answers": ["x^2+C", "A"], "expected": [True, True]},
    {"id": "int-c-no-constant", "kp_id": "int.basic", "answers": ["x^2", "A"], "expected": [False, True]},
]


def get_pack(kp_id: str) -> KpPack:
    if kp_id not in KP_PACKS:
        raise KeyError(f"未知知识点：{kp_id}，可选：{', '.join(KP_PACKS)}")
    return KP_PACKS[kp_id]


def get_questions(kp_id: str) -> list[QuestionCard]:
    return [q.model_copy(deep=True) for q in QUESTION_BANK[kp_id]]


def get_answer_key(question_id: str) -> AnswerKey:
    if question_id not in ANSWER_KEYS:
        raise KeyError(f"题号 {question_id} 没有独立答案键")
    return ANSWER_KEYS[question_id]


def all_kp_ids() -> list[str]:
    return list(KP_PACKS)
