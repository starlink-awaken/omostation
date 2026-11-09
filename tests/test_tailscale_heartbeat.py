"""tailscale-heartbeat.sh —— socket 探测与写面跟随 profile.

实测 (2026-11-09): `/Library/LaunchDaemons/com.tailscale.brew.plist` 只传
`--state=...`, **不传 `--socket=`** ⇒ daemon 用默认 `/var/run/tailscaled.socket`,
brew socket 根本不存在。而脚本硬编码 brew socket ⇒ 每次 `status` 都连不上 →
心跳一直 `FAIL (zombie_interface=true)`, launchd 末次退出码恒 1。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "health" / "tailscale-heartbeat.sh"

FAKE = """#!/bin/bash
# 假 tailscale: brew socket 一律连不上, 默认 socket 可用并输出最小 --json 状态。
for arg in "$@"; do
  case "$arg" in
    --socket=/var/run/tailscale.brew.sock) exit 1 ;;
  esac
done
echo '{"Peer":{"macmini":{"TailscaleIPs":["100.64.110.118"],"Online":true}}}'
exit 0
"""


def _fake_tailscale(tmp_path: Path) -> Path:
    fake = tmp_path / "tailscale"
    fake.write_text(FAKE, encoding="utf-8")
    fake.chmod(0o755)
    return fake


def _run(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "TAILSCALE_BIN": str(_fake_tailscale(tmp_path)),
        "OMOSTATION_STATE_ROOT": str(tmp_path / "state"),
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def _state_file(tmp_path: Path) -> Path:
    return tmp_path / "state" / ".omo" / "state" / "tailscale-heartbeat.json"


def test_probes_socket_candidates_when_explicit_socket_missing(tmp_path: Path) -> None:
    """显式 brew socket 连不上时, 探测必须落到能用的那个 —— 旧版硬编码 ⇒ 一直 FAIL."""
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(_state_file(tmp_path).read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["zombie_interface"] is False
    assert payload["macmini_online"] is True


def test_state_file_follows_profile_state_root(tmp_path: Path) -> None:
    """产物落在 `OMOSTATION_STATE_ROOT` —— 旧版用 SCRIPT_DIR 反推, 落在安装位上."""
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _state_file(tmp_path).is_file(), f"产物没落在 state 根: {result.stdout}"
