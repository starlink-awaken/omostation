"""`runtime.observed_at` 必须是采集时刻 —— 模板拿它算快照年龄。

缺陷（DASHBOARD-TEMPLATE-CONTRACT-GAP，2026-11-10 实测）：`collect_runtime()` 不产出
`observed_at`，而 `template.html:3013` 的 `R = D.runtime || {}` 正是读它。实测
`current.json` 与 `/data.json` 的 `runtime.observed_at` 均为 `None` ⇒
`R.observed_at || D.observed_at` 求值为 `undefined` ⇒ `Date.parse(undefined)` = `NaN`
⇒ 页面 `ageLabel()` 每 30 秒刷新出「运行观测距今 NaN 分钟。」，且
`NaN > freshThreshold` 恒 false ⇒ **新鲜度过期提示永不触发**。

判据自证：本文件的 `test_collect_runtime_exposes_observation_clock` 在把该赋值删掉后
必须变红，否则「字段存在」可能只是检测器没接上。
"""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


class _Completed:
    def __init__(self, stdout, returncode=0):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def _load(monkeypatch):
    spec = importlib.util.spec_from_file_location("panorama_runtime_observed_at", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    def fake_run(cmd, **kwargs):
        joined = " ".join(str(part) for part in cmd)
        if "meta-doctor.py" in joined:
            return _Completed(json.dumps({"summary": {"ok": True}}))
        if "launchctl" in joined:
            return _Completed("3")
        if "crontab" in joined:
            return _Completed("7")
        if "scheduler-compile.py" in joined:
            return _Completed(json.dumps({"ok": True}))
        return _Completed("")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    return module


def test_collect_runtime_exposes_observation_clock(monkeypatch):
    module = _load(monkeypatch)

    rt = module.collect_runtime()

    assert rt["launchd_omostation_jobs"] == 3
    assert rt["crontab_lines"] == 7
    stamp = rt["observed_at"]
    assert isinstance(stamp, str) and stamp
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert abs((datetime.now(UTC) - parsed).total_seconds()) < 120


def test_collectors_read_state_root_and_build_payload_exposes_observed_at_and_refresh(tmp_path, monkeypatch):
    module = _load(monkeypatch)
    code_root = tmp_path / "install"
    state_dir = tmp_path / "state"
    code_root.mkdir()
    (state_dir / ".omo/_delivery/signal-poller").mkdir(parents=True)
    (state_dir / ".omo/state/mos").mkdir(parents=True)
    (state_dir / ".omo/_knowledge/workflow-mesh").mkdir(parents=True)
    (state_dir / ".omo/_delivery/signal-poller/watermarks.json").write_text(
        json.dumps({"s:c": {"seen_ids": ["1"], "last_poll": "2026-11-25T00:00:00+00:00"}}),
        encoding="utf-8",
    )
    (state_dir / ".omo/state/signal-poller-state.json").write_text(
        json.dumps({"src1": "abcd"}), encoding="utf-8"
    )
    (state_dir / ".omo/_delivery/signal-poller/poll-log.jsonl").write_text(
        '{"scene_id":"s"}\n', encoding="utf-8"
    )
    (state_dir / ".omo/state/mos/theta-facts.json").write_text(
        json.dumps([{"type": "fact"}]), encoding="utf-8"
    )
    (state_dir / ".omo/_knowledge/workflow-mesh/events.jsonl").write_text(
        json.dumps({"event_type": "scene.succeeded", "payload": {"scene_id": "s1"}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", code_root)
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state_dir))

    sp = module.collect_signal_poller()
    assert sp["watermark_entries"] == 1
    assert sp["poll_count"] == 1
    assert sp["state_keys"] == ["src1"]

    je = module.collect_journey_executions()
    assert je["succeeded"] == 1
    assert je["event_paths_scanned"] == [".omo/_knowledge/workflow-mesh/events.jsonl"]

    md = module.collect_memory_dual_track()
    assert md["theta_facts"] == 1
    tf = module.collect_theta_facts()
    assert tf["total"] == 1

    # Verify top-level observed_at and refresh contract helper expectations on real source AST/output
    src = SCRIPT.read_text(encoding="utf-8")
    assert '"observed_at": generated_at' in src
    assert 'if not isinstance(payload.get("refresh"), dict):' in src
