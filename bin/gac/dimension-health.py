#!/usr/bin/env python3
"""Dimension Health — 维度数据采集与健康度报告 (ADR-0190 系列, Phase 3 执行层).

采集 12 维度健康数据, 生成结构化健康报告:
  - 治理维度 (X1-X4): 审计覆盖 / 文档新鲜度 / 价值证明 / SSOT 一致性
  - 业务维度 (D1-D9): 场景覆盖 / 功能成熟度 / 旅程完成率 / 体验 / 愿景 / 运营 / 运维 / 防腐 / 约束
  - 新增维度 (D10-D11): 进化 / 信任

数据来源:
  - 场景卡目录 (docs/scene-cards/) → 场景活跃度
  - 治理检查 (governance-checks.yaml) → 治理覆盖
  - 脚本注册表 (bin/_registry/) → 能力覆盖
  - 运行态 (system.yaml) → 系统健康

用法:
  python3 bin/gac/dimension-health.py              # 报告
  python3 bin/gac/dimension-health.py --json       # JSON 输出 (仪表盘数据源)
  python3 bin/gac/dimension-health.py --gate       # CI gate 模式 (低于目标分 fail)

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SCENE_DIR = WORKSPACE / "docs" / "scene-cards"
STANDARDS_DIR = WORKSPACE / ".omo" / "standards"
REGISTRY_DIR = WORKSPACE / ".omo" / "_truth" / "registry"

# ── 维度定义 (与 dimension-system.yaml 对齐) ──
DIMENSIONS = {
    "X1_audit": {"name": "审计/边界", "target": 100, "unit": "%"},
    "X2_freshness": {"name": "保鲜/抗熵", "target": 95, "unit": "%"},
    "X3_value": {"name": "价值/成本", "target": 80, "unit": "score"},
    "X4_consistency": {"name": "一致性/SSOT", "target": 100, "unit": "%"},
    "D1_scene": {"name": "场景", "target": 50, "unit": "count"},
    "D2_function": {"name": "功能", "target": 9.5, "unit": "/10"},
    "D3_journey": {"name": "旅程", "target": 80, "unit": "%"},
    "D4_experience": {"name": "体验", "target": 99, "unit": "%"},
    "D5_vision": {"name": "愿景", "target": 88, "unit": "/100"},
    "D6_operations": {"name": "运营", "target": 95, "unit": "%"},
    "D7_maintenance": {"name": "运维", "target": 100, "unit": "%"},
    "D8_anticorrosion": {"name": "防腐", "target": 100, "unit": "%"},
    "D9_constraint": {"name": "约束", "target": 100, "unit": "%"},
    "D10_evolution": {"name": "进化", "target": 70, "unit": "%"},
    "D11_trust": {"name": "信任", "target": 80, "unit": "%"},
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


def collect_scene_metrics() -> dict:
    """采集场景维度指标."""
    metrics = {
        "total_scenes": 0,
        "active_scenes": 0,
        "lifecycle_distribution": {},
        "domain_distribution": {},
    }

    if not SCENE_DIR.exists():
        return metrics

    for path in SCENE_DIR.glob("*.yaml"):
        data = _load_yaml_safe(path)
        if not data:
            continue

        metrics["total_scenes"] += 1
        lifecycle = data.get("lifecycle", "unknown")
        metrics["lifecycle_distribution"][lifecycle] = metrics["lifecycle_distribution"].get(lifecycle, 0) + 1

        # 活跃场景 (assisted/supervised/routine)
        if lifecycle in ("assisted", "supervised", "routine"):
            metrics["active_scenes"] += 1

    return metrics


def collect_governance_metrics() -> dict:
    """采集治理维度指标."""
    metrics = {
        "total_rules": 0,
        "active_rules": 0,
        "deprecated_rules": 0,
        "dimension_coverage": set(),
    }

    registry = REGISTRY_DIR / "governance-checks.yaml"
    data = _load_yaml_safe(registry)
    if not data:
        return metrics

    rules = data.get("gac", {}).get("rules", [])
    metrics["total_rules"] = len(rules)

    for rule in rules:
        lifecycle = rule.get("lifecycle", "unknown")
        if lifecycle == "active":
            metrics["active_rules"] += 1
        elif lifecycle == "deprecated":
            metrics["deprecated_rules"] += 1
        dim = rule.get("dimension")
        if dim:
            metrics["dimension_coverage"].add(dim)

    return metrics


def collect_capability_metrics() -> dict:
    """采集能力覆盖指标."""
    metrics = {
        "total_scripts": 0,
        "registered_scripts": 0,
    }

    # 活跃脚本计数
    bin_dir = WORKSPACE / "bin"
    if bin_dir.exists():
        for f in bin_dir.rglob("*"):
            if f.is_file() and f.suffix in (".py", ".sh") and "_archive" not in f.parts and "__pycache__" not in f.parts:
                metrics["total_scripts"] += 1

    # 注册脚本计数
    registry_dir = WORKSPACE / "bin" / "_registry" / "scripts"
    if registry_dir.exists():
        for f in registry_dir.rglob("*.yaml"):
            metrics["registered_scripts"] += 1

    return metrics


def compute_dimension_scores(scene_m: dict, gov_m: dict, cap_m: dict) -> dict:
    """计算各维度分数."""
    scores = {}

    # X1: 审计覆盖 (基于治理规则覆盖度)
    x1_score = min(100.0, (gov_m["active_rules"] / max(1, gov_m["total_rules"])) * 100)
    scores["X1_audit"] = round(x1_score, 1)

    # X2: 文档新鲜度 (基于场景卡活跃度)
    x2_score = min(100.0, (scene_m["active_scenes"] / max(1, scene_m["total_scenes"])) * 100)
    scores["X2_freshness"] = round(x2_score, 1)

    # X3: 价值证明 (基于活跃能力比)
    x3_score = min(100.0, (cap_m["registered_scripts"] / max(1, cap_m["total_scripts"])) * 100)
    scores["X3_value"] = round(x3_score, 1)

    # X4: SSOT 一致性 (基于治理维度覆盖)
    x4_score = min(100.0, (len(gov_m["dimension_coverage"]) / 4) * 100)  # 4 个治理维度
    scores["X4_consistency"] = round(x4_score, 1)

    # D1: 场景覆盖
    d1_score = min(100.0, scene_m["active_scenes"] / 50 * 100)  # target=50
    scores["D1_scene"] = round(d1_score, 1)

    # D2: 功能成熟度 (基于注册率)
    d2_score = min(10.0, (cap_m["registered_scripts"] / max(1, cap_m["total_scripts"])) * 10)
    scores["D2_function"] = round(d2_score, 1)

    # D3: 旅程完成率 (基于 supervised+routine 占比)
    supervised_count = scene_m["lifecycle_distribution"].get("supervised", 0) + scene_m["lifecycle_distribution"].get("routine", 0)
    d3_score = min(100.0, supervised_count / max(1, scene_m["total_scenes"]) * 100)
    scores["D3_journey"] = round(d3_score, 1)

    # D4-D11: 综合估算 (基于整体健康度)
    base_health = (x1_score + x2_score + x3_score + x4_score) / 4
    for dim in ["D4_experience", "D5_vision", "D6_operations", "D7_maintenance",
                "D8_anticorrosion", "D9_constraint", "D10_evolution", "D11_trust"]:
        scores[dim] = round(base_health, 1)

    return scores


def collect() -> dict:
    """主采集. 返回完整报告."""
    scene_m = collect_scene_metrics()
    gov_m = collect_governance_metrics()
    cap_m = collect_capability_metrics()
    scores = compute_dimension_scores(scene_m, gov_m, cap_m)

    # 计算综合健康分
    avg_score = sum(scores.values()) / len(scores) if scores else 0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_health": round(avg_score, 1),
            "total_scenes": scene_m["total_scenes"],
            "active_scenes": scene_m["active_scenes"],
            "total_rules": gov_m["total_rules"],
            "active_rules": gov_m["active_rules"],
            "total_scripts": cap_m["total_scripts"],
            "registered_scripts": cap_m["registered_scripts"],
        },
        "scene_metrics": scene_m,
        "governance_metrics": {
            **gov_m,
            "dimension_coverage": list(gov_m["dimension_coverage"]),
        },
        "capability_metrics": cap_m,
        "dimension_scores": scores,
        "dimension_targets": {d: info["target"] for d, info in DIMENSIONS.items()},
    }


def main() -> int:
    args = sys.argv[1:]
    json_mode = "--json" in args
    gate_mode = "--gate" in args

    report = collect()

    if json_mode:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=== Dimension Health (维度健康度报告) ===")
    print(f"综合健康分: {report['summary']['overall_health']:.1f}/100")
    print()
    print(f"场景: {report['summary']['active_scenes']}/{report['summary']['total_scenes']} 活跃")
    print(f"治理规则: {report['summary']['active_rules']}/{report['summary']['total_rules']} 活跃")
    print(f"脚本: {report['summary']['registered_scripts']}/{report['summary']['total_scripts']} 注册")
    print()
    print("维度得分:")
    for dim_id, score in report["dimension_scores"].items():
        target = report["dimension_targets"].get(dim_id, 0)
        name = DIMENSIONS.get(dim_id, {}).get("name", dim_id)
        status = "✅" if score >= target else "⚠️"
        print(f"  {status} {dim_id} ({name}): {score:.1f}/{target}")

    # Gate 模式: 任一维度低于目标分 50% 则 fail
    if gate_mode:
        failed = [d for d, s in report["dimension_scores"].items()
                  if s < report["dimension_targets"].get(d, 0) * 0.5]
        if failed:
            print(f"\n❌ 维度健康度不足: {failed}")
            return 1

    print("\n✅ Dimension Health 采集完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
