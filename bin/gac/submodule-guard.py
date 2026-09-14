#!/usr/bin/env python3
"""
统一子模块守卫 — 检查子模块指针变更的 fast-forward 一致性.

使用:
  python bin/gac/submodule-guard.py --staged    # pre-commit 模式
  python bin/gac/submodule-guard.py --merge     # pre-merge-commit 模式 (跳过祖先检查)

退出码:
  0 = 合规
  1 = 不合规
"""

import argparse
import os
import subprocess
import sys


def get_submodules(root: str) -> list[str]:
    """从 .gitmodules 获取子模块路径."""
    gitmodules = os.path.join(root, ".gitmodules")
    if not os.path.exists(gitmodules):
        return []
    result = subprocess.run(
        ["git", "config", "--file", gitmodules, "--get-regexp", "path"],
        capture_output=True, text=True, check=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            paths.append(parts[1])
    return paths


def get_staged_submodules(root: str) -> list[str]:
    """获取 staged 的子模块变更 (仅返回真实子模块路径)."""
    # 获取所有已注册的子模块路径
    known_submodules = set(get_submodules(root))
    if not known_submodules:
        return []
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    )
    # 只返回属于已注册子模块的变更
    staged = []
    for line in result.stdout.splitlines():
        if not line.startswith("projects/"):
            continue
        # 匹配精确子模块路径或其子路径
        for sub in known_submodules:
            if line == sub or line.startswith(sub + "/"):
                staged.append(sub)
                break
    return list(set(staged))


def check_submodule(sub_path: str, root: str, merge_mode: bool) -> tuple[bool, str]:
    """检查单个子模块. 返回 (ok, message)."""
    full_path = os.path.join(root, sub_path)

    # 校验 1: 子模块目录必须已初始化
    if not os.path.exists(os.path.join(full_path, ".git")) and not os.path.isdir(os.path.join(full_path, ".git")):
        return False, f"{sub_path} 未初始化 (请先: git submodule update --init {sub_path})"

    # merge 模式下跳过祖先检查
    if merge_mode:
        return True, f"{sub_path} merge 模式, 跳过祖先检查"

    # 校验 2: fast-forward 一致性
    staged_result = subprocess.run(
        ["git", "ls-files", "--stage", "--", sub_path],
        capture_output=True, text=True, check=True,
    )
    staged_sha = ""
    for line in staged_result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "160000":
            staged_sha = parts[1]
            break

    base_result = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"HEAD:{sub_path}"],
        capture_output=True, text=True,
    )
    base_sha = base_result.stdout.strip()

    if not base_sha or not staged_sha or base_sha == staged_sha:
        return True, f"{sub_path} 无变更或新增"

    # 检查 fast-forward
    env = os.environ.copy()
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env.pop("GIT_INDEX_FILE", None)
    env.pop("GIT_OBJECT_DIRECTORY", None)
    env.pop("GIT_ALTERNATE_OBJECT_DIRECTORIES", None)

    anc_result = subprocess.run(
        ["git", "-C", full_path, "merge-base", "--is-ancestor", base_sha, staged_sha],
        capture_output=True, env=env,
    )

    if anc_result.returncode != 0:
        # 检查 known-debt 指纹
        import hashlib
        fingerprint = hashlib.sha256(f"{sub_path}\n{base_sha}\n{staged_sha}".encode()).hexdigest()[:16]
        debt_path = os.path.join(root, ".omo/_truth/registry/gate-known-debt.yaml")
        if os.path.exists(debt_path):
            with open(debt_path, encoding="utf-8") as f:
                if fingerprint in f.read():
                    return True, f"{sub_path} known-debt 豁免 ({fingerprint})"
        return False, f"{sub_path} 不是 fast-forward (base={base_sha[:12]}, staged={staged_sha[:12]})"

    return True, f"{sub_path} fast-forward 校验通过"


def main() -> int:
    parser = argparse.ArgumentParser(description="统一子模块守卫")
    parser.add_argument("--staged", action="store_true", help="检查 staged 子模块变更 (pre-commit)")
    parser.add_argument("--merge", action="store_true", help="merge 模式 (跳过祖先检查)")
    args = parser.parse_args()

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    merge_mode = args.merge

    if args.staged:
        submodules = get_staged_submodules(root)
    else:
        submodules = get_submodules(root)

    if not submodules:
        return 0

    failed = 0
    for sub in submodules:
        ok, msg = check_submodule(sub, root, merge_mode)
        if not ok:
            print(f"❌ {msg}", file=sys.stderr)
            failed += 1
        else:
            print(f"✅ {msg}", file=sys.stderr)

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
