#!/usr/bin/env python3
"""debt-dashboard-mirror-sync — 刷新债务看板镜像并把它送回 origin/main。

`.omo/_control/debt-dashboard/current.yaml` 是 `.omo/debt/dashboard/current.yaml`
的 **git-tracked 镜像**（`projects/omo/src/omo/omo_debt_io.py` 的 `refresh_outputs`
同步写出），存在的理由是让 `meta-doctor` 的新鲜度心跳有东西可读。但 `omo debt`
的 post-hook 只负责刷新，**没有任何环节提交它** —— 于是 origin/main 上那份一直腐烂，
A2/A5 因此在每个干净检出（publisher、CI）里恒红：2026-10-20 实测镜像
`generated_at` 已 817 小时（SLA 336），而工作区里那份是 4 天前的未提交值。

`meta-doctor` 的心跳对 `absent` 是放行的，但 `drift-face-detector` 把缺失判成
`DASHBOARD-MISSING`（high）、`state-freshness-check` 也没把这条标 `optional` ——
所以「取消跟踪 + gitignore」不可行，镜像必须在场且新鲜。

本脚本补上缺失的那一环：刷新 → 只暂存镜像 → `chore(auto)` 提交 → push。

**为什么必须 push**：本机既有的 `chore(auto)` cron（mcptool-drift-report、
capability-registry）只做 commit，没有任何环节 push，而 fullrefresh 每 180s 会把
工作区 `reset --hard origin/main` —— 于是那些提交被反复抹掉。实证：
`mcptool-drift-report.yaml` 在 origin/main 上的最后提交停在 2026-09-25，
`capability-registry.yaml` 停在 2026-10-04。只 commit 不 push 等于没修。

用法:
    python3 bin/ssot/debt-dashboard-mirror-sync.py             # 刷新 + 提交 + push
    python3 bin/ssot/debt-dashboard-mirror-sync.py --dry-run   # 只报告将要做什么
    python3 bin/ssot/debt-dashboard-mirror-sync.py --no-push   # 只提交不 push

退出码: 0=已同步/无需变更/跳过; 1=错误 (fail-closed)。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bin" / "lib"))
from repo_root import code_root  # noqa: E402

MIRROR_REL = Path(".omo/_control/debt-dashboard/current.yaml")
COMMIT_MESSAGE = "chore(auto): debt dashboard mirror sync [skip ci]"
OMO_BIN = "projects/omo/.venv/bin/omo"


def _git(ws: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ws), capture_output=True,
                          text=True, check=check)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def refresh_mirror(ws: Path, now: str) -> None:
    """重生成镜像。omo 的 venv 入口，不经过 uv run 的解析开销。"""
    entry = ws / OMO_BIN
    if not entry.is_file():
        # 端到端实测 (2026-10-21, 浅克隆未 init 子模块): 入口缺失时 subprocess.run
        # 抛 FileNotFoundError, 未捕获 => cron 日志里留一整条 traceback, 而不是一句
        # 可操作的话。缺的就是这个 venv —— 说清楚怎么补。
        raise RuntimeError(
            f"omo venv entry missing: {entry} — run "
            f"`git submodule update --init projects/omo` in {ws}"
        )
    try:
        result = subprocess.run(
            [str(entry), "debt", "refresh", "--omo-dir", str(ws / ".omo"), "--now", now],
            cwd=str(ws / "projects" / "omo"), capture_output=True, text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"debt refresh could not start: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"debt refresh failed rc={result.returncode}: {(result.stderr or result.stdout)[-400:]}"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只报告, 不写盘不提交")
    ap.add_argument("--no-push", action="store_true", help="只提交, 不 push")
    args = ap.parse_args(argv)

    ws = code_root()
    if not (ws / ".git").exists():
        print(f"skip: {ws} is not a git checkout", file=sys.stderr)
        return 0

    branch = _git(ws, "symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.strip()
    if branch != "main":
        print(f"skip: HEAD is {branch or 'detached'}, not main")
        return 0

    if args.dry_run:
        print(f"would refresh {ws / MIRROR_REL} and commit {COMMIT_MESSAGE!r}")
        return 0

    refresh_mirror(ws, _now())
    _git(ws, "add", str(MIRROR_REL))

    staged = _git(ws, "diff", "--cached", "--quiet", check=False)
    if staged.returncode == 0:
        print("no change: mirror already current")
        return 0

    _git(ws, "commit", "-q", "-m", COMMIT_MESSAGE)
    print(f"committed: {MIRROR_REL}")

    if args.no_push:
        return 0
    pushed = _git(ws, "push", "origin", "main", check=False)
    if pushed.returncode != 0:
        # 非 fast-forward 被拒是安全结局 (工作区落后 origin/main); 其余按错误上报。
        print(f"push rc={pushed.returncode}: {(pushed.stderr or pushed.stdout)[-400:]}",
              file=sys.stderr)
        return 1
    print("pushed origin main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
