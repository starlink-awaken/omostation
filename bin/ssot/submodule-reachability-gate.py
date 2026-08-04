#!/usr/bin/env python3
"""Verify that root gitlinks point to commits reachable from submodule remotes."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2]

# 治本 followup E (2026-07-04): pre-push hook 跑时 git 设 GIT_DIR/GIT_WORK_TREE 指向主仓,
# 泄漏到 subprocess 的 `git -C <submodule>` → 读主仓而非子模块 → fetch/branch --contains 错乱 → 全误报 unreachable
# (实测: 干净环境 17 gitlinks PASS / 模拟 hook 17 FAIL, 同 followup C sync GIT_DIR 病根).
# pop 后 subprocess 继承干净环境, git -C <submodule> 读子模块自己的 .git.
for _env in ("GIT_DIR", "GIT_WORK_TREE", "GIT_QUARANTINE_PATH"):
    os.environ.pop(_env, None)


def run(cmd: list[str], *, cwd: Path = WORKSPACE, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def submodule_paths() -> list[str]:
    result = run(["git", "config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"])
    if result.returncode != 0:
        return []
    return [line.split(maxsplit=1)[1] for line in result.stdout.splitlines() if line.strip()]


def gitlink_sha(path: str, source: str) -> str | None:
    if source == "worktree":
        result = run(["git", "-C", path, "rev-parse", "HEAD"])
        return result.stdout.strip() if result.returncode == 0 else None
    if source == "index":
        result = run(["git", "ls-files", "-s", "--", path])
        if result.returncode != 0 or not result.stdout.strip():
            return None
        parts = result.stdout.split()
        return parts[1] if len(parts) >= 2 and parts[0] == "160000" else None

    result = run(["git", "ls-tree", "HEAD", "--", path])
    if result.returncode != 0 or not result.stdout.strip():
        return None
    meta, _sep, _name = result.stdout.partition("\t")
    parts = meta.split()
    return parts[2] if len(parts) >= 3 and parts[0] == "160000" else None


def remote_contains(path: str, sha: str, *, fetch: bool) -> tuple[bool, str]:
    submodule_dir = WORKSPACE / path
    if not submodule_dir.exists():
        return False, "submodule working tree missing"
    # G1 (P79, 2026-08-04): partial worktree 降级 — 子模块目录存在但非有效 git repo
    # (PASW ISOLATED partial init / 新建 worktree 未 init) → 本地 push 降级 warning 不 block.
    # 治本 #907 35+ iteration: partial worktree reachability gate false-positive 死路
    # (init 子模块超时 10min, escape hatch 不覆盖 reachability).
    # 安全网: CI (full checkout, 子模块全 init) 跑同一 gate 正常验证, 是最终守门员.
    init_check = run(
        ["git", "rev-parse", "--is-inside-work-tree"], cwd=submodule_dir
    )
    # stdout 检查覆盖失败 (空) + false 两种非 init 情况, returncode 冗余
    if init_check.stdout.strip() != "true":
        return (
            True,
            "submodule not initialized (partial worktree) - CI full checkout will verify",
        )

    if fetch:
        # CI actions/checkout depth=1 → submodule shallow → 非 HEAD SHA 不在浅历史
        # → branch --contains 误报 unreachable (#907 cockpit 0fa09c6 实证可达但 gate fail).
        # shallow repo 先 --unshallow 拿 full history; 失败回退 normal fetch.
        # 单 heads refspec (heads→remotes/origin/*, 不覆盖本地 checked-out refs/heads/main).
        # 配合 unshallow (C 层) 拿全 main 历史 — unshallow 后 heads refs 已含所有可达 SHA.
        refspec = "+refs/heads/*:refs/remotes/origin/*"
        shallow_res = run(["git", "rev-parse", "--is-shallow-repository"], cwd=submodule_dir)
        is_shallow = shallow_res.stdout.strip() == "true"
        if is_shallow:
            fetch_result = run(["git", "fetch", "--quiet", "--unshallow", "origin", refspec], cwd=submodule_dir)
            if fetch_result.returncode != 0:
                fetch_result = run(["git", "fetch", "--quiet", "origin", refspec], cwd=submodule_dir)
        else:
            fetch_result = run(["git", "fetch", "--quiet", "origin", refspec], cwd=submodule_dir)
        if fetch_result.returncode != 0:
            return False, f"fetch failed: {fetch_result.stderr.strip()}"

    contains = run(["git", "branch", "-r", "--contains", sha], cwd=submodule_dir)
    branches = [
        line.strip()
        for line in contains.stdout.splitlines()
        if line.strip() and "origin/HEAD" not in line
    ]
    if branches:
        return True, ", ".join(branches[:3])
    return False, "not contained in fetched origin branches"


def check(source: str, *, fetch: bool) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    checked = 0
    for path in submodule_paths():
        sha = gitlink_sha(path, source)
        if sha is None:
            findings.append({"path": path, "sha": None, "ok": False, "reason": f"no {source} gitlink"})
            continue
        checked += 1
        ok, detail = remote_contains(path, sha, fetch=fetch)
        findings.append({"path": path, "sha": sha, "ok": ok, "reason": detail})
    failures = [item for item in findings if not item["ok"]]
    return {
        "ok": not failures,
        "source": source,
        "fetch": fetch,
        "checked": checked,
        "failures": failures,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify submodule gitlinks are reachable from origin")
    parser.add_argument("--source", choices=("head", "index", "worktree"), default="head")
    parser.add_argument("--fetch", action="store_true", help="Fetch origin branches before checking")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    # 防御: WORKSPACE 不存在 (worktree 被 cleanup 误清等) → 友好退出, 不 traceback
    # (2026-08-03: 曾因 worktree 被 cleanup 清理, subprocess cwd 失效 → FileNotFoundError)
    if not WORKSPACE.exists():
        sys.stderr.write(
            f"❌ WORKSPACE 不存在: {WORKSPACE}\n"
            f"   worktree 可能被外部清理 (cleanup TTL?). 中止 push 避免误判 unreachable.\n"
        )
        return 2

    report = check(args.source, fetch=args.fetch)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["ok"]:
        print(f"submodule-reachability: PASS ({report['checked']} gitlinks, source={args.source})")
    else:
        for item in report["failures"]:
            print(f"{item['path']}: {item['sha'] or '-'} unreachable: {item['reason']}")
        print(f"submodule-reachability: FAIL ({len(report['failures'])} failures)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
