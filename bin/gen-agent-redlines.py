#!/usr/bin/env python3
"""生成 agent-redlines.md (宪法 Wave 1: severity 分层 digest).

从 governance-checks.yaml::gac.rules 推导 severity:
  red  (阻塞 merge): executor 含 hook_pre_edit (事前拦) / ci_gate (CI 拦)
  gray (warn/审计): 其他 (omo_audit/gac_local_gate/radar_cron 等)

用法: python3 gen-agent-redlines.py [output_path]
默认输出: docs/generated/agent-redlines.md
"""
import yaml, sys, os
from collections import defaultdict

REGISTRY = ".omo/_truth/registry/governance-checks.yaml"
OUTPUT = sys.argv[1] if len(sys.argv) > 1 else "docs/generated/agent-redlines.md"
RED_EXECUTORS = {"hook_pre_edit", "ci_gate"}


def main():
    docs = list(yaml.safe_load_all(open(REGISTRY)))
    body = docs[1] if len(docs) > 1 else docs[0]
    rules = body.get("gac", {}).get("rules", [])
    red, gray = [], []
    for r in rules:
        (red if (set(r.get("executor") or []) & RED_EXECUTORS) else gray).append(r)

    L = [
        "# Agent 红线/灰线清单 (宪法 Wave 1)",
        "",
        f"> 自动生成 from `governance-checks.yaml::gac.rules` ({len(rules)} rules). **不要手编辑**.",
        f"> severity 推导: executor ∈ {{hook_pre_edit, ci_gate}} → 🔴 red (阻塞); 否则 → 🟡 gray (warn).",
        f"> 重新生成: `python3 bin/gen-agent-redlines.py`",
        "",
        f"## 🔴 红线 ({len(red)} 条 — 阻塞 merge, agent 必须遵守)",
        "",
    ]
    by = defaultdict(list)
    for r in red:
        by[r.get("dimension", "?")].append(r)
    for dim in sorted(by):
        L += [
            f"### {dim} ({len(by[dim])})", "",
            "| ID | Name | check_type | executor |",
            "|----|------|-----------|----------|",
        ]
        for r in by[dim]:
            L.append(
                f"| `{r.get('id','?')}` | {r.get('name','?')} | "
                f"{r.get('check_type','?')} | {','.join(r.get('executor') or [])} |"
            )
        L.append("")

    L += [f"## 🟡 灰线 ({len(gray)} 条 — warn/审计, 不阻塞 merge)", ""]
    byg = defaultdict(list)
    for r in gray:
        byg[r.get("dimension", "?")].append(r)
    for dim in sorted(byg):
        L += [f"### {dim} ({len(byg[dim])})", ""]
        for r in byg[dim]:
            L.append(f"- `{r.get('id','?')}`: {r.get('name','?')} ({r.get('check_type','?')})")
        L.append("")

    os.makedirs(os.path.dirname(OUTPUT) or ".", exist_ok=True)
    open(OUTPUT, "w").write("\n".join(L))
    print(f"✅ {OUTPUT}: {len(red)} red + {len(gray)} gray = {len(rules)} total")


if __name__ == "__main__":
    main()
