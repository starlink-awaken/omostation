"""测试 spec 绑定 lint 规则。

验证：
- L3 + started_at 2026-09-01+ + 无绑定 → error
- 有绑定 + digest 匹配 → ok
- digest 不匹配 → error
- 老 bet（无 started_at 或早于 2026-09-01）→ 不强制
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("bet_ledger", ROOT / "bin/plan/bet-ledger.py")
bl = importlib.util.module_from_spec(_spec)
sys.modules["bet_ledger"] = bl
_spec.loader.exec_module(bl)

_is_spec_binding_required = bl._is_spec_binding_required
_file_sha256 = bl._file_sha256
cmd_lint = bl.cmd_lint


def test_l3_bet_after_cutoff_requires_spec():
    """L3 bet + started_at 2026-09-01 + status in_progress → 必须有 spec 绑定。"""
    bet = {
        "id": "BET-TEST",
        "risk_level": "L3",
        "status": "in_progress",
        "started_at": "2026-09-01",
        "track": "T1",
        "window": "Y1Q1",
        "title": "Test",
        "appetite": "high",
        "goal": "test",
        "done_when": ["ok"],
        "verify": ["echo ok"],
        "workflow": "generic",
        "write_surfaces": ["docs/"],
    }
    assert _is_spec_binding_required(bet), "L3 bet after 2026-09-01 should require spec"


def test_l2_bet_after_cutoff_requires_spec():
    """L2 bet + started_at 2026-09-01 + status review → 必须有 spec 绑定。"""
    bet = {
        "id": "BET-TEST",
        "risk_level": "L2",
        "status": "review",
        "started_at": "2026-09-01",
        "track": "T1",
        "window": "Y1Q1",
        "title": "Test",
        "appetite": "high",
        "goal": "test",
        "done_when": ["ok"],
        "verify": ["echo ok"],
        "workflow": "generic",
        "write_surfaces": ["docs/"],
    }
    assert _is_spec_binding_required(bet), "L2 bet after 2026-09-01 should require spec"


def test_old_bet_before_cutoff_not_required():
    """早于 2026-09-01 的 bet → 不强制 spec 绑定（向后兼容）。"""
    bet = {
        "id": "BET-OLD",
        "risk_level": "L3",
        "status": "in_progress",
        "started_at": "2026-08-31",
        "track": "T1",
        "window": "Y1Q1",
        "title": "Old",
        "appetite": "high",
        "goal": "test",
        "done_when": ["ok"],
        "verify": ["echo ok"],
        "workflow": "generic",
        "write_surfaces": ["docs/"],
    }
    assert not _is_spec_binding_required(bet), "Old bet should not require spec"


def test_bet_no_started_at_not_required():
    """没有 started_at 的 bet → 不强制（无法判断）。"""
    bet = {
        "id": "BET-NODATE",
        "risk_level": "L3",
        "status": "in_progress",
        "track": "T1",
        "window": "Y1Q1",
        "title": "No Date",
        "appetite": "high",
        "goal": "test",
        "done_when": ["ok"],
        "verify": ["echo ok"],
        "workflow": "generic",
        "write_surfaces": ["docs/"],
    }
    assert not _is_spec_binding_required(bet), "Bet without started_at should not require spec"


def test_l1_bet_not_required():
    """L1 bet → 不强制 spec 绑定。"""
    bet = {
        "id": "BET-L1",
        "risk_level": "L1",
        "status": "in_progress",
        "started_at": "2026-09-01",
        "track": "T1",
        "window": "Y1Q1",
        "title": "L1",
        "appetite": "low",
        "goal": "test",
        "done_when": ["ok"],
        "verify": ["echo ok"],
        "workflow": "generic",
        "write_surfaces": ["docs/"],
    }
    assert not _is_spec_binding_required(bet), "L1 bet should not require spec"


def test_candidate_status_not_required():
    """status=candidate → 不强制 spec 绑定。"""
    bet = {
        "id": "BET-CANDIDATE",
        "risk_level": "L3",
        "status": "candidate",
        "started_at": "2026-09-01",
        "track": "T1",
        "window": "Y1Q1",
        "title": "Candidate",
        "appetite": "high",
        "goal": "test",
        "done_when": ["ok"],
        "verify": ["echo ok"],
        "workflow": "generic",
        "write_surfaces": ["docs/"],
    }
    assert not _is_spec_binding_required(bet), "Candidate bet should not require spec"


def test_file_sha256_returns_hash():
    """_file_sha256 返回正确的 SHA256 哈希。"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"hello world")
        f.flush()
        path = Path(f.name)
    try:
        digest = _file_sha256(path)
        assert len(digest) == 64, f"SHA256 should be 64 chars, got {len(digest)}"
        # "hello world" 的已知 SHA256
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert digest == expected, f"SHA256 mismatch: {digest}"
    finally:
        path.unlink()


def test_cmd_lint_catches_missing_spec():
    """cmd_lint 检测 L3 bet 缺少 spec 绑定。"""
    data = {
        "meta": {
            "status_enum": ["candidate", "in_progress", "review", "done"],
            "windows": ["Y1Q1"],
            "tracks": ["T1"],
        },
        "tracks": ["T1"],
        "bets": [
            {
                "id": "BET-L3-NO-SPEC",
                "risk_level": "L3",
                "status": "in_progress",
                "started_at": "2026-09-01",
                "track": "T1",
                "window": "Y1Q1",
                "title": "No Spec",
                "appetite": "high",
                "goal": "test",
                "done_when": ["ok"],
                "verify": ["echo ok"],
                "workflow": "generic",
                "write_surfaces": ["docs/"],
            }
        ],
    }
    rc = cmd_lint(data, type("Args", (), {})())
    assert rc != 0, "cmd_lint should fail for missing spec"


def test_cmd_lint_passes_with_valid_spec():
    """cmd_lint 通过有有效 spec 绑定的 bet。"""
    # 创建临时 spec 文件
    spec_dir = ROOT / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    temp_spec = spec_dir / "_TEMP_TEST_SPEC.md"
    temp_spec.write_text("# Test Spec\n\nContent here.")
    spec_digest = _file_sha256(temp_spec)

    try:
        data = {
            "meta": {
                "status_enum": ["candidate", "in_progress", "review", "done"],
                "windows": ["Y1Q1"],
                "tracks": ["T1"],
            },
            "tracks": ["T1"],
            "bets": [
                {
                    "id": "BET-L3-WITH-SPEC",
                    "risk_level": "L3",
                    "status": "in_progress",
                    "started_at": "2026-09-01",
                    "track": "T1",
                    "window": "Y1Q1",
                    "title": "With Spec",
                    "appetite": "high",
                    "goal": "test",
                    "done_when": ["ok"],
                    "verify": ["echo ok"],
                    "workflow": "generic",
                    "write_surfaces": ["docs/"],
                    "accepted_specifications": [
                        {
                            "spec_ref": "_TEMP_TEST_SPEC.md",
                            "content_digest": spec_digest,
                        }
                    ],
                }
            ],
        }
        rc = cmd_lint(data, type("Args", (), {})())
        assert rc == 0, f"cmd_lint should pass with valid spec, got {rc}"
    finally:
        temp_spec.unlink(missing_ok=True)
