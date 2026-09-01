"""BET-Y1Q4-T2-03 OCR layout engine: clustering / tables / seals / rendering."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("ocr", ROOT / "projects/agora/src/agora/server/tools_bos/ocr.py")
assert spec and spec.loader
OCR = importlib.util.module_from_spec(spec)
sys.modules["ocr"] = OCR
spec.loader.exec_module(OCR)


def _box(text, x, y, w=100, h=30, conf=0.9):
    return OCR.TextBox(text=text, x=x, y=y, w=w, h=h, confidence=conf)


def test_cluster_lines_merges_same_band():
    boxes = [_box("国卫办发布", 100, 200), _box("2026年8月", 600, 205)]
    lines = OCR.cluster_lines(boxes)
    assert len(lines) == 1 and len(lines[0].boxes) == 2


def test_cluster_lines_separates_far_bands():
    boxes = [_box("line1", 100, 200), _box("line2", 100, 400)]
    lines = OCR.cluster_lines(boxes)
    assert len(lines) == 2


def test_detect_tables_aligned_columns():
    rows = [
        [_box("A", 150, 400), _box("B", 350, 400), _box("C", 550, 400)],
        [_box("a", 152, 450), _box("b", 348, 450), _box("c", 552, 450)],
        [_box("d", 150, 500), _box("e", 350, 500), _box("f", 550, 500)],
    ]
    lines = OCR.cluster_lines([b for row in rows for b in row])
    tables, used = OCR.detect_tables(lines)
    assert len(tables) == 1 and len(tables[0]) == 3 and used == {0, 1, 2}


def test_detect_tables_not_triggered_by_sparse_rows():
    boxes = [_box("A", 150, 400), _box("B", 350, 400), _box("lone", 150, 500)]
    lines = OCR.cluster_lines(boxes)
    tables, _ = OCR.detect_tables(lines)
    assert tables == []


def test_seal_lexicon_single_fragment_anchors():
    seals, members = OCR.detect_seals([_box("医保专用章", 900, 1000, conf=0.5)])
    assert len(seals) == 1 and "专用章" in seals[0]["nearby_text"]
    assert members


def test_seal_cluster_low_confidence():
    seals, _ = OCR.detect_seals([_box("国家卫生健康", 700, 680, conf=0.41), _box("委员会印章", 712, 716, conf=0.38)])
    assert len(seals) == 1 and seals[0]["type"] == "seal"


def test_handwriting_short_low_confidence():
    hw, _ = OCR.classify_handwriting([_box("同意", 180, 700, conf=0.44)])
    assert len(hw) == 1 and hw[0]["type"] == "handwriting"


def test_handwriting_excludes_seal_wording():
    hw, _ = OCR.classify_handwriting([_box("专用章", 900, 1000, conf=0.5)])
    assert hw == []


def test_render_markdown_sections():
    layout = OCR.DocumentLayout(
        heading="测试通知",
        meta_lines=["文号  日期"],
        body=["正文段落"],
        tables=[[["列1", "列2"], ["a", "b"]]],
        seals=[{"type": "seal", "bbox": [1, 2, 3, 4], "nearby_text": "专用章", "confidence": 0.5}],
        handwriting=[{"type": "handwriting", "bbox": [1, 2, 3, 4], "text": "同意", "confidence": 0.4}],
    )
    md = OCR.render_markdown(layout)
    assert "# 测试通知" in md and "> 文号  日期" in md
    assert "| 列1 | 列2 |" in md
    assert "印章锚点" in md and "手写签批" in md


def test_full_stub_pipeline_fidelity():
    report = OCR.test_document_layout()
    assert report["layout_fidelity"] >= 0.95
    assert report["checks"]["table_detected"] and report["checks"]["seal_anchored"]
