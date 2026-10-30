from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Type, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_config
from langgraph.types import interrupt
from pydantic import BaseModel, ValidationError

from config.prompts import (
    ANSWER_EQUIVALENCE_PROMPT,
    AUDITOR_PROMPT,
    CORRECTION_PROMPT,
    DIAGNOSTIC_PROMPT,
    PRACTICE_PROMPT,
    TEACHER_PROMPT,
)
from core.llm import (
    AnswerEquivalenceOutput,
    AuditOutput,
    CorrectionOutput,
    DiagnosticPaperOutput,
    DiagnosticQuestion,
    PracticeOutput,
    TeacherOutput,
    get_llm,
)
from core.state import DEFAULT_TARGET_SCORE, MistakeEntry, TrainerState

T = TypeVar("T", bound=BaseModel)

_BENCHMARK_PAPER_CACHE: Dict[str, DiagnosticPaperOutput] = {}

VOICE_NOISE_RULES = """
【语音抗噪与数学口误还原规则】
注意：人类回答可能来自语音输入法直接转写。请具备极强的容错与语义推断能力。
1. 先根据上下文、当前问题、学习主题和数学常识，还原真实意图，再判断概念对错。
2. 不得因同音错字、断句、标点、口语重复、语气词或公式格式不规范，直接判定概念错误。
3. 常见口误示例（按上下文选择最合理解释）：
   - “跟号 / 更号 / 根号” → 根号 √
   - “X-X方 / 叉减叉方” → x - x^2
   - “可倒 / 可到” → 可导
   - “联续” → 连续
   - “基限” → 极限
   - “平房” → 平方
   - “艾克斯 / 埃克斯” → x
   - “得尔塔 / 德尔塔” → Δ
   - “倒数 / 导树 / 岛数” → 根据上下文判断是“倒数”还是“导数”
4. 如果一句话存在歧义，优先选择与当前知识点一致的解释；仍不确定时，在反馈中说明你的还原假设。
5. 只有还原后的数学逻辑仍然错误，才判定概念错误；语音格式本身不计入扣分。
6. 如果你进一步还原了学习者的口语表述，请在 instruction_response 或 feedback 的第一句友好提示：
   “（已自动将您的口语表述还原为标准公式：...）”
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _turn(agent: str, content: str, role: str = "assistant") -> Dict[str, Any]:
    return {
        "role": role,
        "agent": agent,
        "content": content,
        "timestamp": _utc_now(),
    }


def _append_history(
    state: TrainerState,
    *turns: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [*(state.get("dialogue_history") or []), *turns]


def _history_text(history: List[Dict[str, Any]], limit: int = 12) -> str:
    if not history:
        return "（暂无历史对话）"
    lines: List[str] = []
    for turn in history[-limit:]:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role", "unknown"))
        agent = str(turn.get("agent", "")).strip()
        content = str(turn.get("content", "")).strip()[:1200]
        label = f"{role}/{agent}" if agent else role
        lines.append(f"[{label}] {content}")
    return "\n".join(lines) if lines else "（暂无历史对话）"


def _mistake_book_text(mistakes: List[Dict[str, Any]], limit: int = 8) -> str:
    if not mistakes:
        return "（暂无错题）"
    lines: List[str] = []
    for index, item in enumerate(mistakes[-limit:], start=1):
        if not isinstance(item, dict):
            continue
        lines.append(
            f"{index}. 概念：{item.get('concept', '')}；"
            f"误区：{item.get('user_flaw', '')}；"
            f"正确认知：{item.get('key_insight', '')}"
        )
    return "\n".join(lines) if lines else "（暂无错题）"


def _primary_concept(state: TrainerState) -> str:
    for gap in state.get("knowledge_gaps") or []:
        if isinstance(gap, str) and gap.strip():
            return gap.strip()
    topic = (state.get("topic") or "").strip()
    return topic or "未命名主题"


def _base_context(state: TrainerState) -> str:
    gaps = "、".join(state.get("knowledge_gaps") or []) or "未明确"
    return (
        f"学习主题：{state.get('topic', '')}\n"
        f"初始基准分：{state.get('benchmark_score', 0)}\n"
        f"当前综合得分：{state.get('current_score', 0)}\n"
        f"通关目标：{state.get('target_score', DEFAULT_TARGET_SCORE)}\n"
        f"核心薄弱点：{gaps}\n"
        f"学习计划：{state.get('learning_plan', '') or '未制定'}\n"
        f"当前问题：{state.get('current_task', '') or '无'}\n"
        f"历史轮次：{state.get('iteration_count', 0)}\n"
        f"审计反馈：{state.get('audit_feedback', '') or '无'}\n"
        f"错题本：\n{_mistake_book_text(state.get('mistake_book') or [])}\n"
        f"历史对话：\n{_history_text(state.get('dialogue_history') or [])}"
    )


def _coerce_human_response(value: Any) -> str:
    if value is None:
        response = ""
    elif isinstance(value, str):
        response = value
    elif isinstance(value, dict):
        response = str(
            value.get("human_response")
            or value.get("response")
            or value.get("content")
            or ""
        )
    else:
        response = str(value)
    response = response.strip()
    if not response:
        raise ValueError("human_response must be a non-empty string")
    return response


def normalize_voice_input(text: str) -> tuple[str, List[str]]:
    """Normalize common Chinese voice-transcription math errors before LLM review."""
    normalized = text.strip()
    notes: List[str] = []

    square_pattern = re.compile(
        r"(?<![A-Za-z])([A-Za-z])\s*(?:[-−－]|减)\s*\1\s*方",
        re.IGNORECASE,
    )

    def _replace_square(match: re.Match[str]) -> str:
        variable = match.group(1)
        notes.append(f"{match.group(0)} → {variable} - {variable}^2")
        return f"{variable} - {variable}^2"

    normalized = square_pattern.sub(_replace_square, normalized)

    replacements = [
        ("跟号", "根号", "跟号 → 根号"),
        ("更号", "根号", "更号 → 根号"),
        ("可倒", "可导", "可倒 → 可导"),
        ("联续", "连续", "联续 → 连续"),
        ("基限", "极限", "基限 → 极限"),
        ("平房", "平方", "平房 → 平方"),
        ("艾克斯", "x", "艾克斯 → x"),
        ("埃克斯", "x", "埃克斯 → x"),
        ("得尔塔", "Δ", "得尔塔 → Δ"),
        ("德尔塔", "Δ", "德尔塔 → Δ"),
    ]
    for source, target, note in replacements:
        if source in normalized:
            normalized = normalized.replace(source, target)
            notes.append(note)

    return normalized, list(dict.fromkeys(notes))


def _voice_context(raw: str, normalized: str, notes: List[str]) -> str:
    if not notes:
        return ""
    return (
        "\n【系统语音清洗】\n"
        f"原始转写：{raw}\n"
        f"清洗后：{normalized}\n"
        f"已还原：{'；'.join(notes)}\n"
        "系统会在反馈前添加还原提示；请直接基于清洗后的文本判断，不要重复提示。\n"
    )


def _request_human_response(*, agent: str, question: str, instruction: str) -> str:
    resumed = interrupt(
        {
            "type": "human_input_required",
            "agent": agent,
            "question": question,
            "instruction": instruction,
        }
    )
    return _coerce_human_response(resumed)


def _invoke_structured(
    schema: Type[T],
    system_prompt: str,
    human_prompt: str,
    temperature: float = 0.3,
) -> T:
    method = os.getenv("STRUCTURED_OUTPUT_METHOD", "json_mode").strip() or "json_mode"
    if method not in {"json_mode", "function_calling", "json_schema"}:
        method = "json_mode"

    if method == "json_mode":
        schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        human_prompt = (
            f"{human_prompt}\n\n"
            "【结构化输出要求】\n"
            "只输出一个合法 JSON 对象，不要输出 Markdown 代码块、前后缀或额外解释。\n"
            "所有 string 字段必须是字符串，所有 array 字段必须是数组。\n"
            "禁止输出 null、空对象或省略必填字段。\n"
            f"JSON Schema：\n{schema_text}"
        )

    structured_llm = get_llm(temperature=temperature).with_structured_output(
        schema,
        method=method,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]
    last_error: Exception | None = None

    for attempt in range(1, 3):
        try:
            result = structured_llm.invoke(messages)
            if result is None:
                raise ValueError("structured output was null")
            if isinstance(result, schema):
                return result
            return schema.model_validate(result)
        except (OutputParserException, ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            if attempt >= 2:
                break
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=(
                        f"{human_prompt}\n\n"
                        "上一次输出为空或不是合法 JSON。请重新输出一个完整 JSON 对象；"
                        "禁止输出 null、空对象、Markdown 代码块或省略字段。"
                    )
                ),
            ]

    raise RuntimeError(
        f"structured output failed for {schema.__name__}: {last_error}"
    ) from last_error


def _benchmark_cache_key(topic: str) -> str:
    try:
        config = get_config()
        thread_id = str(config.get("configurable", {}).get("thread_id", "default"))
    except Exception:
        thread_id = "default"
    return f"{thread_id}|{topic}"


def _normalize_benchmark_paper(
    paper: DiagnosticPaperOutput,
) -> DiagnosticPaperOutput:
    standard_weights = [20, 25, 30, 25]
    questions: List[DiagnosticQuestion] = []
    for index, question in enumerate(paper.questions):
        question.id = index + 1
        question.weight = standard_weights[index]
        if question.question_type == "single_choice":
            normalized_options: List[str] = []
            for option_index, option in enumerate(question.options):
                text = str(option).strip()
                if not re.match(r"^[A-Da-d][\.\．、\)\s]", text):
                    text = f"{chr(65 + option_index)}. {text}"
                normalized_options.append(text)
            question.options = normalized_options
        else:
            question.options = []
        questions.append(question)
    paper.questions = questions
    paper.total_score = 100
    return paper


def _extract_benchmark_answers(value: Any) -> Dict[int, str]:
    if isinstance(value, dict):
        raw = value.get("benchmark_answers") or value.get("answers") or []
    elif isinstance(value, list):
        raw = value
    else:
        raw = []

    answers: Dict[int, str] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            question_id = _as_int(item.get("id"), -1)
            if question_id <= 0:
                continue
            answer = item.get("answer")
            answers[question_id] = "" if answer is None else str(answer).strip()
    return answers


def _normalize_answer_text(value: Any) -> str:
    raw = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", raw).lower()
    for token in ("$", "\\(", "\\)", "\\[", "\\]", "{", "}"):
        text = text.replace(token, "")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/")
    text = text.replace("，", ",").replace("。", ".")
    return re.sub(r"\s+", "", text)


def _resolve_choice_letter(answer: Any, options: List[str]) -> str:
    raw = "" if answer is None else str(answer)
    text = unicodedata.normalize("NFKC", raw).strip()
    if not text:
        return ""
    match = re.match(r"^([A-Da-d])(?:[\.\．、\)\s]|$)", text)
    if match:
        return match.group(1).upper()

    normalized = _normalize_answer_text(text)
    for index, option in enumerate(options):
        option_text = unicodedata.normalize("NFKC", str(option)).strip()
        stripped = re.sub(r"^[A-Da-d][\.\．、\)\s]*", "", option_text)
        if normalized in {
            _normalize_answer_text(option_text),
            _normalize_answer_text(stripped),
        }:
            return chr(65 + index)
    first = text[:1].upper()
    return first if first in "ABCD" else ""


def _is_answer_correct(question: DiagnosticQuestion, user_answer: str) -> bool:
    if question.question_type == "single_choice":
        expected = _resolve_choice_letter(question.standard_answer, question.options)
        actual = _resolve_choice_letter(user_answer, question.options)
        return bool(expected) and expected == actual

    if not str(user_answer or "").strip():
        return False
    if _normalize_answer_text(user_answer) == _normalize_answer_text(
        question.standard_answer
    ):
        return True

    try:
        result = _invoke_structured(
            AnswerEquivalenceOutput,
            ANSWER_EQUIVALENCE_PROMPT,
            (
                f"题目：{question.content}\n"
                f"标准答案：{question.standard_answer}\n"
                f"学生答案：{user_answer}\n"
                "请只判断两者是否等价。"
            ),
            temperature=0.0,
        )
        return bool(result.is_equivalent)
    except Exception:
        return False


def _grade_benchmark(
    paper: DiagnosticPaperOutput,
    answers: Dict[int, str],
) -> tuple[int, List[str], List[Dict[str, Any]]]:
    score = 0
    gaps: List[str] = []
    graded: List[Dict[str, Any]] = []
    for question in paper.questions:
        user_answer = answers.get(question.id, "")
        correct = _is_answer_correct(question, user_answer)
        if correct:
            score += question.weight
        else:
            concept = question.target_concept.strip()
            if concept and concept not in gaps:
                gaps.append(concept)
        graded.append(
            {
                "id": question.id,
                "target_concept": question.target_concept,
                "weight": question.weight,
                "standard_answer": question.standard_answer,
                "user_answer": user_answer,
                "correct": correct,
            }
        )
    return score, gaps, graded


def _build_learning_plan(gaps: List[str]) -> str:
    if not gaps:
        return "摸底全部正确。进入高难度迁移、边界条件和反例训练。"
    steps = "；".join(f"{index}. {gap}" for index, gap in enumerate(gaps, start=1))
    return f"按薄弱点顺序补强：{steps}。每个点先复述定义，再做变式与反例。"


def diagnostic_node(state: TrainerState) -> dict:
    topic = (state.get("topic") or "").strip()
    if not topic:
        raise ValueError("diagnostic_node requires a non-empty topic")

    cache_key = _benchmark_cache_key(topic)
    paper = _BENCHMARK_PAPER_CACHE.get(cache_key)
    if paper is None:
        human_prompt = f"""
