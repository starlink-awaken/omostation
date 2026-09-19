"""债务闭环节律检查 — 回归测试.

2026-09-19 实证: AGENT_COORDINATION (sev=high) 标 resolved 却无 closed_at,
且 last_reviewed == opened (从未复审); 连同台 7 项都如此。另 8 项同时带
status 与 lifecycle_state 且 7 项矛盾 (按 status 查询会得到错误答案)。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/check-debt-closure-discipline.py"


def _load():
    spec = importlib.util.spec_from_file_location("debt_closure", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["debt_closure"] = mod
    spec.loader.exec_module(mod)
    return mod


def _item(d: Path, name: str, **fields) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    lines = []
    for k, v in fields.items():
        if v is None:
            continue
        lines.append(f"{k}: {v!r}" if isinstance(v, str) else f"{k}: {v}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# ── C. 终态无闭环时间戳 ──────────────────────────────────


def test_flags_terminal_without_closed_at(tmp_path):
    d = tmp_path / "items"
    _item(d, "a.yaml", id="A", lifecycle_state="resolved",
          opened_at="2026-07-14", last_reviewed_at="2026-07-14",
          resolution_evidence="已修复")
    tool = _load()
    r = tool.scan(d)
    assert len(r["no_closed_at"]) == 1
    assert r["no_closed_at"][0]["never_reviewed"] is True


def test_terminal_with_closed_at_passes(tmp_path):
    d = tmp_path / "items"
    _item(d, "a.yaml", id="A", lifecycle_state="closed",
          closed_at="2026-09-01T00:00:00Z", close_reason="verified",
          resolution_evidence="已修复")
    tool = _load()
    r = tool.scan(d)
    assert r["no_closed_at"] == [] and r["no_evidence"] == []


def test_non_terminal_not_required_to_have_closure(tmp_path):
    d = tmp_path / "items"
    _item(d, "a.yaml", id="A", lifecycle_state="identified", opened_at="2026-09-01")
    tool = _load()
    r = tool.scan(d)
    assert r["no_closed_at"] == [] and r["no_evidence"] == []
    assert r["terminal"] == 0


# ── B. 终态无闭环证据 ────────────────────────────────────


def test_flags_terminal_without_evidence(tmp_path):
    d = tmp_path / "items"
    _item(d, "a.yaml", id="A", lifecycle_state="resolved", closed_at="2026-09-01")
    tool = _load()
    r = tool.scan(d)
    assert len(r["no_evidence"]) == 1
    assert r["no_evidence"][0]["evidence"] == "(缺失)"


def test_flags_pending_placeholder_evidence(tmp_path):
    d = tmp_path / "items"
    _item(d, "a.yaml", id="A", lifecycle_state="resolved", closed_at="2026-09-01",
          resolution_evidence="<pending>")
    tool = _load()
    r = tool.scan(d)
    assert len(r["no_evidence"]) == 1


def test_closed_evidence_field_accepted(tmp_path):
    """resolution_evidence 缺失时, closed_evidence 可作为等价证据."""
    d = tmp_path / "items"
    _item(d, "a.yaml", id="A", lifecycle_state="resolved", closed_at="2026-09-01",
          closed_evidence="S1 auto-close: verification passed")
    tool = _load()
    assert tool.scan(d)["no_evidence"] == []


# ── A. 状态字段并存 ──────────────────────────────────────


def test_flags_dual_fields(tmp_path):
    d = tmp_path / "items"
    _item(d, "a.yaml", id="A", status="registered", lifecycle_state="closed",
          closed_at="2026-08-08", resolution_evidence="ok")
    tool = _load()
    r = tool.scan(d)
    assert len(r["dual_fields"]) == 1
    assert r["dual_fields"][0]["conflicting"] is True


def test_dual_fields_same_value_still_flagged(tmp_path):
    """即使两者取值相同也应统一 (单一事实源) —— 只是不标 conflicting."""
    d = tmp_path / "items"
    _item(d, "a.yaml", id="A", status="closed", lifecycle_state="closed",
          closed_at="2026-08-08", resolution_evidence="ok")
    tool = _load()
    r = tool.scan(d)
    assert len(r["dual_fields"]) == 1
    assert r["dual_fields"][0]["conflicting"] is False


# ── 退出码与边界 ─────────────────────────────────────────


def test_main_exit_codes(tmp_path, monkeypatch):
    tool = _load()
    d = tmp_path / "items"
    monkeypatch.setattr(tool, "ITEMS_DIR", d)

    _item(d, "ok.yaml", id="OK", lifecycle_state="closed", closed_at="2026-09-01",
          resolution_evidence="ok")
    assert tool.main(["--json"]) == 0

    _item(d, "bad.yaml", id="BAD", lifecycle_state="resolved")
    assert tool.main(["--json"]) == 1


def test_missing_dir_is_not_failure(tmp_path):
    tool = _load()
    r = tool.scan(tmp_path / "nope")
    assert r["scanned"] == 0 and r["dual_fields"] == []


def test_tool_never_writes(tmp_path, monkeypatch):
    """核心约束: 本工具**只报不修** —— 不得凭空补写闭环证据."""
    d = tmp_path / "items"
    p = _item(d, "a.yaml", id="A", lifecycle_state="resolved", opened_at="2026-07-14")
    before = p.read_text(encoding="utf-8")
    tool = _load()
    monkeypatch.setattr(tool, "ITEMS_DIR", d)
    tool.main(["--json"])
    assert p.read_text(encoding="utf-8") == before, "检查器不得修改债务记录"


def test_real_registry_matches_fix_state():
    """本 PR 已修 A 类 (字段并存); C 类待 owner 补真实闭环记录.

    此测试锁住"修复后不再有 A 类", 并允许 C 类暂存 (只报不修)。
    """
    tool = _load()
    r = tool.scan()
    assert r["scanned"] > 0
    assert r["dual_fields"] == [], (
        "状态字段并存: " + ", ".join(d["file"] for d in r["dual_fields"])
    )
    # C 类不在此断言为 0 —— 需 owner 补真实记录, 见工具输出


# ── fix-debt-fields 的格式保全 (2026-09-19 修正) ─────────


def _load_fixer():
    spec = importlib.util.spec_from_file_location(
        "fix_debt_fields",
        Path(__file__).resolve().parents[1] / "bin/gac/fix-debt-fields.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fix_debt_fields"] = mod
    spec.loader.exec_module(mod)
    return mod


FIXTURE = """id: "A"
title: "标题 — 带破折号"
status: registered
lifecycle_state: "closed"
severity: "high"
description: |-
  多行块标量第一行
  第二行
