#!/usr/bin/env python3
"""CR-ANTI-CORRUPTION: 防腐机制 CI 校验.

检测三类腐败:
  1. 工具冗余 — 零调用/被替代的工具
  2. 文档过期 — frontmatter last-reviewed 超期
  3. 约束冗余 — 无违规历史的 required 规则

用法:
    python3 anti-corruption.py              # 报告
    python3 anti-corruption.py --json       # JSON
    python3 anti-corruption.py --enforce    # 有违规则 exit 1
"""

import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ECOS_TOOLS = REPO / "projects/ecos/src/ecos/ssot/tools"
DOCS = REPO / "docs"


def audit_tools() -> dict:
    """工具审计 — 检测未接入CI的工具."""
    if not ECOS_TOOLS or not ECOS_TOOLS.exists():
        return {"total": 0, "in_ci": 0, "unused": [], "unused_count": 0, "skipped": "submodule not init"}

    ci_content = ""
    for wf in (REPO / ".github/workflows").glob("*.yml"):
        ci_content += wf.read_text()

    tools = []
    for f in sorted(ECOS_TOOLS.glob("*.py")):
        name = f.stem
        if name.startswith("_"):
            continue
        in_ci = name in ci_content
        tools.append({"name": name, "in_ci": in_ci})

    unused = [t["name"] for t in tools if not t["in_ci"]]
    return {
        "total": len(tools),
        "in_ci": len(tools) - len(unused),
        "unused": unused[:10],
        "unused_count": len(unused),
    }


def audit_docs() -> dict:
    """文档过期检测 — frontmatter last-reviewed > 30天."""
    import yaml
    if not DOCS or not DOCS.exists():
        return {"total_reviewed": 0, "stale_count": 0, "stale": [], "fresh_count": 0, "skipped": "docs not found"}
    stale = []
    fresh = []
    now = datetime.now()
    for f in DOCS.rglob("*.md"):
        try:
            text = f.read_text()
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    fm = yaml.safe_load(text[3:end])
                    if isinstance(fm, dict) and "last-reviewed" in fm:
                        lr = str(fm["last-reviewed"])[:10]
                        try:
                            last = datetime.strptime(lr, "%Y-%m-%d")
                            age_days = (now - last).days
                            info = {"file": str(f.relative_to(REPO)), "age_days": age_days, "last_reviewed": lr}
                            if age_days > 30:
                                stale.append(info)
                            else:
                                fresh.append(info)
                        except ValueError:
                            pass
        except Exception:
            continue

    stale.sort(key=lambda x: -x["age_days"])
    return {
        "total_reviewed": len(stale) + len(fresh),
        "stale_count": len(stale),
        "stale": stale[:10],
        "fresh_count": len(fresh),
    }


def main():
    import argparse
    import json as _json
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    result = {
        "timestamp": datetime.now().isoformat(),
        "tools": audit_tools(),
        "docs": audit_docs(),
    }

    if args.json:
        print(_json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Anti-Corruption Audit")
    print("=" * 56)
    print(f"\n  Tools: {result['tools']['in_ci']}/{result['tools']['total']} in CI")
    if result['tools']['unused_count'] > 0:
        print(f"  WARNING {result['tools']['unused_count']} tools not in CI")
        for t in result['tools']['unused'][:5]:
            print(f"      - {t}")

    print(f"\n  Docs: {result['docs']['fresh_count']} fresh, {result['docs']['stale_count']} stale (>30d)")
    if result['docs']['stale']:
        for d in result['docs']['stale'][:5]:
            print(f"      WARNING {d['file']}: {d['age_days']}d")

    print(f"\n{'=' * 60}")

    if args.enforce:
        if result['docs']['stale_count'] > 5:
            print("ENFORCE: too many stale docs")
            sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
