#!/usr/bin/env python3
"""Architecture Drift — 架构漂移检测 (ADR-0190 系列, Phase 4 防腐层).

检测架构标准漂移:
  - 场景卡生命周期漂移 (长期停留在 shadow/assisted 未升级)
  - 维度覆盖漂移 (新增维度未纳入采集)
  - 注册表引用漂移 (SSOT 索引声明的文件/注册表不存在)
  - 标准文件变更频率 (长期未更新的标准)

用法:
  python3 bin/gac/architecture-drift.py              # 检测, exit 0=pass, 1=有漂移
  python3 bin/gac/architecture-drift.py --gate       # CI gate 模式
  python3 bin/gac/architecture-drift.py --json       # JSON 输出
  python3 bin/gac/architecture-drift.py --report     # 详细报告

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SCENE_DIR = WORKSPACE / "docs" / "scene-cards"
STANDARDS_DIR = WORKSPACE / ".omo" / "standards"
REGISTRY_DIR = WORKSPACE / ".omo" / "_truth" / "registry"

# ── 漂移阈值 ──
DRIFT_THRESHOLDS = {
    "shadow_max_days": 30,       # shadow 超过 30 天未升级 = 漂移
    "assisted_max_days": 60,     # assisted 超过 60 天未升级 = 漂移
    "standard_stale_days": 90,   # 标准文件超过 90 天未更新 = 漂移
    "missing_registry_days": 30, # 注册表缺失超过 30 天 = 漂移
}


def _load_yaml_safe(path: Path) -> dict | None:
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
        return body if isinstance(body, dict) else None
    except Exception:
        return None


def _file_age_days(path: Path) -> float | None:
    """返回文件最后修改天数."""
    if not path.exists():
        return None
    try:
        mtime = path.stat().st_mtime
        mdt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - mdt).total_seconds() / 86400
    except Exception:
        return None


def detect_lifecycle_drift() -> list[dict]:
    """检测场景卡生命周期漂移."""
    drifts = []

    if not SCENE_DIR.exists():
        return drifts

    for path in SCENE_DIR.glob("*.yaml"):
        data = _load_yaml_safe(path)
        if not data:
            continue

        scene_id = data.get("scene_id", path.stem)
        lifecycle = data.get("lifecycle", "")
        age_days = _file_age_days(path)

        if age_days is None:
            continue

        # shadow 超期检测
        if lifecycle == "shadow" and age_days > DRIFT_THRESHOLDS["shadow_max_days"]:
            drifts.append({
                "type": "lifecycle_stale",
                "severity": "warning",
                "scene_id": scene_id,
                "message": f"场景卡 {scene_id} 在 shadow 阶段停留 {age_days:.0f} 天 (阈值 {DRIFT_THRESHOLDS['shadow_max_days']} 天)",
                "lifecycle": lifecycle,
                "age_days": round(age_days, 1),
            })

        # assisted 超期检测
        if lifecycle == "assisted" and age_days > DRIFT_THRESHOLDS["assisted_max_days"]:
            drifts.append({
                "type": "lifecycle_stale",
                "severity": "warning",
                "scene_id": scene_id,
                "message": f"场景卡 {scene_id} 在 assisted 阶段停留 {age_days:.0f} 天 (阈值 {DRIFT_THRESHOLDS['assisted_max_days']} 天)",
                "lifecycle": lifecycle,
                "age_days": round(age_days, 1),
            })

    return drifts


def detect_standard_staleness() -> list[dict]:
    """检测标准文件陈旧性."""
    drifts = []

    standard_files = [
        "scene-card-lifecycle.yaml",
        "business-domains.yaml",
        "dimension-system.yaml",
        "value-loop-standard.yaml",
        "architecture-ssot-index.yaml",
    ]

    for std_name in standard_files:
        path = STANDARDS_DIR / std_name
        age_days = _file_age_days(path)

        if age_days is None:
            drifts.append({
                "type": "standard_missing",
                "severity": "error",
                "standard": std_name,
                "message": f"标准文件缺失: {std_name}",
            })
        elif age_days > DRIFT_THRESHOLDS["standard_stale_days"]:
            drifts.append({
                "type": "standard_stale",
                "severity": "warning",
                "standard": std_name,
                "message": f"标准文件 {std_name} 已 {age_days:.0f} 天未更新 (阈值 {DRIFT_THRESHOLDS['standard_stale_days']} 天)",
                "age_days": round(age_days, 1),
            })

    return drifts


def detect_registry_drift() -> list[dict]:
    """检测注册表引用漂移."""
    drifts = []

    ssot_index = _load_yaml_safe(STANDARDS_DIR / "architecture-ssot-index.yaml")
    if not ssot_index:
        return drifts

    # 检查核心文档
    core_docs = ssot_index.get("core_documents", {})
    for doc_name, doc_info in core_docs.items():
        if isinstance(doc_info, dict) and "path" in doc_info:
            doc_path = WORKSPACE / doc_info["path"]
            if not doc_path.exists():
                drifts.append({
                    "type": "registry_drift",
                    "severity": "error",
                    "reference": doc_name,
                    "message": f"SSOT 索引声明的核心文档不存在: {doc_info['path']}",
                })

    # 检查标准文件
    standards = ssot_index.get("standards", {})
    for std_name, std_info in standards.items():
        if isinstance(std_info, dict) and "path" in std_info:
            std_path = WORKSPACE / std_info["path"]
            if not std_path.exists():
                drifts.append({
                    "type": "registry_drift",
                    "severity": "error",
                    "reference": std_name,
                    "message": f"SSOT 索引声明的标准文件不存在: {std_info['path']}",
                })

    # 检查注册表
    registries = ssot_index.get("registries", {})
    for reg_name, reg_info in registries.items():
        if isinstance(reg_info, dict) and "path" in reg_info:
            reg_path = WORKSPACE / reg_info["path"]
            if not reg_path.exists():
                drifts.append({
                    "type": "registry_drift",
                    "severity": "warning",
                    "reference": reg_name,
                    "message": f"SSOT 索引声明的注册表不存在: {reg_info['path']}",
                })
        elif isinstance(reg_info, str):
            reg_path = WORKSPACE / reg_info
            if not reg_path.exists():
                drifts.append({
                    "type": "registry_drift",
                    "severity": "warning",
                    "reference": reg_name,
                    "message": f"SSOT 索引声明的注册表不存在: {reg_info}",
                })

    return drifts


def detect_dimension_coverage_drift() -> list[dict]:
    """检测维度覆盖漂移."""
    drifts = []

    dim_standard = _load_yaml_safe(STANDARDS_DIR / "dimension-system.yaml")
    if not dim_standard:
        return drifts

    dimensions = dim_standard.get("dimensions", {})
    expected = {"X1_audit", "X2_freshness", "X3_value", "X4_consistency",
                "D1_scene", "D2_function", "D3_journey", "D4_experience",
                "D5_vision", "D6_operations", "D7_maintenance"}

    missing = expected - set(dimensions.keys())
    for m in missing:
        drifts.append({
            "type": "dimension_missing",
            "severity": "warning",
            "dimension": m,
            "message": f"维度系统缺少预期维度: {m}",
        })

    return drifts


def detect() -> tuple[int, list[dict], dict]:
    """主检测. 返回 (exit_code, drifts, summary)."""
    all_drifts: list[dict] = []

    detectors = [
        ("lifecycle", detect_lifecycle_drift),
        ("standard_staleness", detect_standard_staleness),
        ("registry_drift", detect_registry_drift),
        ("dimension_coverage", detect_dimension_coverage_drift),
    ]

    for name, detector_fn in detectors:
        try:
            drifts = detector_fn()
            all_drifts.extend(drifts)
        except Exception as e:
            all_drifts.append({
                "type": "detector_error",
                "severity": "error",
                "detector": name,
                "message": f"检测器 {name} 异常: {e}",
            })

    errors = [d for d in all_drifts if d.get("severity") == "error"]
    warnings = [d for d in all_drifts if d.get("severity") == "warning"]

    summary = {
        "total_drifts": len(all_drifts),
        "errors": len(errors),
        "warnings": len(warnings),
        "by_type": {},
    }

    for d in all_drifts:
        t = d.get("type", "unknown")
        summary["by_type"][t] = summary["by_type"].get(t, 0) + 1

    return (1 if errors else 0, all_drifts, summary)


def main() -> int:
    args = sys.argv[1:]
    gate_mode = "--gate" in args
    json_mode = "--json" in args

    exit_code, drifts, summary = detect()

    if json_mode:
        print(json.dumps(
            {
                "ok": summary["errors"] == 0,
                "summary": summary,
                "drifts": drifts,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 1 if (gate_mode and summary["errors"] > 0) else exit_code

    print("=== Architecture Drift (架构漂移检测) ===")
    print(f"漂移总数: {summary['total_drifts']}")
    print(f"错误: {summary['errors']}, 警告: {summary['warnings']}")
    print(f"按类型: {summary['by_type']}")
    print()

    for d in drifts:
        severity = d.get("severity", "?")
        icon = "❌" if severity == "error" else "⚠️"
        print(f"  {icon} [{d.get('type', '?')}] {d.get('message', '')}")

    if not drifts:
        print("✅ 无架构漂移")
    elif summary["errors"] == 0:
        print(f"\n⚠️  {len(drifts)} 个漂移警告 (无错误)")
    else:
        print(f"\n❌ {summary['errors']} 个漂移错误")

    if gate_mode and summary["errors"] > 0:
        return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
