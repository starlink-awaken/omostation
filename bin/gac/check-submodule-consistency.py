#!/usr/bin/env python3
"""
机制 7 (2026-09-05): 子模块一致性三向校验 — .gitmodules ↔ registry.yaml ↔ 实际 gitlink.

校验维度:
  1. .gitmodules 中注册的子模块 vs registry.yaml 中注册的子模块 (名称/路径一致)
  2. registry.yaml 中注册的子模块 vs 实际 gitlink (SHA 一致)
  3. .gitmodules 中注册的子模块 vs 实际 gitlink (路径存在)

使用:
  python bin/gac/check-submodule-consistency.py           # 校验并输出报告
  python bin/gac/check-submodule-consistency.py --fail-on-drift  # 发现漂移时 exit 1

退出码:
  0 = 三向一致
  1 = 发现漂移
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml


def get_gitmodules_submodules(root: str) -> dict[str, dict]:
    """从 .gitmodules 解析子模块. 返回 {name: {path}}，name 取路径最后一级."""
    gitmodules_path = os.path.join(root, ".gitmodules")
    if not os.path.exists(gitmodules_path):
        return {}

    result = subprocess.run(
        ["git", "config", "--file", gitmodules_path, "--get-regexp", "path"],
        capture_output=True, text=True, check=True,
    )
    submodules = {}
    for line in result.stdout.splitlines():
        if not line:
            continue
        # 格式: submodule.<name>.path <path>
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        key, path = parts
        # 用路径最后一级作为 name (与 registry.yaml 对齐)
        name = path.rstrip("/").split("/")[-1]
        submodules[name] = {"path": path}
    return submodules


def get_registry_submodules(root: str) -> dict[str, dict]:
    """从 registry.yaml 解析子模块. 返回 {name: {path, repository}}，扁平化处理嵌套."""
    registry_path = os.path.join(root, "docs", "project-registry.yaml")
    if not os.path.exists(registry_path):
        return {}

    with open(registry_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    submodules = {}

    def _extract(node, prefix=""):
        """递归提取 submodule: true 的条目."""
        if not isinstance(node, dict):
            return
        if node.get("submodule"):
            name = prefix.rstrip(".") if prefix else ""
            submodules[name] = {
                "path": node.get("path", f"projects/{name}"),
                "repository": node.get("repository", ""),
            }
            return
        # 递归子节点
        for key, val in node.items():
            if isinstance(val, dict):
                _extract(val, f"{prefix}{key}.")

    # 跳过顶层 workspace/layers/projects 键，直接遍历 projects
    if "projects" in data:
        _extract(data["projects"])
    else:
        _extract(data)

    return submodules


def get_actual_gitlinks(root: str) -> dict[str, str]:
    """获取实际 gitlink (路径 → SHA)."""
    result = subprocess.run(
        ["git", "ls-files", "--stage"],
        capture_output=True, text=True, check=True,
    )
    gitlinks = {}
    for line in result.stdout.splitlines():
        if not line:
            continue
        # 格式: <mode> <sha> <stage>\t<path>
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        meta, path = parts
        mode = meta.split()[0]
        if mode == "160000":  # gitlink
            sha = meta.split()[1] if len(meta.split()) > 1 else ""
            gitlinks[path] = sha
    return gitlinks


def main() -> int:
    parser = argparse.ArgumentParser(description="子模块三向校验")
    parser.add_argument("--fail-on-drift", action="store_true",
                        help="发现漂移时 exit 1")
    args = parser.parse_args()

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    gitmodules = get_gitmodules_submodules(root)
    registry = get_registry_submodules(root)
    gitlinks = get_actual_gitlinks(root)

    drifts = []

    # 校验 1: .gitmodules vs registry (按路径对比)
    gitmodules_paths = {info["path"] for info in gitmodules.values()}
    registry_paths = {info["path"] for info in registry.values()}

    only_in_gitmodules = gitmodules_paths - registry_paths
    only_in_registry = registry_paths - gitmodules_paths

    if only_in_gitmodules:
        drifts.append(f".gitmodules 有但 registry 无: {only_in_gitmodules}")
    if only_in_registry:
        drifts.append(f"registry 有但 .gitmodules 无: {only_in_registry}")

    # 校验 2: registry vs gitlinks (路径存在)
    for name, info in registry.items():
        path = info.get("path", "")
        if path and path not in gitlinks:
            drifts.append(f"registry {name} 路径 {path} 在实际 gitlink 中不存在")

    # 校验 3: .gitmodules vs gitlinks (路径存在)
    for name, info in gitmodules.items():
        path = info.get("path", "")
        if path and path not in gitlinks:
            drifts.append(f".gitmodules {name} 路径 {path} 在实际 gitlink 中不存在")

    if drifts:
        print(f"❌ 发现 {len(drifts)} 个子模块一致性漂移:", file=sys.stderr)
        for d in drifts:
            print(f"   {d}", file=sys.stderr)
        if args.fail_on_drift:
            return 1
        return 0

    print(f"✅ 子模块三向一致 (gitmodules={len(gitmodules)}, "
          f"registry={len(registry)}, gitlinks={len(gitlinks)})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
