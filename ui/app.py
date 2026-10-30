from __future__ import annotations

import hashlib
import html
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from core.llm import PLACEHOLDER_API_KEY  # noqa: E402
from core.state import create_initial_state  # noqa: E402
from langgraph.types import Command  # noqa: E402

BOOT_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
BOOT_BASE_URL = (
    os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1").strip()
    or "https://api.deepseek.com/v1"
)
BOOT_MODEL = os.getenv("MODEL_NAME", "deepseek-flash").strip() or "deepseek-flash"

AGENT_LABELS = {
    "diagnostic": "测评老师",
    "teacher": "教学启发官",
    "practice": "课后例题官",
    "correction": "纠错与错题本官",
    "auditor": "终审审计官",
    "human": "你",
}

CSS = """
<style>
:root {
    --bg: #f8fafc;
    --card: #ffffff;
    --ink: #0f172a;
    --muted: #475569;
    --line: #e2e8f0;
    --accent: #2563eb;
    --accent-hover: #1d4ed8;
    --accent-soft: #dbeafe;
    --danger: #dc2626;
    --success: #16a34a;
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--ink) !important;
    color-scheme: light !important;
}
html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif !important;
}
.stApp, .stApp p, .stApp li, .stApp label,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp [data-testid="stMarkdownContainer"] *,
.stApp [data-testid="stText"] * {
    color: var(--ink) !important;
}
.stApp a { color: var(--accent) !important; }
h1, h2, h3, h4, h5, h6 {
    font-family: "Inter", "Segoe UI", "Microsoft YaHei", sans-serif !important;
    color: var(--ink) !important;
    letter-spacing: -.02em;
}
.stApp [data-testid="stCaptionContainer"] *,
.stApp .stCaption, .stApp .stCaption * {
    color: var(--muted) !important;
}

[data-testid="stSidebar"] {
    background: var(--card) !important;
    border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebar"] .stApp,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: var(--ink) !important;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] *,
[data-testid="stSidebar"] .stCaption * {
    color: var(--muted) !important;
}
[data-testid="stSidebarCollapseButton"] button { color: var(--ink) !important; }

.hero-kicker {
    color: var(--accent) !important;
    font-size: .76rem;
    font-weight: 800;
    letter-spacing: .14em;
    text-transform: uppercase;
    margin-bottom: .25rem;
}
.hero-title {
    font-family: "Inter", "Segoe UI", "Microsoft YaHei", sans-serif !important;
    font-size: clamp(1.9rem, 4vw, 2.75rem);
    font-weight: 800;
    line-height: 1.15;
    margin: .1rem 0 .7rem;
    color: var(--ink) !important;
}
.hero-sub {
    color: var(--muted) !important;
    font-size: 1rem;
    line-height: 1.8;
    max-width: 62rem;
    margin-bottom: 1.2rem;
}

.paper-card, .task-card, [data-testid="stMetric"], [data-testid="stForm"],
[data-testid="stExpander"], [data-testid="stChatMessage"] {
    background: var(--card) !important;
    border: 1px solid var(--line) !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, .04), 0 8px 24px rgba(15, 23, 42, .05) !important;
}
.paper-card {
    border-radius: 14px;
    padding: 1.15rem 1.25rem;
    min-height: 10.5rem;
}
.paper-card h3 { margin: .35rem 0 .55rem; font-size: 1.1rem; color: var(--ink) !important; }
.paper-card p { color: var(--muted) !important; line-height: 1.75; font-size: .93rem; margin: 0; }
.card-index { color: var(--accent) !important; font-size: .74rem; font-weight: 800; letter-spacing: .14em; }
.task-card {
    border-left: 5px solid var(--accent) !important;
    border-radius: 14px;
    padding: 1.2rem 1.35rem;
    margin: .8rem 0 1rem;
}
.task-question {
    font-size: 1.1rem;
    line-height: 1.8;
    margin: .35rem 0 .7rem;
    color: var(--ink) !important;
    font-weight: 600;
}
.task-instruction {
    color: var(--muted) !important;
    font-size: .9rem;
    line-height: 1.7;
    border-top: 1px dashed var(--line);
    padding-top: .7rem;
}
.sidebar-brand { font-size: 1.1rem; font-weight: 800; line-height: 1.4; margin: .3rem 0 .2rem; color: var(--ink) !important; }

.chip {
    display: inline-block;
    background: #eff6ff !important;
    color: #1d4ed8 !important;
    border: 1px solid #bfdbfe;
    border-radius: 999px;
    padding: .28rem .7rem;
    margin: .18rem .25rem .18rem 0;
    font-size: .82rem;
    line-height: 1.45;
}
.section-gap { height: .7rem; }
.voice-note {
    background: #eff6ff !important;
    border: 1px solid #bfdbfe !important;
    border-radius: 10px;
    padding: .7rem .85rem;
    margin: .5rem 0;
    color: #1e3a8a !important;
    font-size: .9rem;
    line-height: 1.6;
}
.voice-note * { color: #1e3a8a !important; }
.benchmark-result {
    background: #f0fdf4 !important;
    border: 1px solid #bbf7d0 !important;
    border-left: 5px solid #16a34a !important;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin: .6rem 0 1rem;
}
.benchmark-result * { color: #14532d !important; }
.benchmark-result .benchmark-label {
    color: #15803d !important;
    font-size: .78rem;
    font-weight: 800;
    letter-spacing: .1em;
    text-transform: uppercase;
}
.benchmark-result .benchmark-score {
    color: #0f172a !important;
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.2;
    margin: .2rem 0 .5rem;
}
.benchmark-result .benchmark-score span {
    color: #475569 !important;
    font-size: 1rem;
}
.benchmark-result .chip {
    background: #dcfce7 !important;
    color: #166534 !important;
    border-color: #86efac !important;
}

input, textarea, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
    color: var(--ink) !important;
    background-color: var(--card) !important;
    caret-color: var(--ink) !important;
}
input::placeholder, textarea::placeholder { color: #94a3b8 !important; }
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
    background-color: var(--card) !important;
    border-color: var(--line) !important;
}
[data-baseweb="select"] *, [data-baseweb="popover"] *, [data-baseweb="menu"] * {
    color: var(--ink) !important;
    background-color: var(--card) !important;
}
.stApp label, .stApp [data-testid="stWidgetLabel"] *,
.stApp [data-testid="stWidgetLabel"] { color: var(--ink) !important; }

[data-testid="stMetric"] { border-radius: 12px; padding: .7rem .9rem; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { color: var(--muted) !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { color: var(--ink) !important; }
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * { color: var(--success) !important; }

[data-testid="stProgress"] > div > div > div > div { background: var(--accent) !important; }
[data-testid="stProgress"] * { color: var(--muted) !important; }

.stButton > button, [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {
    background: var(--card) !important;
    color: var(--ink) !important;
    border: 1px solid var(--line) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}
.stButton > button:hover, [data-testid="stDownloadButton"] button:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}
[data-testid="stBaseButton-primary"] {
    background: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    font-weight: 700 !important;
}
.stApp [data-testid="stBaseButton-primary"] *,
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span {
    color: #ffffff !important;
}
[data-testid="stBaseButton-primary"]:hover { background: var(--accent-hover) !important; }

[data-testid="stChatMessage"] { border-radius: 12px !important; padding: .8rem 1rem !important; margin-bottom: .6rem; }
[data-testid="stChatMessage"] * { color: var(--ink) !important; }
[data-testid="stChatMessage"] [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }

[data-testid="stExpander"] { border-radius: 12px !important; overflow: hidden; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: var(--ink) !important; font-weight: 600; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] * { color: var(--ink) !important; }
[data-testid="stExpander"] [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }

[data-testid="stAlert"] { border-radius: 10px !important; border: 1px solid var(--line) !important; }
[data-testid="stAlert"] *, [data-testid="stAlert"] p { color: var(--ink) !important; }
[data-testid="stAudioInput"] * { color: var(--ink) !important; }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stHeader"] * { color: var(--ink) !important; }

code, pre { background: #f1f5f9 !important; color: var(--ink) !important; }
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stToolbar"] { visibility: hidden !important; height: 0 !important; }
[data-testid="stDecoration"] { display: none !important; }
</style>
"""

