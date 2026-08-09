"""BET-Y3H1-T5-01: journey 编排模板化集成测试.

Covered:
- 模板参数化渲染 ({{param}} 占位符替换)
- 至少 3 个 journey spec 共用同一模板
- 模板变更影响面可查 (scan_template_usage)
- 模板化 journey 可完整执行
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # .../ws-bet-t5-01
sys.path.insert(0, str(ROOT / "bin" / "ssot"))

_spec = importlib.util.spec_from_file_location("journey_runner", ROOT / "bin" / "ssot" / "journey-runner.py")
jr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jr)

from _shared import load_yaml


def test_template_render_substitutes_params():
    spec_data = load_yaml(jr._find_journey_spec("intake-review-deliver-inbox"))
    rendered = jr._render_template(spec_data)
    assert rendered["states"][0]["scene"] == "unified-inbox"
    assert rendered["states"][1]["scene"] == "document-review"
    assert rendered["states"][3]["scene"] == "engineering-delivery"
    assert len(rendered["states"]) == 6


def test_three_specs_share_template():
    for jid in (
        "intake-review-deliver-inbox",
        "intake-review-deliver-meeting",
        "intake-review-deliver-oversight",
    ):
        spec_data = load_yaml(jr._find_journey_spec(jid))
        assert spec_data.get("template") == "intake-review-deliver", jid


def test_scan_template_usage_reports_blast_radius():
    usage = jr.scan_template_usage()
    assert "intake-review-deliver" in usage["templates"]
    assert len(usage["usage"]["intake-review-deliver"]) == 3
    assert usage["total_template_refs"] == 3


def test_template_journey_runs():
    result = jr.run_journey("intake-review-deliver-inbox", dry_run=True)
    assert result["status"] == "completed"


def test_template_journey_meeting_runs():
    result = jr.run_journey("intake-review-deliver-meeting", dry_run=True)
    assert result["status"] == "completed"


def test_template_journey_oversight_runs():
    result = jr.run_journey("intake-review-deliver-oversight", dry_run=True)
    assert result["status"] == "completed"


def test_linear_journey_unaffected():
    """Existing non-template journey must still run."""
    result = jr.run_journey("inbox-to-decision", dry_run=True)
    assert result["status"] in ("completed", "paused")