学习主题：{topic}

请生成一份标准化摸底诊断卷。严格执行：
- 固定 4 题，权重依次 20/25/30/25，总分 100；
- 覆盖基础概念、典型陷阱、核心列式/计算、迁移反推；
- 至少 2 道 single_choice（每题 4 个带 A/B/C/D 前缀的选项）和 1 道 blank；
- 数学公式使用 $...$；
- 只输出 JSON，不要任何解释、教案或思考过程。
"""
        paper = _invoke_structured(
            DiagnosticPaperOutput,
            DIAGNOSTIC_PROMPT,
            human_prompt,
            temperature=0.2,
        )
        paper = _normalize_benchmark_paper(paper)
        _BENCHMARK_PAPER_CACHE[cache_key] = paper

    paper_payload = paper.model_dump()
    resume_value = interrupt(
        {
            "type": "benchmark_paper",
            "agent": "diagnostic",
            "title": paper.title,
            "total_score": paper.total_score,
            "questions": paper_payload["questions"],
            "instruction": "请完成以下摸底诊断题，提交后系统会客观判分并进入教学。",
        }
    )

    answers = _extract_benchmark_answers(resume_value)
    benchmark_score, knowledge_gaps, graded = _grade_benchmark(paper, answers)
    _BENCHMARK_PAPER_CACHE.pop(cache_key, None)

    learning_plan = _build_learning_plan(knowledge_gaps)
    gaps_text = "、".join(knowledge_gaps) if knowledge_gaps else "无"
    result_text = (
        f"摸底完成：初始测评得分 {benchmark_score}/100。\n"
        f"命中薄弱知识点：{gaps_text}。\n"
        f"学习计划：{learning_plan}"
    )
    human_response = (
        f"我已提交摸底诊断卷，初始得分 {benchmark_score}/100。"
        f"未掌握知识点：{gaps_text}。"
        "请根据这些薄弱点开始第一轮启发式教学，不要重复摸底。"
    )

    paper_state = paper.model_dump()
    paper_state["graded"] = graded

    return {
        "benchmark_score": benchmark_score,
        "benchmark_paper": paper_state,
        "current_score": benchmark_score,
        "knowledge_gaps": knowledge_gaps,
        "learning_plan": learning_plan,
        "current_task": "摸底已完成。请根据薄弱点开始第一轮启发式教学。",
        "human_response": human_response,
        "dialogue_history": _append_history(
            state,
            _turn("diagnostic", result_text),
        ),
        "audit_feedback": "",
        "next_agent": "teacher",
    }


def teacher_node(state: TrainerState) -> dict:
    raw_human_response = (state.get("human_response") or "").strip()
    if not raw_human_response:
        raw_human_response = _request_human_response(
            agent="teacher",
            question=state.get("current_task", ""),
            instruction="请回答当前问题，并写出你的推理过程。",
        )

    human_response, voice_notes = normalize_voice_input(raw_human_response)
    human_prompt = f"""
{_base_context(state)}

