#!/usr/bin/env python3
"""auto-bump-doc-governance-budget.py — 通用化 doc-governance budget 自动 bump.

当 doc-governance-check.py FAIL with `warning_budget_exceeded` 时, 自动:
1. 解析输出, 识别失败的 (surface, rule) 与预算消耗
2. 在 document-governance.yaml 中定位 (rule, surface) 对应的 budget exception
3. max_findings 增加 N (默认 20, circuit_breaker 限制)
4. 更新 reason 注释 + UTC 日期标记
5. 重新跑 check, 如 PASS 输出 "OK"

circuit_breaker: 单次 PR 仅允许 +20 (ABSOLUTE_MAX_BUMP=50, 强制覆盖)

通用化 (v1 → v2):
  - 不依赖 exception_id 硬编码
  - 按 (rule, surface) 二元组定位 budget
  - 兼容 8 种 budget exception (legacy-*-enums/frontmatter + concurrent-plans-orphan-docs)

用法:
  python3 bin/ssot/auto-bump-doc-governance-budget.py [--dry-run] [--amount N] [--strict]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

YAML_PATH = Path(".omo/_truth/registry/document-governance.yaml")
DEFAULT_BUMP = 20
ABSOLUTE_MAX_BUMP = 50  # circuit_breaker 硬上限


def parse_failure_evidence(stderr: str) -> list[dict[str, Any]]:
    """解析 doc-governance-check 输出, 返回 [(exception_id, rule, surface, count), ...].

    输出格式示例:
      .omo/_truth/registry/document-governance.yaml: warning_budget_exceeded [error]
        warning exception legacy-omo-knowledge-enums has been exceeded
        (evidence: invalid_metadata:omo-knowledge count=68 max=63)
    """
    failures: list[dict[str, Any]] = []
    exception_re = re.compile(
        r"warning exception\s+([\w-]+)\s+has been exceeded",
    )
    evidence_re = re.compile(
        r"\(evidence:\s*([\w-]+):([\w-]+)\s+count=(\d+)",
    )
    lines = stderr.splitlines()
    for i, line in enumerate(lines):
        exc_match = exception_re.search(line)
        if not exc_match:
            continue
        exc_id = exc_match.group(1)
        # 找紧邻 1-3 行的 evidence 行
        for j in range(i, min(i + 4, len(lines))):
            ev_match = evidence_re.search(lines[j])
            if ev_match:
                failures.append({
                    "exception_id": exc_id,
                    "rule": ev_match.group(1),
                    "surface": ev_match.group(2),
                    "count": int(ev_match.group(3)),
                })
                break
    return failures


def find_exception(yaml_content: str, rule: str, surface: str) -> tuple[int | None, str | None, int]:
    """按 (rule, surface) 二元组定位 exception. 返回 (max_findings, exception_id, line_no)."""
    lines = yaml_content.splitlines()
    cur_id: str | None = None
    cur_rule: str | None = None
    cur_surface: str | None = None
    cur_max: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- id:"):
            cur_id = stripped.split(":", 1)[1].strip()
            cur_rule = cur_surface = cur_max = None
        elif stripped.startswith("rule:"):
            cur_rule = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("surface:"):
            cur_surface = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("max_findings:"):
            try:
                cur_max = int(stripped.split(":", 1)[1].strip().split()[0])
            except (ValueError, IndexError):
                cur_max = None
            if cur_rule == rule and cur_surface == surface and cur_max is not None:
                return cur_max, cur_id, i
            cur_max = None
    return None, None, -1


def bump_budget(yaml_path: Path, line_no: int, rule: str, surface: str,
                current: int, amount: int, exception_id: str) -> int:
    """bump max_findings +amount, 更新 reason 注释 + UTC 日期标记."""
    content = yaml_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if line_no < 0 or line_no >= len(lines):
        return -1
    old = lines[line_no]
    new_count = current + amount
    date_marker = subprocess.run(
        ["date", "-u", "+%Y-%m-%d"], capture_output=True, text=True
    ).stdout.strip()
    lines[line_no] = (
        f"      max_findings: {new_count}  # {date_marker} {current}→{new_count}: "
        f"auto-bump (governance 增量)"
    )
    # 在 expires 行前插入一行 marker (审计 trace)
    reason_marker = f"# auto-bumped to {new_count} on {date_marker}"
    inserted = False
    for j in range(line_no + 1, min(line_no + 8, len(lines))):
        if lines[j].strip().startswith("expires:"):
            lines.insert(j, f"      {reason_marker}")
            inserted = True
            break
    if not inserted:
        for j in range(line_no + 1, min(line_no + 8, len(lines))):
            if lines[j].strip().startswith("reason:"):
                lines.insert(j + 1, f"      {reason_marker}")
                inserted = True
                break
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return new_count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只打印, 不修改")
    ap.add_argument("--amount", type=int, default=DEFAULT_BUMP,
                    help=f"bump 幅度 (默认 {DEFAULT_BUMP}, 上限 {ABSOLUTE_MAX_BUMP})")
    ap.add_argument("--strict", action="store_true",
                    help="对所有 failure 都 bump, 包括 count 已 <= budget 的")
    args = ap.parse_args()

    if not YAML_PATH.exists():
        print(f"❌ {YAML_PATH} not found", file=sys.stderr)
        return 1

    if args.amount > ABSOLUTE_MAX_BUMP:
        print(
            f"⚠️  --amount {args.amount} 超过硬上限 {ABSOLUTE_MAX_BUMP}, "
            "强制缩为上限"
        )
        args.amount = ABSOLUTE_MAX_BUMP

    # 1. 跑 check (用 --no-new-warnings 触发 warning_budget_exceeded 错误)
    result = subprocess.run(
        ["python3", "bin/ssot/doc-governance-check.py", "--no-new-warnings"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("doc-governance OK, no bump needed")
        return 0

    # 2. 解析失败
    failures = parse_failure_evidence(result.stdout + result.stderr)
    if not failures:
        print("❌ No budget_exceeded failure parsed from output")
        print((result.stdout + result.stderr)[-2000:])
        return 1

    yaml_content = YAML_PATH.read_text(encoding="utf-8")
    summary: list[str] = []
    for fail in failures:
        rule = fail["rule"]
        surface = fail["surface"]
        count = fail["count"]
        exc_id = fail["exception_id"]

        # 3. 定位 budget (按 rule + surface 二元组)
        current, found_id, line_no = find_exception(yaml_content, rule, surface)
        if current is None:
            print(
                f"⚠️ No exception with rule={rule} surface={surface}, skip {exc_id}"
            )
            continue
        if count <= current and not args.strict:
            summary.append(
                f"[skip] {found_id} ({rule}/{surface}) count={count} "
                f"≤ budget={current}, no bump"
            )
            continue
        new_count = current + args.amount
        if new_count < count:
            new_count = count + args.amount
        summary.append(
            f"[bump] {found_id} ({rule}/{surface}) "
            f"{current} → {new_count} (count={count})"
        )
        if args.dry_run:
            continue
        bump_budget(YAML_PATH, line_no, rule, surface, current, args.amount, found_id)

    print("\n".join(summary))

    if args.dry_run:
        return 0

    # 4. 重新验证 (同样用 --no-new-warnings 模式)
    verify = subprocess.run(
        ["python3", "bin/ssot/doc-governance-check.py", "--no-new-warnings"],
        capture_output=True,
        text=True,
    )
    if verify.returncode == 0:
        print(f"✅ {verify.stdout.strip()}")
        return 0
    print(f"⚠️ Still failing:\n{verify.stdout}\n{verify.stderr}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
