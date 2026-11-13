"""「名字暗示会同步/推送」的 flag 必须**诚实**：不落地就明说并指路。

契约来源：2026-11-13 —— 同 `--to-inbox`（#5332）一起扫出的两条**假成功空转**：

- `bin/gac/bridge-runtime.py --sync-all` 只打印 `✓ All bridges synced` 就 return 0，
  而 `BRIDGES` 与 `delegate()` 就在旁边 —— 既没遍历也没调用。
- `bin/gac/kernel-bridge.py --sync-state` 只打印 `✓ State sync completed` 就 return 0，
  而 `_load_state` / `_save_state` 就在旁边 —— 不读不写。

两条还都写成 `main()` 而不是 `sys.exit(main())` ⇒ **退出码永远是 0**，调用方
（CI / 上层脚本）无论如何都收不到失败信号。本文件一并钉住退出码的传递。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_bridge_runtime_sync_all_refuses_and_points_at_delegate() -> None:
    result = _run("bin/gac/bridge-runtime.py", "--sync-all")
    assert result.returncode != 0, result.stdout
    assert "✓" not in result.stdout, result.stdout
    assert "--delegate" in result.stdout, result.stdout
    assert "--list-bridges" in result.stdout, result.stdout


def test_kernel_bridge_sync_state_refuses_and_points_at_delegate() -> None:
    result = _run("bin/gac/kernel-bridge.py", "--sync-state")
    assert result.returncode != 0, result.stdout
    assert "✓" not in result.stdout, result.stdout
    assert "--delegate" in result.stdout, result.stdout
    assert "--status" in result.stdout, result.stdout


def test_honest_paths_still_exit_zero() -> None:
    assert _run("bin/gac/bridge-runtime.py", "--list-bridges").returncode == 0
    assert _run("bin/gac/kernel-bridge.py", "--status").returncode == 0


def test_exit_codes_propagate_at_all() -> None:
    """反证：入口必须真的传退出码 —— 否则上面几条拒绝就只是打印，CI 收不到信号。

    用 kernel-bridge 的 `--delegate <未知函数>`：它 return 1（未知函数）。
    """
    result = _run("bin/gac/kernel-bridge.py", "--delegate", "no-such-function")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "Unknown function" in (result.stdout + result.stderr)
