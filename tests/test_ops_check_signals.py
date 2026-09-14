"""Tests for ops check-signals drift detector (BET-Y1Q4-T16)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse

from bin.ops.cli import cmd_check_signals


def _args(json: bool = True) -> argparse.Namespace:
    return argparse.Namespace(json=json)


def test_word_boundary_omostation_not_matched_by_omo_token(capsys) -> None:
    """批次 18 回归: crontab 里的 `omostation-helper` 不得被 id 尾段 `omo` 子串误命中。"""
    services = [
        {
            "id": "cron.omo",
            "enabled": True,
            "scheduler": "cron",
            "program": {"interpreter": "bash", "entrypoint": "bin/omo-job.py"},
        }
    ]
    crontab = "0 3 * * * cd /w && bash bin/omostation-helper.sh\n"
    with patch("bin.ops.cli.load_services", return_value=services), patch(
        "subprocess.run"
    ) as run:
        run.return_value.stdout = crontab
        rc = cmd_check_signals(_args())
    assert rc == 1  # omo 未命中 omostation-helper -> drift
    out = json.loads(capsys.readouterr().out)
    assert out["drift_count"] == 1


def test_cron_entrypoint_match_passes(capsys) -> None:
    services = [
        {
            "id": "cron.log_rotate",
            "enabled": True,
            "scheduler": "cron",
            "program": {"interpreter": "python3", "entrypoint": "bin/ssot/log-rotate.py"},
        }
    ]
    crontab = "0 3 * * * cd /w && python3 bin/ssot/log-rotate.py --daily\n"
    with patch("bin.ops.cli.load_services", return_value=services), patch(
        "subprocess.run"
    ) as run:
        run.return_value.stdout = crontab
        rc = cmd_check_signals(_args())
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["drift_count"] == 0


def test_crontab_token_fallback_matches(capsys) -> None:
    """占位 entrypoint 靠 crontab_token 兜底匹配真实 make 目标。"""
    services = [
        {
            "id": "cron.worktree_prune",
            "enabled": True,
            "scheduler": "cron",
            "program": {"interpreter": "uv", "entrypoint": "projects/omo"},
            "crontab_token": "worktree-prune",
        }
    ]
    crontab = "30 4 * * * cd /w && make worktree-prune >> /w/runtime/cron/branch-prune.log 2>&1\n"
    with patch("bin.ops.cli.load_services", return_value=services), patch(
        "subprocess.run"
    ) as run:
        run.return_value.stdout = crontab
        rc = cmd_check_signals(_args())
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["drift_count"] == 0


def test_disabled_entries_skipped(capsys) -> None:
    services = [
        {
            "id": "cron.dead_thing",
            "enabled": False,
            "scheduler": "cron",
            "program": {"interpreter": "uv", "entrypoint": "projects/omo"},
        }
    ]
    with patch("bin.ops.cli.load_services", return_value=services), patch(
        "subprocess.run"
    ) as run:
        run.return_value.stdout = ""
        rc = cmd_check_signals(_args())
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["checked"] == 0


def test_launchd_missing_plist_is_drift(capsys, tmp_path, monkeypatch) -> None:
    services = [
        {
            "id": "gw.some_daemon",
            "enabled": True,
            "scheduler": "launchd",
            "generate": True,
            "label": "com.omostation.some-daemon",
        }
    ]
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    with patch("bin.ops.cli.load_services", return_value=services), patch(
        "subprocess.run"
    ) as run:
        run.return_value.stdout = ""
        rc = cmd_check_signals(_args())
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert "plist 缺失" in out["drifts"][0]["anchor"]
