# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
from __future__ import annotations

import importlib


def test_generate_html_includes_selected_pipeline():
    generate_html = importlib.import_module("eidos.pipeline.webui").generate_html

    html = generate_html("knowledge-base")

    assert "Eidos Pipeline Dashboard" in html
    assert "知识库构建 (完整版)" in html
    assert "推理链路 (完整版)" not in html
