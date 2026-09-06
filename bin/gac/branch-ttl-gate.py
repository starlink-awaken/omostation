#!/usr/bin/env python3
"""branch-ttl-gate.py — 分支 TTL 强制执行 (T10-127, 吸收 gac-worktree-prune.sh)

双段 TTL (policy 驱动): work/ 分支按 prefixes.work.ttl_days, agent/ 按 prefixes.agent.ttl_days。
默认 dry-run; --enforce 实删。删除时联动 D2 claim 清理。

用法:
  python3 bin/gac/branch-ttl-gate.py                 # dry-run
  python3 bin/gac/branch-ttl-gate.py --enforce       # 实删
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import yaml

WS_ROOT = Path(__file__).resolve().parents[2]
POLICY = WS_ROOT / ".omo/_truth/registry/branch-prefix-policy.yaml"


def _git(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd or WS_ROOT)
    return r.stdout.strip() if r.returncode == 0 else ""


def _load_ttls() -> dict[str, int]:
    """从 policy 读 ttl_days (小时化), 未知前缀回退默认。"""
    ttls = {"work": 168, "agent": 168}
    try:
        p = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
        for prefix in ("work", "agent"):
            days = (p.get("prefixes", {}) or {}).get(prefix, {}).get("ttl_days")
            if isinstance(days, int):
                ttls[prefix] = days * 24
    except Exception:
        pass
    return ttls


def _claim_release(session: str) -> None:
    cli = WS_ROOT / "bin/gac/swarm-discipline-cli.py"
    if cli.exists():
        subprocess.run(
            [sys.executable, str(cli), "branch-release", "--session", session],
            capture_output=True, timeout=30,
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--enforce", action="store_true", help="实删 (默认 dry-run)")
    args = ap.parse_args()

    ttls = _load_ttls()
    mode = "ENFORCE" if args.enforce else "DRY-RUN"
    print(f"=== Branch TTL Gate ({mode}) ttl={ttls} ===")
    now = time.time()
    stale: dict[str, list[str]] = {"work": [], "agent": []}
    while_fragments = []
    for branch_line in _git("branch", "--format=%(refname:short)").splitlines():
        branch = branch_line.strip().lstrip("* ")
        if not branch or branch == "main":
            continue
        prefix = branch.split("/", 1)[0]
        if prefix not in ttls:
            continue
        # open PR 保护
        if _git_pr_open(branch):
            continue
        last_commit = _git("log", "-1", "--format=%ct", branch)
        try:
            age_hours = (now - int(last_commit)) / 3600 if last_commit else 0
        except ValueError:
            continue
        if age_hours >= ttls[prefix]:
            stale[prefix].append(f"{branch} ({age_hours:.0f}h)")
            while_fragments.append(branch)

    removed = 0
    for prefix, branches in stale.items():
        for b in branches:
            print(f"  过期: {b}")
            if args.enforce:
                session = b.rsplit("/", 1)[-1]
                wt = WS_ROOT.parent / f"ws-{session}"
                if wt.is_dir() and _git("status", "--porcelain", cwd=wt):
                    print(f"    ⏭  跳过 (worktree 有未提交改动): {b}")
                    continue
                subprocess.run(["git", "branch", "-D", b], capture_output=True)
                _claim_release(session)
                removed += 1
    total = sum(len(v) for v in stale.values())
    print(f"=== 结果: 发现 {total}, 实删 {removed} ===")
    return 0


def _git_pr_open(branch: str) -> bool:
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number"],
            capture_output=True, text=True, timeout=30,
        )
        import json
        return bool(json.loads(out.stdout or "[]"))
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
