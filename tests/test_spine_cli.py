"""Unit tests for cockpit spine CLI commands (ADR-0437)."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from cockpit.commands.spine import (
    cmd_spine,
    cmd_spine_diff,
    cmd_spine_distill,
    cmd_spine_draft,
    cmd_spine_sign,
    cmd_spine_status,
)


def test_spine_sign_and_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_state = tmp_path / ".omo" / "state"
    fake_state.mkdir(parents=True, exist_ok=True)
    fake_bin_gac = tmp_path / "bin" / "gac"
    fake_bin_gac.mkdir(parents=True, exist_ok=True)
    fake_connector = fake_bin_gac / "value-evolution-connector.py"
    fake_connector.touch()

    def fake_subprocess_run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "--record-diff" in cmd:
            buf_file = fake_state / "lora-replay-buffer.jsonl"
            inst_idx = cmd.index("--instruction") + 1
            signed_idx = cmd.index("--signed") + 1
            domain_idx = cmd.index("--domain") + 1
            payload = {
                "instruction": cmd[inst_idx],
                "input": "",
                "output": cmd[signed_idx],
                "domain": cmd[domain_idx],
                "timestamp": 1234567890.0,
            }
            with buf_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("cockpit.commands.spine.subprocess.run", fake_subprocess_run)
    monkeypatch.setattr("cockpit.commands.spine._ws", lambda: tmp_path)

    # Initially empty
    args_diff = argparse.Namespace(spine_command="diff")
    assert cmd_spine(args_diff) == 0

    # Sign a diff
    args_sign = argparse.Namespace(
        spine_command="sign",
        original="def add(a, b): return a+b",
        signed="def add(a: int, b: int) -> int:\n    return a + b",
        domain="signature-style",
    )
    assert cmd_spine(args_sign) == 0

    # Verify state written
    buf_file = fake_state / "lora-replay-buffer.jsonl"
    assert buf_file.exists()
    lines = buf_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["domain"] == "signature-style"
    assert "add" in data["instruction"]

    # Diff command shows the sample
    assert cmd_spine(args_diff) == 0

    # Distill command succeeds with 1 sample
    args_distill = argparse.Namespace(
        spine_command="distill",
        domain="signature-style",
        epochs=2,
    )
    assert cmd_spine(args_distill) == 0


def test_spine_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_state = tmp_path / ".omo" / "state"
    fake_state.mkdir(parents=True, exist_ok=True)
    tel_file = fake_state / "mesh-telemetry.json"
    tel_file.write_text(
        json.dumps({
            "is_connected": True,
            "active_transport": "THUNDERBOLT_5_DMA",
            "link_speed_gbps": 120.0,
            "avg_dma_latency_ms": 0.21,
            "mbp_vram_used_pct": 62.5,
            "mbp_vram_used_mb": 81920.0,
            "kv_spillover_active": False,
            "total_blocks_migrated": 14,
            "numa_pool_size_gb": 152.0,
            "daemon_uptime_s": 3600.0,
            "lora_active_adapter": "lora-user-signature-style",
            "timestamp_utc": "2026-08-30T04:00:00Z",
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr("cockpit.commands.spine._ws", lambda: tmp_path)

    args = argparse.Namespace(spine_command="status")
    assert cmd_spine(args) == 0
