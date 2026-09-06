#!/usr/bin/env python3
"""
机制 22a (2026-09-05): 分支 TTL 过期策略执行器.

读取 .omo/_truth/registry/branch-ttl-policy.yaml 策略文件, 对过期分支执行
remind / auto-close / auto-delete 动作.

使用:
  python bin/gac/branch-ttl-gate.py              # 默认: 仅提醒 (advisory)
  python bin/gac/branch-ttl-gate.py --enforce    # 强制执行 (auto-delete)
  python bin/gac/branch-ttl-gate.py --json       # JSON 输出 (供 workflow)

退出码:
  0 = 无过期分支或仅提醒模式
  1 = 发现过期分支 (提醒模式) 或执行失败 (enforce 模式)
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


def load_policy(root: str) -> dict:
    """加载 TTL 策略文件."""
    # 先尝试新策略文件 (机制 22b)
    new_policy_path = os.path.join(root, ".omo/_truth/registry/branch-prefix-policy.yaml")
    if os.path.exists(new_policy_path):
        with open(new_policy_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        # 转换为新格式
        prefixes = data.get("prefixes", {})
        policies = []
        for prefix, info in prefixes.items():
            policies.append({
                "prefix": prefix + "/" if not prefix.endswith("-") else prefix,
                "ttl_days": info.get("ttl_days", 30),
                "action": info.get("action", "remind"),
            })
        return {
            "default": {"ttl_days": 30, "action": "remind"},
            "policies": policies,
            "immortal": data.get("immortal", []),
        }

    # 回退到旧策略文件
    policy_path = os.path.join(root, ".omo/_truth/registry/branch-ttl-policy.yaml")
    if not os.path.exists(policy_path):
        return {"default": {"ttl_days": 30, "action": "remind"}, "policies": [], "immortal": []}
    with open(policy_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_remote_branches(root: str) -> list[dict]:
    """获取远程分支的最后 commit 日期."""
    result = subprocess.run(
        ["git", "for-each-ref",
         "--format=%(refname:short)|%(committerdate:short)|%(committerdate:unix)",
         "refs/remotes/origin/"],
        capture_output=True, text=True, check=True,
        cwd=root,
    )
    branches = []
    for line in result.stdout.splitlines():
        if not line or "HEAD" in line:
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        ref, date_str, unix_str = parts
        if ref == "origin/main":
            continue
        try:
            ts = int(unix_str)
        except ValueError:
            continue
        branches.append({"ref": ref, "date": date_str, "ts": ts})
    return branches


def match_policy(ref: str, policies: list[dict]) -> dict:
    """匹配分支到策略."""
    for policy in policies:
        prefix = policy.get("prefix", "")
        if ref.startswith(prefix):
            return policy
    return {}


def find_open_pr(repo: str, branch: str) -> int | None:
    """查找分支的 open PR 编号."""
    result = subprocess.run(
        ["gh", "pr", "list", "--head", branch, "--state", "open",
         "--json", "number", "--jq", ".[0].number"],
        capture_output=True, text=True, cwd=repo,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            return int(result.stdout.strip())
        except ValueError:
            pass
    return None


def close_pr(repo: str, pr_number: int) -> bool:
    """关闭 PR."""
    result = subprocess.run(
        ["gh", "pr", "close", str(pr_number), "--comment", "[TTL] 分支过期自动关闭"],
        capture_output=True, cwd=repo,
    )
    return result.returncode == 0


def delete_remote_branch(repo: str, ref: str) -> bool:
    """删除远程分支."""
    # 提取分支名 (origin/xxx -> xxx)
    branch = ref.replace("origin/", "", 1) if ref.startswith("origin/") else ref
    result = subprocess.run(
        ["git", "push", "origin", "--delete", branch],
        capture_output=True, cwd=repo,
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="分支 TTL 过期策略")
    parser.add_argument("--enforce", action="store_true",
                        help="强制执行: 删除 auto-delete 分支, 关闭 auto-close PR")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    repo = root
    policy_data = load_policy(root)
    default_policy = policy_data.get("default", {"ttl_days": 30, "action": "remind"})
    policies = policy_data.get("policies", [])
    immortal = set(policy_data.get("immortal", []))

    branches = get_remote_branches(root)
    now_ts = datetime.now(timezone.utc).timestamp()

    expired = []
    fresh = []

    for b in branches:
        ref = b["ref"]
        if ref in immortal:
            continue

        # 匹配策略
        matched = match_policy(ref, policies)
        ttl_days = matched.get("ttl_days", default_policy.get("ttl_days", 30))
        action = matched.get("action", default_policy.get("action", "remind"))

        age_days = (now_ts - b["ts"]) / 86400
        is_expired = age_days > ttl_days

        record = {
            "ref": ref,
            "date": b["date"],
            "age_days": round(age_days, 1),
            "ttl_days": ttl_days,
            "action": action,
            "matched_prefix": matched.get("prefix", "(default)"),
        }

        if is_expired:
            # 查找 open PR
            pr = find_open_pr(repo, ref.replace("origin/", "", 1))
            record["open_pr"] = pr

            if args.enforce:
                if action == "auto-delete":
                    if pr:
                        record["result"] = f"closed PR #{pr}" if close_pr(repo, pr) else f"close PR #{pr} failed"
                    deleted = delete_remote_branch(repo, ref)
                    record["result"] = "deleted" if deleted else "delete failed"
                elif action == "auto-close" and pr:
                    record["result"] = f"closed PR #{pr}" if close_pr(repo, pr) else f"close PR #{pr} failed"
                else:
                    record["result"] = "reminded"
            else:
                record["result"] = "reminded"

            expired.append(record)
        else:
            fresh.append(record)

    if args.json:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "enforce": args.enforce,
            "expired_count": len(expired),
            "fresh_count": len(fresh),
            "expired": expired,
            "fresh": fresh,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0

    if expired:
        print(f"⚠️ 发现 {len(expired)} 个过期分支:", file=sys.stderr)
        for e in expired:
            pr_info = f" (PR #{e['open_pr']})" if e.get("open_pr") else ""
            print(f"   {e['ref']}  {e['age_days']}/{e['ttl_days']}天  "
                  f"action={e['action']}{pr_info} -> {e['result']}", file=sys.stderr)
        return 1

    print(f"✅ 所有 {len(fresh)} 个远程分支在 TTL 内", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
