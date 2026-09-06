#!/usr/bin/env python3
"""Branch naming gate — 校验分支名符合 branch-prefix-policy.yaml 命名 SSOT.

被 hook-runner 以 blocking 引用 (manifest: branch-naming, pre-commit/pre-push/pre-rebase 段).
此前为 placeholder 空壳 (exit 0 零校验); 本实现恢复真实校验:

- 读 --policy 的 naming 段 (每个前缀一条正则) + immortal 段 (放行列表)
- --branch 匹配任一 naming 正则 → PASS
- --branch 命中 immortal (origin/main, origin/HEAD) → PASS
- 否则 → FAIL (exit 1), 列出允许的前缀

用法:
    check-branch-naming.py --branch <branch> --policy <path>
"""

import argparse
import re
import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERR = 2


def load_policy(policy_path: str) -> dict:
    """读取 branch-prefix-policy.yaml, 返回 {naming: {prefix: regex}, immortal: [...]}."""
    import yaml

    path = Path(policy_path)
    if not path.is_file():
        print(f"[check-branch-naming] ❌ policy 文件不存在: {path}", file=sys.stderr)
        sys.exit(EXIT_ERR)

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 — yaml 解析失败统一报错
        print(f"[check-branch-naming] ❌ policy 解析失败: {exc}", file=sys.stderr)
        sys.exit(EXIT_ERR)

    naming = data.get("naming") or {}
    if not isinstance(naming, dict) or not naming:
        print(f"[check-branch-naming] ❌ policy 缺少 naming 段: {path}", file=sys.stderr)
        sys.exit(EXIT_ERR)

    compiled = {}
    for prefix, pattern in naming.items():
        if not isinstance(pattern, str):
            print(f"[check-branch-naming] ❌ naming.{prefix} 不是正则字符串", file=sys.stderr)
            sys.exit(EXIT_ERR)
        try:
            compiled[prefix] = re.compile(pattern)
        except re.error as exc:
            print(f"[check-branch-naming] ❌ naming.{prefix} 正则无效 ({pattern!r}): {exc}", file=sys.stderr)
            sys.exit(EXIT_ERR)

    immortal = data.get("immortal") or []
    return {"naming": compiled, "immortal": list(immortal)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Branch naming gate (policy SSOT)")
    parser.add_argument("--branch", required=True, help="分支名 (git rev-parse --abbrev-ref HEAD)")
    parser.add_argument("--policy", required=True, help="branch-prefix-policy.yaml 路径")
    args = parser.parse_args()

    policy = load_policy(args.policy)
    branch = args.branch.strip()

    # immortal 放行 (origin/main, origin/HEAD)
    if branch in policy["immortal"]:
        print(f"✓ branch naming: {branch} (immortal 放行)")
        return EXIT_PASS

    matched = None
    for prefix, regex in policy["naming"].items():
        if regex.fullmatch(branch):
            matched = prefix
            break

    if matched:
        print(f"✓ branch naming: {branch} (前缀 {matched})")
        return EXIT_PASS

    allowed = ", ".join(sorted(policy["naming"].keys()))
    print(f"❌ branch naming: {branch} 不符合分支前缀策略", file=sys.stderr)
    print(f"   允许前缀: {allowed}", file=sys.stderr)
    print("   示例: work/my-topic, fix/xxx, chore/yyy, feat/zzz, temp-xxx, pr/xxx", file=sys.stderr)
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
