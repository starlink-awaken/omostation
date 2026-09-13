"""scene-signal-poller dispatch reliability — watermark-on-success + batch dedup.

A failed journey dispatch must NOT watermark the signal (it must be retried
on the next poll), and duplicate ids within one connector batch must not be
dispatched twice.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "scene_signal_poller", ROOT / "bin/ssot/scene-signal-poller.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["scene_signal_poller"] = module
    spec.loader.exec_module(module)
    return module


CARD = {
    "scene_id": "scene-test-ingest",
    "lifecycle": "assisted",
    "activation": "controlled",
    "triggers": [
        {"type": "signal", "signal": "note.created", "connector": "applenotes"},
    ],
}

ITEMS = [
    {"id": "dup-1", "title": "first"},
    {"id": "dup-1", "title": "first again"},
    {"id": "dup-2", "title": "second"},
]


@pytest.fixture()
def poller(tmp_path):
    mod = _load_module()
    scenes = tmp_path / "cards"
    scenes.mkdir()
    (scenes / "scene-test-ingest.yaml").write_text(
        json.dumps(CARD), encoding="utf-8"
    )
    mod.SCENES_DIR = scenes
    mod.WATERMARK_PATH = tmp_path / "watermarks.json"
    return mod


def _run_poll(mod, *, fail_first: bool):
    calls = {"n": 0}

    def fake_run(*args, **kwargs):
        calls["n"] += 1
        if fail_first and calls["n"] == 1:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")
        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps({"run_id": "r1", "status": "escalated"})
        )

    with patch.object(mod.subprocess, "run", side_effect=fake_run), \
         patch.object(mod, "_iris_list", return_value=[dict(i) for i in ITEMS]):
        return mod.poll(), calls


def test_failed_dispatch_not_watermarked(poller):
    mod = poller
    result, _ = _run_poll(mod, fail_first=True)
    wm = mod._load_watermarks()
    seen = wm.get("scene-test-ingest:applenotes", {}).get("seen_ids", [])
    assert "dup-1" not in seen
    statuses = [d["status"] for d in result["details"]]
    assert statuses.count("error") == 1

    # Next poll retries the failed signal and succeeds → watermarked then
    result2, _ = _run_poll(mod, fail_first=False)
    wm2 = mod._load_watermarks()
    seen2 = wm2.get("scene-test-ingest:applenotes", {}).get("seen_ids", [])
    assert "dup-1" in seen2 and "dup-2" in seen2
    assert len(seen2) == 2  # batch dedup: dup-1 dispatched once


def test_batch_dedup_dispatches_once(poller):
    mod = poller
    result, calls = _run_poll(mod, fail_first=False)
    # 3 items in batch, but only 2 unique ids → 2 dispatches
    assert calls["n"] == 2
    assert result["new_signals"] == 2
    wm = mod._load_watermarks()
    assert sorted(wm["scene-test-ingest:applenotes"]["seen_ids"]) == ["dup-1", "dup-2"]


def test_success_watermarks_signal(poller):
    mod = poller
    _run_poll(mod, fail_first=False)
    first, _ = _run_poll(mod, fail_first=False)
    # second poll: everything already seen → nothing new
    assert first["new_signals"] == 0
