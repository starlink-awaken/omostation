#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 分支命名合规校验 — 强制命名空间隔离.

使用:
  python bin/gac/check-branch-naming.py --branch work/test --policy .omo/_truth/registry/branch-prefix-policy.yaml
  python bin/gac/check-branch-naming.py --list --policy .omo/_truth/registry/branch-prefix-policy.yaml

退出码:
  0 = 合规 (或 main/HEAD)
  1 = 不合规
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml


def load_policy(policy_path: str) -> dict:
    """加载策略文件."""
    if not os.path.exists(policy_path):
        print(f"⚠️ 策略文件不存在: {policy_path}", file=sys.stderr)
        return {}
    with open(policy_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def check_branch(branch: str, policy: dict) -> tuple[bool, str, dict]:
    """检查分支名是否合规. 返回 (ok, matched_prefix, prefix_info)."""
    naming = policy.get("naming", {})
    prefixes = policy.get("prefixes", {})
    immortal = set(policy.get("immortal", []))

    # 永不过期的分支
    if branch in immortal or branch in ("main", "HEAD", ""):
        return True, "main", {}

    # 精确匹配 main
    if re.match(naming.get("main", "^main$"), branch):
        return True, "main", {}

    # 逐前缀匹配
    for prefix, info in prefixes.items():
        pattern = info.get("pattern", "")
        if pattern and re.match(pattern, branch):
            return True, prefix, info

    # 全不匹配
    return False, "", {}


def list_prefixes(policy: dict) -> list[dict]:
    """列出所有可用前缀."""
    prefixes = policy.get("prefixes", {})
    result = []
    for prefix, info in prefixes.items():
        result.append({
            "prefix": prefix,
            "pattern": info.get("pattern", ""),
            "ttl_days": info.get("ttl_days", 30),
            "action": info.get("action", "remind"),
            "creators": info.get("creators", []),
            "description": info.get("description", ""),
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="分支命名合规校验")
    parser.add_argument("--branch", type=str, help="待检查的分支名")
    parser.add_argument("--policy", type=str, required=True, help="策略文件路径")
    parser.add_argument("--list", action="store_true", help="列出所有可用前缀")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    policy = load_policy(args.policy)

    if args.list:
        prefixes = list_prefixes(policy)
        if args.json:
            print(json.dumps({"available_prefixes": prefixes}, indent=2, ensure_ascii=False))
        else:
            print("可用前缀:")
            for p in prefixes:
                print(f"  {p['prefix']:10s}  pattern={p['pattern']}  ttl={p['ttl_days']}d  creators={p['creators']}  {p['description']}")
        return 0

    if not args.branch:
        parser.error("--branch or --list is required")

    ok, matched, info = check_branch(args.branch, policy)

    if args.json:
        result = {
            "branch": args.branch,
            "ok": ok,
            "matched_prefix": matched,
            "info": info,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if ok else 1

    if ok:
        print(f"✅ 分支 '{args.branch}' 合规 (前缀: {matched})", file=sys.stderr)
        return 0

    # 不合规
    print(f"❌ 分支 '{args.branch}' 不符合前缀策略", file=sys.stderr)
    print("可用前缀:", file=sys.stderr)
    for prefix, pinfo in policy.get("prefixes", {}).items():
        print(f"  {prefix:10s}  {pinfo.get('pattern', '')}  ({pinfo.get('description', '')})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
