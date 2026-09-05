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

    # Distill honestly fails without an omlxc env (no simulated success, D1)
    args_distill = argparse.Namespace(
        spine_command="distill",
        domain="signature-style",
        epochs=2,
    )
    assert cmd_spine(args_distill) == 1


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


def test_spine_draft_with_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter_dir = tmp_path / ".omo" / "state" / "lora-adapters" / "adapter-xiamingxing-v1"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "adapter_config.json").write_text('{"base_model_name_or_path": "qwen3.8-27b"}', encoding="utf-8")
    (adapter_dir / "adapters.safetensors").write_bytes(b"mock_weights")

    monkeypatch.setattr("cockpit.commands.spine._ws", lambda: tmp_path)
    monkeypatch.setattr(
        "cockpit.commands.spine._omlxc_python",
        lambda code, **kw: (0, json.dumps({"exists": True, "path": str(adapter_dir), "size_bytes": 100})),
    )
    monkeypatch.setattr("subprocess.call", lambda *args, **kw: 0)

    args = argparse.Namespace(spine_command="draft", prompt="test draft prompt")
    assert cmd_spine(args) == 0


def test_spine_distill_routed_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_state = tmp_path / ".omo" / "state"
    fake_state.mkdir(parents=True, exist_ok=True)
    buf_file = fake_state / "lora-replay-buffer.jsonl"
    buf_file.write_text(
        json.dumps({"instruction": "i", "output": "o", "domain": "document-review"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("cockpit.commands.spine._ws", lambda: tmp_path)

    fake_job = {
        "job_id": "ft-test-123",
        "domain": "document-review",
        "sample_count": 12,
        "status": "routed",
        "target_node": "node-macmini-m4",
        "target_endpoint": "192.168.1.20:8765",
        "adapter_path": str(tmp_path / ".omo" / "state" / "lora-adapters" / "adapter-xiamingxing-v1"),
        "detail": "roamed to mesh peer",
    }
    monkeypatch.setattr(
        "cockpit.commands.spine._omlxc_python",
        lambda code, **kw: (0, json.dumps(fake_job)),
    )

    args = argparse.Namespace(spine_command="distill", domain="document-review", epochs=3)
    assert cmd_spine(args) == 0
    assert (tmp_path / ".omo" / "state" / "lora-adapters" / "adapter-xiamingxing-v1" / "adapter_config.json").exists()

