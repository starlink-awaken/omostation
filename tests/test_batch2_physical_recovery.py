"""Batch2 C1 — physical recovery dry-run must never claim physical gate."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "bin" / "delivery"


def _load():
    path = DELIVERY / "physical_recovery.py"
    spec = importlib.util.spec_from_file_location("batch2_physical_recovery", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["batch2_physical_recovery"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_dry_run_never_sets_physical_gate(tmp_path: Path):
    pr = _load()
    report = pr.run_recovery(
        dry_run=True,
        hosts=["127.0.0.1"],
        out_dir=tmp_path,
    )
    assert report["dry_run"] is True
    assert report["meets_physical_gate"] is False
    assert report["meets_gate"] is False
    assert report["g_del_3_plan"]["meets_physical_gate"] is False
    assert report["g_del_1_precheck"]["meets_physical_gate"] is False
    assert "meets_physical_gate" in json.dumps(report)
    # file evidence written
    assert Path(report["report_path"]).is_file()
    body = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
    assert body["meets_physical_gate"] is False


def test_shell_wrapper_exists():
    sh = DELIVERY / "physical-recovery.sh"
    assert sh.is_file()
    text = sh.read_text(encoding="utf-8")
    assert "physical_recovery.py" in text
