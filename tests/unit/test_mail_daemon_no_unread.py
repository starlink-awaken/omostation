"""无未读邮件轮次: 结果须与正常轮次同形, 否则 main() 打印 KeyError → launchd exit 1 (TASK-F54F176A)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("src_dir", ["bin/ssot", "runtime/ssot-stable"])
def test_no_unread_cycle_prints_and_exits_zero(
    src_dir: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.syspath_prepend(str(WORKSPACE / src_dir))
    sys.modules.pop("mail_daemon", None)
    import mail_daemon

    monkeypatch.setattr(mail_daemon, "HEARTBEAT", tmp_path / "heartbeat.jsonl")
    monkeypatch.setattr(mail_daemon, "read_all", lambda **_: [])

    argv = ["--once"] if src_dir == "runtime/ssot-stable" else []
    assert mail_daemon.main(argv) == 0
    assert "0封 0任务 0草稿" in capsys.readouterr().out
    sys.modules.pop("mail_daemon", None)
