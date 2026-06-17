from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from omo.omo_lint import cmd_lint_direct_omo_io
from omo.omo_paths import PROJECTS_DIR


def _run_gatekeeper(target: Path) -> subprocess.CompletedProcess[str]:
    gatekeeper = PROJECTS_DIR / "ecos" / "scripts" / "contract_gatekeeper.py"
    return subprocess.run(
        [sys.executable, str(gatekeeper), str(target)],
        capture_output=True,
        text=True,
        cwd=str(PROJECTS_DIR.parent),
    )


def test_gatekeeper_blocks_direct_omo_write_text(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from pathlib import Path\n"
        "path = Path('.omo/state/system.yaml')\n"
        "path.write_text('boom', encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = _run_gatekeeper(bad)

    assert result.returncode == 1
    assert "forbidden direct mutation" in result.stdout


def test_gatekeeper_allows_read_only_omo_access(tmp_path: Path) -> None:
    ok = tmp_path / "ok.py"
    ok.write_text(
        "from pathlib import Path\n"
        "content = Path('.omo/state/system.yaml').read_text(encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = _run_gatekeeper(ok)

    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_cmd_lint_direct_omo_io_runs_gatekeeper(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "with open('.omo/state/system.yaml', 'w', encoding='utf-8') as handle:\n"
        "    handle.write('boom')\n",
        encoding="utf-8",
    )

    rc = cmd_lint_direct_omo_io([str(bad)])

    captured = capsys.readouterr()
    assert rc == 1
    assert "forbidden direct mutation" in captured.out
