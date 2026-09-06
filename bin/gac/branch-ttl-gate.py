#!/usr/bin/env python3
"""branch-ttl-gate.py — 分支 TTL 强制执行 (T10-127, 吸收 gac-worktree-prune.sh)

双段 TTL (policy 驱动): work/ 分支按 prefixes.work.ttl_days, agent/ 按 prefixes.agent.ttl_days。
默认 dry-run; --enforce 实删。删除时联动 D2 claim 清理。

用法:
  python3 bin/gac/branch-ttl-gate.py                 # dry-run
  python3 bin/gac/branch-ttl-gate.py --enforce       # 实删
  python3 bin/gac/branch-ttl-gate.py --submodules    # 扫描所有子模块
  python3 bin/gac/branch-ttl-gate.py --submodules --dry-run  # 子模块 dry-run
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


def _parse_submodule_paths() -> list[Path]:
    """从 .gitmodules 解析子模块路径。"""
    gitmodules = WS_ROOT / ".gitmodules"
    if not gitmodules.exists():
        return []
    paths: list[Path] = []
    for line in gitmodules.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("path ="):
            sub_path = line.split("=", 1)[1].strip()
            full = WS_ROOT / sub_path
            if full.exists() and (full / ".git").exists():
                paths.append(full)
    return paths


def _scan_repo_branches(repo_dir: Path, ttls: dict[str, int], now: float) -> dict[str, list[str]]:
    """扫描单个仓库的过期分支。"""
    stale: dict[str, list[str]] = {"work": [], "agent": []}
    branch_out = _git("branch", "--format=%(refname:short)", cwd=repo_dir)
    if not branch_out:
        return stale
    for branch_line in branch_out.splitlines():
        branch = branch_line.strip().lstrip("* ")
        if not branch or branch == "main":
            continue
        prefix = branch.split("/", 1)[0]
        if prefix not in ttls:
            continue
        last_commit = _git("log", "-1", "--format=%ct", branch, cwd=repo_dir)
        try:
            age_hours = (now - int(last_commit)) / 3600 if last_commit else 0
        except ValueError:
            continue
        if age_hours >= ttls[prefix]:
            stale[prefix].append(f"{branch} ({age_hours:.0f}h)")
    return stale


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--enforce", action="store_true", help="实删 (默认 dry-run)")
    ap.add_argument("--submodules", action="store_true",
                    help="同时扫描所有子模块的远程分支")
    ap.add_argument("--dry-run", action="store_true",
                    help="显式 dry-run (与 --submodules 搭配)")
    args = ap.parse_args()

    ttls = _load_ttls()
    enforce = args.enforce and not args.dry_run
    mode = "ENFORCE" if enforce else "DRY-RUN"
    print(f"=== Branch TTL Gate ({mode}) ttl={ttls} ===")
    now = time.time()

    # 主仓扫描
    stale_main: dict[str, list[str]] = {"work": [], "agent": []}
    while_fragments: list[str] = []
    for branch_line in _git("branch", "--format=%(refname:short)").splitlines():
        branch = branch_line.strip().lstrip("* ")
        if not branch or branch == "main":
            continue
        prefix = branch.split("/", 1)[0]
        if prefix not in ttls:
            continue
        if _git_pr_open(branch):
            continue
        last_commit = _git("log", "-1", "--format=%ct", branch)
        try:
            age_hours = (now - int(last_commit)) / 3600 if last_commit else 0
        except ValueError:
            continue
        if age_hours >= ttls[prefix]:
            stale_main[prefix].append(f"{branch} ({age_hours:.0f}h)")
            while_fragments.append(branch)

    total_main = sum(len(v) for v in stale_main.values())
    removed_main = 0
    for prefix, branches in stale_main.items():
        for b in branches:
            print(f"  过期: {b}")
            if enforce:
                session = b.rsplit("/", 1)[-1]
                wt = WS_ROOT.parent / f"ws-{session}"
                if wt.is_dir() and _git("status", "--porcelain", cwd=wt):
                    print(f"    ⏭  跳过 (worktree 有未提交改动): {b}")
                    continue
                subprocess.run(["git", "branch", "-D", b], capture_output=True)
                _claim_release(session)
                removed_main += 1
    print(f"  主仓: 发现 {total_main}, 实删 {removed_main}")

    # 子模块扫描
    total_sub = 0
    if args.submodules:
        sub_paths = _parse_submodule_paths()
        print(f"\n=== 子模块分支扫描 ({len(sub_paths)} repos) ===")
        for sub_dir in sub_paths:
            sub_name = sub_dir.relative_to(WS_ROOT)
            stale_sub = _scan_repo_branches(sub_dir, ttls, now)
            sub_total = sum(len(v) for v in stale_sub.values())
            total_sub += sub_total
            if sub_total > 0:
                print(f"  📁 {sub_name}:")
                for prefix, branches in stale_sub.items():
                    for b in branches:
                        print(f"    过期: {b}")
            else:
                print(f"  ✅ {sub_name}: no stale branches")

    grand_total = total_main + total_sub
    grand_removed = removed_main
    print(f"\n=== 结果: 主仓发现 {total_main} (实删 {removed_main}), "
          f"子模块发现 {total_sub}, 总计 {grand_total} ===")
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
