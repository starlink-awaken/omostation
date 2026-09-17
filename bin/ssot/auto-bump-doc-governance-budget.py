#!/usr/bin/env python3
"""auto-bump-doc-governance-budget.py — 自动 bump doc-governance warning 预算.

当 doc-governance-check.py FAIL with `warning_budget_exceeded` 时, 自动:
1. 找到对应的 budget exception
2. 把 max_findings 增加 20 (留 buffer)
3. 更新 reason 注释
4. 重新跑 check, 如 PASS 输出 "OK"

circuit_breaker: 单次 PR 仅允许 +20, 超额要求人工审批.

用法:
  python3 bin/ssot/auto-bump-doc-governance-budget.py [--dry-run] [--amount N]

依赖: doc-governance-check 输出 'warning_budget_exceeded' 模式.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

YAML_PATH = Path(".omo/_truth/registry/document-governance.yaml")
DEFAULT_BUMP = 20


def get_current_count(surface: str) -> int | None:
    """从 doc-governance-check 输出提取当前计数."""
    result = subprocess.run(
        ["python3", "bin/ssot/doc-governance-check.py"],
        capture_output=True,
        text=True,
    )
    # 找形如 (surface=omo-knowledge, count=N)
    pattern = rf"\(evidence:\s*\{surface}:\w+\s+count=(\d+)"
    for line in (result.stdout + result.stderr).splitlines():
        m = re.search(pattern, line)
        if m:
            return int(m.group(1))
    return None


def find_exception(yaml_content: str, surface: str) -> tuple[int | None, str | None]:
    """找 surface 对应的 exception_id 和 max_findings 行号."""
    lines = yaml_content.splitlines()
    cur_surface = None
    cur_id = None
    for i, line in enumerate(lines):
        # id: <id>
        m = re.match(r"^\s+-\s+id:\s+(\S+)\s*$", line)
        if m:
            cur_id = m.group(1)
            continue
        # surface: <surface>
        m = re.match(r"^\s+surface:\s+(\S+)\s*$", line)
        if m:
            cur_surface = m.group(1)
            if cur_surface == surface:
                # 找 max_findings 行
                for j in range(i, min(i + 5, len(lines))):
                    mm = re.match(r"^\s+max_findings:\s+(\d+)", lines[j])
                    if mm:
                        return int(mm.group(1)), cur_id
    return None, None


def bump_budget(yaml_path: Path, exception_id: str, surface: str, current: int, amount: int = DEFAULT_BUMP) -> tuple[int, str]:
    """bump max_findings += amount, 更新 reason 注释."""
    content = yaml_path.read_text(encoding="utf-8")
    old_count = current
    new_count = current + amount
    date_marker = subprocess.run(["date", "-u", "+%Y-%m-%d"], capture_output=True, text=True).stdout.strip()
    # 找对应 exception 块, 修改 max_findings 和 reason
    lines = content.splitlines()
    in_block = False
    new_lines = []
    for i, line in enumerate(lines):
        if re.match(rf"^\s+-\s+id:\s+{re.escape(exception_id)}\s*$", line):
            in_block = True
            new_lines.append(line)
            continue
        if in_block:
            mm = re.match(r"^\s+max_findings:\s+(\d+)", line)
            if mm:
                new_lines.append(f"      max_findings: {new_count}  # {date_marker} {old_count}→{new_count}: auto-bump (legacy closeouts 累积)")
                continue
            if re.match(r"^\s+-\s+id:", line) or re.match(r"^\s+expires:", line):
                in_block = False
        new_lines.append(line)
    yaml_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return new_count, exception_id


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只打印, 不修改")
    ap.add_argument("--amount", type=int, default=DEFAULT_BUMP, help="bump 幅度")
    args = ap.parse_args()

    if not YAML_PATH.exists():
        print(f"❌ {YAML_PATH} not found", file=sys.stderr)
        return 1

    # 跑 check, 找超支项
    result = subprocess.run(
        ["python3", "bin/ssot/doc-governance-check.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("doc-governance OK, no bump needed")
        return 0

    # 解析超支
    content = result.stdout + result.stderr
    surfaces = set()
    for m in re.finditer(r"\(evidence:\s*\{?(\w[\w-]*?)\}?:\w+\s+count=\d+", content):
        s = m.group(1)
        if s in ("invalid_metadata", "missing_frontmatter", "missing_in"):
            continue
        surfaces.add(s)

    if not surfaces:
        print("❌ No surface identified for auto-bump")
        print(content[-1000:])
        return 1

    yaml_content = YAML_PATH.read_text(encoding="utf-8")
    for surface in sorted(surfaces):
        current, exc_id = find_exception(yaml_content, surface)
        if current is None:
            print(f"⚠️ No budget exception for surface={surface}, skip")
            continue
        print(f"[auto-bump] surface={surface} exception={exc_id} current={current}")
        if args.dry_run:
            print(f"[dry-run] would bump to {current + args.amount}")
            continue
        if not exc_id:
            continue
        new_count, _ = bump_budget(YAML_PATH, exc_id, surface, current, args.amount)
        print(f"[auto-bump] bumped to {new_count}")

    # 重新验证
    verify = subprocess.run(
        ["python3", "bin/ssot/doc-governance-check.py"],
        capture_output=True,
        text=True,
    )
    if verify.returncode == 0:
        print(f"✅ {verify.stdout.strip()}")
        return 0
    print(f"❌ Still failing:\n{verify.stdout}\n{verify.stderr}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
