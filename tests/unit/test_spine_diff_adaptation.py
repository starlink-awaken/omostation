"""Unit tests for Spine Diff Capture & Continuous Adaptation Loop (BET-Y2Q1-T4-03)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "value_evolution_connector",
    str(REPO_ROOT / "bin" / "gac" / "value-evolution-connector.py"),
)
vec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vec)

analyze_signature_diff = vec.analyze_signature_diff
circuit_breaker_sanitize = vec.circuit_breaker_sanitize
record_signature_diff = vec.record_signature_diff


def test_circuit_breaker_sanitization() -> None:
    """Verify that credentials, phones, and local usernames are scrubbed."""
    raw_text = (
        "发件人：13912345678, 密钥：sk-abcdef1234567890abcdef1234567890, "
        "路径：/Users/xiamingxing/confidential.md, 邮箱：admin@example.com"
    )
    cleaned = circuit_breaker_sanitize(raw_text)
    assert "13912345678" not in cleaned
    assert "<REDACTED_PHONE>" in cleaned
    assert "sk-abcdef1234567890abcdef1234567890" not in cleaned
    assert "<REDACTED_SECRET>" in cleaned
    assert "/Users/xiamingxing/" not in cleaned
    assert "/Users/<REDACTED_USER>/" in cleaned
    assert "admin@example.com" not in cleaned
    assert "<REDACTED_EMAIL>" in cleaned


def test_analyze_signature_diff_metrics() -> None:
    """Verify detailed diff analysis and normalized revision rate calculation."""
    original = "尊敬的各位领导：现将医共体推进情况作如下汇报..."
    signed = "关于医共体建设推进情况的汇报\n各处室：目前各项指标推进良好。"
    analysis = analyze_signature_diff(original, signed)

    assert analysis["original_length"] == len(original)
    assert analysis["signed_length"] == len(signed)
    assert analysis["edit_distance"] > 0
    assert 0.0 < analysis["revision_rate"] <= 1.0
    assert len(analysis["replacements"]) > 0
    assert len(analysis["modifications_summary"]) > 0


def test_zero_diff_safeguard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that identical draft and signature produce 0 revision rate and no DPO pair."""
    monkeypatch.setattr(vec, "REVISION_RATE_LOG", tmp_path / "rev.json")
    monkeypatch.setattr(vec, "DPO_PAIRS_LOG", tmp_path / "dpo.jsonl")
    monkeypatch.setattr(vec, "PREFERENCES_LOG", tmp_path / "pref.jsonl")
    monkeypatch.setattr(vec, "LORA_REPLAY_LOG", tmp_path / "replay.jsonl")

    text = "此为最终无修改内容，无需任何润色。"
    analysis = analyze_signature_diff(text, text)

    assert analysis["edit_distance"] == 0
    assert analysis["revision_rate"] == 0.0
    assert len(analysis["replacements"]) == 0

    result = record_signature_diff(
        original=text,
        signed=text,
        domain="test-unit-zero",
    )
    assert result["ok"] is True
    assert result["revision_rate"] == 0.0
    assert result["dpo_pair_created"] is False


def test_record_signature_diff_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify end-to-end recording of diffs, DPO pairs, preferences, and revision rate."""
    test_state_dir = tmp_path / ".omo" / "state"
    test_facts_dir = tmp_path / ".omo" / "_knowledge" / "facts"
    test_state_dir.mkdir(parents=True, exist_ok=True)
    test_facts_dir.mkdir(parents=True, exist_ok=True)

    rev_file = test_state_dir / "principal-revision-rate.json"
    dpo_file = test_state_dir / "dpo-preference-pairs.jsonl"
    pref_file = test_facts_dir / "personal-preferences.jsonl"
    replay_file = test_state_dir / "lora-replay-buffer.jsonl"

    monkeypatch.setattr(vec, "REVISION_RATE_LOG", rev_file)
    monkeypatch.setattr(vec, "DPO_PAIRS_LOG", dpo_file)
    monkeypatch.setattr(vec, "PREFERENCES_LOG", pref_file)
    monkeypatch.setattr(vec, "LORA_REPLAY_LOG", replay_file)

    original = "尊敬的处长：现就有关公文草稿特此汇报，请您审阅。"
    signed = "关于公文办理进展的汇报\n处长：相关事宜已按计划推进完毕。"

    res = vec.record_signature_diff(
        original=original,
        signed=signed,
        instruction="办理公文汇报",
        domain="gov-admin",
    )

    assert res["ok"] is True
    assert res["domain"] == "gov-admin"
    assert res["revision_rate"] > 0.0
    assert res["dpo_pair_created"] is True
    assert res["preferences_extracted"] > 0

    # 1. Check revision rate JSON schema
    assert rev_file.is_file()
    rev_data = json.loads(rev_file.read_text(encoding="utf-8"))
    assert rev_data["schema_version"] == "principal-revision-rate/v1"
    assert rev_data["total_records"] == 1
    assert len(rev_data["history"]) == 1
    assert rev_data["history"][0]["domain"] == "gov-admin"

    # 2. Check DPO preference pair
    assert dpo_file.is_file()
    dpo_lines = [json.loads(line) for line in dpo_file.read_text(encoding="utf-8").splitlines() if line]
    assert len(dpo_lines) == 1
    assert dpo_lines[0]["domain"] == "gov-admin"
    assert dpo_lines[0]["chosen"] == signed
    assert dpo_lines[0]["rejected"] == original

    # 3. Check preferences facts
    assert pref_file.is_file()
    pref_lines = [json.loads(line) for line in pref_file.read_text(encoding="utf-8").splitlines() if line]
    assert len(pref_lines) > 0
    assert any(p.get("domain") == "gov-admin" for p in pref_lines)


def test_cli_invocation_json(tmp_path: Path) -> None:
    """Verify the CLI supports --record-diff with --json output and exit code 0."""
    import os
    script_path = REPO_ROOT / "bin" / "gac" / "value-evolution-connector.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--record-diff",
        "--original",
        "原初稿A",
        "--signed",
        "定稿结果B",
        "--domain",
        "test-cli",
        "--json",
    ]
    env = {
        **os.environ,
        "OMO_REVISION_RATE_LOG": str(tmp_path / "rev.json"),
        "OMO_DPO_PAIRS_LOG": str(tmp_path / "dpo.jsonl"),
        "OMO_PREFERENCES_LOG": str(tmp_path / "pref.jsonl"),
        "OMO_LORA_REPLAY_LOG": str(tmp_path / "replay.jsonl"),
    }
    res = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    assert res.returncode == 0, f"CLI failed: {res.stderr}"

    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["domain"] == "test-cli"
    assert data["revision_rate"] > 0.0
    assert "average_revision_rate" in data
