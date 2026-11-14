"""`gac-healthcheck` 的 CORE_FILES 不得指向已退役/未跟踪的路径。

契约来源：2026-11-15 —— `CORE_FILES` 里有两条指向**已退役**文件：
- `.omo/cron/opc-closeout-crontab` —— 2026-08-22「登记退役」并归档到
  `.omo/cron/_archived-20260822-opc-closeout-crontab`；
- `bin/gac/gac-ingest-legacy.py` —— 由 #1839 归档到 `bin/_archive/migrations/`。

两条都让「核心文件」检查恒红（实测 25/27），而红的原因不是交付缺文件，
是**清单没跟退役走**。本文件把「清单里的主仓路径必须在 origin/main 上被跟踪」钉住。
（`projects/` 下的条目属于子模块，用主仓 ls-tree 看不到内容，跳过。）
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "gac-healthcheck.py"


def _load():
    spec = importlib.util.spec_from_file_location("gac_healthcheck_core_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gac_healthcheck_core_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _tracked_on_main(rel: str) -> bool:
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "origin/main", "--", rel],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(proc.stdout.strip())


def test_core_files_has_no_retired_entries() -> None:
    module = _load()
    retired = [
        rel
        for rel in module.CORE_FILES.values()
        if "opc-closeout-crontab" in rel and "_archived" not in rel
    ]
    assert retired == [], f"CORE_FILES 仍要求已退役的 crontab: {retired}"
    assert "bin/gac/gac-ingest-legacy.py" not in module.CORE_FILES.values()


def test_main_repo_core_files_are_tracked_on_origin_main() -> None:
    """清单里每条主仓路径都必须在 origin/main 上被跟踪 —— 否则这条红是假的。"""
    module = _load()
    untracked = {
        name: rel
        for name, rel in module.CORE_FILES.items()
        if not rel.startswith("projects/") and not _tracked_on_main(rel)
    }
    assert untracked == {}, f"CORE_FILES 指向 origin/main 上不存在的主仓路径: {untracked}"
