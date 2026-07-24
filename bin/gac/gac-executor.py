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
  hook_pre_edit → bin/gac/gac-hook-pre-edit.py
  mcp_tool      → projects/omo/src/omo/mcp_server.py (check_gac_rule)
  mof_validate  → bin/gac/gac-mof-validate.py
  mof_audit     → bin/mof-audit 或 projects/ecos mof-audit
  evidence_smoke→ bin/gac/evidence-smoke.py
  radar_cron    → bin/gac/gac-drift.py
  gc_cron       → bin/gac/gac-gc.py

用法:
  python3 bin/gac/gac-executor.py           # 检测 executor drift, 有 missing 返回 1
  python3 bin/gac/gac-executor.py --json    # JSON 输出 (gac-healthcheck 消费)

退出码: 0 = 全 executor 存在, 1 = 有 missing executor
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
SERVICES_REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"

# executor → 实际存在性检查 (文件/目录; 多候选任一存在即 ok)
EXECUTOR_PRESENCE: dict[str, list[str]] = {
    "ci_gate": [".github/workflows/gac-gate.yml"],
    "omo_audit": ["projects/omo/src/omo/cli.py", "projects/omo/src/omo/omo_audit.py"],
    "hook_pre_edit": ["bin/gac/gac-hook-pre-edit.py"],
    "mcp_tool": ["projects/omo/src/omo/mcp_server.py"],
    "mof_validate": ["bin/gac/gac-mof-validate.py"],
    "mof_audit": ["projects/ecos/src/ecos/ssot/tools/mof-audit.py", "bin/mof-audit"],
    "evidence_smoke": ["bin/gac/evidence-smoke.py"],
    "radar_cron": ["bin/gac/gac-drift.py"],
    "gc_cron": ["bin/gac/gac-gc.py"],
    "gac_local_gate": ["bin/gac/gac-local-gate.py"],  # F-14 (2026-07-03): gac-local-gate 工具作为执行通道, 3 规则已声明 (CR-X2-GOVERNANCE-SEMANTIC-GATE / CR-L0-MATRIX-PORT-CONSISTENCY / CR-L0-MATRIX-LAUNCHD-COVERAGE)
    "foundry_cron": ["bin/gac/knowledge-foundry-cron.py"],  # 破自指 (ADR-0220): 独立 launchd daily, ghost executor 检测由它跑 (非 radar_cron=被检测对象自己)
    "hook_post": [],  # 声明占位, 无独立文件 (hook_post 是 PostToolUse 事件, 非文件)
}

