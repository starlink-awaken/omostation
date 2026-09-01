"""Unit tests for bin/ssot/proposal-to-adr.py 提案状态机 (BET-Y1Q3-T10-19).

验证:
- mark_status: 枚举校验 / 迁移校验 (禁回退) / 幂等 noop
- _status_counts: 各状态计数 (历史无状态视为 new)
- convert: 处理最新 new 提案 → signal 草稿并标记 drafted (ADR-0443)
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# 文件名含连字符 (proposal-to-adr.py), 无法直接 import → importlib 按路径加载
_BIN_SSOT = Path(__file__).resolve().parents[3] / "bin" / "ssot"
_spec = importlib.util.spec_from_file_location("proposal_to_adr", _BIN_SSOT / "proposal-to-adr.py")
assert _spec is not None and _spec.loader is not None
pta = importlib.util.module_from_spec(_spec)
import sys

sys.path.insert(0, str(_BIN_SSOT))
_spec.loader.exec_module(pta)


@pytest.fixture
def _env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(pta, "PROPOSALS_DIR", tmp_path / "evolution-proposals")
    monkeypatch.setattr(pta, "DECISIONS_DIR", tmp_path / "decisions")
    monkeypatch.setattr(pta, "SIGNALS_DIR", tmp_path / "signals")
    return tmp_path


def _write_proposal(tmp_root: Path, name: str, status: str | None = None, extra: dict | None = None) -> Path:
    proposals_dir = tmp_root / "evolution-proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": "2026-08-26T00:00:00Z",
        "proposals": [{"level": "S3", "source": "test", "proposal": "test proposal", "type": "test"}],
    }
    if status is not None:
        data["status"] = status
    if extra:
        data.update(extra)
    path = proposals_dir / f"{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_mark_status_rejects_invalid_status(_env: Path) -> None:
    result = pta.mark_status("proposal-p1", "invalid_status")
    assert result["status"] == "error"
    assert "invalid status" in result["reason"]


def test_mark_status_rejects_rewind(_env: Path) -> None:
    _write_proposal(_env, "proposal-p1", status="drafted")
    result = pta.mark_status("proposal-p1", "new")
    assert result["status"] == "error"
    assert "no rewind" in result["reason"]


def test_mark_status_advances(_env: Path) -> None:
    _write_proposal(_env, "proposal-p1", status="drafted")
    result = pta.mark_status("proposal-p1", "adopted")
    assert result["status"] == "ok"
    assert result["from"] == "drafted"
    assert result["to"] == "adopted"
    # 已写回文件
    data = json.loads((_env / "evolution-proposals" / "proposal-p1.json").read_text(encoding="utf-8"))
    assert data["status"] == "adopted"


def test_mark_status_missing_proposal(_env: Path) -> None:
    result = pta.mark_status("nope", "adopted")
    assert result["status"] == "error"
    assert "not found" in result["reason"]


def test_status_counts_treats_missing_as_new(_env: Path) -> None:
    _write_proposal(_env, "proposal-p1", status=None)  # 历史无 status → new
    _write_proposal(_env, "proposal-p2", status="adopted")
    _write_proposal(_env, "proposal-p3", status="verified")
    counts = pta._status_counts()
    assert counts["new"] == 1
    assert counts["adopted"] == 1
    assert counts["verified"] == 1
    assert counts["drafted"] == 0
    assert counts["executed"] == 0


def test_convert_drafts_latest_new(_env: Path) -> None:
    _write_proposal(_env, "proposal-p-new", status="new")
    _write_proposal(_env, "proposal-p-old", status="drafted")  # 已处理, 不应重复转
    result = pta.convert(dry_run=False)
    assert result["status"] == "created"
    assert result["proposal_id"] == "proposal-p-new"
    # p-new 已标记 drafted
    data = json.loads((_env / "evolution-proposals" / "proposal-p-new.json").read_text(encoding="utf-8"))
    assert data["status"] == "drafted"
    # ADR-0443: draft 只写 signals/, 不占 ADR 编号或污染 decisions/。
    assert (_env / "signals").exists()
    drafts = list((_env / "signals").glob("*.md"))
    assert len(drafts) == 1
    content = drafts[0].read_text(encoding="utf-8")
    assert "lifecycle: signal" in content
    assert "# Signal:" in content
    assert "# ADR-" not in content
    assert not (_env / "decisions").exists()
    assert "adr_id" not in result
    assert result["signal_id"].startswith("signal://evolution/")
    assert result["path"].endswith(drafts[0].name)


def test_convert_dry_run_noop_on_missing(_env: Path) -> None:
    result = pta.convert(dry_run=True)
    assert result["status"] == "noop"
