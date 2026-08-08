#!/usr/bin/env python3
# bin/gac/gac-execution-gap.py — GaC 声明/执行鸿沟量化 (同 evidence-smoke 治 BOS 鸿沟一类)
#
# 读 governance-checks.yaml CR, 对 check_type 分类:
#   - 有执行实现: ssot_lint/mof_stage_gate/bos_resolve 等 (有对应 gate 脚本)
#   - 声明期(无执行实现): mesh_routing/memory_rag 等 (CR 声明了但无执行 script)
# report 鸿沟, 防 GaC 报绿是"声明合法"层绿非"执行到位"层绿。
#
# 用法: python3 bin/gac/gac-execution-gap.py [--json]

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"

# 已知声明期 check_type: CR 可声明但无执行 script (target 是 HTTP server/无自检逻辑)
DECLARED_ONLY_CHECK_TYPES = {"mesh_routing", "memory_rag"}


def load_rules() -> list[dict]:
    import yaml
    text = REGISTRY.read_text(encoding="utf-8")
    # strip frontmatter (--- ... ---)
    if text.startswith("---"):
        parts = text.split("---", 2)
        text = parts[2] if len(parts) > 2 else text
    data = yaml.safe_load(text) or {}
    return data.get("gac", {}).get("rules", []) or []


def main() -> int:
    as_json = "--json" in sys.argv
    rules = load_rules()
    declared_only = [r for r in rules if r.get("check_type") in DECLARED_ONLY_CHECK_TYPES]
    total = len(rules)
    gap_rate = (len(declared_only) / total) if total else 0.0
    result = {
        "total_cr": total,
        "declared_only_count": len(declared_only),
        "gap_rate": round(gap_rate, 4),
        "declared_only": [{"id": r.get("id"), "check_type": r.get("check_type"),
                           "executor": r.get("executor"), "target": r.get("target")}
                          for r in declared_only],
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("═" * 60)
        print("GaC 声明/执行鸿沟量化")
        print("═" * 60)
        print(f"  声明 CR 总数:        {total}")
        print(f"  声明期(无执行实现):  {len(declared_only)}")
        print(f"  鸿沟率:              {gap_rate:.2%}")
        if declared_only:
            print("  声明期 CR:")
            for r in declared_only:
                print(f"    - {r.get('id')}: check_type={r.get('check_type')} "
                      f"executor={r.get('executor')} target={r.get('target')}")
        print("═" * 60)
        print("注: 鸿沟率=0 不代表无债 — 仅当 mesh_routing/memory_rag 类 CR 上线后此量化才暴露")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
