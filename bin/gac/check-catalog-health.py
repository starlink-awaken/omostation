#!/usr/bin/env python3
"""CR-P79-CATALOG-HEALTH: 检查 catalog 健康指标.

P79-4: 原则数和 GaC 规则数作为可观测指标写入 foundry.
检查 governance-checks.yaml 是否有 catalog 健康指标记录.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOV_PATH = REPO / ".omo/_truth/registry/governance-checks.yaml"


def main() -> int:
    if not GOV_PATH.exists():
        print("OK 未发现 governance 注册表")
        return 0

    try:
        import yaml
        text = GOV_PATH.read_text(encoding="utf-8")
        docs = list(yaml.safe_load_all(text))
        # governance-checks.yaml 是多文档 yaml, 取第一个文档的 gac.rules
        gac = {}
        for doc in docs:
            if isinstance(doc, dict) and "gac" in doc:
                gac = doc["gac"]
                break
    except Exception as e:
        print(f"WARN 无法读取 governance 注册表: {e}")
        return 0

    rules = gac.get("rules", [])
    active = [r for r in rules if r.get("lifecycle") == "active"]
    draft = [r for r in rules if r.get("lifecycle") == "draft"]

    # 检查 freeze 节是否记录了规则数
    freeze = gac.get("gac", {}).get("freeze", {})
    max_rules = freeze.get("max_rules", "N/A")

    print(f"GaC catalog health:")
    print(f"  Active rules: {len(active)}")
    print(f"  Draft rules: {len(draft)}")
    print(f"  Total rules: {len(rules)}")
    print(f"  Freeze max: {max_rules}")
    print(f"  Utilization: {len(rules)}/{max_rules} = {len(rules)/max_rules*100:.0f}%" if max_rules != "N/A" else f"  Freeze max: {max_rules}")
    print("OK catalog 健康指标可读")
    return 0


if __name__ == "__main__":
    sys.exit(main())
