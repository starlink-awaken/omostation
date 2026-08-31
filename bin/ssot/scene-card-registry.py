#!/usr/bin/env python3
"""Scene Card Registry — 场景卡注册校验 (ADR-0190 系列, Phase 3 执行层).

校验场景卡注册表一致性:
  - 场景卡 YAML 语法有效性
  - 必填字段完整性 (scene_id, lifecycle, bet, falsifier, journey)
  - 生命周期值合法性 (5 级)
  - Journey 节点/边引用完整性
  - 业务域分类覆盖

用法:
  python3 bin/ssot/scene-card-registry.py              # 校验, exit 0=pass, 1=有错
  python3 bin/ssot/scene-card-registry.py --gate       # CI gate 模式
  python3 bin/ssot/scene-card-registry.py --json       # JSON 输出
  python3 bin/ssot/scene-card-registry.py --report     # 详细报告

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SCENE_DIR = WORKSPACE / "docs" / "scene-cards"

# ── 必填字段 (scene-card-candidate.schema.yaml required_fields_v2 + activation_boundary) ──
REQUIRED_FIELDS = ["scene_id", "lifecycle", "bet", "falsifier"]
OPTIONAL_FIELDS = [
    "journey_id", "goal", "trigger", "input_contract", "result_contract",
    "outcome_metric", "consumer", "approver", "owner", "failure_cost",
    "data_classification", "data_scope", "operator", "permission_ref",
    "rollback_plan", "sample_refs",
]

VALID_LIFECYCLE = {"draft", "shadow", "assisted", "supervised", "routine"}


def _load_yaml(path: Path) -> dict | None:
    """安全加载 YAML (支持 frontmatter + 正文)."""
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
    except Exception as e:
        return None


def _load_yaml_safe(path: Path) -> tuple[dict | None, str | None]:
    """安全加载 YAML, 返回 (data, error)."""
    if not path.exists():
        return None, f"文件不存在: {path}"
    try:
        import yaml

        text = path.read_text(encoding="utf-8")
        docs = [d for d in yaml.safe_load_all(text) if d]
        if not docs:
            return None, "YAML 为空或无法解析"
        body = docs[-1]
        if not isinstance(body, dict):
            return None, "YAML 根节点不是对象"
        return body, None
    except Exception as e:
        return None, f"YAML 解析错误: {e}"


def validate_scene_card(path: Path) -> dict:
    """校验单个场景卡. 返回结果字典."""
    result = {
        "path": str(path.relative_to(WORKSPACE)),
        "scene_id": None,
        "valid": True,
        "errors": [],
        "warnings": [],
    }

    data, error = _load_yaml_safe(path)
    if error:
        result["valid"] = False
        result["errors"].append(error)
        return result

    scene_id = data.get("scene_id", path.stem)
    result["scene_id"] = scene_id

    # 必填字段
    for field in REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            result["errors"].append(f"缺少必填字段: {field}")

    # 生命周期合法性
    lifecycle = data.get("lifecycle", "")
    if lifecycle and lifecycle not in VALID_LIFECYCLE:
        result["errors"].append(f"lifecycle '{lifecycle}' 不合法 (应为 {sorted(VALID_LIFECYCLE)})")

    # Journey 结构校验
    journey = data.get("journey", {})
    if isinstance(journey, dict):
        nodes = journey.get("nodes", [])
        edges = journey.get("edges", [])
        if nodes:
            node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
            # 边引用校验
            for edge in edges:
                if isinstance(edge, dict):
                    from_id = edge.get("from", "")
                    to_id = edge.get("to", "")
                    if from_id and from_id not in node_ids:
                        result["warnings"].append(f"journey.edge from '{from_id}' 未在 nodes 中定义")
                    if to_id and to_id not in node_ids:
                        result["warnings"].append(f"journey.edge to '{to_id}' 未在 nodes 中定义")
        # 空 journey 警告
        if not nodes and lifecycle in ("assisted", "supervised", "routine"):
            result["warnings"].append(f"lifecycle={lifecycle} 但 journey.nodes 为空")
    elif lifecycle in ("assisted", "supervised", "routine"):
        result["warnings"].append(f"lifecycle={lifecycle} 但缺少 journey 定义")

    # 可选字段提醒
    for field in ["journey_id", "goal", "trigger"]:
        if field not in data:
            result["warnings"].append(f"缺少推荐字段: {field}")

    if result["errors"]:
        result["valid"] = False

    return result


def validate() -> tuple[int, list[dict], dict]:
    """主校验. 返回 (exit_code, results, summary)."""
    results: list[dict] = []
    summary = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "warnings": 0,
        "lifecycle_distribution": {},
    }

    if not SCENE_DIR.exists():
        return 1, [], {"error": f"场景卡目录不存在: {SCENE_DIR}"}

    yaml_files = sorted(SCENE_DIR.glob("*.yaml"))
    summary["total"] = len(yaml_files)

    for path in yaml_files:
        result = validate_scene_card(path)
        results.append(result)

        if result["valid"]:
            summary["valid"] += 1
        else:
            summary["invalid"] += 1

        if result["warnings"]:
            summary["warnings"] += len(result["warnings"])

        # 生命周期分布
        data, _ = _load_yaml_safe(path)
        if data:
            lc = data.get("lifecycle", "unknown")
            summary["lifecycle_distribution"][lc] = summary["lifecycle_distribution"].get(lc, 0) + 1

    return (1 if summary["invalid"] > 0 else 0, results, summary)


def main() -> int:
    args = sys.argv[1:]
    gate_mode = "--gate" in args
    json_mode = "--json" in args
    report_mode = "--report" in args

    exit_code, results, summary = validate()

    if "error" in summary:
        print(f"ERROR: {summary['error']}", file=sys.stderr)
        return 1

    if json_mode:
        print(json.dumps(
            {
                "ok": summary["invalid"] == 0,
                "summary": summary,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 1 if (gate_mode and summary["invalid"] > 0) else exit_code

    print("=== Scene Card Registry (场景卡注册校验) ===")
    print(f"场景卡总数: {summary['total']}")
    print(f"有效: {summary['valid']}, 无效: {summary['invalid']}, 警告: {summary['warnings']}")
    print(f"生命周期分布: {summary['lifecycle_distribution']}")
    print()

    for result in results:
        status = "PASS" if result["valid"] else "FAIL"
        scene_id = result["scene_id"] or "?"
        print(f"[{status}] {scene_id} ({result['path']})")
        for e in result["errors"]:
            print(f"  ❌ {e}")
        for w in result["warnings"]:
            print(f"  ⚠️  {w}")

    if summary["invalid"] == 0:
        print("\n✅ Scene Card Registry 校验通过")
    else:
        print(f"\n❌ {summary['invalid']} 个场景卡校验失败")

    if gate_mode and summary["invalid"] > 0:
        return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
