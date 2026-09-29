"""周期报送/项目监督调度器读督办台账与业务指标, 不再统计代码仓 PR 数。"""

from __future__ import annotations

import importlib.util as iu
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(rel: str):
    spec = iu.spec_from_file_location(f"jr_{rel.replace('/', '_')}", ROOT / rel)
    mod = iu.module_from_spec(spec)
    sys.path.insert(0, str((ROOT / rel).parent))
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    f = tmp_path / "tracked-tasks.json"
    f.write_text(json.dumps([
        {"subject": "自查", "deadline": "2026-09-20", "status": "pending"},
        {"subject": "核查", "deadline": "2099-01-01", "status": "pending"},
        {"subject": "已汇总", "deadline": "2026-09-10", "status": "compiled"},
    ]), encoding="utf-8")
    monkeypatch.setenv("OMO_TRACKED_TASKS", str(f))


@pytest.mark.parametrize("rel", ["bin/ssot/journey-runner.py", "runtime/ssot-stable/journey-runner.py"])
def test_reporting_compiles_from_ledger_and_metrics(rel: str, ledger) -> None:
    jr = _load(rel)
    r = jr.dispatch_real_reporting({"metrics": {"电子病历达标医院": 12}}, {})["report"]
    assert r["compiled"] is True and r["metrics"]["电子病历达标医院"] == 12
    assert r["ledger"]["total"] == 3 and r["ledger"]["overdue"] == 1
    assert "git" not in json.dumps(r)


@pytest.mark.parametrize("rel", ["bin/ssot/journey-runner.py", "runtime/ssot-stable/journey-runner.py"])
def test_supervision_risk_from_ledger_overdue(rel: str, ledger) -> None:
    jr = _load(rel)
    sup = jr.dispatch_real_supervision({}, {})["supervision"]
    assert sup["risk_level"] == "medium" and sup["blocked_count"] == 1  # 逾期 1 条
    assert sup["source"] == "deadline-tracker 台账逾期数"


@pytest.mark.parametrize("rel", ["bin/ssot/journey-runner.py", "runtime/ssot-stable/journey-runner.py"])
def test_explicit_blocked_count_wins(rel: str, ledger) -> None:
    jr = _load(rel)
    assert jr.dispatch_real_supervision({"blocked_count": 3}, {})["supervision"]["risk_level"] == "high"
