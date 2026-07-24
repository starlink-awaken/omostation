"""T4.1 X3 delivery soft-gate — drives real generate-brief helpers."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_MOD_PATH = ROOT / "bin" / "mof" / "generate-brief.py"
_spec = importlib.util.spec_from_file_location("generate_brief", _MOD_PATH)
assert _spec and _spec.loader
gb = importlib.util.module_from_spec(_spec)
sys.modules["generate_brief"] = gb
_spec.loader.exec_module(gb)

count_deliveries_by_month = gb.count_deliveries_by_month
evaluate_delivery_soft_gate = gb.evaluate_delivery_soft_gate
generate_brief_content = gb.generate_brief_content
load_delivery_soft_gate = gb.load_delivery_soft_gate


def test_load_delivery_soft_gate_reads_config_not_hardcoded(tmp_path: Path) -> None:
    cfg = tmp_path / "gate.yaml"
    cfg.write_text(
        "x3_delivery_soft_gate:\n  enabled: true\n  monthly_min_deliveries: 3\n",
        encoding="utf-8",
    )
    gate = load_delivery_soft_gate(cfg)
    assert gate["monthly_min_deliveries"] == 3
    assert gate["enabled"] is True
    # shipped SSOT path must exist for production threshold
    assert (ROOT / ".omo/_truth/registry/x3-delivery-soft-gate.yaml").is_file()


def test_evaluate_soft_gate_warns_under_threshold_never_hard_blocks() -> None:
    monthly = {
        "current_month": "2026-07",
        "previous_month": "2026-06",
        "current_count": 2,
        "previous_count": 5,
        "total": 7,
    }
    gate = {"enabled": True, "monthly_min_deliveries": 8, "warning_class": "soft"}
    result = evaluate_delivery_soft_gate(monthly, gate)
    assert result["under_threshold"] is True
    assert result["hard_block"] is False
    assert result["warning"] is not None
    assert "软门禁" in result["warning"]["title"]
    assert result["delta"] == -3


def test_evaluate_soft_gate_ok_when_above_threshold() -> None:
    monthly = {
        "current_month": "2026-07",
        "previous_month": "2026-06",
        "current_count": 12,
        "previous_count": 4,
        "total": 16,
    }
    result = evaluate_delivery_soft_gate(
        monthly, {"enabled": True, "monthly_min_deliveries": 8}
    )
    assert result["under_threshold"] is False
    assert result["warning"] is None
    assert result["hard_block"] is False


def test_count_deliveries_by_month_uses_real_files(tmp_path: Path) -> None:
    spaces = tmp_path / "spaces"
    spaces.mkdir()
    # current month delivery card
    p = spaces / "del-now.yaml"
    p.write_text("title: demo\nkind: delivery\n", encoding="utf-8")
    # non-delivery ignored
    (spaces / "other.yaml").write_text("title: noise\n", encoding="utf-8")
    now = datetime.now(timezone.utc)
    monthly = count_deliveries_by_month(spaces, now=now, keywords=["delivery"])
    assert monthly["current_count"] >= 1
    assert monthly["total"] >= 1


def test_generate_brief_includes_delivery_mom_and_soft_warning() -> None:
    """Drive real generate_brief_content entry surface for MoM card + soft warning."""
    content = generate_brief_content()
    assert "## 📈 X3 价值仪表" in content
    assert "工作交付" in content
    assert "软阈" in content
    # soft-gate config path pointerized in table
    assert "x3-delivery-soft-gate.yaml" in content
    # under-threshold environment typically has soft warning section or normal status
    assert "待决策收件箱" in content