人类最新回答：
{human_response}
{_voice_context(raw_human_response, human_response, voice_notes)}

请依据苏格拉底提问法和费曼技巧进行启发式点拨：
- 不要直接给出最终答案；
- 指出回答中的逻辑缺口；
- 给出 instruction_response；
- 再提出一个能继续逼问或启发学习者的问题 question_to_human。
"""

    output = _invoke_structured(
        TeacherOutput,
        f"{TEACHER_PROMPT}\n\n{VOICE_NOISE_RULES}",
        human_prompt,
        temperature=0.35,
    )
    instruction_response = output.instruction_response
    if voice_notes:
        instruction_response = (
            f"（已自动将您的口语表述还原为标准公式：{'；'.join(voice_notes)}）\n"
            f"{instruction_response}"
        )
    content = f"{instruction_response}\n\n追问：{output.question_to_human}"
    human_turn_content = human_response
    if voice_notes:
        human_turn_content = (
            f"{human_response}\n\n[系统语音还原：{'；'.join(voice_notes)}]"
        )
    return {
        "human_response": "",
        "current_task": output.question_to_human,
        "dialogue_history": _append_history(
            state,
            _turn("human", human_turn_content, role="human"),
            _turn("teacher", content),
        ),
        "audit_feedback": "",
        "next_agent": "practice",
    }


def practice_node(state: TrainerState) -> dict:
    human_prompt = f"""
{_base_context(state)}