st.set_page_config(
    page_title="AI 反向人类特训系统",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def load_engine():
    from core.graph import MAX_CYCLES, app

    return app, MAX_CYCLES


@st.cache_resource(show_spinner=False)
def load_whisper_model():
    from faster_whisper import WhisperModel

    model_size = os.getenv("WHISPER_MODEL", "base").strip() or "base"
    local_only = os.getenv("WHISPER_LOCAL_ONLY", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    return WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        local_files_only=local_only,
    )


def _to_simplified(text: str) -> str:
    try:
        import zhconv

        return zhconv.convert(text, "zh-cn")
    except Exception:
        return text


def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    if not audio_bytes:
        raise ValueError("empty audio payload")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            handle.write(audio_bytes)
            temp_path = Path(handle.name)

        model = load_whisper_model()
        segments, _info = model.transcribe(
            str(temp_path),
            language="zh",
            beam_size=5,
            vad_filter=True,
            initial_prompt="以下是普通话数学课堂的口语回答，请用简体中文转写。",
            condition_on_previous_text=False,
        )
        transcript = "".join(segment.text for segment in segments).strip()
        return _to_simplified(transcript)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def init_session_state() -> None:
    defaults = {
        "graph_state": None,
        "thread_id": None,
        "started": False,
        "celebrated": False,
        "form_epoch": 0,
        "session_epoch": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _html_text(value: Any) -> str:
    return html.escape(str(value or "")).replace("\n", "<br>")


def _shorten(text: Any, limit: int = 64) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _agent_label(agent: Any) -> str:
    return AGENT_LABELS.get(str(agent or ""), "系统")


def _last_assistant_agent(history: List[Dict[str, Any]]) -> str:
    for turn in reversed(history):
        if turn.get("role") == "assistant" and turn.get("agent"):
            return str(turn.get("agent"))
    return ""


def _agent_for_interrupt(state: Dict[str, Any], payload: Dict[str, Any]) -> str:
    last_agent = _last_assistant_agent(state.get("dialogue_history") or [])
    if last_agent == "diagnostic":
        return "测评老师"
    if last_agent == "practice":
        return "课后例题官"
    if last_agent == "teacher":
        return "教学启发官"
    if last_agent == "auditor":
        return "教学启发官" if payload.get("agent") == "teacher" else "课后例题官"
    if payload.get("agent") == "teacher":
        return "教学启发官"
    if payload.get("agent") == "correction":
        return "课后例题官"
    return _agent_label(payload.get("agent"))


def _extract_interrupt(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    items = state.get("__interrupt__") or []
    if isinstance(items, dict):
        items = [items]
    if not items:
        return None
    first = items[0]
    value = getattr(first, "value", first)
    if isinstance(value, dict):
        return value
    return {
        "agent": "teacher",
        "question": str(value),
        "instruction": "请回答当前问题，并写出你的推理过程。",
    }


def _is_passed(state: Dict[str, Any]) -> bool:
    current = _as_int(state.get("current_score"), 0)
    target = _as_int(state.get("target_score"), 90)
    return current >= target


def _has_valid_key() -> bool:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(key and key != PLACEHOLDER_API_KEY)


def _mask_key(key: str) -> str:
    key = key.strip()
    if not key:
        return "未配置"
    if key == PLACEHOLDER_API_KEY:
        return "占位符未替换"
    if len(key) <= 10:
        return "已配置"
    return f"{key[:7]}...{key[-4:]}"


def _format_timestamp(value: Any) -> str:
    if not value:
        return "未知时间"
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return text


def _target_score_from_env() -> int:
    raw = os.getenv("TARGET_SCORE", "90")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 90
    return value if 0 <= value <= 100 else 90


def _interrupt_widget_key(state: Dict[str, Any], payload: Dict[str, Any]) -> str:
    source = "|".join(
        [
            str(st.session_state.get("session_epoch", 0)),
            str(payload.get("agent", "")),
            str(payload.get("question", "")),
            str(state.get("iteration_count", 0)),
        ]
    )
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    return f"answer_{digest}"


def _reset_session() -> None:
    st.session_state["graph_state"] = None
    st.session_state["thread_id"] = None
    st.session_state["started"] = False
    st.session_state["celebrated"] = False
    st.session_state["form_epoch"] = _as_int(st.session_state.get("form_epoch"), 0) + 1
    st.session_state["session_epoch"] = _as_int(st.session_state.get("session_epoch"), 0) + 1
    st.session_state.pop("last_audio_digest", None)
    st.session_state.pop("last_transcript", None)
    st.rerun()


def _start_training(topic: str, app: Any) -> None:
    if not _has_valid_key():
        st.error("请先在左侧「API 配置」中填入有效的 API Key。")
        return

    thread_id = f"trainer-{uuid.uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}
    target_score = _target_score_from_env()

    with st.spinner("测评老师正在摸底诊断，请稍候..."):
        try:
            state = app.invoke(
                create_initial_state(topic, target_score=target_score),
                config=config,
            )
        except Exception as exc:
            st.error(f"启动失败：{exc}")
            with st.expander("查看技术详情", expanded=False):
                st.exception(exc)
            return

    st.session_state["thread_id"] = thread_id
    st.session_state["graph_state"] = state
    st.session_state["started"] = True
    st.session_state["celebrated"] = False
    st.rerun()


def _resume(answer: Any, app: Any) -> None:
    state = st.session_state.get("graph_state")
    thread_id = st.session_state.get("thread_id")
    if not state or not thread_id:
        st.error("会话状态已丢失，请点击左侧「重置当前训练」重新开始。")
        return

    config = {"configurable": {"thread_id": thread_id}}
    with st.spinner("Agent 正在批阅、追问并推进，请稍候..."):
        try:
            new_state = app.invoke(Command(resume=answer), config=config)
        except Exception as exc:
            st.error(f"本轮推进失败：{exc}")
            with st.expander("查看技术详情", expanded=False):
                st.exception(exc)
            st.caption("如果连续失败，请点击侧边栏的「重置当前训练」重新开始。")
            return

    st.session_state["graph_state"] = new_state
    st.session_state.pop("last_audio_digest", None)
    st.session_state.pop("last_transcript", None)
    st.rerun()


def render_sidebar(state: Dict[str, Any], max_cycles: int) -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-brand">AI 反向人类特训系统</div>', unsafe_allow_html=True)
        st.caption("90 分通关制 · 苏格拉底式反向特训")

        with st.expander("API 配置", expanded=not _has_valid_key()):
            current_key = os.getenv("OPENAI_API_KEY", "").strip()
            override_key = str(st.session_state.get("ui_api_key", "")).strip()
            if override_key:
                st.info(f"当前生效：{_mask_key(override_key)}（界面临时覆盖）")
            elif _has_valid_key():
                st.success(f"已从 .env 读取：{_mask_key(current_key)}")
            else:
                st.warning("未检测到有效 API Key")

            ui_key = st.text_input(
                "临时 API Key",
                type="password",
                key="ui_api_key",
                placeholder="sk-...",
            )
            if ui_key.strip():
                os.environ["OPENAI_API_KEY"] = ui_key.strip()
                st.caption("已在当前进程临时生效，不写回 .env。")
            elif BOOT_API_KEY:
                os.environ["OPENAI_API_KEY"] = BOOT_API_KEY

            base_url = st.text_input(
                "Base URL",
                value=BOOT_BASE_URL,
                key="ui_base_url",
            )
            os.environ["OPENAI_BASE_URL"] = base_url.strip() or BOOT_BASE_URL

            model_options = ["deepseek-flash", "deepseek-v4-pro"]
            if BOOT_MODEL not in model_options:
                model_options.append(BOOT_MODEL)
            default_index = model_options.index(BOOT_MODEL) if BOOT_MODEL in model_options else 0
            model = st.selectbox(
                "模型",
                model_options,
                index=default_index,
                key="ui_model",
            )
            os.environ["MODEL_NAME"] = model
            structured_method = (
                os.getenv("STRUCTURED_OUTPUT_METHOD", "json_mode").strip()
                or "json_mode"
            )
            st.caption(f"结构化输出：{structured_method}，兼容 DeepSeek 思考模型。")

        st.divider()
        st.markdown("### 薄弱知识点")
        gaps = state.get("knowledge_gaps") or []
        if gaps:
            chips = "".join(
                f'<span class="chip">{html.escape(str(gap))}</span>'
                for gap in gaps
            )
            st.markdown(chips, unsafe_allow_html=True)
        else:
            st.caption("完成摸底后显示。")

        st.divider()
        st.markdown("### 思维库与错题本")
        mistakes = state.get("mistake_book") or []
        if not mistakes:
            st.caption("答错后自动收录，形成你的思维模型库。")
        else:
            st.caption(f"已收录 {len(mistakes)} 条")
            for index, item in enumerate(reversed(mistakes), start=1):
                if not isinstance(item, dict):
                    continue
                concept = _shorten(item.get("concept", "未命名概念"), 42)
                with st.expander(f"{index}. {concept}", expanded=False):
                    st.markdown(f"**涉及概念**\n\n{item.get('concept', '')}")
                    st.markdown(f"**🔴 错误思维**\n\n{item.get('user_flaw', '')}")
                    st.markdown(f"**🟢 核心认知**\n\n{item.get('key_insight', '')}")
                    st.caption(f"收录时间：{_format_timestamp(item.get('timestamp'))}")

        st.divider()
        st.caption(f"最大循环轮次：{max_cycles}")
        if st.session_state.get("started"):
            if st.button("重置当前训练", use_container_width=True):
                _reset_session()


def render_landing(app: Any) -> None:
    st.markdown(
        """
        <div class="hero-kicker">AI 反向人类特训系统 · 90 分通关制</div>
        <div class="hero-title">把“听懂了”逼成“真的会”</div>
        <p class="hero-sub">
            五个智能体组成闭环：测评老师摸底，教学启发官追问，
            课后例题官设置概念陷阱，纠错官沉淀错题本，审计官守住 90 分门槛。
        </p>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class="paper-card">
                <div class="card-index">01 · DIAGNOSE</div>
                <h3>先诊断，不装懂</h3>
                <p>用梯度题定位真实水平，找出最影响通关的薄弱点，而不是从头到尾平均用力。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div class="paper-card">
                <div class="card-index">02 · INQUIRE</div>
                <h3>被追问，才长出逻辑</h3>
                <p>教学启发官只提问、不给答案，用生活类比和反例逼你用自己的话讲清因果。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            """
            <div class="paper-card">
                <div class="card-index">03 · AUDIT</div>
                <h3>90 分才放行</h3>
                <p>概念、推理、边界、迁移、修正五维审计；没有证据的能力，一律按未掌握处理。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

    if not _has_valid_key():
        st.warning("API Key 尚未配置。请在左侧「API 配置」填写，或在 .env 中设置 OPENAI_API_KEY。")

    with st.form("start_training_form"):
        topic = st.text_input(
            "学习主题",
            key=f"start_topic_{st.session_state.get('form_epoch', 0)}",
            placeholder="例如：高等数学：拉格朗日中值定理 / Python：元类与反射机制",
        )
        submitted = st.form_submit_button(
            "🚀 开启特训",
            type="primary",
            use_container_width=True,
        )

    st.caption("点击开始后，测评老师会先摸底；随后系统会挂起，等待你的第一轮回答。")

    if submitted:
        if not topic.strip():
            st.warning("请先输入学习主题。")
        elif not _has_valid_key():
            st.error("请先在左侧配置有效的 API Key。")
        else:
            _start_training(topic.strip(), app)


def render_status_bar(state: Dict[str, Any], max_cycles: int) -> None:
    topic = str(state.get("topic", "未命名主题"))
    current = _as_int(state.get("current_score"), 0)
    target = max(1, _as_int(state.get("target_score"), 90))
    benchmark = _as_int(state.get("benchmark_score"), 0)
    iteration = _as_int(state.get("iteration_count"), 0)

    st.markdown(
        f"""
        <div class="hero-kicker">AI 反向人类特训系统 · 90 分通关制</div>
        <div class="hero-title">{html.escape(topic)}</div>
        """,
        unsafe_allow_html=True,
    )

    ratio = min(max(current / target, 0.0), 1.0)
    st.progress(ratio, text=f"通关进度 {current} / {target} 分")

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric(
        "当前得分",
        str(current),
        delta=f"{current - benchmark:+d} vs 初始基准",
    )
    metric2.metric("初始基准分", str(benchmark))
    metric3.metric("循环轮次", f"{iteration} / {max_cycles}")


def render_benchmark_result(state: Dict[str, Any]) -> None:
    paper = state.get("benchmark_paper") or {}
    if not paper or not state.get("learning_plan"):
        return

    score = _as_int(state.get("benchmark_score"), 0)
    gaps = state.get("knowledge_gaps") or []
    chips = "".join(
        f'<span class="chip">{html.escape(str(gap))}</span>' for gap in gaps
    ) or '<span class="chip">未命中薄弱点</span>'

    st.markdown(
        f"""
        <div class="benchmark-result">
            <div class="benchmark-label">摸底诊断完成 · 初始测评</div>
            <div class="benchmark-score">{score} <span>/ 100</span></div>
            <div class="benchmark-label">命中薄弱知识点</div>
            <div>{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_turns(turns: List[Dict[str, Any]]) -> None:
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role", "assistant"))
        content = str(turn.get("content", "")).strip()
        if not content:
            continue
        timestamp = _format_timestamp(turn.get("timestamp"))
        if role == "human":
            with st.chat_message("user", avatar="🧑‍💻"):
                st.caption(f"你 · {timestamp}")
                st.markdown(content)
        else:
            with st.chat_message("assistant", avatar="🎓"):
                st.caption(f"{_agent_label(turn.get('agent'))} · {timestamp}")
                st.markdown(content)


def render_chat_history(state: Dict[str, Any]) -> None:
    history = [
        turn
        for turn in (state.get("dialogue_history") or [])
        if isinstance(turn, dict)
    ]
    if not history:
        return

    st.markdown("### 对话流")
    older = history[:-8]
    recent = history[-8:]
    if older:
        with st.expander(f"查看更早的 {len(older)} 条对话", expanded=False):
            _render_turns(older)
    _render_turns(recent)


def render_benchmark_paper(
    state: Dict[str, Any],
    payload: Dict[str, Any],
    app: Any,
) -> None:
    questions = payload.get("questions") or []
    if not questions:
        st.error("摸底试卷生成失败，请重置后重试。")
        return

    title = str(payload.get("title") or "摸底诊断卷")
    total_score = _as_int(payload.get("total_score"), 100)
    st.markdown(
        f"""
        <div class="paper-card">
            <div class="hero-kicker">标准化摸底诊断</div>
            <div class="hero-title" style="font-size:1.65rem;">{html.escape(title)}</div>
            <p class="hero-sub" style="margin-bottom:.15rem;">
                共 {len(questions)} 题 · 满分 {total_score} 分 · 提交后客观判卷
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("请完成全部题目后提交；系统会按每题权重真实计分，不估算、不虚报。")

    paper_key = hashlib.sha1(
        (
            f"{st.session_state.get('thread_id', '')}|"
            f"{title}|"
            f"{st.session_state.get('session_epoch', 0)}"
        ).encode("utf-8")
    ).hexdigest()[:12]

    answers: Dict[int, str] = {}
    with st.form(f"benchmark_form_{paper_key}"):
        for index, question in enumerate(questions):
            if not isinstance(question, dict):
                continue
            question_id = _as_int(question.get("id"), 0)
            question_type = str(question.get("question_type", "blank"))
            concept = str(question.get("target_concept", ""))
            weight = _as_int(question.get("weight"), 0)
            content = str(question.get("content", ""))

            st.markdown(
                f"**第 {question_id} 题** · {concept} · **{weight} 分**"
            )
            st.markdown(content)

            if question_type == "single_choice":
                options = [
                    str(option)
                    for option in (question.get("options") or [])
                ]
                selected = st.radio(
                    "选择答案",
                    options,
                    index=None,
                    key=f"bench_{paper_key}_{question_id}",
                    label_visibility="collapsed",
                )
                answers[question_id] = selected or ""
            else:
                answers[question_id] = st.text_input(
                    "你的答案",
                    key=f"bench_{paper_key}_{question_id}",
                    placeholder="填写数值、表达式或关键词",
                    label_visibility="collapsed",
                )

            if index < len(questions) - 1:
                st.divider()

        submitted = st.form_submit_button(
            "📝 提交摸底卷",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        missing = [
            str(question_id)
            for question_id, answer in answers.items()
            if not str(answer).strip()
        ]
        if missing:
            st.warning(f"还有第 {', '.join(missing)} 题未作答，请完成后再提交。")
            return

        answer_payload = [
            {"id": question_id, "answer": answer}
            for question_id, answer in answers.items()
        ]
        _resume({"benchmark_answers": answer_payload}, app)


def render_interrupt(
    state: Dict[str, Any],
    payload: Dict[str, Any],
    app: Any,
) -> None:
    if payload.get("type") == "benchmark_paper":
        render_benchmark_paper(state, payload, app)
        return

    question = payload.get("question") or state.get("current_task") or "请回答当前问题。"
    instruction = (
        payload.get("instruction")
        or "请写出你的推理过程，不只写结论。"
    )
    agent_label = _agent_for_interrupt(state, payload)
    iteration = _as_int(state.get("iteration_count"), 0)

    st.markdown(
        f"""
        <div class="task-card">
            <div class="hero-kicker">{html.escape(agent_label)} · 等待你的思考</div>
            <div class="task-question">{_html_text(question)}</div>
            <div class="task-instruction">{_html_text(instruction)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"第 {iteration + 1} 轮 · 系统已挂起，提交后自动恢复工作流")

    answer_key = _interrupt_widget_key(state, payload)

    st.markdown("#### 🎙️ 语音作答（可选）")
    if hasattr(st, "audio_input"):
        audio_value = st.audio_input(
            "🎙️ 点击按住直接语音作答（可选）",
            key=f"audio_{answer_key}",
        )
    else:
        audio_value = None
        st.caption("当前 Streamlit 版本不支持录音，请直接使用文字作答。")

    if audio_value is not None:
        audio_bytes = audio_value.getvalue()
        digest = hashlib.sha1(
            answer_key.encode("utf-8") + audio_bytes
        ).hexdigest()
        if st.session_state.get("last_audio_digest") != digest:
            with st.spinner("正在离线转写语音，请稍候..."):
                try:
                    transcript = transcribe_audio_bytes(audio_bytes)
                except Exception as exc:
                    transcript = ""
                    st.error(f"语音转写失败：{exc}")
                    st.caption(
                        "若本地没有 Whisper 模型，可设置 WHISPER_LOCAL_ONLY=0 "
                        "允许自动下载，或直接使用文字作答。"
                    )
            st.session_state["last_audio_digest"] = digest
            st.session_state["last_transcript"] = transcript
            if transcript:
                st.session_state[answer_key] = transcript
            else:
                st.warning("没有识别到有效语音，请重录或直接输入文字。")

        transcript = st.session_state.get("last_transcript", "")
        if transcript:
            st.markdown(
                f'<div class="voice-note">🎙️ 语音转写：{html.escape(transcript)}<br>'
                '<span>识别可能有误，请在下方确认或修改后提交。</span></div>',
                unsafe_allow_html=True,
            )

    st.caption(
        "首次使用请允许浏览器访问麦克风；录音结束后会自动离线转写并填入下方输入框，"
        "也可以直接打字作答。"
    )

    with st.form(f"answer_form_{answer_key}"):
        answer = st.text_area(
            "你的思考与解答",
            key=answer_key,
            height=180,
            placeholder="写出你的推理过程、条件、反例……",
        )
        submitted = st.form_submit_button(
            "💡 提交我的思考与解答",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not answer.strip():
            st.warning("请先写下你的思考，再提交。")
        elif not _has_valid_key():
            st.error("请先在左侧「API 配置」中填入有效的 API Key。")
        else:
            _resume(answer.strip(), app)


def _render_report(state: Dict[str, Any]) -> None:
    st.markdown("### 训练档案")

    with st.expander("学习计划", expanded=True):
        st.markdown(state.get("learning_plan") or "未生成学习计划。")

    with st.expander("薄弱知识点", expanded=False):
        gaps = state.get("knowledge_gaps") or []
        if gaps:
            for gap in gaps:
                st.markdown(f"- {gap}")
        else:
            st.caption("无记录")

    with st.expander("错题本与思维模型", expanded=False):
        mistakes = state.get("mistake_book") or []
        if not mistakes:
            st.caption("本轮没有收录错题。")
        else:
            for index, item in enumerate(mistakes, start=1):
                if not isinstance(item, dict):
                    continue
                st.markdown(f"**{index}. {item.get('concept', '未命名概念')}**")
                st.markdown(f"- 🔴 错误思维：{item.get('user_flaw', '')}")
                st.markdown(f"- 🟢 核心认知：{item.get('key_insight', '')}")
                st.caption(f"收录时间：{_format_timestamp(item.get('timestamp'))}")
                st.divider()

    with st.expander("完整对话记录", expanded=False):
        history = state.get("dialogue_history") or []
        if not history:
            st.caption("无对话记录")
        else:
            for turn in history:
                if not isinstance(turn, dict):
                    continue
                role = turn.get("role")
                label = "你" if role == "human" else _agent_label(turn.get("agent"))
                st.markdown(f"**{label}**")
                st.markdown(str(turn.get("content", "")))
                st.divider()


def _build_report(state: Dict[str, Any], max_cycles: int) -> str:
    lines = [
        "# AI 反向人类特训结业报告",
        "",
        f"- 学习主题：{state.get('topic', '未命名主题')}",
        f"- 初始基准分：{state.get('benchmark_score', 0)}",
        f"- 最终得分：{state.get('current_score', 0)} / {state.get('target_score', 90)}",
        f"- 循环轮次：{state.get('iteration_count', 0)} / {max_cycles}",
        "",
        "## 终审审计官评语",
        "",
        str(state.get("audit_feedback", "")),
        "",
        "## 学习计划",
        "",
        str(state.get("learning_plan", "")),
        "",
        "## 核心薄弱点",
        "",
    ]
    for gap in state.get("knowledge_gaps") or []:
        lines.append(f"- {gap}")

    lines.extend(["", "## 错题本与思维模型", ""])
    mistakes = state.get("mistake_book") or []
    if not mistakes:
        lines.append("本轮没有收录错题。")
    else:
        for index, item in enumerate(mistakes, start=1):
            if not isinstance(item, dict):
                continue
            lines.extend(
                [
                    f"### {index}. {item.get('concept', '未命名概念')}",
                    f"- 🔴 错误思维：{item.get('user_flaw', '')}",
                    f"- 🟢 核心认知：{item.get('key_insight', '')}",
                    f"- 收录时间：{_format_timestamp(item.get('timestamp'))}",
                    "",
                ]
            )

    lines.extend(["", "## 完整对话记录", ""])
    for turn in state.get("dialogue_history") or []:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        label = "你" if role == "human" else _agent_label(turn.get("agent"))
        lines.append(f"**{label}**：{turn.get('content', '')}")
        lines.append("")

    return "\n".join(lines)


def _report_filename(state: Dict[str, Any]) -> str:
    topic = str(state.get("topic", "training"))
    safe = re.sub(r"[^\w一-鿿-]+", "_", topic).strip("_")[:40] or "training"
    return f"AI特训结业报告_{safe}.md"


def render_completion(state: Dict[str, Any], max_cycles: int) -> None:
    if not st.session_state.get("celebrated"):
        st.balloons()
        st.session_state["celebrated"] = True

    current = _as_int(state.get("current_score"), 0)
    target = max(1, _as_int(state.get("target_score"), 90))
    st.success(f"通关成功：{current} / {target} 分。你已通过终审审计。")

    st.markdown("### 终审审计官评语")
    st.info(state.get("audit_feedback") or "审计官未留下评语。")

    _render_report(state)

    report = _build_report(state, max_cycles)
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "下载完整通关报告",
            report,
            file_name=_report_filename(state),
            mime="text/markdown",
            use_container_width=True,
        )
    with col2:
        if st.button("开启新主题", type="primary", use_container_width=True):
            _reset_session()


def render_stopped(state: Dict[str, Any], max_cycles: int) -> None:
    current = _as_int(state.get("current_score"), 0)
    target = _as_int(state.get("target_score"), 90)
    iteration = _as_int(state.get("iteration_count"), 0)

    st.warning(f"本轮训练结束，当前得分 {current} / {target}，尚未达到通关线。")
    if iteration >= max_cycles:
        st.caption(f"已达到最大循环轮次 {max_cycles}，系统自动熔断。")

    st.markdown("### 审计官最后评语")
    st.info(state.get("audit_feedback") or "未生成审计评语。")

    _render_report(state)

    if st.button("重新开始特训", type="primary", use_container_width=True):
        _reset_session()


def main() -> None:
    init_session_state()
    app, max_cycles = load_engine()
    state = st.session_state.get("graph_state") or {}

    render_sidebar(state, max_cycles)

    if not st.session_state.get("started"):
        render_landing(app)
        return

    if not state:
        st.error("会话状态已丢失，请重新开始。")
        if st.button("返回开局"):
            _reset_session()
        return

    render_status_bar(state, max_cycles)
    render_benchmark_result(state)

    if _is_passed(state):
        render_completion(state, max_cycles)
        return

    payload = _extract_interrupt(state)
    if payload:
        render_chat_history(state)
        render_interrupt(state, payload, app)
        return

    render_stopped(state, max_cycles)


if __name__ == "__main__":
    main()
