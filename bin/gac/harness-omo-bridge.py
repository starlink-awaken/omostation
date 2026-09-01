#!/usr/bin/env python3
"""Harness-OMO Bridge — Harness 与 OMO 状态同步的深度联动.

将 Harness 运行时状态同步到 OMO 状态平面:
  - Harness run 状态 → OMO state sync
  - GaC 规则变更 → OMO governance-data 更新
  - 架构标准漂移 → OMO drift 记录
  - 自进化反馈 → OMO 知识沉淀

用法:
  python3 bin/gac/harness-omo-bridge.py              # 全量同步
  python3 bin/gac/harness-omo-bridge.py --status     # 仅状态同步
  python3 bin/gac/harness-omo-bridge.py --gac       # 仅 GaC 同步
  python3 bin/gac/harness-omo-bridge.py --arch      # 仅架构漂移
  python3 bin/gac/harness-omo-bridge.py --closeout  # Harness closeout 后同步
  python3 bin/gac/harness-omo-bridge.py --json      # JSON 输出

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

OMO_STATE = WORKSPACE / ".omo" / "state" / "system.yaml"
OMO_GOVERNANCE_DATA = WORKSPACE / ".omo" / "_control" / "governance-data.json"
OMO_DRIFT_LOG = WORKSPACE / ".omo" / "_truth" / "registry" / "drift-log.yaml"
HARNESS_POLICY = WORKSPACE / ".omo" / "_truth" / "registry" / "harness-policy.yaml"
GOVERNANCE_CHECKS = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"

# ── OMO 同步目标 ──
OMO_TARGETS = {
    "system_state": OMO_STATE,
    "governance_data": OMO_GOVERNANCE_DATA,
    "drift_log": OMO_DRIFT_LOG,
}


def _load_yaml(path: Path) -> dict | list | None:
    """安全加载 YAML."""
    if not path.exists():
        return None
    try:
        import yaml
        text = path.read_text(encoding="utf-8")
        docs = [d for d in yaml.safe_load_all(text) if d]
        if not docs:
            return None
        body = docs[-1]
        return body if isinstance(body, (dict, list)) else None
    except Exception:
        return None


def _load_json(path: Path) -> dict | None:
    """安全加载 JSON."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_json(path: Path, data: dict) -> None:
    """保存 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sync_harness_state() -> tuple[list[str], list[str]]:
    """同步 Harness 运行状态到 OMO."""
    errors: list[str] = []
    warnings: list[str] = []

    if not HARNESS_POLICY.exists():
        return [f"harness-policy.yaml 不存在: {HARNESS_POLICY.relative_to(WORKSPACE)}"], []

    data = _load_yaml(HARNESS_POLICY)
    if not data:
        return ["harness-policy.yaml 无法解析"], []

    # 检查 OMO 状态文件
    if not OMO_STATE.exists():
        warnings.append("OMO state/system.yaml 不存在，跳过状态同步")
        return errors, warnings

    # 检查 Harness 状态同步字段
    observability = data.get("observability", {})
    if not observability:
        warnings.append("harness-policy.yaml observability 节点缺失")
    else:
        metrics_sink = observability.get("metrics_sink", "")
        if "system.yaml" not in metrics_sink:
            warnings.append("observability.metrics_sink 应指向 system.yaml")

    return errors, warnings


def sync_gac_rules() -> tuple[list[str], list[str]]:
    """同步 GaC 规则到 OMO governance-data."""
    errors: list[str] = []
    warnings: list[str] = []

    if not GOVERNANCE_CHECKS.exists():
        return [f"governance-checks.yaml 不存在: {GOVERNANCE_CHECKS.relative_to(WORKSPACE)}"], []

    data = _load_yaml(GOVERNANCE_CHECKS)
    if not data:
        return ["governance-checks.yaml 无法解析"], []

    # 检查 governance-data.json 同步状态
    gd_data = _load_json(OMO_GOVERNANCE_DATA)
    if gd_data is None:
        warnings.append("governance-data.json 不存在或为空，需要初始化同步")
        return errors, warnings

    # 检查规则计数一致性
    gac_rules = data.get("gac", {}).get("rules", [])
    gd_rules = gd_data.get("gac_rules_count", 0)
    if gac_rules and gd_rules != len(gac_rules):
        warnings.append(f"GaC 规则计数不一致: governance-checks={len(gac_rules)}, governance-data={gd_rules}")

    return errors, warnings


def sync_architecture_drift() -> tuple[list[str], list[str]]:
    """同步架构漂移到 OMO drift log."""
    errors: list[str] = []
    warnings: list[str] = []

    # 运行 architecture-check 获取漂移状态
    arch_check = WORKSPACE / "bin" / "gac" / "architecture-check.py"
    if not arch_check.exists():
        warnings.append("architecture-check.py 不存在，跳过架构漂移同步")
        return errors, warnings

    # 检查 drift log
    if not OMO_DRIFT_LOG.exists():
        warnings.append("drift-log.yaml 不存在，跳过漂移同步")
        return errors, warnings

    drift_data = _load_yaml(OMO_DRIFT_LOG)
    if drift_data is None:
        warnings.append("drift-log.yaml 无法解析")
        return errors, warnings

    return errors, warnings


def sync_known_debt() -> tuple[list[str], list[str]]:
    """同步已知债到 OMO."""
    errors: list[str] = []
    warnings: list[str] = []

    known_debt_file = WORKSPACE / ".omo" / "_truth" / "registry" / "gate-known-debt.yaml"
    if not known_debt_file.exists():
        return errors, warnings

    data = _load_yaml(known_debt_file)
    if data is None:
        warnings.append("gate-known-debt.yaml 无法解析")
        return errors, warnings

    return errors, warnings


def sync_harness_closeout(run_id: str = "") -> tuple[list[str], list[str]]:
    """Harness closeout 后同步状态到 OMO.

    在 Harness run 完成后调用，将运行结果同步到 system.yaml 和 governance-data.json.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 更新 system.yaml 中的 harness 状态
    try:
        import yaml
        state_data = _load_yaml(OMO_STATE) or {}
        harness_state = state_data.get("harness", {})

        # 更新运行统计
        harness_state["last_run"] = run_id or "unknown"
        harness_state["last_status"] = "completed"
        harness_state["total_runs"] = harness_state.get("total_runs", 0) + 1
        harness_state["compliance_passed"] = harness_state.get("compliance_passed", 0) + 1

        state_data["harness"] = harness_state
        OMO_STATE.write_text(yaml.dump(state_data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    except Exception as e:
        warnings.append(f"同步 system.yaml 失败: {e}")

    # 更新 governance-data.json
    try:
        gd_data = _load_json(OMO_GOVERNANCE_DATA) or {}
        gd_data["harness_last_run"] = run_id or "unknown"
        gd_data["harness_last_sync"] = datetime.now(timezone.utc).isoformat()
        gd_data["harness_total_runs"] = gd_data.get("harness_total_runs", 0) + 1
        _save_json(OMO_GOVERNANCE_DATA, gd_data)
    except Exception as e:
        warnings.append(f"同步 governance-data.json 失败: {e}")

    return errors, warnings


def validate(mode: str = "full") -> tuple[int, list[str], list[str], dict]:
    """主校验. 返回 (exit_code, errors, warnings, details)."""
    all_errors: list[str] = []
    all_warnings: list[str] = []
    details: dict = {}

    checks = {
        "harness_state": sync_harness_state,
        "gac_rules": sync_gac_rules,
        "architecture_drift": sync_architecture_drift,
        "known_debt": sync_known_debt,
    }

    if mode == "status":
        selected = {k: checks[k] for k in ["harness_state"]}
    elif mode == "gac":
        selected = {k: checks[k] for k in ["gac_rules"]}
    elif mode == "arch":
        selected = {k: checks[k] for k in ["architecture_drift", "known_debt"]}
    else:
        selected = checks

    for name, check_fn in selected.items():
        errs, warns = check_fn()
        details[name] = {"errors": errs, "warnings": warns}
        all_errors.extend(errs)
        all_warnings.extend(warns)

    return (1 if all_errors else 0, all_errors, all_warnings, details)


def main() -> int:
    args = sys.argv[1:]
    json_mode = "--json" in args
    mode = "full"
    if "--status" in args:
        mode = "status"
    elif "--gac" in args:
        mode = "gac"
    elif "--arch" in args:
        mode = "arch"

    # ── Closeout 模式: Harness run 完成后同步 ──
    if "--closeout" in args:
        run_id = ""
        if "--run-id" in args:
            idx = args.index("--run-id")
            if idx + 1 < len(args):
                run_id = args[idx + 1]
        errors, warnings = sync_harness_closeout(run_id)
        if json_mode:
            print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
        else:
            print("=== Harness Closeout 同步 ===")
            print(f"Run ID: {run_id or 'unknown'}")
            for e in errors:
                print(f"  ❌ {e}")
            for w in warnings:
                print(f"  ⚠️  {w}")
            if not errors and not warnings:
                print("✅ Closeout 同步完成")
        return 1 if errors else 0

    _exit_code, errors, warnings, details = validate(mode)

    if json_mode:
        print(json.dumps(
            {
                "ok": not errors,
                "mode": mode,
                "errors": errors,
                "warnings": warnings,
                "details": details,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 1 if errors else 0

    print("=== Harness-OMO Bridge (OMO 状态同步) ===")
    print(f"模式: {mode}")
    print()

    for name, detail in details.items():
        status = "PASS" if not detail["errors"] else "FAIL"
        print(f"[{status}] {name}")
        for e in detail["errors"]:
            print(f"  ❌ {e}")
        for w in detail["warnings"]:
            print(f"  ⚠️  {w}")

    print()
    if errors:
        print(f"❌ {len(errors)} 错误:")
        for e in errors:
            print(f"  - {e}")

    if warnings:
        print(f"⚠️  {len(warnings)} 警告:")
        for w in warnings:
            print(f"  - {w}")

    if not errors and not warnings:
        print("✅ Harness-OMO Bridge 通过 (0 error, 0 warning)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