请针对当前最核心的薄弱点，生成一道“概念陷阱变式题”。
要求：
- 只出一道题；
- 不泄露答案或陷阱；
- 给出一个方向性 hint，但不能直接解题；
- 题目要检验因果、边界、反例或迁移，而不是记忆。
"""

    output = _invoke_structured(
        PracticeOutput,
        PRACTICE_PROMPT,
        human_prompt,
        temperature=0.4,
    )
    content = f"练习题：{output.practice_question}\n\n提示：{output.hint}"
    return {
        "current_task": output.practice_question,
        "human_response": "",
        "dialogue_history": _append_history(state, _turn("practice", content)),
        "next_agent": "correction",
    }


def correction_node(state: TrainerState) -> dict:
    raw_human_response = (state.get("human_response") or "").strip()
    if not raw_human_response:
        raw_human_response = _request_human_response(
            agent="correction",
            question=state.get("current_task", ""),
            instruction="请提交你对当前例题的完整作答与推理过程。",
        )

    human_response, voice_notes = normalize_voice_input(raw_human_response)
    human_prompt = f"""
{_base_context(state)}

人类对当前例题的回答：
{human_response}
{_voice_context(raw_human_response, human_response, voice_notes)}

请逐句审查并判断 is_correct。
若回答有漏洞或错误，必须给出 user_flaw、key_insight 和可执行 feedback。
若回答正确，user_flaw 和 key_insight 可以为空字符串。
"""

    output = _invoke_structured(
        CorrectionOutput,
        f"{CORRECTION_PROMPT}\n\n{VOICE_NOISE_RULES}",
        human_prompt,
        temperature=0.1,
    )
    feedback = output.feedback
    if voice_notes:
        feedback = (
            f"（已自动将您的口语表述还原为标准公式：{'；'.join(voice_notes)}）\n"
            f"{feedback}"
        )
    human_turn_content = human_response
    if voice_notes:
        human_turn_content = (
            f"{human_response}\n\n[系统语音还原：{'；'.join(voice_notes)}]"
        )
    history = _append_history(
        state,
        _turn("human", human_turn_content, role="human"),
        _turn("correction", feedback),
    )

    mistake_book = list(state.get("mistake_book") or [])
    if not output.is_correct:
        entry = MistakeEntry(
            concept=_primary_concept(state),
            user_flaw=output.user_flaw.strip()
            or "回答中存在未明确表述的思维漏洞",
            key_insight=output.key_insight.strip()
            or "需要回到定义、条件与边界重新建立因果链",
        )
        mistake_book.append(entry.model_dump())

    return {
        "mistake_book": mistake_book,
        "human_response": human_response,
        "dialogue_history": history,
        "next_agent": "auditor",
    }


def auditor_node(state: TrainerState) -> dict:
    target_score = _as_int(state.get("target_score"), DEFAULT_TARGET_SCORE)
    human_prompt = f"""
{_base_context(state)}

