"""ADR-0466 第三道防线: 七天归档生命周期工具的保留期语义回归.

背景: 原实现把保留期截止时刻硬编码成单个批次日期 (2026-10-26)。该批次销毁后,
`--auto` 永远处于「已过期」态 —— 未来任何新归档一落地就会被立刻销毁, 与 ADR-0466 §4
承诺的「7 天保留期」相悖。现按**逐条目落位时间**判定, 本测试锁死该语义。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "ops" / "purge-test-archive-7d.py"


def _load():
    spec = importlib.util.spec_from_file_location("purge_test_archive", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["purge_test_archive"] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_card(path: Path, created_at: datetime) -> None:
    path.write_text(
        json.dumps(
            {
                "id": path.stem,
                "type": "agora_task",
                "status": "approved",
                "created_at": created_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )


def _archive(tmp_path: Path, monkeypatch):
    """返回 (mod, archive) —— 同一个模块对象, 否则 monkeypatch 打不中被测代码。"""
    archive = tmp_path / "cards_archive"
    archive.mkdir()
    dispatches = tmp_path / "dispatches_archive"
    dispatches.mkdir()
    mod = _load()
    monkeypatch.setattr(mod, "CARDS_ARCHIVE", archive)
    monkeypatch.setattr(mod, "DISPATCHES_ARCHIVE", dispatches)
    monkeypatch.setattr(mod, "ARCHIVES", (("cards", archive), ("dispatches", dispatches)))
    return mod, archive


def test_fresh_entry_survives_auto_purge(tmp_path, monkeypatch):
    """刚落位 1 天的条目不得被 --auto 销毁 (7 天保留期必须真的存在)。"""
    mod, archive = _archive(tmp_path, monkeypatch)
    _write_card(archive / "fresh.json", datetime.now(timezone.utc) - timedelta(days=1))

    assert mod.purge(force=False) == 0
    assert (archive / "fresh.json").exists()


def test_expired_entry_is_purged(tmp_path, monkeypatch):
    """落位超过 7 天的条目必须被销毁。"""
    mod, archive = _archive(tmp_path, monkeypatch)
    _write_card(archive / "stale.json", datetime.now(timezone.utc) - timedelta(days=30))

    assert mod.purge(force=False) == 1
    assert not (archive / "stale.json").exists()


def test_force_purge_removes_everything(tmp_path, monkeypatch):
    """--purge 是人工显式指令, 不看保留期。"""
    mod, archive = _archive(tmp_path, monkeypatch)
    _write_card(archive / "fresh.json", datetime.now(timezone.utc))

    assert mod.purge(force=True) == 1
    assert not (archive / "fresh.json").exists()


def test_created_at_wins_over_mtime(tmp_path, monkeypatch):
    """卡片按自身 created_at 判龄 —— mtime 被 touch 不改写其落位语义。"""
    mod, archive = _archive(tmp_path, monkeypatch)
    card = archive / "card.json"
    _write_card(card, datetime.now(timezone.utc) - timedelta(days=30))
    now_ts = time.time()
    os.utime(card, (now_ts, now_ts))  # mtime 改成「刚刚」

    assert mod.purge(force=False) == 1
    assert not card.exists()


def test_archive_dir_survives_purge(tmp_path, monkeypatch):
    """归档目录本身保留 (后续轮次的落位区), 只删条目。"""
    mod, archive = _archive(tmp_path, monkeypatch)
    _write_card(archive / "stale.json", datetime.now(timezone.utc) - timedelta(days=30))

    mod.purge(force=False)
    assert archive.exists()
