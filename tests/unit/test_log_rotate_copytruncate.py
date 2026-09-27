"""log-rotate 当前份必须 copytruncate: launchd 守护持有 O_APPEND 句柄, rename 会让后续输出写进旧 inode (TASK-F54F176A)."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("log_rotate", WORKSPACE / "bin" / "ssot" / "log-rotate.py")
assert _spec and _spec.loader
log_rotate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(log_rotate)


def test_daemon_output_after_rotation_stays_visible(tmp_path: Path) -> None:
    log = tmp_path / "agent-tick-daemon.log"
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND)  # 同 launchd StandardOutPath
    inode = log.stat().st_ino
    os.write(fd, b"before-rotate\n")

    assert log_rotate._rotate_one(log, keep=3, dry_run=False)
    os.write(fd, b"after-rotate\n")
    os.close(fd)

    assert log.stat().st_ino == inode
    assert log.read_bytes() == b"after-rotate\n"
    assert (tmp_path / "agent-tick-daemon.log.1").read_bytes() == b"before-rotate\n"


def test_history_chain_still_shifts(tmp_path: Path) -> None:
    log = tmp_path / "x.log"
    log.write_text("new")
    (tmp_path / "x.log.1").write_text("old1")
    (tmp_path / "x.log.2").write_text("old2")

    log_rotate._rotate_one(log, keep=3, dry_run=False)

    assert (tmp_path / "x.log.1").read_text() == "new"
    assert (tmp_path / "x.log.2").read_text() == "old1"
    assert (tmp_path / "x.log.3").read_text() == "old2"
    assert log.read_text() == ""
