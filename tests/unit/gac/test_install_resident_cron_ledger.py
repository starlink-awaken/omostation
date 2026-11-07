"""`bin/ssot/install-resident-cron.sh` 的 ledger 口径用例.

**为什么钉这条非对称** (2026-11-07): 同一个安装器里五类角色 daemon 行曾显式钉住
`--ledger ${WORKSPACE}/runtime/omo/event-ledger.sqlite3`, 而 ingest 行也必须钉 ——
两者的理由**不同**:

- `omo.resident.daemon` 的 `--ledger` 默认值就是 `event_ledger_path()`
  (`OMO_EVENT_LEDGER_DB` > `state_root()/runtime/omo/event-ledger.sqlite3`),
  所以钉住是**冗余**的, 而且会盖掉 state-root 机制: 一旦给 cron 声明 profile,
  这五条仍写检出, 与 launchd 平面 (plist 里钉了 OMOSTATION_STATE_ROOT) 分裂成
  两个 ledger (债务 RESIDENT-PLANE-SPLIT-LAUNCHD-INERT)。
- `omo.resident.ingest` 的 `--ledger` 默认是 **None**, 而 `if ledger is not None`
  才入账 —— 省掉等于**停掉**事件灌入库。所以 ingest 的钉是承重的。

判据跑真实的安装脚本 (用假 crontab 接住输出), 而不是读源码文本。
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
INSTALLER = WORKSPACE / "bin" / "ssot" / "install-resident-cron.sh"


def _render(tmp_path: Path) -> list[str]:
    """跑安装脚本, 把假 crontab 收到的内容返回为行列表。"""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    spool = tmp_path / "crontab.txt"
    fake = fake_bin / "crontab"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-l" ]; then cat "$SPOOL" 2>/dev/null; exit 0; fi\n'
        'cat > "$SPOOL"\n',
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}", "SPOOL": str(spool)}
    subprocess.run(["bash", str(INSTALLER)], env=env, check=True, capture_output=True, text=True)
    return spool.read_text(encoding="utf-8").splitlines()


def test_daemon_role_lines_do_not_pin_the_checkout_ledger(tmp_path: Path) -> None:
    """五类角色 daemon 行不得显式钉住检出 ledger —— 交给 event_ledger_path() 解析。"""
    daemon_lines = [l for l in _render(tmp_path) if "resident daemon --once" in l]
    assert len(daemon_lines) == 5, f"应渲染出 5 条角色行, 实得 {len(daemon_lines)}"
    for line in daemon_lines:
        assert "--ledger" not in line, f"角色行钉死了 ledger, 会盖掉 state-root 机制: {line}"


def test_ingest_line_keeps_its_ledger_pin(tmp_path: Path) -> None:
    """ingest 行的 --ledger 是承重的 (默认 None = 不入账), 必须保留。

    正控制: 与上一条配对 —— 否则「两条都删」也能让上一条变绿。
    """
    ingest_lines = [l for l in _render(tmp_path) if "resident ingest" in l]
    assert len(ingest_lines) == 1, f"应渲染出 1 条 ingest 行, 实得 {len(ingest_lines)}"
    assert "--ledger" in ingest_lines[0], "ingest 行丢了 --ledger —— 事件将不再入账"


def test_event_ledger_path_equals_the_old_pin_without_profile_env() -> None:
    """无 profile env 时 event_ledger_path() 与旧的显式钉逐字节相同。

    这条是「本改动在今天的 cron 环境里零行为变化」的根据。

    需要本检出的 omo 源码在 (子模块未初始化的 worktree 里 import 会退到 venv 里
    那份, 量的就不是本检出的构造), 否则明确跳过而不是假绿。
    """
    omo_src = WORKSPACE / "projects" / "omo" / "src"
    if not (omo_src / "omo" / "omo_paths.py").is_file():
        import pytest

        pytest.skip(f"omo 子模块未初始化: {omo_src}")
    script = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from omo.omo_paths import event_ledger_path, code_root;"
        "print(event_ledger_path() == code_root() / 'runtime/omo/event-ledger.sqlite3')"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("OMOSTATION_STATE_ROOT", "OMO_EVENT_LEDGER_DB")}
    out = subprocess.run(
        [sys.executable, "-c", script, str(omo_src)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "True", f"不等价 ⇒ 本改动会改变今天的 cron 行为: {out.stdout} {out.stderr}"
