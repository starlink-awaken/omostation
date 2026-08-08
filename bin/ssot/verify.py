#!/usr/bin/env python3
"""Task Verify -- 任务完成验证门禁 + 能力缺口清零率 (统一验证入口).

合并 gap-verify + task-verify: 两种模式共享同一个扫描逻辑和 dataclass.
  - --mode task (默认): 门禁检查 -- 防止虚假完成 (DoD: code + evidence + dry-run)
  - --mode gap: 清零率跟踪 -- 按 phase/priority 分组的 resolved/total
  - --mode all: 两者都输出

Usage:
  python3 bin/ssot/verify.py                          # 门禁 (等价于之前的 task-verify)
  python3 bin/ssot/verify.py --mode gap               # 清零率 (等价于之前的 gap-verify)
  python3 bin/ssot/verify.py --mode gap --verbose     # 每个 gap 的明细
  python3 bin/ssot/verify.py --mode all --json        # 完整 JSON 输出
  python3 bin/ssot/verify.py --strict                 # 强制跑每个 verification_cmd
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from _shared import ROOT, check_evidence, is_runnable_cmd, load_yaml, run_verification


@dataclass
class TaskCheck:
    id: str
    title: str
    phase: str = "?"
    priority: str = "?"
    source: str = "gap-item"
    state: str = "open"
    evidence_count: int = 0
    evidence_ok: bool = False
    verification_pass: bool | None = None
    verification_error: str | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def is_completed(self) -> bool:
        return self.state in ("resolved", "completed")

    @property
    def is_verified(self) -> bool:
        """真完成 = 状态完成 + evidence 存在."""
        return self.is_completed and self.evidence_ok


def scan(root: Path | None = None, strict: bool = False) -> list[TaskCheck]:
    """Scan all gap-items and return TaskCheck list."""
    root = root or ROOT
    checks: list[TaskCheck] = []
    gap_dir = root / ".omo" / "debt" / "gap-items"
    if not gap_dir.is_dir():
        return checks
    for path in sorted(gap_dir.glob("*.yaml")):
        if path.name == "TEMPLATE.yaml":
            continue
        data = load_yaml(path)
        state = str(data.get("lifecycle_state", "open"))
        ev_count, ev_ok = check_evidence(data, root)
        check = TaskCheck(
            id=str(data.get("id", path.stem)),
            title=str(data.get("title", "")),
            phase=str(data.get("phase", "?")),
            priority=str(data.get("priority", "?")),
            source="gap-item",
            state=state,
            evidence_count=ev_count,
            evidence_ok=ev_ok,
        )
        cmd = data.get("verification_cmd") or ""
        if is_runnable_cmd(cmd) and strict:
            check.verification_pass, check.verification_error = run_verification(cmd, root)
        if check.is_completed and not check.evidence_ok:
            check.issues.append("resolved 但 evidence_refs 为空或文件不存在 → 虚假完成")
        if check.verification_pass is False:
            check.issues.append(f"verification_cmd 失败: {check.verification_error}")
        checks.append(check)
    return checks


def _count_by(key_fn, checks) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in checks:
        k = key_fn(c)
        out[k] = out.get(k, 0) + 1
    return out


def build_result(checks: list[TaskCheck], mode: str) -> dict:
    """Build output dict from checks, varying fields by mode."""
    completed = [c for c in checks if c.is_completed]
    verified = [c for c in completed if c.is_verified]
    unverified = [c for c in completed if not c.is_verified]
    open_tasks = [c for c in checks if not c.is_completed]
    red_flags = [c.id for c in unverified]
    verification_failed = [c.id for c in checks if c.verification_pass is False]

    result: dict = {
        "schema": "verify/v1",
        "mode": mode,
        "total": len(checks),
        "completed": len(completed),
        "verified": len(verified),
        "unverified": len(unverified),
        "open": len(open_tasks),
        "verification_rate": round(len(verified) / len(completed), 2) if completed else 1.0,
        "red_flags": red_flags,
        "verification_failed": verification_failed,
        "tasks": [c.__dict__ for c in checks],
    }

    # gap-specific fields
    resolved = [c for c in checks if c.state == "resolved"]
    result["resolved"] = len(resolved)
    result["clearance_rate"] = round(len(resolved) / len(checks), 2) if checks else 0.0
    result["by_phase"] = _count_by(lambda c: c.phase, checks)
    result["by_priority"] = _count_by(lambda c: c.priority, checks)

    return result


def print_task_mode(result: dict) -> int:
    """Print output for --mode task (门禁检查风格)."""
    print(f"Task Verify: {result['verified']}/{result['completed']} completed-verified "
          f"(验证率 {result['verification_rate']:.0%})")
    print(f"  completed: {result['completed']}  verified: {result['verified']}  "
          f"unverified: {result['unverified']}  open: {result['open']}")

    if result["unverified"]:
        print(f"\n⚠️ RED FLAG -- {result['unverified']} tasks marked completed but NO evidence:")
        for c in result["tasks"]:
            if c["id"] in result["red_flags"]:
                print(f"  ❌ {c['id']}: {c['title']}")
                for issue in c["issues"]:
                    print(f"     → {issue}")

    if result["unverified"]:
        print("\n→ 门禁失败: 存在虚假完成 (resolved 无 evidence). 需补 evidence 或降级为 open.")
        return 1
    print("\n✅ 门禁通过: 所有 completed 任务都有 evidence.")
    return 0


def print_gap_mode(result: dict, verbose: bool) -> int:
    """Print output for --mode gap (清零率风格)."""
    print(f"Gap Verify: {result['resolved']}/{result['total']} resolved "
          f"(清零率 {result['clearance_rate']:.0%})")
    print(f"  open: {result['open']}  by_phase: {result['by_phase']}")
    print(f"  by_priority: {result['by_priority']}")

    if result["red_flags"]:
        print(f"\n⚠️ Red flags -- resolved but no evidence ({len(result['red_flags'])}):")
        for gid in result["red_flags"]:
            print(f"  ❌ {gid}: lifecycle_state=resolved but evidence_refs missing")
    if result["verification_failed"]:
        print(f"\n⚠️ Verification failed ({len(result['verification_failed'])}):")
        for gid in result["verification_failed"]:
            print(f"  ❌ {gid}")

    if verbose:
        print("\nAll gaps:")
        for c in result["tasks"]:
            marker = "✅" if c["is_verified"] else "⬜"
            phase = c.get("phase", "?")
            print(f"  {marker} [{phase:6s}] {c['id']}: {c['title']}")

    return 1 if result["red_flags"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["gap", "task", "all"], default="task",
                        help="验证模式: gap=清零率, task=门禁, all=全部 (default: task)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="每个 gap 明细 (仅 gap/all 模式)")
    parser.add_argument("--strict", action="store_true",
                        help="强制跑每个 verification_cmd")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)

    checks = scan(args.root, args.strict)
    result = build_result(checks, args.mode)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.mode == "gap":
        return print_gap_mode(result, args.verbose)

    if args.mode == "task":
        return print_task_mode(result)

    # mode == "all": print both
    code_gap = print_gap_mode(result, args.verbose)
    print()
    code_task = print_task_mode(result)
    return code_task or code_gap


if __name__ == "__main__":
    raise SystemExit(main())
