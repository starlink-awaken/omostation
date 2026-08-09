#!/usr/bin/env python3
"""semantic_diff.py — L0 约束语义级 Diff 报告器

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 1 步 3:
约束变更的语义级影响报告（added/removed/changed + 影响维度），用于 CI 门禁。

用法:
    python3 bin/ssot/semantic_diff.py <old.yaml> <new.yaml>
"""

import sys
from pathlib import Path

import yaml


def semantic_diff(old: dict, new: dict) -> list[dict]:
    """语义级 diff：added/removed/changed 约束 + 影响维度。

    判定:
    - added: 新约束（old 无 new 有）
    - removed: 旧约束（old 有 new 无）
    - changed: 同 id 但 severity/dimension 变化
    """
    old_c = {c["id"]: c for c in old.get("constraints", [])}
    new_c = {c["id"]: c for c in new.get("constraints", [])}
    diffs: list[dict] = []
    for cid in sorted(set(new_c) - set(old_c)):
        diffs.append({"type": "added", "constraint_id": cid,
                      "severity": new_c[cid].get("severity", "medium"),
                      "impact_families": [new_c[cid].get("dimension", "?")]})
    for cid in sorted(set(old_c) - set(new_c)):
        diffs.append({"type": "removed", "constraint_id": cid,
                      "severity": old_c[cid].get("severity", "medium"),
                      "impact_families": [old_c[cid].get("dimension", "?")]})
    for cid in sorted(set(old_c) & set(new_c)):
        o, n = old_c[cid], new_c[cid]
        if o.get("severity") != n.get("severity") or o.get("dimension") != n.get("dimension"):
            diffs.append({"type": "changed", "constraint_id": cid,
                          "severity": n.get("severity", "medium"),
                          "impact_families": [n.get("dimension", "?")]})
    return diffs


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: semantic_diff.py <old.yaml> <new.yaml>", file=sys.stderr)
        return 2
    old = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
    new = yaml.safe_load(Path(sys.argv[2]).read_text(encoding="utf-8"))
    diffs = semantic_diff(old, new)
    for d in diffs:
        print(f"[{d['type'].upper()}] {d['constraint_id']} ({d['severity']}) → {d['impact_families']}")
    if not diffs:
        print("[OK] 无语义变更")
        return 0
    return 1 if any(d["type"] == "removed" for d in diffs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
