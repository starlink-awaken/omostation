#!/usr/bin/env python3
"""CI 平面可观测性检测器 (ADR-0379 E-3).

基于 .omo/_truth/registry/ci-surfaces.yaml SSOT 检查 CI 平面健康:

1. unregistered-check (error) — workflows / sgf-policy 中执行的 check 类工具
   未在 SSOT 登记 (新增检查未登记 = CI 面 drift).
2. gate-parity (error) — sgf-policy gate 命令引用的工具未在 SSOT 登记.
3. orphan-script (warn) — scripts/check-*.py 存在但未接线到任何 workflow/gate,
   且未在 SSOT 显式登记 status: orphan.
4. overlap (warn) — 同一 tool 在 2+ 个 workflow 执行 (重复计算嫌疑).
5. double-trigger (error) — workflow 用 `on: [push, pull_request]` 无 main 分支限制,
   PR 分支每个 push 跑两遍 (E-4 根因).

用法:
  python3 bin/gac/check-ci-surfaces.py           # 人类可读报告
  python3 bin/gac/check-ci-surfaces.py --json    # JSON (healthcheck/仪表盘)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
CI_SURFACES = WORKSPACE / ".omo" / "_truth" / "registry" / "ci-surfaces.yaml"
WORKFLOWS_DIR = WORKSPACE / ".github" / "workflows"
SGF_POLICY = (
    WORKSPACE
    / "projects"
    / "ecos"
    / "src"
    / "ecos"
    / "ssot"
    / "mof"
    / "m1"
    / "governance"
    / "sgf-policy.yaml"
)

# check 类工具路径前缀 (非 check 的 util/install/setup 不算 CI 检查面)
CHECK_PREFIX = ("scripts/check-", "bin/gac/", "bin/ssot/", "bin/mof/", "bin/adr/", "bin/sweep/")

# 已知故意 double-trigger 豁免 (无 main 分支限制但确有意义的) — 默认空, 只允许显式登记
DOUBLE_TRIGGER_EXEMPT = set()


def _load_yaml(path: Path) -> dict:
    import yaml

    if not path.exists():
        return {}
    try:
        docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    except Exception:
        return {}
    return docs[-1] if docs else {}


def _workflow_triggers(text: str) -> list[str]:
    """提取 workflow 触发集合 (简化分类)."""
    triggers: list[str] = []
    if "workflow_call" in text:
        triggers.append("callable")
    if "schedule:" in text:
        triggers.append("scheduled")
    if "workflow_dispatch" in text:
        triggers.append("manual")
    if "on: [push, pull_request]" in text or "on: [push,pull_request]" in text:
        triggers += ["push", "per_pr"]
    else:
        if re.search(r"^\s+push:\s*$", text, re.M):
            triggers.append("push")
        if re.search(r"^\s+pull_request:\s*$", text, re.M):
            triggers.append("per_pr")
    return triggers


def _discover_wiring() -> dict[str, dict]:
    """扫描 workflows + sgf-policy, 返回 tool -> {workflows, gate}."""
    tools: dict[str, dict] = {}
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="ignore")
        name = wf.name
        for m in re.finditer(
            r"(python3|python|uv run[^|]*|bash)\s+((?:bin|scripts)/[\w./-]+\.(?:py|sh))", text
        ):
            tool = m.group(2)
            entry = tools.setdefault(tool, {"workflows": [], "gate": False})
            if name not in entry["workflows"]:
                entry["workflows"].append(name)
    policy = _load_yaml(SGF_POLICY)
    for gate in policy.get("gates") or []:
        for part in gate.get("command") or []:
            if part.endswith(".py") and part.startswith(("bin/", "scripts/")):
                entry = tools.setdefault(part, {"workflows": [], "gate": False})
                entry["gate"] = True
    return tools


def _is_check_tool(tool: str) -> bool:
    return tool.startswith(CHECK_PREFIX)



def check_workflow_trigger_drift(registry: dict, workflow_dir: Path) -> list[str]:
    """ADR-0381 E-5: workflow 实际触发/path-filter 与 ci-surfaces workflow_triggers 登记比对."""
    warnings: list[str] = []
    registered = {
        str(w.get("workflow")): w
        for w in (registry.get("workflow_triggers") or [])
        if isinstance(w, dict) and w.get("workflow")
    }
    for wf in sorted(workflow_dir.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="ignore")
        name = wf.name
        triggers = []
        if "workflow_call" in text:
            triggers.append("callable")
        if re.search(r"^\s+schedule:\s*$", text, re.M) or "schedule:" in text:
            triggers.append("scheduled")
        if "workflow_dispatch" in text:
            triggers.append("manual")
        if "on: [push, pull_request]" in text or "on: [push,pull_request]" in text:
            triggers += ["push", "per_pr"]
        else:
            if re.search(r"^\s+push:\s*$", text, re.M):
                triggers.append("push")
            if re.search(r"^\s+pull_request:\s*$", text, re.M):
                triggers.append("per_pr")
        path_filtered = bool(re.search(r"^\s+paths:\s*$", text, re.M))
        entry = registered.get(name)
        if entry is None:
            warnings.append(f"trigger-drift: {name} 未登记在 ci-surfaces workflow_triggers")
            continue
        reg_trig = sorted(str(x) for x in (entry.get("triggers") or []))
        if sorted(set(triggers)) != reg_trig:
            warnings.append(
                f"trigger-drift: {name} 实际触发 {sorted(set(triggers))} != 登记 {reg_trig} (重跑 ci-surfaces 生成器)"
            )
        if bool(entry.get("path_filtered")) != path_filtered:
            warnings.append(
                f"trigger-drift: {name} path_filtered 实际={path_filtered} 登记={entry.get('path_filtered')}"
            )
        if path_filtered:
            actual_paths = set()
            paths_re = re.compile(r"^\s+paths:\s*$((?:\n\s+- [^\n]+)*)", re.M)
            for m in paths_re.finditer(text):
                for line in m.group(1).split("\n"):
                    pm = re.match(r"\s+- (.*)$", line)
                    if pm:
                        actual_paths.add(pm.group(1).strip().strip("'\""))
            reg_paths = {str(x) for x in (entry.get("paths") or [])}
            if actual_paths != reg_paths:
                warnings.append(
                    f"trigger-drift: {name} paths 实际={len(actual_paths)} 条 != 登记 {len(reg_paths)} 条 (重跑生成器)"
                )
    return warnings


def check_ci_surfaces() -> dict:
    """执行全部检测, 返回结构化报告."""
    errors: list[str] = []
    warnings: list[str] = []

    registry = _load_yaml(CI_SURFACES)
    surfaces = registry.get("surfaces") or []
    registered_tools = {
        str(s.get("tool") or ""): s for s in surfaces if isinstance(s, dict) and s.get("tool")
    }
    orphan_registered = {
        str(s.get("tool"))
        for s in surfaces
        if isinstance(s, dict) and s.get("status") == "orphan"
    }

    wiring = _discover_wiring()

    # 1/2. unregistered + gate-parity: wiring 中 check 工具不在 SSOT
    for tool, meta in sorted(wiring.items()):
        if not _is_check_tool(tool):
            continue
        if tool in registered_tools:
            continue
        if meta["gate"]:
            errors.append(f"gate-parity: sgf-policy gate 引用了未登记的检查工具 {tool} (CR-CI-SURFACE-SSOT)")
        else:
            errors.append(f"unregistered-check: workflow {','.join(meta['workflows'])} 执行了未登记的检查 {tool} (CR-CI-SURFACE-SSOT)")

    # 2.5 E-5: workflow 触发/path-filter 登记 drift (workflow_triggers section)
    warnings.extend(check_workflow_trigger_drift(registry, WORKFLOWS_DIR))

    # 3. orphan-script: 磁盘上 check-*.py 未接线且未登记为 orphan
    for script in sorted((WORKSPACE / "scripts").glob("check-*.py")):
        rel = f"scripts/{script.name}"
        if rel in registered_tools:
            continue
        if rel in orphan_registered:
            continue
        if rel in wiring:
            continue
        warnings.append(f"orphan-script: {rel} 未接线到任何 workflow/gate 且未在 ci-surfaces.yaml 登记 (接线或删除)")

    # 4. overlap: 同一 tool 在 2+ workflow (runner 是多 workflow 执行引擎, 豁免)
    OVERLAP_EXEMPT = {"bin/gac/ci-check-runner.py", "bin/gac/check-ci-surfaces.py"}
    for tool, meta in sorted(wiring.items()):
        if not _is_check_tool(tool):
            continue
        if tool in OVERLAP_EXEMPT:
            continue
        if len(meta["workflows"]) > 1:
            warnings.append(
                f"overlap: {tool} 在 {len(meta['workflows'])} 个 workflow 执行: {','.join(meta['workflows'])}"
            )

    # 5. double-trigger: on: [push, pull_request] 无 main 分支限制
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="ignore")
        if "on: [push, pull_request]" not in text and "on: [push,pull_request]" not in text:
            continue
        if wf.name in DOUBLE_TRIGGER_EXEMPT:
            continue
        errors.append(
            f"double-trigger: {wf.name} 用 on: [push, pull_request] — PR 分支每个 push 双跑; "
            "改为 push: {branches: [main]} + pull_request (ADR-0379 E-4)"
        )

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warn_count": len(warnings),
        "surfaces": len(surfaces),
        "registered_tools": len(registered_tools),
        "orphan_registered": len(orphan_registered),
        "wired_tools": len(wiring),
    }


def _tool_id(tool: str) -> str:
    return tool.replace("/", "-").replace(".", "-").rstrip("-")


def fix_ci_surfaces() -> dict:
    """Auto-register missing surfaces and workflow_triggers. Return summary."""
    import yaml

    registry = _load_yaml(CI_SURFACES)
    surfaces = list(registry.get("surfaces") or [])
    wf_triggers = list(registry.get("workflow_triggers") or [])
    registered_tools = {str(s.get("tool") or "") for s in surfaces if isinstance(s, dict) and s.get("tool")}
    registered_wfs = {str(w.get("workflow") or "") for w in wf_triggers if isinstance(w, dict) and w.get("workflow")}

    wiring = _discover_wiring()
    added_surfaces = 0
    added_wf_triggers = 0

    for tool, meta in sorted(wiring.items()):
        if not _is_check_tool(tool):
            continue
        if tool in registered_tools:
            continue
        surfaces.append({
            "id": _tool_id(tool),
            "tool": tool,
            "workflow": meta["workflows"][0] if meta["workflows"] else "(none)",
            "gate": meta["gate"],
            "triggers": [],
            "status": "active",
            "note": "auto-registered by check-ci-surfaces.py --fix",
        })
        added_surfaces += 1

    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        name = wf.name
        if name in registered_wfs:
            continue
        text = wf.read_text(encoding="utf-8", errors="ignore")
        triggers = []
        if "workflow_call" in text:
            triggers.append("callable")
        if "schedule:" in text:
            triggers.append("scheduled")
        if "workflow_dispatch" in text:
            triggers.append("manual")
        if re.search(r"^\s+push:\s*$", text, re.M):
            triggers.append("push")
        if re.search(r"^\s+pull_request:\s*$", text, re.M):
            triggers.append("per_pr")
        path_filtered = bool(re.search(r"^\s+paths:\s*$", text, re.M))
        entry: dict = {"workflow": name, "triggers": triggers, "path_filtered": path_filtered}
        if path_filtered:
            paths_re = re.compile(r"^\s+paths:\s*$((?:\n\s+- [^\n]+)*)", re.M)
            paths = []
            for m in paths_re.finditer(text):
                for line in m.group(1).split("\n"):
                    pm = re.match(r"\s+- (.*)$", line)
                    if pm:
                        paths.append(pm.group(1).strip().strip("'\""))
            if paths:
                entry["paths"] = paths
        wf_triggers.append(entry)
        added_wf_triggers += 1

    if added_surfaces or added_wf_triggers:
        surfaces.sort(key=lambda s: str(s.get("tool", "")))
        wf_triggers.sort(key=lambda w: str(w.get("workflow", "")))
        registry["surfaces"] = surfaces
        registry["workflow_triggers"] = wf_triggers
        with open(CI_SURFACES, "w", encoding="utf-8") as f:
            yaml.dump(registry, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return {"added_surfaces": added_surfaces, "added_wf_triggers": added_wf_triggers}


def main() -> int:
    args = sys.argv[1:]
    json_mode = "--json" in args
    fix_mode = "--fix" in args

    if fix_mode:
        result = fix_ci_surfaces()
        if json_mode:
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"fix: +{result['added_surfaces']} surfaces, +{result['added_wf_triggers']} workflow_triggers")
        report = check_ci_surfaces()
        if not json_mode:
            for e in report["errors"]:
                print(f"  ❌ {e}")
            for w in report["warnings"]:
                print(f"  ⚠️  {w}")
            if not report["errors"] and not report["warnings"]:
                print("✅ CI 平面干净")
        return 1 if report["errors"] else 0

    report = check_ci_surfaces()
    if json_mode:
        import json

        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["errors"] else 0
    print("=== CI 平面可观测性 (check-ci-surfaces.py, ADR-0379) ===")
    print(f"SSOT: ci-surfaces.yaml | surfaces={report['surfaces']} wired={report['wired_tools']} orphan_registered={report['orphan_registered']}")
    for e in report["errors"]:
        print(f"  ❌ {e}")
    for w in report["warnings"]:
        print(f"  ⚠️  {w}")
    if not report["errors"] and not report["warnings"]:
        print("✅ CI 平面干净")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
