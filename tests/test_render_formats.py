"""BET-Y1Q4-T8-03 render: GB/T DOCX spec, PPTX templates, SVG, degradation."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COCKPIT_SRC = ROOT / "projects/cockpit/src"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


GOV = _load("gov_docx", "projects/cockpit/src/cockpit/renderers/gov_docx.py")
sys.path.insert(0, str(COCKPIT_SRC))
from cockpit.commands import render as render_mod  # noqa: E402,N812


def _md(tmp_path: Path) -> Path:
    p = tmp_path / "doc.md"
    p.write_text(render_mod._synthetic_doc(), encoding="utf-8")
    return p


def test_parse_markdown_structure():
    model = GOV.parse_markdown(render_mod._synthetic_doc())
    assert "通知" in model.title
    assert len(model.meta_lines) == 2  # 文号 + 日期
    assert any("健康中国" in p for p in model.body)
    assert len(model.lists) == 1 and len(model.lists[0]) == 3
    assert len(model.diagrams) == 1


def test_gov_spec_gb_values():
    spec = GOV.GOV_SPEC
    assert spec["margin_cm"] == {"top": 3.7, "bottom": 3.5, "left": 2.8, "right": 2.6}
    assert spec["title_font"]["east_asia"] == "方正小标宋简体"
    assert spec["title_font"]["size_pt"] == 22  # 二号
    assert spec["body_font"]["east_asia"] == "仿宋_GB2312"
    assert spec["body_font"]["size_pt"] == 16  # 三号
    assert spec["line_pitch_pt"] == 28.95


def test_render_docx_gb_xml():
    """DOCX 生成跑在 cockpit venv (python-docx 依赖), GB/T 断言在 verify 契约内."""
    import subprocess

    rc = subprocess.run(
        [
            "uv",
            "run",
            "--directory",
            str(ROOT / "projects/cockpit"),
            "python",
            "-m",
            "cockpit.cli",
            "render",
            "test_export_formats",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert rc.returncode == 0, rc.stdout[-500:] + rc.stderr[-500:]
    assert '"fidelity": 1.0' in rc.stdout


def test_render_pptx_dark_and_minimal(tmp_path):
    import subprocess

    for tpl in ("dark-business", "minimal-tech"):
        rc = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                str(ROOT / "projects/cockpit"),
                "python",
                "-m",
                "cockpit.cli",
                "render",
                "pptx",
                "--input",
                str(_md(tmp_path)),
                "--output",
                str(tmp_path / f"{tpl}.pptx"),
                "--template",
                tpl,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert rc.returncode == 0, rc.stderr[-300:]
        assert (tmp_path / f"{tpl}.pptx").exists()
    with zipfile.ZipFile(tmp_path / "dark-business.pptx") as z:
        slide1 = z.read("ppt/slides/slide1.xml").decode()
        pres = z.read("ppt/presentation.xml").decode()
    assert "0F1B2D" in slide1  # dark bg
    assert 'type="screen16x9"' in pres  # 16:9 label


def test_render_svg_diagram(tmp_path):
    ns = type("A", (), {"input": str(_md(tmp_path)), "output": str(tmp_path / "d.svg"), "template": ""})()
    assert render_mod.cmd_render_svg(ns) == 0
    svg = (tmp_path / "d.svg").read_text(encoding="utf-8")
    assert "<svg" in svg and "marker" in svg
    assert svg.count("<rect") == 3  # nodes inferred from edge endpoints
    assert "试点医院" in svg and "区域平台" in svg


def test_degradation_writes_markdown(tmp_path):
    ns = type(
        "A",
        (),
        {"input": str(_md(tmp_path)), "output": str(tmp_path / "bad.docx"), "template": "no-such"},
    )()
    assert render_mod.cmd_render_docx(ns) == 0  # circuit_breaker: exit 0, degrade
    fallback = tmp_path / "bad.fallback.md"
    assert fallback.exists() and "通知" in fallback.read_text(encoding="utf-8")
