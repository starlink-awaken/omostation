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


def changed_submodule_paths(base: str) -> set[str]:
    """增量模式: 提取 git diff <base>..HEAD 中发生 gitlink 变化的 submodule 路径.

    治理整合 (2026-08-08): 全仓 reachability gate 会让任一并行 agent 的本地
    子模块 commit 未推送时冻结所有人的 push. 本地 pre-push 应只检查本次
    实际变更的 gitlink; CI full checkout 仍是全量最终守门员.
    .gitmodules 自身变化视为结构变更 → 回退全量检查 (防御).
    """
    # 基线不可解析 (拼错 / ref 未 fetch / 新克隆还没有 origin/main) 时必须回退全量。
    # 原实现返回 set(), 而空集会命中 check() 的 incremental-empty 快速路径
    # → 直接 ok=True, 报 "PASS (0 gitlinks)" 且 rc=0 —— 守门员一个都没查却宣称通过。
    # pre-push hook 传的正是 origin/main, 新克隆里它可能尚不存在。
    if run(["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"]).returncode != 0:
        sys.stderr.write(f"[reachability] 基线 {base} 不可解析, 回退全量检查\n")
        return set(submodule_paths())
    result = run(["git", "diff", "--name-only", base, "HEAD", "--", ".gitmodules", "projects/*"])
    if result.returncode != 0:
        sys.stderr.write(f"[reachability] git diff 相对 {base} 失败, 回退全量检查\n")
        return set(submodule_paths())
    changed = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if not changed:
        return set()
    if ".gitmodules" in changed:
        return set(submodule_paths())
    return {p for p in changed if p != ".gitmodules"}


def gitlink_sha(path: str, source: str) -> str | None:
    if source == "worktree":
        # An uninitialized submodule may still have an empty directory. Running
        # `git -C` there walks up into the superproject and returns the root
        # HEAD, which is not the gitlink. Fall back to the staged gitlink until
        # the submodule has its own Git marker.
        if not (WORKSPACE / path / ".git").exists():
            return gitlink_sha(path, "index")
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
    if not (submodule_dir / ".git").exists():
        return (
            True,
            "submodule not initialized (partial worktree) - CI full checkout will verify",
        )
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


def changed_submodules(base_ref: str, source: str) -> set[str] | None:
    """相对 base_ref 真正变了 gitlink 的子模块路径。

    base_ref 不可解析(未 fetch / 新克隆 / 分支不存在)时返回 None,
    调用方回退全量 —— 增量只用来提速, 绝不能因基线缺失而漏检。
    """
    if run(["git", "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"]).returncode != 0:
        return None
    changed: set[str] = set()
    for path in submodule_paths():
        base = run(["git", "ls-tree", base_ref, "--", path])
        base_sha = None
        if base.returncode == 0 and base.stdout.strip():
            meta, _sep, _name = base.stdout.partition("\t")
            parts = meta.split()
            if len(parts) >= 3 and parts[0] == "160000":
                base_sha = parts[2]
        if gitlink_sha(path, source) != base_sha:
            changed.add(path)
    return changed


def check(
    source: str, *, fetch: bool, skip_paths: set[str] | None = None, only_paths: set[str] | None = None
) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    checked = 0
    skipped = 0
    paths = submodule_paths()
    if only_paths is not None:
        # 增量模式: 只检查本次 diff 实际变化的 submodule
        paths = [p for p in paths if p in only_paths]
        if not paths:
            return {
                "ok": True,
                "source": source,
                "fetch": fetch,
                "checked": 0,
                "skipped": 0,
                "mode": "incremental-empty",
                "failures": [],
                "findings": [],
            }
    for path in paths:
        if skip_paths and path in skip_paths:
            skipped += 1
            continue
        if only_paths is not None and path not in only_paths:
            skipped += 1
            continue
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
        "skipped": skipped,
        "failures": failures,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify submodule gitlinks are reachable from origin")
    parser.add_argument("--source", choices=("head", "index", "worktree"), default="head")
    parser.add_argument("--fetch", action="store_true", help="Fetch origin branches before checking")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--skip", nargs="*", default=[], help="Submodule paths to skip (known false positives)")
    parser.add_argument("--skip-file", type=str, help="File with submodule paths to skip (one per line)")
    parser.add_argument(
        "--changed-from",
        type=str,
        default=None,
        metavar="REF",
        help="Incremental mode: only check submodules whose gitlink changed between <base>..HEAD "
        "(e.g. origin/main). Unchanged submodules are skipped — parallel-agent mid-flight state "
        "no longer blocks local pushes. CI full checkout (no flag) remains the full-coverage gate. "
        "基线不可解析时自动回退全量。",
    )
    args = parser.parse_args()

    # 防御: WORKSPACE 不存在 (worktree 被 cleanup 误清等) → 友好退出, 不 traceback
    # (2026-08-03: 曾因 worktree 被 cleanup 清理, subprocess cwd 失效 → FileNotFoundError)
    if not WORKSPACE.exists():
        sys.stderr.write(
            f"❌ WORKSPACE 不存在: {WORKSPACE}\n"
            f"   worktree 可能被外部清理 (cleanup TTL?). 中止 push 避免误判 unreachable.\n"
        )
        return 2

    skip_paths: set[str] = set(args.skip)
    if args.skip_file:
        skip_file = Path(args.skip_file)
        if skip_file.exists():
            skip_paths.update(
                line.strip() for line in skip_file.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            )

    only_paths: set[str] | None = None
    mode = "full"
    if args.changed_from:
        only_paths = changed_submodules(args.changed_from, args.source)
        if only_paths is None:
            sys.stderr.write(
                f"[reachability] 基线 {args.changed_from} 不可解析, 回退全量校验\n"
            )
            mode = "full (baseline unresolvable)"
        else:
            mode = f"changed-from {args.changed_from}"

    report = check(args.source, fetch=args.fetch, skip_paths=skip_paths, only_paths=only_paths)
    report["mode"] = mode
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["ok"]:
        skip_msg = f", skipped={report['skipped']}" if report["skipped"] else ""
        mode_msg = f", mode={mode}" if mode != "full" else ""
        print(
            f"submodule-reachability: PASS ({report['checked']} gitlinks, "
            f"source={args.source}{skip_msg}{mode_msg})"
        )
    else:
        for item in report["failures"]:
            print(f"{item['path']}: {item['sha'] or '-'} unreachable: {item['reason']}")
        print(f"submodule-reachability: FAIL ({len(report['failures'])} failures)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