evidence_refs:
- "引号风格为双引号"
- '以及单引号'
"""


def test_fixer_removes_status_line_only(tmp_path):
    """修正: 行级删除 status, 不再用 yaml.dump 整文件重写.

    2026-09-19 实证 yaml.dump 会: 双引号→单引号、折行、把 description 的
    `|-` 块标量改成带空行的引号字符串 —— 格式严重退化, 而这些是人读的债务记录。
    """
    items = tmp_path / ".omo" / "debt" / "items"
    items.mkdir(parents=True)
    p = items / "a.yaml"
    p.write_text(FIXTURE, encoding="utf-8")

    fixer = _load_fixer()
    report = fixer.fix_debt_items(tmp_path, apply=True)
    assert len(report["applied"]) == 1

    after = p.read_text(encoding="utf-8")
    # status 行已删除
    assert "\nstatus:" not in after and not after.startswith("status:")
    # 其余逐字节不变 (仅少了那一行)
    expected = FIXTURE.replace("status: registered\n", "", 1)
    assert after == expected, "除 status 行外不得有任何改动"


def test_fixer_preserves_block_scalar_and_quotes(tmp_path):
    """块标量 `|-` 与引号风格必须原样保留."""
    items = tmp_path / ".omo" / "debt" / "items"
    items.mkdir(parents=True)
    p = items / "a.yaml"
    p.write_text(FIXTURE, encoding="utf-8")
    fixer = _load_fixer()
    fixer.fix_debt_items(tmp_path, apply=True)
    after = p.read_text(encoding="utf-8")
    assert "description: |-" in after, "块标量标记不得被改写"
    assert '- "引号风格为双引号"' in after, "双引号风格不得被改写"


def test_fixer_does_not_touch_nested_status(tmp_path):
    """只删顶层 status; 嵌套 status / lifecycle_state 不得误删."""
    items = tmp_path / ".omo" / "debt" / "items"
    items.mkdir(parents=True)
    p = items / "a.yaml"
    p.write_text(
        "id: A\n"
        "status: registered\n"
        "lifecycle_state: closed\n"
        "meta:\n"
        "  status: keep-me\n",
        encoding="utf-8")
    fixer = _load_fixer()
    fixer.fix_debt_items(tmp_path, apply=True)
    after = p.read_text(encoding="utf-8")
    assert "  status: keep-me" in after, "嵌套 status 必须保留"
    assert "lifecycle_state: closed" in after
    assert not after.startswith("status:")
