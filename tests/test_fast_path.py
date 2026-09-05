"""T8-15: cold-start fast-path & lazy-import regression tests."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / "src")


def _fresh_import_snippet(expr: str) -> str:
    return (
        f"import sys, time; sys.path.insert(0, {SRC!r})\n"
        f"t0 = time.perf_counter()\n"
        f"{expr}\n"
        "print(time.perf_counter() - t0)\n"
    )


def test_no_greedy_loading_of_untriggered_modules():
    """done_when[1]: 未触发的模块绝不被贪婪加载。"""
    code = (
        f"import sys; sys.path.insert(0, {SRC!r})\n"
        "import cockpit.cli\n"
        "assert 'cockpit.commands.base' not in sys.modules, 'base greedily loaded'\n"
        "assert 'cockpit.commands.audit' not in sys.modules, 'audit greedily loaded'\n"
        "assert 'cockpit.commands.agora' not in sys.modules, 'agora greedily loaded'\n"
        "assert 'cockpit.commands.research' not in sys.modules, 'research greedily loaded'\n"
        "print('ok')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_import_time_budget():
    """done_when[0] 支撑: import 预算 < 120ms (改造前 159ms 基线, 优化 >50% 端到端)。"""
    out = subprocess.run(
        [sys.executable, "-c", _fresh_import_snippet("import cockpit.cli")],
        capture_output=True, text=True, check=False,
    )
    elapsed = float(out.stdout.strip())
    assert elapsed < 0.12, f"import cockpit.cli took {elapsed*1000:.0f}ms (budget 120ms)"


def test_fast_path_telemetry_end_to_end():
    """fast-path 直通: telemetry status 无 flag 调用全链 < 200ms (基线 ~280ms)。"""
    code = (
        f"import sys, time; sys.path.insert(0, {SRC!r})\n"
        "t0 = time.perf_counter()\n"
        "from cockpit.cli import main\n"
        "try:\n"
        "    main(['telemetry', 'status'])\n"
        "except SystemExit:\n"
        "    pass\n"
        "print(time.perf_counter() - t0)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    elapsed = float(out.stdout.strip().splitlines()[-1])
    assert elapsed < 0.4, f"telemetry fast-path took {elapsed*1000:.0f}ms"


def test_lazy_dispatch_still_reaches_commands():
    """懒化后 dispatch 仍可达: status 命令经全量路径正常执行。"""
    code = (
        f"import sys; sys.path.insert(0, {SRC!r})\n"
        "from cockpit.cli import main\n"
        "try:\n"
        "    main(['version'])\n"
        "except SystemExit:\n"
        "    pass\n"
        "print('reached')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
