"""A2 — physical-hosts weekly reaffirmation includes suspend day-count."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_generate_brief():
    path = ROOT / "bin" / "mof" / "generate-brief.py"
    name = "generate_brief_batch1"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    # script uses WORKSPACE = parents[2] from bin/mof → Workspace
    spec.loader.exec_module(mod)
    return mod


def test_suspend_day_count_and_reaffirmation_line():
    gb = _load_generate_brief()
    with tempfile.TemporaryDirectory() as td:
        card = Path(td) / "needs-human-p80-physical-hosts.yaml"
        created = datetime(2026, 7, 17, tzinfo=timezone.utc)
        card.write_text(
            "---\n"
            "id: NEEDS-HUMAN-P80-PHYSICAL-HOSTS\n"
            "needs-human: true\n"
            f'created_at: "{created.isoformat().replace("+00:00", "Z")}"\n'
            "title: physical hosts\n",
            encoding="utf-8",
        )
        now = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
        days = gb.physical_hosts_suspend_day_count(card, now=now)
        assert days == 7
        line = gb.physical_hosts_weekly_reaffirmation(now=now, card_path=card)
        assert line is not None
        assert line["suspend_day_count"] == 7
        assert "挂起第 7 天" in line["title"]
        assert "physical" in line["title"].lower() or "物理" in line["title"]


def test_no_reaffirmation_without_card():
    gb = _load_generate_brief()
    with tempfile.TemporaryDirectory() as td:
        missing = Path(td) / "nope.yaml"
        assert gb.physical_hosts_suspend_day_count(missing) is None
        assert gb.physical_hosts_weekly_reaffirmation(card_path=missing) is None
