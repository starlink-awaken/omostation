"""mof-driven.py — M0 引擎 model-driven 7 阶段暴露 (M4 Phase 2.3)

设计: 把 projects/model-driven/ 的 7 LifecycleStage + transitions 映
射到 m3-meta.yaml 的对应 m3 Element, 但不动 model-driven 引擎本身.

约束 (ADR-0132 D4):
  - model-driven 7 阶段引擎不改 (P52 ADR-0117 已撤销 8 阶段)
  - data 只读, 通过 import 实现
  - 输出 m3-meta 兼容的 yaml (可被 mof-bootstrap check_4 校验)

用法:
    uv run python3 -m ecos.ssot.mof.m0.mof_driven --emit > .omo/_derived/m0-driven.yaml
    uv run python3 -m ecos.ssot.mof.m0.mof_driven --validate
    uv run python3 -m ecos.ssot.mof.m0.mof_driven --transition-graph

默认写到 projects/ecos/.omo/_derived/ (源端; ADR-0137 投影面范式).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 7 阶段映射表 (model-driven LifecycleStage → m3-meta Stage.* 前缀)
# 基于 e2f8f4d7 实证 m3_extended.py line 21-37
STAGE_TO_M3 = {
    "planning": "Stage.Planning",
    "design": "Stage.Design",
    "development": "Stage.Development",
    "deployment": "Stage.Deployment",
    "runtime": "Stage.Runtime",
    "operations": "Stage.Operations",
    "business_ops": "Stage.BusinessOps",
}


def _safe_import_model_driven():
    """懒加载 model-driven, 找不到返回 None.

    关键: 不强制依赖. 当 model-driven 子模块未初始化时, P2-S3 fall back
    到 yaml fixture (data-driven). 不让 m2 ecosystem 失败回滚。
    """
    candidates = [
        Path("projects/model-driven/src"),
        Path("../model-driven/src"),
        Path(__file__).resolve().parents[5] / "projects" / "model-driven" / "src",
    ]
    for cand in candidates:
        if cand.exists():
            sys.path.insert(0, str(cand))
            try:
                from model_driven.lifecycle.transitions import (
                    STANDARD_TRANSITIONS,  # type: ignore
                )
                from model_driven.mof.m3_extended import LifecycleStage  # type: ignore

                return LifecycleStage, STANDARD_TRANSITIONS
            except Exception:
                continue
    return None, None


def collect_stages() -> list[dict]:
    """收集 7 阶段 → m3 Element 形状的 m1 实例."""
    LifecycleStage, _ = _safe_import_model_driven()
    stages: list[dict] = []
    if LifecycleStage is None:
        # Fallback: 静态 7 阶段 (无论 model-driven 引擎是否在线)
        for value, m3_id in STAGE_TO_M3.items():
            stages.append(
                {
                    "id": f"STAGE-{value.upper()}",
                    "name": value.replace("_", " ").title(),
                    "type": "Stage",
                    "m3_parent": m3_id,
                    "order": list(STAGE_TO_M3.keys()).index(value),
                    "model_driven_value": value,
                    "engine_source": "fallback",
                }
            )
        return stages
    for idx, stage in enumerate(LifecycleStage):
        stages.append(
            {
                "id": f"STAGE-{stage.value.upper()}",
                "name": stage.name.replace("_", " ").title(),
                "type": "Stage",
                "m3_parent": STAGE_TO_M3[stage.value],
                "order": idx,
                "model_driven_value": stage.value,
                "engine_source": "model_driven_lifecycle",
            }
        )
    return stages


def collect_transitions() -> list[dict]:
    """收集 transitions → m3 关系形状."""
    _, STANDARD_TRANSITIONS = _safe_import_model_driven()
    transitions: list[dict] = []
    if STANDARD_TRANSITIONS is None:
        return transitions
    for tr in STANDARD_TRANSITIONS:
        transitions.append(
            {
                "from_stage": tr.from_stage.value,
                "to_stage": tr.to_stage.value,
                "from_m3": STAGE_TO_M3.get(tr.from_stage.value),
                "to_m3": STAGE_TO_M3.get(tr.to_stage.value),
                "condition": getattr(tr, "condition", ""),
            }
        )
    return transitions


def build_m0_snapshot() -> dict[str, Any]:
    """组装 M0 快照 yaml (m3-meta 兼容形状)."""
    return {
        "version": "1.0.0",
        "m0_type": "M0EngineSnapshot",
        "engine_source": "projects/model-driven",
        "stage_count": len(STAGE_TO_M3),
        "stages": collect_stages(),
        "transitions": collect_transitions(),
        "adr_refs": ["ADR-0132", "ADR-0117"],
    }


def emit_yaml(data: dict[str, Any]) -> str:
    """输出 yaml 格式 (避免依赖 PyYAML, 手写最小序列化)."""
    lines = []
    lines.append(f'version: "{data["version"]}"')
    lines.append(f"m0_type: {data['m0_type']}")
    lines.append(f"engine_source: {data['engine_source']}")
    lines.append(f"stage_count: {data['stage_count']}")
    lines.append(f"adr_refs: {data['adr_refs']}")
    lines.append("stages:")
    for s in data["stages"]:
        lines.append(f"  - id: {s['id']}")
        lines.append(f'    name: "{s["name"]}"')
        lines.append(f"    type: {s['type']}")
        lines.append(f"    m3_parent: {s['m3_parent']}")
        lines.append(f"    order: {s['order']}")
        lines.append(f"    model_driven_value: {s['model_driven_value']}")
        lines.append(f"    engine_source: {s['engine_source']}")
    if data["transitions"]:
        lines.append("transitions:")
        for tr in data["transitions"]:
            lines.append(f"  - from_stage: {tr['from_stage']}")
            lines.append(f"    to_stage: {tr['to_stage']}")
            lines.append(f"    from_m3: {tr['from_m3']}")
            lines.append(f"    to_m3: {tr['to_m3']}")
    return "\n".join(lines) + "\n"


def validate(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """校验 M0 snapshot 是否与 m3-meta 兼容 (7 阶段 + m3_parent 一致)."""
    errors: list[str] = []
    if data["stage_count"] != 7:
        errors.append(f"stage_count = {data['stage_count']}, 期望 7 (P52 ADR-0117)")
    seen = set()
    for s in data["stages"]:
        m3 = s.get("m3_parent")
        if m3 not in STAGE_TO_M3.values():
            errors.append(f"{s['id']}: m3_parent {m3} 不在 7 阶段 m3 meta set")
        if s["id"] in seen:
            errors.append(f"duplicate stage id: {s['id']}")
        seen.add(s["id"])
    # transitions 完整性
    for tr in data["transitions"]:
        if not tr.get("from_m3") or not tr.get("to_m3"):
            errors.append(
                f"transition {tr['from_stage']}→{tr['to_stage']} 缺 m3 anchor"
            )
    return (len(errors) == 0), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit", action="store_true", help="输出 yaml 到 stdout")
    parser.add_argument("--validate", action="store_true", help="校验 m3-meta 兼容")
    parser.add_argument(
        "--transition-graph", action="store_true", help="输出 transition 图 JSON"
    )
    parser.add_argument(
        "--write",
        type=Path,
        default=Path(
            "../.omo/_derived/m0-driven.yaml"
        ),  # ADR-0137: 写源端 (子模块内 .omo/_derived/)
        help="写入文件 (默认 projects/ecos/.omo/_derived/m0-driven.yaml)",
    )
    args = parser.parse_args()

    data = build_m0_snapshot()

    if args.emit:
        sys.stdout.write(emit_yaml(data))
        return 0

    if args.transition_graph:
        graph = {s["id"]: [] for s in data["stages"]}
        for tr in data["transitions"]:
            from_id = f"STAGE-{tr['from_stage'].upper()}"
            to_id = f"STAGE-{tr['to_stage'].upper()}"
            graph[from_id].append(to_id)
        print(json.dumps(graph, indent=2, ensure_ascii=False))
        return 0

    if args.validate:
        ok, errors = validate(data)
        print(f"✓ stage_count: {data['stage_count']}")
        print(f"✓ stages: {len(data['stages'])}")
        print(f"✓ transitions: {len(data['transitions'])}")
        if ok:
            print("✓ m3-meta 兼容校验 PASS")
            return 0
        for e in errors:
            print(f"  ❌ {e}")
        return 1

    # 默认: emit yaml 写入 .omo/_derived/m0-driven.yaml
    args.write.parent.mkdir(parents=True, exist_ok=True)
    args.write.write_text(emit_yaml(data))
    print(f"✅ M0 snapshot 写入 {args.write}")
    print(
        f"   stage_count: {data['stage_count']}, transitions: {len(data['transitions'])}"
    )
    ok, errors = validate(data)
    if not ok:
        for e in errors:
            print(f"   ❌ {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