请综合全流程表现重新核定 current_score，并给出裁决。
硬性要求：
- 只有同时满足 new_score >= {target_score} 且 decision == "pass"，才算通过；
- 若概念仍模糊，decision 使用 "re_teach"；
- 若概念已懂但做题熟练度不足，decision 使用 "re_practice"。
"""

    output = _invoke_structured(
        AuditOutput,
        AUDITOR_PROMPT,
        human_prompt,
        temperature=0.0,
    )

    passed = output.new_score >= target_score and output.decision == "pass"
    if passed:
        decision = "pass"
        next_agent = "end"
    elif output.decision == "re_practice":
        decision = "re_practice"
        next_agent = "practice"
    else:
        decision = "re_teach"
        next_agent = "teacher"

    audit_feedback = (
        f"[得分 {output.new_score}/{target_score}｜裁决 {decision}]\n"
        f"{output.audit_feedback}"
    )
    history = _append_history(
        state,
        _turn("auditor", audit_feedback),
    )

    return {
        "current_score": output.new_score,
        "audit_feedback": audit_feedback,
        "iteration_count": _as_int(state.get("iteration_count"), 0) + 1,
        "dialogue_history": history,
        "next_agent": next_agent,
        "human_response": state.get("human_response", ""),
    }


__all__ = [
    "diagnostic_node",
    "teacher_node",
    "practice_node",
    "correction_node",
    "auditor_node",
    "normalize_voice_input",
]
