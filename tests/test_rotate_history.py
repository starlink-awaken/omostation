"""Tests for bin/gac/rotate-history.py

Covers:
  - empty / missing file no trim
  - 90-day window keeps recent records
  - --apply actually trims files
  - --json emits correct structure
  - --keep changes window
  - Invalid JSON ignored without crash
  - --apply idempotent
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "rotate-history.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location("_rh", SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def rh():
    return _load_mod()


def _mk(path: Path, dates: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    recs = [{"ts": d, "health_score": 50} for d in dates]
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
        encoding="utf-8",
    )


def _ts(days_ago: int) -> str:
    """相对 now 的时间戳。

    `rotate-history.py` 的保留窗口是**相对** `datetime.now(UTC)` 算的 (`cutoff = now - keep_days`),
    而 fixture 若写绝对日期, 窗口会随时间把记录推出去 —— 用例今天绿、几个月后红, 与真回归
    无法用眼景区分 (AGENTS.md §7②「时钟炸弹」)。走 CLI 的用例一律用本 helper 派生时间。
    """
    return (
        (datetime.now(UTC) - timedelta(days=days_ago))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def test_empty_file(rh):
    assert rh._load_records(Path("/nonexistent")) == []


def test_trim_keeps_recent(rh):
    now = datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    recs = [
        {"ts": "2026-01-01T00:00:00Z"},
        {"ts": "2026-06-01T00:00:00Z"},
        {"ts": "2026-08-23T11:00:00Z"},
    ]
    trimmed = rh._trim_records(recs, 90, now)
    assert len(trimmed) == 2
    assert trimmed[0]["ts"] == "2026-06-01T00:00:00Z"


def test_trim_all_within_window(rh):
    now = datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    recs = [{"ts": "2026-08-22T00:00:00Z"}, {"ts": "2026-08-23T00:00:00Z"}]
    trimmed = rh._trim_records(recs, 90, now)
    assert len(trimmed) == 2


def test_apply_trims(rh, tmp_path: Path):
    p = tmp_path / "h.jsonl"
    # 1/10/30 天前落在 90 天窗口内, 120 天前在窗口外 —— 与真实运行时刻无关。
    _mk(p, [_ts(d) for d in (1, 10, 30, 120)])
    assert rh.main(["--target", str(p), "--apply", "--keep", "90"]) == 0
    remaining = len(p.read_text(encoding="utf-8").strip().split("\n"))
    assert remaining == 3


def test_missing_file(rh, tmp_path: Path, capsys):
    rc = rh.main(["--target", str(tmp_path / "nope.jsonl")])
    assert rc == 0
    assert "missing" in capsys.readouterr().out


def test_bad_json(rh, tmp_path: Path, capsys):
    p = tmp_path / "bad.jsonl"
    lines = [
        json.dumps({"ts": _ts(1)}),
        "NOT VALID JSON",
        json.dumps({"ts": _ts(2)}),
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rc = rh.main(["--target", str(p), "--keep", "90"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "2" in out


def test_json_output(rh, tmp_path: Path):
    p = tmp_path / "h.jsonl"
    _mk(p, [_ts(1)])
    assert rh.main(["--target", str(p), "--json", "--keep", "90"]) == 0


def test_keep_180(rh):
    now = datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    recs = [{"ts": "2026-01-01T00:00:00Z"}, {"ts": "2026-06-01T00:00:00Z"}]
    assert len(rh._trim_records(recs, 90, now)) == 1
    assert len(rh._trim_records(recs, 180, now)) == 1


def test_idempotent(rh, tmp_path: Path):
    p = tmp_path / "h.jsonl"
    _mk(p, [_ts(1), _ts(2)])
    rh.main(["--target", str(p), "--apply", "--keep", "90"])
    c1 = len(p.read_text(encoding="utf-8").strip().split("\n"))
    rh.main(["--target", str(p), "--apply", "--keep", "90"])
    c2 = len(p.read_text(encoding="utf-8").strip().split("\n"))
    assert c1 == c2 == 2


def test_dry_run_no_write(rh, tmp_path: Path):
    p = tmp_path / "h.jsonl"
    _mk(p, [f"2026-{m:02d}-15T00:00:00Z" for m in range(1, 13)])
    before = len(p.read_text(encoding="utf-8").strip().split("\n"))
    rh.main(["--target", str(p), "--keep", "90"])
    after = len(p.read_text(encoding="utf-8").strip().split("\n"))
    assert before == after == 12
