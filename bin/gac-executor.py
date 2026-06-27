#!/usr/bin/env python3
"""gac-executor — GaC 执行器注册 drift 检测 (机制 3/4 深化).

GaC 规则声明 executor (ci_gate/omo_audit/evidence_smoke 等), 但声明的 executor
是否真存在/注册? 本工具检测 声明 vs 实际 drift:

  声明 (governance-checks.yaml::gac.rules.executor) vs 实际 (文件/命令/CI workflow)
  missing executor = 规则声明了不存在的执行器 = drift

比 gac-bootstrap 层5 (executor enum 合法性) 更深: 查实际存在性, 非仅 enum.

executor 实际映射:
  ci_gate       → .github/workflows/gac-gate.yml (CI workflow)
  omo_audit     → omo CLI (projects/omo/src/omo/cli.py)
  hook_pre_edit → bin/gac-hook-pre-edit.py
  mcp_tool      → projects/omo/src/omo/mcp_server.py (check_gac_rule)
  mof_validate  → bin/gac-mof-validate.py
  mof_audit     → bin/mof-audit 或 projects/ecos mof-audit
  evidence_smoke→ bin/evidence-smoke.py
  radar_cron    → bin/gac-drift.py
  gc_cron       → bin/gac-gc.py

用法:
  python3 bin/gac-executor.py           # 检测 executor drift, 有 missing 返回 1
  python3 bin/gac-executor.py --json    # JSON 输出 (gac-healthcheck 消费)

退出码: 0 = 全 executor 存在, 1 = 有 missing executor
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"

# executor → 实际存在性检查 (文件/目录; 多候选任一存在即 ok)
EXECUTOR_PRESENCE: dict[str, list[str]] = {
    "ci_gate": [".github/workflows/gac-gate.yml"],
    "omo_audit": ["projects/omo/src/omo/cli.py", "projects/omo/src/omo/omo_audit.py"],
    "hook_pre_edit": ["bin/gac-hook-pre-edit.py"],
    "mcp_tool": ["projects/omo/src/omo/mcp_server.py"],
    "mof_validate": ["bin/gac-mof-validate.py"],
    "mof_audit": ["projects/ecos/src/ecos/ssot/tools/mof-audit.py", "bin/mof-audit"],
    "evidence_smoke": ["bin/evidence-smoke.py"],
    "radar_cron": ["bin/gac-drift.py"],
    "gc_cron": ["bin/gac-gc.py"],
    "hook_post": [],  # 声明占位, 无独立文件 (hook_post 是 PostToolUse 事件, 非文件)
}


def load_rules() -> list[dict]:
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    return docs[-1].get("gac", {}).get("rules", []) if docs else []


def check_executor_presence(executor: str) -> tuple[bool, str]:
    """检查 executor 实际存在性. 返回 (exists, detail)."""
    candidates = EXECUTOR_PRESENCE.get(executor, [])
    if not candidates:
        # 未知 executor (不在映射表) = 无映射, 标记需人工确认
        return (False, "无存在性映射 (未知 executor, 需确认)")
    for c in candidates:
        if (WORKSPACE / c).exists():
            return (True, c)
    return (False, f"候选都不存在: {candidates}")


def run_check(as_json: bool = False) -> int:
    """主 executor drift 检测."""
    rules = load_rules()

    # 收集所有声明的 executor + 每规则的 executor 状态
    declared_executors: set[str] = set()
    executor_status: dict[str, dict] = {}  # executor → {exists, detail, rule_count}
    rule_issues: list[dict] = []

    for r in rules:
        execs = r.get("executor", [])
        for e in execs:
            declared_executors.add(e)
            if e not in executor_status:
                exists, detail = check_executor_presence(e)
                executor_status[e] = {"exists": exists, "detail": detail, "rule_count": 0}
            executor_status[e]["rule_count"] += 1
            if not executor_status[e]["exists"]:
                rule_issues.append({"rule": r.get("id", "?"), "executor": e})

    # executor 覆盖统计 (多少规则用每个 executor)
    coverage = Counter()
    for r in rules:
        for e in r.get("executor", []):
            coverage[e] += 1

    missing_executors = [e for e, s in executor_status.items() if not s["exists"]]
    report = {
        "rules_total": len(rules),
        "declared_executors": sorted(declared_executors),
        "executor_presence": {
            e: {"exists": s["exists"], "detail": s["detail"], "rule_count": s["rule_count"]}
            for e, s in sorted(executor_status.items())
        },
        "missing_executors": missing_executors,
        "rules_with_missing_executor": len(rule_issues),
        "ok": len(missing_executors) == 0,
    }

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    print("═══ GaC 执行器注册 drift 检测 (声明 vs 实际存在) ═══")
    print(f"▶ 规则总数: {report['rules_total']}")
    print(f"▶ 声明 executor: {len(declared_executors)} 种")
    print()
    print("executor 存在性:")
    for e, s in sorted(report["executor_presence"].items()):
        status = "✅" if s["exists"] else "❌"
        print(f"  {status} {e} (规则数={s['rule_count']}): {s['detail']}")

    if missing_executors:
        print(f"\n❌ missing executor ({len(missing_executors)}): {missing_executors}")
        print(f"   受影响规则: {report['rules_with_missing_executor']}")
    else:
        print(f"\n✅ 全 executor 实际存在 (声明 vs 实际 0 drift)")

    print(f"\n═══ 总体: {'✅ executor drift 闭环' if report['ok'] else '❌ 有 missing executor'} ═══")
    return 0 if report["ok"] else 1


def main() -> int:
    return run_check(as_json="--json" in sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