# 可调度 CLI executor (机制3深化 POC: GaC 驱动执行, --run 去重跑每种一次)
# 不可直接调度: ci_gate (CI workflow push 触发), omo_audit (omo governance 慢),
#               hook_pre_edit/mcp_tool (事件驱动, 非 CLI)
RUNNABLE_EXECUTORS: dict[str, list[str]] = {
    "mof_validate": ["bin/gac/gac-mof-validate.py"],
    "radar_cron": ["bin/gac/gac-drift.py", "--json"],
    "gc_cron": ["bin/gac/gac-gc.py", "--dry-run"],
    "evidence_smoke": ["bin/gac/evidence-smoke.py"],
    "mof_audit": ["projects/ecos/src/ecos/ssot/tools/mof-audit.py"],
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
        print("\n✅ 全 executor 实际存在 (声明 vs 实际 0 drift)")

    print(f"\n═══ 总体: {'✅ executor drift 闭环' if report['ok'] else '❌ 有 missing executor'} ═══")
    return 0 if report["ok"] else 1


def check_executor_evidence() -> dict:
    """ghost executor 检测: scheduler:gha 服务的 liveness.signal 新鲜度.

    executor 文件存在 (presence ✓) 不等于真能跑出结果. 扫 services.yaml 里
    scheduler:gha 服务的 liveness.signal, 超 max_stale_hours 无 evidence 落盘 = ghost
    (连挂/静默). 治 ADR-0220 自指失效: 本检测由 foundry_cron (独立 launchd daily) 调用,
    不依赖 radar_cron (被检测对象自己), 破自指死循环.
    """
    if not SERVICES_REGISTRY.is_file():
        return {"checked_total": 0, "alive": 0, "ghosts": [], "ok": True,
                "error": "services.yaml missing"}
    docs = [d for d in yaml.safe_load_all(SERVICES_REGISTRY.read_text(encoding="utf-8")) if d]
    services = docs[-1].get("services", []) if docs else []
    now = datetime.now(timezone.utc)
    alive: list[dict] = []
    ghosts: list[dict] = []
    for svc in services:
        if svc.get("scheduler") != "gha":
            continue
        liveness = svc.get("liveness") or {}
        signal = liveness.get("signal")
        if not signal:
            continue
        max_stale = liveness.get("max_stale_hours", 24)
        sig_rel = signal.split("::")[0]
        sig_path = WORKSPACE / sig_rel
        entry: dict = {"id": svc.get("id"), "signal": signal, "max_stale_hours": max_stale}
        # 目录 signal (如 evidence-smoke/) 取最新文件 mtime; 文件 signal 直接 mtime
        if sig_path.is_dir():
            files = sorted(
                [p for p in sig_path.glob("*") if p.is_file()],
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            if not files:
                entry.update(status="ghost", reason=f"signal dir empty: {sig_rel}")
                ghosts.append(entry)
                continue
            mtime = datetime.fromtimestamp(files[0].stat().st_mtime, tz=timezone.utc)
        elif sig_path.is_file():
            mtime = datetime.fromtimestamp(sig_path.stat().st_mtime, tz=timezone.utc)
        else:
            entry.update(status="ghost", reason=f"signal missing: {sig_rel}")
            ghosts.append(entry)
            continue
        age_h = (now - mtime).total_seconds() / 3600
        entry["age_hours"] = round(age_h, 1)
        if age_h > max_stale:
            entry.update(status="ghost", reason=f"stale {age_h:.1f}h > {max_stale}h")
            ghosts.append(entry)
        else:
            entry["status"] = "alive"
            alive.append(entry)
    return {
        "checked_total": len(alive) + len(ghosts),
        "alive": len(alive),
        "ghosts": ghosts,
        "ok": len(ghosts) == 0,
    }


def run_ghost_check(as_json: bool = False) -> int:
    """ghost executor 检测主入口 (破自指: foundry_cron 调, 非 radar_cron)."""
    report = check_executor_evidence()
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    print("═══ GaC ghost executor 检测 (scheduler:gha liveness 新鲜度) ═══")
    print(f"▶ 检查服务数: {report['checked_total']} (alive={report['alive']} ghost={len(report['ghosts'])})")
    for g in report["ghosts"]:
        print(f"  👻 {g['id']}: {g.get('reason', '?')} (signal={g['signal']})")
    print(f"\n═══ 总体: {'✅ 全 gha 服务 evidence 新鲜' if report['ok'] else '❌ 有 ghost executor'} ═══")
    return 0 if report["ok"] else 1


def run_executors(as_json: bool = False) -> int:
    """机制3深化 POC: 调度可跑 CLI executor (去重, 每种一次).

    证明 GaC 规则声明的 executor 真能被调度 (不只声明存在).
    不替代 cron (cron 触发实际脚本, GaC 是注册+调度层).
    """
    import subprocess

    results: dict[str, dict] = {}
    rules = load_rules()
    exec_rule_count: dict[str, int] = {}
    for r in rules:
        for e in r.get("executor", []):
            exec_rule_count[e] = exec_rule_count.get(e, 0) + 1

    for executor, rel_cmd in RUNNABLE_EXECUTORS.items():
        cmd = [sys.executable, str(WORKSPACE / rel_cmd[0]), *rel_cmd[1:]]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=WORKSPACE)
            results[executor] = {
                "ok": r.returncode == 0,
                "exit": r.returncode,
                "rules_covered": exec_rule_count.get(executor, 0),
            }
        except subprocess.TimeoutExpired:
            results[executor] = {"ok": False, "error": "timeout 120s", "rules_covered": exec_rule_count.get(executor, 0)}
        except (subprocess.SubprocessError, OSError) as e:
            results[executor] = {"ok": False, "error": str(e), "rules_covered": exec_rule_count.get(executor, 0)}

    all_ok = all(r.get("ok") for r in results.values())

    if as_json:
        print(json.dumps({"executors": results, "ok": all_ok}, ensure_ascii=False, indent=2))
        return 0 if all_ok else 1

    print("═══ GaC 执行器调度 POC (机制3深化: GaC 驱动执行) ═══")
    for executor, r in results.items():
        status = "✅" if r.get("ok") else "❌"
        detail = f"exit={r['exit']}" if "exit" in r else f"err={r.get('error', '?')[:40]}"
        print(f"  {status} {executor} (规则={r['rules_covered']}): {detail}")
    print(f"\n═══ 总体: {'✅ 可调度 executor 全活' if all_ok else '❌ 有 executor 调度失败'} ═══")
    return 0 if all_ok else 1


def main() -> int:
    args = sys.argv[1:]
    if "ghost-check" in args:
        return run_ghost_check(as_json="--json" in args)
    if "--run" in args:
        return run_executors(as_json="--json" in args)
    return run_check(as_json="--json" in args)


if __name__ == "__main__":
    sys.exit(main())
