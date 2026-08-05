#!/usr/bin/env python3
"""CR-X-META-HEALTH: GaC 治理系统自检.

检查治理系统自身健康度:
1. 规则数 ≤ freeze max_rules
2. 每个 active 规则有唯一 ID
3. 无重复规则 ID
4. CI 步骤数 ≥ 规则数 / 10
5. 无生命周期为 draft 超过 90 天的规则
"""

import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOV_PATH = REPO / ".omo/_truth/registry/governance-checks.yaml"
CI_PATH = REPO / ".github/workflows/gac-gate.yml"

STALE_DRAFT_DAYS = 90


def main() -> int:
    if not GOV_PATH.exists():
        print("OK governance-checks.yaml 不存在, 跳过自检")
        return 0

    try:
        import yaml
        text = GOV_PATH.read_text(encoding="utf-8")
        docs = list(yaml.safe_load_all(text))
        gac = None
        for doc in docs:
            if isinstance(doc, dict) and "gac" in doc:
                gac = doc["gac"]
                break
        if not gac:
            print("WARN 未找到 gac 配置")
            return 0
    except Exception as e:
        print(f"WARN 无法读取 governance 注册表: {e}")
        return 0

    issues = []
    rules = gac.get("rules", [])
    active = [r for r in rules if r.get("lifecycle") == "active"]
    draft = [r for r in rules if r.get("lifecycle") == "draft"]
    freeze = gac.get("freeze", {})
    max_rules = freeze.get("max_rules", 0)

    # 1. 规则数 ≤ freeze max_rules
    if max_rules and len(rules) > max_rules:
        issues.append(f"规则数 {len(rules)} > freeze max_rules {max_rules}")

    # 2. 唯一 ID 检查
    ids = [r.get("id") for r in rules if r.get("id")]
    dupes = [iid for iid, cnt in Counter(ids).items() if cnt > 1]
    if dupes:
        issues.append(f"重复规则 ID: {', '.join(dupes[:5])}")

    # 3. 无 ID 的规则
    no_id = [r for r in rules if not r.get("id")]
    if no_id:
        issues.append(f"{len(no_id)} 条规则缺少 ID")

    # 4. CI 步骤数
    ci_steps = 0
    if CI_PATH.exists():
        ci_text = CI_PATH.read_text(encoding="utf-8")
        ci_steps = ci_text.count("- name:")
    min_expected = len(active) // 10
    if ci_steps < min_expected:
        issues.append(f"CI 步骤 {ci_steps} < 预期最小值 {min_expected} (active={len(active)})")

    # 5. 过期 draft
    now = datetime.now(timezone.utc)
    for r in draft:
        created = r.get("created_at")
        if created and isinstance(created, str):
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age = (now - created_dt).days
                if age > STALE_DRAFT_DAYS:
                    issues.append(f"draft 规则 {r.get('id', '?')} 已过 {age} 天")
            except (ValueError, TypeError):
                pass

    if issues:
        print(f"WARN GaC 自检发现 {len(issues)} 个问题:")
        for i in issues:
            print(f"  - {i}")
        return 0  # advisory

    print(f"OK GaC 自检通过: {len(active)} active, {len(draft)} draft, {ci_steps} CI steps, freeze={max_rules}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
