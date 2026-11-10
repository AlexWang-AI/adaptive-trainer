"""Handbook figures: current architecture + 7-day onboarding path."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"

NAVY = "#1F2A44"
BLUE = "#2F5597"
LIGHT_BLUE = "#DCE6F1"
TEAL = "#2A7F7F"
LIGHT_TEAL = "#D9EDED"
GREEN = "#548235"
LIGHT_GREEN = "#E2EFDA"
AMBER = "#C55A11"
LIGHT_AMBER = "#FBE5D6"
RED = "#B00020"
LIGHT_RED = "#F8D7DA"
PURPLE = "#5B3F9E"
LIGHT_PURPLE = "#EDE7F6"
GRAY = "#595959"
LIGHT_GRAY = "#F2F2F2"
WHITE = "#FFFFFF"


def f(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def wrap(draw, text, font, max_w):
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for ch in para:
            if draw.textlength(cur + ch, font=font) <= max_w:
                cur += ch
            else:
                if cur:
                    lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    return lines


def block(draw, xy, text, font, max_w, color=GRAY, gap=5):
    x, y = xy
    for line in wrap(draw, text, font, max_w):
        draw.text((x, y), line, font=font, fill=color)
        y += font.size + gap
    return y


def box(draw, xy, title, body="", *, fill=WHITE, outline=NAVY, title_color=NAVY,
        title_size=30, body_size=21, radius=16, width=3, dash=False, pad=18):
    x1, y1, x2, y2 = xy
    if dash:
        step = 18
        for x in range(x1, x2, step * 2):
            draw.line((x, y1, min(x + step, x2), y1), fill=outline, width=width)
            draw.line((x, y2, min(x + step, x2), y2), fill=outline, width=width)
        for y in range(y1, y2, step * 2):
            draw.line((x1, y, x1, min(y + step, y2)), fill=outline, width=width)
            draw.line((x2, y, x2, min(y + step, y2)), fill=outline, width=width)
    else:
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    draw.text((x1 + pad, y1 + pad), title, font=f(title_size, True), fill=title_color)
    if body:
        block(draw, (x1 + pad, y1 + pad + title_size + 10), body, f(body_size), x2 - x1 - 2 * pad, GRAY)


def arrow(draw, start, end, color=NAVY, width=4, dash=False, head=14):
    import math
    x1, y1 = start
    x2, y2 = end
    if dash:
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) // 22))
        for i in range(n):
            t1, t2 = i / n, (i + 0.55) / n
            draw.line((x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1,
                       x1 + (x2 - x1) * t2, y1 + (y2 - y1) * t2), fill=color, width=width)
    else:
        draw.line((x1, y1, x2, y2), fill=color, width=width)
    ang = math.atan2(y2 - y1, x2 - x1)
    for s in (-0.5, 0.5):
        draw.line((x2, y2, x2 - head * math.cos(ang + s), y2 - head * math.sin(ang + s)), fill=color, width=width)


def title_bar(draw, w, title, subtitle):
    draw.rectangle((0, 0, w, 108), fill=NAVY)
    draw.text((55, 22), title, font=f(42, True), fill=WHITE)
    draw.text((55, 76), subtitle, font=f(22), fill="#C9D6EA")


def fig_current():
    W, H = 2200, 1350
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    title_bar(d, W, "当前讲课系统架构（2026-11-10 代码快照）", "前端 → API → lesson-only 图 → 教材接地 / 旁路判题 / 学习闭环")

    # frontend
    box(d, (760, 140, 1440, 225), "前端 Next.js :3000", "讲练 SSE · 题卡 · 知识树 · 复习队列 · 学习看板", fill=LIGHT_BLUE, outline=BLUE)

    # API layer
    box(d, (60, 275, 1320, 470), "api_server.py（新栈，1010 行）",
        "POST /api/teach_stream（SSE）· /api/judge · /api/side_ask · /api/diagnose\n"
        "/api/practice_more · /api/curriculum · /api/kp_detail · /api/mastery\n"
        "/api/analytics · /api/review/due · /api/review/answer · /api/ledger\n"
        "/api/learner_note · /api/mistakes · /api/health_v3",
        fill=LIGHT_GREEN, outline=GREEN, title_size=32, body_size=20)
    box(d, (1380, 275, 2140, 470), "api.py（旧 v2 栈，仍挂载）",
        "6 个旧端点 · MemorySaver\n/api/teach_turn · /api/teach_answer\n重启即丢会话；不要在新功能里使用",
        fill=LIGHT_RED, outline=RED, title_size=30, body_size=20, dash=True)
    arrow(d, (1100, 225), (1000, 275), BLUE)
    arrow(d, (1200, 225), (1600, 275), RED, dash=True)

    # core graph
    box(d, (60, 520, 900, 760), "v3core.graph（lesson-only）",
        "START → lesson → END\n"
        "· 只保留 1 个写节点：一次调用出讲义 + 3 题\n"
        "· 没有 wait/judge：判题走 /api/judge 旁路\n"
        "· SqliteSaver 检查点 · token 预算 · degrade",
        fill=LIGHT_TEAL, outline=TEAL, title_size=32, body_size=20)
    arrow(d, (480, 470), (480, 520), GREEN)

    box(d, (960, 520, 1600, 760), "v3core.nodes / prompts",
        "run_lesson_practice：流式解析 · schema 校验\n"
        "_check_cards：题干/选项/难度/source_quote\n"
        "_auto_tag_types：题型标签兜底\n"
        "build_request：画像 + 教材依据 + focus",
        fill=LIGHT_BLUE, outline=BLUE, title_size=30, body_size=20)
    arrow(d, (900, 620), (960, 620), TEAL)

    box(d, (1660, 520, 2140, 760), "v3core.judge（旁路）",
        "choice → text → numeric\n→ sympy → cjk → llm\n→ fallback\n每次判题落库（事务）",
        fill=LIGHT_AMBER, outline=AMBER, title_size=30, body_size=20)
    arrow(d, (1320, 470), (1800, 520), AMBER)

    box(d, (960, 800, 1600, 960), "v3core.agents（只读旁路）",
        "side_answer：当前题 + 讲义片段\n"
        "diagnose：学生自述 → 最早出错步\n"
        "generate_questions_only：再练一组（教材题型）",
        fill=LIGHT_TEAL, outline=TEAL, title_size=30, body_size=20)
    box(d, (1660, 800, 2140, 960), "LLM 客户端",
        "clients.get_llm_client()\n进程内单例 · OpenAI 兼容\nDeepSeek V4 Flash",
        fill=LIGHT_GRAY, outline=GRAY, title_size=28, body_size=20)
    arrow(d, (1280, 760), (1280, 800), TEAL)
    arrow(d, (1600, 880), (1660, 880), GRAY)

    # data layer
    box(d, (60, 1000, 600, 1210), "教材接地层",
        "curriculum_data.json\n18 讲 · 71 分支 · 232 KP\n376 结论 · 1074 要点 · 363 例题\n→ curriculum.textbook_block()",
        fill=LIGHT_AMBER, outline=AMBER, title_size=30, body_size=19)
    box(d, (650, 1000, 1250, 1210), "学生数据层",
        "students.db：student_kp / mistakes /\nreview_queue / mastery_history / misconception\n"
        "mastery.db：kp_mastery 通关\nmistakes.db：思路诊断",
        fill=LIGHT_BLUE, outline=BLUE, title_size=30, body_size=19)
    box(d, (1300, 1000, 1800, 1210), "会话 + 观测",
        "checkpoints.sqlite：lesson 状态\nruns/trace.jsonl：节点/判题/token\n（暂无 Langfuse/OTel 接入）",
        fill=LIGHT_GRAY, outline=GRAY, title_size=30, body_size=19)
    box(d, (1850, 1000, 2140, 1210), "风险",
        "无认证\nstudent_id 客户端传\nlive v3core 无 pytest\n旧栈仍在",
        fill=LIGHT_RED, outline=RED, title_size=28, body_size=19, dash=True)

    for x in (330, 950, 1550):
        arrow(d, (x, 960 if x == 950 else 760), (x, 1000), GRAY, dash=True, width=3)

    d.text((55, 1250), "读法：绿色是新栈主链路；红色虚线是历史包袱；判题/侧问/诊断都是旁路，不写主图。",
           font=f(20), fill=GRAY)
    d.text((55, 1290), "来源：本次代码走查 api_server.py / v3core/graph.py / nodes.py / judge.py / learning.py / db.py / curriculum.py。",
           font=f(18), fill=GRAY)
    img.save(OUT / "fig_current.png", quality=95)


def fig_7day():
    W, H = 2200, 900
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    title_bar(d, W, "7 天新人训练路径：每天一个可验收的交付物", "不追求读完全部代码，追求每天能跑、能改、能证明")

    days = [
        ("Day 1", "跑通环境", "check / demo / tests\n画一次请求链路", LIGHT_BLUE, BLUE),
        ("Day 2", "读懂主链路", "graph → nodes →\nprompts → judge", LIGHT_TEAL, TEAL),
        ("Day 3", "加一个测试", "给 judge 或\nlearning 写 pytest", LIGHT_GREEN, GREEN),
        ("Day 4", "改一个门禁", "加一条 checks\n或题型校验", LIGHT_AMBER, AMBER),
        ("Day 5", "加一个只读接口", "契约 + 测试 +\ntrace 字段", LIGHT_PURPLE, PURPLE),
        ("Day 6", "做一次评测", "30 条用例 +\npass^k 报告", "#FFF2CC", "#BF9000"),
        ("Day 7", "演示与交接", "PR + 5 分钟 demo\n+ 交接文档", LIGHT_RED, RED),
    ]
    x0 = 60
    y1 = 220
    w = 285
    gap = 22
    for i, (day, title, body, fill, outline) in enumerate(days):
        x1 = x0 + i * (w + gap)
        box(d, (x1, y1, x1 + w, y1 + 300), day, "", fill=fill, outline=outline, title_size=34, body_size=20)
        d.text((x1 + 18, y1 + 70), title, font=f(27, True), fill=outline)
        block(d, (x1 + 18, y1 + 120), body, f(21), w - 36, GRAY)
        if i < len(days) - 1:
            arrow(d, (x1 + w, y1 + 150), (x1 + w + gap - 4, y1 + 150), GRAY, width=3)

    d.text((60, 570), "每天结束前必须留下三样东西：① 一条能复跑的命令；② 一段 trace 或测试输出；③ 一句「今天改变了什么」。",
           font=f(24, True), fill=NAVY)
    d.text((60, 620), "如果只有 2 天：Day 1 + Day 3；如果只有 1 天：跑通 starter_kit 的 check/demo/test，并读 graph.py 的 lesson_node。",
           font=f(22), fill=GRAY)
    d.text((60, 700), "禁止：第一天就读完 232 个知识点、第一天就改 contracts.py、第一天就上多 agent。",
           font=f(22, True), fill=RED)
    img.save(OUT / "fig_7day.png", quality=95)


if __name__ == "__main__":
    fig_current()
    fig_7day()
    for p in sorted(OUT.glob("*.png")):
        print(p.name, p.stat().st_size)
