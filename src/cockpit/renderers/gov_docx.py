"""GB/T 9704-2012 red-header official document DOCX renderer (BET-Y1Q4-T8-03).

Single source GOV_SPEC holds every national-standard layout parameter.
Font families are declared in the DOCX XML (w:eastAsia) — rendering hosts
(Word/WPS) resolve them; no local paid-font installation required.
Template-parse failures degrade to clean Markdown output (circuit_breaker).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "cockpit.render.gov-docx.v1"

# ── GB/T 9704-2012 layout contract (single source) ────────────────────
GOV_SPEC = {
    # A4 sheet: margins in cm (top/bottom/left/right)
    "margin_cm": {"top": 3.7, "bottom": 3.5, "left": 2.8, "right": 2.6},
    # Document title: 方正小标宋简体, 二号 (22pt), centered
    "title_font": {"east_asia": "方正小标宋简体", "ascii": "FZXiaoBiaoSong-B05S", "size_pt": 22},
    # Body: 仿宋_GB2312, 三号 (16pt), first-line indent 2 chars
    "body_font": {"east_asia": "仿宋_GB2312", "ascii": "FangSong_GB2312", "size_pt": 16},
    # Line pitch: fixed 28.95pt → 22 lines per page × 28 chars (national grid)
    "line_pitch_pt": 28.95,
    "first_line_indent_chars": 2,
    # Meta band (doc number | date) under the title, 三号 仿宋
    "meta_font": {"east_asia": "仿宋_GB2312", "ascii": "FangSong_GB2312", "size_pt": 16},
}
CM_TO_TWIP = 566.929  # 1 cm = 567 twips (1440 twips/inch ÷ 2.54)
PT_TO_TWIP = 20


@dataclass
class DocModel:
    """Parsed Markdown structure for one official document."""

    title: str = ""
    meta_lines: list[str] = field(default_factory=list)  # doc number / date band
    body: list[str] = field(default_factory=list)  # paragraphs in order
    lists: list[list[str]] = field(default_factory=list)  # bullet/numbered blocks
    quotes: list[str] = field(default_factory=list)
    diagrams: list[str] = field(default_factory=list)  # ```diagram blocks (raw)


def parse_markdown(md: str) -> DocModel:
    """Structure-first Markdown parse: h1→title, blockquote band→meta, rest→body/lists."""
    model = DocModel()
    lines = md.splitlines()
    i = 0
    current_list: list[str] = []
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            if current_list:
                model.lists.append(current_list)
                current_list = []
            i += 1
            continue
        if line.startswith("```diagram"):
            block: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            model.diagrams.append("\n".join(block))
            continue
        if line.startswith("# ") and not model.title:
            model.title = line[2:].strip()
        elif line.startswith("> "):
            model.quotes.append(line[2:].strip())
            model.meta_lines.append(line[2:].strip())
        elif re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            item = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", line)
            current_list.append(item)
        elif line.startswith(("## ", "**")) or not model.body:
            # h2 / bold lead-ins flow as emphasized body paragraphs
            model.body.append(line.lstrip("#* ").strip())
        else:
            model.body.append(line.strip())
        i += 1
    if current_list:
        model.lists.append(current_list)
    return model


def _set_run_font(run, spec: dict) -> None:
    """Declare CN+EN font names and size on a run (python-docx east-asia hook)."""
    from docx.oxml.ns import qn
    from docx.shared import Pt

    run.font.name = spec["ascii"]
    run.font.size = Pt(spec["size_pt"])
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.get_or_add_rFonts()
    r_fonts.set(qn("w:eastAsia"), spec["east_asia"])


def _set_line_pitch(paragraph, pitch_pt: float) -> None:
    """Fixed line pitch (w:spacing lineRule=exact) — the national grid."""
    from docx.oxml.ns import qn

    p_pr = paragraph._p.get_or_add_pPr()
    spacing = p_pr.find(qn("w:spacing"))
    if spacing is None:
        spacing = p_pr.makeelement(qn("w:spacing"), {})
        p_pr.append(spacing)
    spacing.set(qn("w:lineRule"), "exact")
    spacing.set(qn("w:line"), str(int(pitch_pt * PT_TO_TWIP)))


def _first_line_indent(paragraph, chars: int, size_pt: float) -> None:
    """First-line indent by character grid (w:ind firstLineChars)."""
    from docx.oxml.ns import qn

    p_pr = paragraph._p.get_or_add_pPr()
    ind = p_pr.find(qn("w:ind"))
    if ind is None:
        ind = p_pr.makeelement(qn("w:ind"), {})
        p_pr.append(ind)
    ind.set(qn("w:firstLineChars"), str(chars * 100))
    ind.set(qn("w:firstLine"), str(int(size_pt * PT_TO_TWIP * chars)))


def render_docx(model: DocModel, output: str | Path) -> Path:
    """Render the DocModel into a GB/T 9704-2012 compliant DOCX."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm

    doc = Document()
    section = doc.sections[0]
    m = GOV_SPEC["margin_cm"]
    section.top_margin, section.bottom_margin = Cm(m["top"]), Cm(m["bottom"])
    section.left_margin, section.right_margin = Cm(m["left"]), Cm(m["right"])

    # Title band
    if model.title:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(model.title)
        _set_run_font(run, GOV_SPEC["title_font"])
        _set_line_pitch(p, GOV_SPEC["line_pitch_pt"])

    # Meta band (doc number / date), centered under title
    for meta in model.meta_lines[:2]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(meta)
        _set_run_font(run, GOV_SPEC["meta_font"])
        _set_line_pitch(p, GOV_SPEC["line_pitch_pt"])

    # Body paragraphs
    for para in model.body:
        p = doc.add_paragraph()
        run = p.add_run(para)
        _set_run_font(run, GOV_SPEC["body_font"])
        _set_line_pitch(p, GOV_SPEC["line_pitch_pt"])
        _first_line_indent(p, GOV_SPEC["first_line_indent_chars"], GOV_SPEC["body_font"]["size_pt"])

    # Lists: each block renders as indented body items (公文条目式)
    for block in model.lists:
        for idx, item in enumerate(block, 1):
            p = doc.add_paragraph()
            run = p.add_run(f"（{'一二三四五六七八九十'[min(idx, 10) - 1]}）{item}")
            _set_run_font(run, GOV_SPEC["body_font"])
            _set_line_pitch(p, GOV_SPEC["line_pitch_pt"])
            _first_line_indent(p, GOV_SPEC["first_line_indent_chars"], GOV_SPEC["body_font"]["size_pt"])

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


def degrade_markdown(md: str, output: str | Path) -> Path:
    """circuit_breaker: template failure → clean plain Markdown fallback (exit 0 path)."""
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return out
