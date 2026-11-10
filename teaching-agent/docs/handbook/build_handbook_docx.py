"""Build a styled DOCX report from report.md.

The Markdown uses a deliberately small subset: headings, paragraphs, pipe tables,
bullet/numbered lists, fenced code, blockquotes, images, and horizontal rules.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parent
MD = ROOT / "handbook.md"
OUT = ROOT / "讲课智能体系统_新人上手指南_2026-11.docx"

NAVY = RGBColor(0x1F, 0x2A, 0x44)
BLUE = RGBColor(0x2F, 0x55, 0x97)
TEAL = RGBColor(0x2A, 0x7F, 0x7F)
GRAY = RGBColor(0x59, 0x59, 0x59)
MIDGRAY = RGBColor(0x7F, 0x7F, 0x7F)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK = RGBColor(0x20, 0x20, 0x20)
RED = RGBColor(0xB0, 0x00, 0x20)

NAVY_HEX = "1F2A44"
HEADER_FILL = "1F2A44"
CALLOUT_FILL = "EAF1FB"
CODE_FILL = "F5F5F5"
ZEBRA_FILL = "F7F9FC"
LIGHT_BLUE_FILL = "DCE6F1"
LIGHT_TEAL_FILL = "D9EDED"
LIGHT_AMBER_FILL = "FBE5D6"

CJK_BODY = "宋体"
CJK_HEAD = "微软雅黑"
MONO = "Consolas"


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------
def set_run_font(run, name: str, size: float, *, bold=False, color=None, italic=False, east=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), east or name)


def shade_cell(cell, hex_fill: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def shade_paragraph(p, hex_fill: str):
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    pPr.append(shd)


def border_paragraph(p, side: str, color: str, sz: int = 18, space: int = 6):
    pPr = p._p.get_or_add_pPr()
    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)
    el = OxmlElement(f"w:{side}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:space"), str(space))
    el.set(qn("w:color"), color)
    pBdr.append(el)


def set_cell_margins(cell, top=40, start=70, bottom=40, end=70):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = tcPr.find(qn("w:tcMar"))
    if tcMar is None:
        tcMar = OxmlElement("w:tcMar")
        tcPr.append(tcMar)
    for tag, val in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        el = OxmlElement(f"w:{tag}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        tcMar.append(el)


def set_table_borders(table, color="D0D7E5", sz=4):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tblPr.append(borders)


def set_repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def set_cant_split(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def set_fixed_table_widths(table, widths_cm: list[float]):
    table.autofit = False
    table.allow_autofit = False
    tbl = table._tbl
    tblPr = tbl.tblPr
    # fixed layout
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    # total width
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:type"), "dxa")
    tblW.set(qn("w:w"), str(int(sum(widths_cm) * 567)))
    # grid
    grid = tbl.find(qn("w:tblGrid"))
    if grid is not None:
        cols = grid.findall(qn("w:gridCol"))
        for col, cm in zip(cols, widths_cm):
            col.set(qn("w:w"), str(int(cm * 567)))
    # cells
    for row in table.rows:
        for cell, cm in zip(row.cells, widths_cm):
            cell.width = Cm(cm)


def set_row_height(row, cm: float):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:trHeight")
    el.set(qn("w:val"), str(int(cm * 567)))
    el.set(qn("w:hRule"), "atLeast")
    trPr.append(el)


def add_hyperlink(paragraph, url: str, text: str, size: float = 10.5):
    part = paragraph.part
    r_id = part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), CJK_BODY)
    rFonts.set(qn("w:hAnsi"), CJK_BODY)
    rFonts.set(qn("w:eastAsia"), CJK_BODY)
    rPr.append(rFonts)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "2F5597")
    rPr.append(color)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    rPr.append(sz)
    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def add_field(paragraph, instr: str):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = instr
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    fld_text = OxmlElement("w:t")
    fld_text.text = "1"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr_el)
    run._r.append(fld_sep)
    run._r.append(fld_text)
    run._r.append(fld_end)


# ---------------------------------------------------------------------------
# inline markdown
# ---------------------------------------------------------------------------
TOKEN = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*\n]+\*)")


def add_inline(paragraph, text: str, *, size: float = 10.5, color=DARK, bold=False):
    for token in TOKEN.split(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            # 递归处理，支持 **加粗里包含 `代码`**
            add_inline(paragraph, token[2:-2], size=size, color=color, bold=True)
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            r = paragraph.add_run(token[1:-1])
            set_run_font(r, CJK_BODY, size, bold=bold, color=color, italic=True)
        elif token.startswith("`") and token.endswith("`"):
            r = paragraph.add_run(token[1:-1])
            set_run_font(r, MONO, size - 1.0, bold=bold, color=RGBColor(0x8B, 0x1A, 0x1A), east=CJK_BODY)
            rPr = r._element.get_or_add_rPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "F2F2F2")
            rPr.append(shd)
        elif token.startswith("[") and "](" in token and token.endswith(")"):
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token)
            if m:
                add_hyperlink(paragraph, m.group(2), m.group(1), size=size)
            else:
                r = paragraph.add_run(token)
                set_run_font(r, CJK_BODY, size, bold=bold, color=color)
        else:
            r = paragraph.add_run(token)
            set_run_font(r, CJK_BODY, size, bold=bold, color=color)


# ---------------------------------------------------------------------------
# document setup
# ---------------------------------------------------------------------------
def setup_styles(doc: Document):
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)
    sec.header_distance = Cm(1.0)
    sec.footer_distance = Cm(1.0)

    normal = doc.styles["Normal"]
    normal.font.name = CJK_BODY
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = DARK
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_BODY)
    pf = normal.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(6)
    pf.space_before = Pt(0)

    specs = {
        "Heading 1": (22, NAVY, 20, 10, True),
        "Heading 2": (15.5, NAVY, 14, 6, False),
        "Heading 3": (12.5, BLUE, 10, 4, False),
        "Heading 4": (11, DARK, 8, 3, False),
    }
    for name, (size, color, before, after, page_break) in specs.items():
        st = doc.styles[name]
        st.font.name = CJK_HEAD
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = color
        st._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_HEAD)
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.line_spacing = 1.2
        st.paragraph_format.keep_with_next = True
        if page_break:
            st.paragraph_format.page_break_before = True

    for name in ("List Bullet", "List Number"):
        st = doc.styles[name]
        st.font.name = CJK_BODY
        st.font.size = Pt(10.5)
        st._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_BODY)
        st.paragraph_format.line_spacing = 1.4
        st.paragraph_format.space_after = Pt(3)


def add_header_footer(doc: Document):
    sec = doc.sections[0]
    header = sec.header
    p = header.paragraphs[0]
    p.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run("讲课智能体系统 · 新人上手指南")
    set_run_font(r, CJK_HEAD, 8.5, color=MIDGRAY)
    r2 = p.add_run("　｜　2026-11-10")
    set_run_font(r2, CJK_HEAD, 8.5, color=MIDGRAY)
    border_paragraph(p, "bottom", "C9D6EA", sz=6, space=4)

    footer = sec.footer
    fp = footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("第 ")
    set_run_font(r, CJK_BODY, 9, color=MIDGRAY)
    add_field(fp, "PAGE")
    r = fp.add_run(" 页 / 共 ")
    set_run_font(r, CJK_BODY, 9, color=MIDGRAY)
    add_field(fp, "NUMPAGES")
    r = fp.add_run(" 页")
    set_run_font(r, CJK_BODY, 9, color=MIDGRAY)


# ---------------------------------------------------------------------------
# cover
# ---------------------------------------------------------------------------
def add_cover(doc: Document):
    # top spacing
    for _ in range(2):
        doc.add_paragraph()

    band = doc.add_table(rows=1, cols=1)
    band.alignment = WD_TABLE_ALIGNMENT.CENTER
    band.autofit = False
    cell = band.cell(0, 0)
    cell.width = Cm(16.6)
    set_fixed_table_widths(band, [16.6])
    set_cant_split(band.rows[0])
    shade_cell(cell, NAVY_HEX)
    set_cell_margins(cell, top=340, bottom=340, start=360, end=360)
    set_row_height(band.rows[0], 7.2)

    p = cell.paragraphs[0]
    r = p.add_run("新人上手指南 · ONBOARDING HANDBOOK")
    set_run_font(r, "Calibri", 9.5, bold=True, color=RGBColor(0xC9, 0xD6, 0xEA))
    p.paragraph_format.space_after = Pt(18)

    p = cell.add_paragraph()
    r = p.add_run("讲课智能体系统\n新人上手指南")
    set_run_font(r, CJK_HEAD, 26, bold=True, color=WHITE)
    p.paragraph_format.line_spacing = 1.25
    p.paragraph_format.space_after = Pt(14)

    p = cell.add_paragraph()
    r = p.add_run("30 分钟跑通 · 7 天独立交付 · 代码级参考")
    set_run_font(r, CJK_HEAD, 13, color=RGBColor(0xDC, 0xE6, 0xF1))

    doc.add_paragraph()

    meta = doc.add_table(rows=4, cols=2)
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta.autofit = False
    rows = [
        ("版本", "v1.0（2026-11-10 09:00 代码快照）"),
        ("适用对象", "刚拿到 DSH harness、会基本 Python、没读过本项目的新同学"),
        ("配套代码", "starter_kit（18 个离线测试，全部通过）"),
        ("一句话", "先跑通、再读懂、再改一个点、每天留下证据"),
    ]
    for i, (k, v) in enumerate(rows):
        meta.cell(i, 0).width = Cm(3.2)
        meta.cell(i, 1).width = Cm(13.4)
        c0, c1 = meta.cell(i, 0), meta.cell(i, 1)
        shade_cell(c0, "F2F5FA")
        set_cell_margins(c0)
        set_cell_margins(c1)
        p0 = c0.paragraphs[0]
        r0 = p0.add_run(k)
        set_run_font(r0, CJK_HEAD, 9.5, bold=True, color=NAVY)
        p1 = c1.paragraphs[0]
        r1 = p1.add_run(v)
        set_run_font(r1, CJK_BODY, 9.5, color=DARK)
        set_cant_split(meta.rows[i])
    set_fixed_table_widths(meta, [3.4, 13.0])
    set_table_borders(meta, color="D0D7E5", sz=3)

    doc.add_paragraph()
    # three metric cards
    cards = doc.add_table(rows=2, cols=3)
    cards.alignment = WD_TABLE_ALIGNMENT.CENTER
    cards.autofit = False
    values = [("30 分钟", "跑通环境 + starter_kit", LIGHT_BLUE_FILL), ("7 天", "独立交付一个改动", LIGHT_TEAL_FILL), ("232 KP", "18 讲 · 71 分支", LIGHT_AMBER_FILL)]
    for j, (big, label, fill) in enumerate(values):
        top = cards.cell(0, j)
        bottom = cards.cell(1, j)
        top.width = Cm(5.5)
        bottom.width = Cm(5.5)
        shade_cell(top, fill)
        shade_cell(bottom, "FFFFFF")
        set_cell_margins(top, top=180, bottom=40, start=120, end=120)
        set_cell_margins(bottom, top=20, bottom=160, start=120, end=120)
        p = top.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(big)
        set_run_font(r, CJK_HEAD, 22, bold=True, color=NAVY)
        p2 = bottom.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r2 = p2.add_run(label)
        set_run_font(r2, CJK_BODY, 9, color=GRAY)
    set_fixed_table_widths(cards, [5.47, 5.47, 5.47])
    set_table_borders(cards, color="FFFFFF", sz=2)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("本手册分 12 章：环境、代码地图、运行链路、架构规则、代码走读、工作流、调试、评测、7 天计划、模板。所有命令均按当前 Windows 环境编写。")
    set_run_font(r, CJK_BODY, 9, color=GRAY, italic=True)
    p.paragraph_format.space_before = Pt(20)

    doc.add_page_break()


# ---------------------------------------------------------------------------
# block renderers
# ---------------------------------------------------------------------------
def add_heading(doc, level: int, text: str, *, page_break: bool | None = None):
    p = doc.add_heading(level=level)
    if page_break is not None:
        p.paragraph_format.page_break_before = page_break
    # strip trailing hashes
    text = text.strip()
    # inline bold inside headings is rare; strip markers
    text = text.replace("**", "")
    r = p.add_run(text)
    return p


def add_paragraph(doc, text: str, *, size=10.5, color=DARK, align=None, space_after=6, indent=True):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    if indent:
        p.paragraph_format.first_line_indent = Cm(0.74)
    # a short bold-only label (e.g. "**证据标注**：") should stay with its list
    stripped = text.strip()
    if stripped.startswith("**") and (stripped.endswith("**") or stripped.endswith("**：") or stripped.endswith("**:")):
        p.paragraph_format.keep_with_next = True
    add_inline(p, text, size=size, color=color)
    return p


def add_callout(doc, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.25)
    p.paragraph_format.right_indent = Cm(0.15)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.4
    shade_paragraph(p, CALLOUT_FILL)
    border_paragraph(p, "left", "2F5597", sz=24, space=6)
    add_inline(p, text, size=10, color=RGBColor(0x1F, 0x2A, 0x44))
    return p


def add_code(doc, lines: list[str]):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.2)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.0
    shade_paragraph(p, CODE_FILL)
    border_paragraph(p, "left", "C9D6EA", sz=12, space=4)
    for idx, line in enumerate(lines):
        r = p.add_run(line)
        set_run_font(r, MONO, 7.6, color=RGBColor(0x33, 0x33, 0x33), east=CJK_BODY)
        if idx < len(lines) - 1:
            r.add_break()
    return p


def add_image(doc, alt: str, rel_path: str):
    path = (ROOT / rel_path).resolve()
    if not path.exists():
        add_paragraph(doc, f"[缺失图片：{rel_path}]", color=RED, indent=False)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(str(path), width=Cm(16.3))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(10)
    r = cap.add_run(alt)
    set_run_font(r, CJK_BODY, 8.8, color=GRAY, italic=True)


def add_table(doc, rows: list[list[str]]):
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    table = doc.add_table(rows=len(rows), cols=ncol)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.allow_autofit = False
    set_table_borders(table, color="D0D7E5", sz=4)

    # content-aware column widths (CJK counts double)
    weights = []
    for j in range(ncol):
        longest = 3
        for r in rows:
            plain = re.sub(r"[`*]", "", r[j])
            w = sum(2 if ord(ch) > 127 else 1 for ch in plain)
            if re.fullmatch(r"[\d.,%/\-]+", plain.strip()):
                w += 3  # numeric columns need a little breathing room
            longest = max(longest, min(30, w))
        weights.append(longest)
    total = max(1, sum(weights))
    widths = [max(1.7, 16.4 * w / total) for w in weights]
    # renormalise after clamping
    scale = 16.4 / sum(widths)
    widths = [w * scale for w in widths]
    set_fixed_table_widths(table, widths)

    font_size = 8.2 if ncol >= 5 else 8.8
    for i, row in enumerate(rows):
        for j, cell_text in enumerate(row):
            cell = table.cell(i, j)
            set_cell_margins(cell, top=30, bottom=30, start=55, end=55)
            if i == 0:
                shade_cell(cell, HEADER_FILL)
            elif i % 2 == 0:
                shade_cell(cell, ZEBRA_FILL)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            if i == 0:
                r = p.add_run(cell_text.replace("**", ""))
                set_run_font(r, CJK_HEAD, font_size, bold=True, color=WHITE)
            else:
                add_inline(p, cell_text, size=font_size, color=DARK)
        set_cant_split(table.rows[i])
    set_repeat_header(table.rows[0])
    # spacing after table
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(2)
    sp.paragraph_format.line_spacing = 1.0
    return table


# ---------------------------------------------------------------------------
# markdown parser
# ---------------------------------------------------------------------------
def build():
    setup_doc = Document()
    setup_styles(setup_doc)
    add_header_footer(setup_doc)
    add_cover(setup_doc)

    text = MD.read_text(encoding="utf-8")
    lines = text.splitlines()
    # start from 摘要 (cover handled separately)
    start = next(i for i, l in enumerate(lines) if l.strip() == "## 先读这一页")
    i = start
    in_front_matter = True
    in_toc = False
    while i < len(lines):
        line = lines[i]

        # fenced code
        if line.startswith("```"):
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            add_code(setup_doc, buf)
            i = j + 1
            continue

        # image
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
        if m:
            add_image(setup_doc, m.group(1), m.group(2))
            i += 1
            continue

        # table
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            j = i + 2
            body = []
            while j < len(lines) and lines[j].startswith("|"):
                body.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            add_table(setup_doc, [header] + body)
            i = j
            continue

        # headings
        if line.startswith("#### "):
            add_heading(setup_doc, 4, line[5:])
            i += 1
            continue
        if line.startswith("### "):
            add_heading(setup_doc, 3, line[4:])
            i += 1
            continue
        if line.startswith("## "):
            title = line[3:].strip()
            if title in ("摘要", "阅读指南", "术语表", "目录", "先读这一页"):
                add_heading(setup_doc, 1, title, page_break=False)
                in_front_matter = True
                in_toc = title == "目录"
            else:
                add_heading(setup_doc, 2, title)
                in_front_matter = False
                in_toc = False
            i += 1
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            add_heading(setup_doc, 1, title, page_break=True)
            in_front_matter = False
            in_toc = False
            i += 1
            continue

        # blockquote
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip(">").strip())
                i += 1
            add_callout(setup_doc, " ".join(x for x in buf if x))
            continue

        # bullets
        if re.match(r"^[-*]\s+", line):
            buf = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                buf.append(re.sub(r"^[-*]\s+", "", lines[i]))
                i += 1
            for item in buf:
                p = setup_doc.add_paragraph(style="List Bullet")
                p.paragraph_format.space_after = Pt(3)
                add_inline(p, item)
            continue

        # numbered list (manual numbering, so each list restarts at 1; TOC keeps chapter numbers)
        if re.match(r"^\d+\.\s+", line):
            buf = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                buf.append(lines[i])
                i += 1
            for idx, raw in enumerate(buf, 1):
                m = re.match(r"^(\d+)\.\s+(.*)", raw)
                num = m.group(1) if (in_toc and m) else str(idx)
                item = m.group(2) if m else raw
                p = setup_doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.95)
                p.paragraph_format.first_line_indent = Cm(-0.6)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.4
                r = p.add_run(f"{num}. ")
                set_run_font(r, CJK_BODY, 10.5, bold=True, color=NAVY)
                add_inline(p, item)
            continue

        # horizontal rule
        if line.strip() == "---":
            p = setup_doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(8)
            border_paragraph(p, "bottom", "C9D6EA", sz=6, space=1)
            i += 1
            continue

        # blank
        if not line.strip():
            i += 1
            continue

        # paragraph (join consecutive non-special lines)
        buf = [line.strip()]
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if (not nxt.strip() or nxt.startswith(("#", "|", ">", "```", "![", "---"))
                    or re.match(r"^[-*]\s+", nxt) or re.match(r"^\d+\.\s+", nxt)):
                break
            buf.append(nxt.strip())
            j += 1
        add_paragraph(setup_doc, "".join(buf) if all("\u4e00" <= c <= "\u9fff" or c in "，。；：！？、（）《》“”‘’—…" for c in "".join(buf)) else " ".join(buf))
        i = j

    setup_doc.core_properties.title = "讲课智能体系统 · 新人上手指南"
    setup_doc.core_properties.subject = "2026-11 讲课 Agent 新人上手与参考代码"
    setup_doc.core_properties.author = "DeepSeek Harness 研究助理"
    setup_doc.core_properties.keywords = "讲课智能体, 新人上手, LangGraph, 代码走读, 评测"
    setup_doc.save(OUT)
    print("saved", OUT)
    print("paragraphs", len(setup_doc.paragraphs), "tables", len(setup_doc.tables))


if __name__ == "__main__":
    build()
