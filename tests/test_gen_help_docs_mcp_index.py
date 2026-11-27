# ---
# status: active
# lifecycle: active
# owner: governance-agent
# ssot: .omo/_truth/registry/document-governance.yaml
# verifier: pytest tests/test_gen_help_docs_mcp_index.py
# ---
"""gen_mcp_index 的两条不变式 (2026-11-27):

1. frontmatter 沿用文件里已有的一份 —— 生成器不得改写人工维护的 `last-reviewed`
   (旧实现硬编码 2026-09-24, 每次再生成都回退它; 而 pre-commit 的 sync-check
   正好在每次 gitlink bump 后触发再生成)。
2. 不再把 ADR-0373 的哨兵时间戳 `1970-01-01T00:00:00Z` 印成「自动生成于 …」
   那种像真实生成时间的措辞。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/gen-help-docs.py"
SPEC = importlib.util.spec_from_file_location("gen_help_docs", MODULE_PATH)
assert SPEC and SPEC.loader
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)

REG = {
    "version": "1.0.0",
    "generated_at": "1970-01-01T00:00:00Z",
    "totals": {"mcp_servers": 1, "mcp_tools": 2},
    "mcp_servers": [
        {
            "id": "demo",
            "layer": "L1",
            "tool_count": 2,
            "transport": "stdio",
            "file": "projects/demo/src/mcp_server.py",
            "tools": ["a", "b"],
            "ports": {},
        }
    ],
}


def _frontmatter_of(text: str) -> str:
    return text.split("# MCP")[0]


def test_existing_last_reviewed_is_preserved(tmp_path: Path) -> None:
    doc = tmp_path / "INDEX-MCP.md"
    doc.write_text(
        "---\nstatus: active\nlifecycle: generated\nowner: governance-team\n"
        "last-reviewed: 2026-11-03\n---\n\n# MCP 服务器索引\n",
        encoding="utf-8",
    )
    out = GEN.gen_mcp_index(REG, GEN._extract_frontmatter(doc))
    assert "last-reviewed: 2026-11-03" in _frontmatter_of(out)


def test_absent_frontmatter_gets_default_date() -> None:
    out = GEN.gen_mcp_index(REG, "")
    assert "last-reviewed:" in _frontmatter_of(out)


def test_sentinel_timestamp_is_labelled_not_presented_as_real() -> None:
    out = GEN.gen_mcp_index(REG, "")
    assert "1970-01-01T00:00:00Z" in out
    assert "ADR-0373" in out
    assert "自动生成于 1970-01-01" not in out
