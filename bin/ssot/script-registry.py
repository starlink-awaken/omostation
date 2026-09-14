#!/usr/bin/env python3
"""
script-registry.py — bin/ script registry management tool.

Usage:
  uv run python3 bin/ssot/script-registry.py register <path>     # Interactive registration
  uv run python3 bin/ssot/script-registry.py validate           # Validate all registrations
  uv run python3 bin/ssot/script-registry.py query --category governance
  uv run python3 bin/ssot/script-registry.py generate-index > docs/generated/script-registry.md
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_DIR = REPO_ROOT / "bin" / "_registry" / "scripts"
SCHEMA_DIR = REPO_ROOT / "bin" / "_registry" / "schemas" / "script-registry" / "v1"
BIN_DIR = REPO_ROOT / "bin"

CATEGORY_MAP = {
    "gac": "governance",
    "mof": "governance",
    "ssot": "governance",
    "plan": "governance",
    "bc-os": "governance",
    "compass_radar.py": "state",
    "health": "state",
    "rotate-history.py": "state",
    "agent-workflow.py": "workflow",
    "workflow": "workflow",
    "sync-planned-to-done.py": "migration",
    "submodule-pointer-transaction.sh": "migration",
    "adr": "knowledge",
    "meta-doctor.py": "knowledge",
    "start-cockpit-dashboard.sh": "runtime",
}


def guess_category(script_path: str) -> str:
    name = Path(script_path).name.lower()
    for key, cat in CATEGORY_MAP.items():
        if key.lower() in name:
            return cat
    return "governance"


def guess_owner(script_path: str) -> str:
    name = Path(script_path).name.lower()
    if any(x in name for x in ["gac", "mof", "ssot", "governance"]):
        return "governance-team"
    if any(x in name for x in ["state", "health", "radar"]):
        return "governance-team"
    if any(x in name for x in ["workflow", "agent"]):
        return "governance-team"
    if any(x in name for x in ["plan", "bet"]):
        return "governance-team"
    return "governance-team"


def register(script_path: str, dry_run: bool = False) -> None:
    p = Path(script_path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        print(f"ERROR: {p} not found")
        sys.exit(1)

    rel = p.relative_to(REPO_ROOT)
    category = guess_category(str(rel))
    owner = guess_owner(str(rel))
    stem = rel.stem
    out = REGISTRY_DIR / category / f"{stem}.yaml"
    # Same-stem scripts in different directories would collide on the same file.
    # If the canonical file exists with a different id, disambiguate by parent dir.
    if out.exists():
        try:
            existing = yaml.safe_load(out.read_text()) if out.suffix == ".yaml" else None
            if existing and existing.get("id") != str(rel):
                out = REGISTRY_DIR / category / f"{stem}-{rel.parent.name}.yaml"
        except Exception:
            out = REGISTRY_DIR / category / f"{stem}-{rel.parent.name}.yaml"


    content = f"""schema: script-registry/v1
id: {rel}
name: {stem.replace('-', ' ').replace('_', ' ').title()}
category: {category}
owner: {owner}
description: ""
inputs: []
outputs:
  - type: exit_code
  - type: json
dependencies: []
triggers: []
related: []
maturity: draft
last_reviewed: "2026-08-24"
"""

    if dry_run:
        print(f"[dry-run] Would write: {out}")
        print(content)
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)
    print(f"Registered: {rel} -> {out}")


def validate() -> None:
    import yaml

    errors = []
    registered = set()
    for f in REGISTRY_DIR.rglob("*.yaml"):
        try:
            data = yaml.safe_load(f.read_text())
            if data and "id" in data:
                registered.add(data["id"])
        except Exception as e:
            errors.append(f"{f}: {e}")

    actual_scripts = set()
    # 只验证 git tracked 脚本 (2026-08-27 深度复盘: iterdir 扫文件系统会把并行
    # agent 的进行中未提交脚本算进来, 冻结所有人的 push — 应只问责已提交面)
    import subprocess
    ls = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD", "--name-only", "--", "bin"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    for line in ls.stdout.splitlines():
        line = line.strip()
        if not line.endswith((".py", ".sh")):
            continue
        parts = Path(line).parts
        if len(parts) > 1 and parts[1] == "_registry":
            continue
        if len(parts) > 1 and parts[1].startswith("_"):
            continue
        actual_scripts.add(line)

    missing = actual_scripts - registered
    extra = registered - actual_scripts

    if missing:
        errors.append(f"Missing registrations: {len(missing)}")
        for m in sorted(missing)[:20]:
            errors.append(f"  - {m}")
    if extra:
        errors.append(f"Orphaned registrations: {len(extra)}")
        for e in sorted(extra)[:20]:
            errors.append(f"  - {e}")

    if errors:
        print("VALIDATION FAILED")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print(f"VALIDATION PASSED: {len(registered)} scripts registered")


def query(category: str = None, owner: str = None, depends_on: str = None) -> None:
    import yaml

    matches = []
    for f in REGISTRY_DIR.rglob("*.yaml"):
        try:
            data = yaml.safe_load(f.read_text())
            if not data or "id" not in data:
                continue
            if category and data.get("category") != category:
                continue
            if owner and data.get("owner") != owner:
                continue
            if depends_on and depends_on not in data.get("dependencies", []):
                continue
            matches.append(data)
        except Exception:
            continue

    for m in matches:
        print(f"{m.get('id', 'N/A')} | {m.get('name', 'N/A')} | {m.get('category', 'N/A')} | {m.get('owner', 'N/A')}")


def generate_index() -> None:
    import yaml

    by_category = {}
    for f in sorted(REGISTRY_DIR.rglob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text())
            if not data or "id" not in data:
                continue
            cat = data.get("category", "unknown")
            by_category.setdefault(cat, []).append(data)
        except Exception:
            continue

    lines = [
        "# Script Registry Index",
        "",
        "> Auto-generated by `bin/ssot/script-registry.py generate-index`",
        "",
        f"Total scripts: {sum(len(v) for v in by_category.values())}",
        "",
    ]
    for cat in sorted(by_category.keys()):
        lines.append(f"## {cat.title()}")
        lines.append("")
        for s in sorted(by_category[cat], key=lambda x: x.get("id", "")):
            lines.append(f"- `{s.get('id', 'N/A')}` — {s.get('name', 'N/A')} (owner: {s.get('owner', 'N/A')})")
        lines.append("")

    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Script registry management")
    sub = parser.add_subparsers(dest="cmd")

    p_reg = sub.add_parser("register", help="Register a script")
    p_reg.add_argument("path", help="Script path")
    p_reg.add_argument("--dry-run", action="store_true")

    sub.add_parser("validate", help="Validate all registrations")

    p_query = sub.add_parser("query", help="Query registry")
    p_query.add_argument("--category", default=None)
    p_query.add_argument("--owner", default=None)
    p_query.add_argument("--depends-on", default=None)

    sub.add_parser("generate-index", help="Generate markdown index")

    args = parser.parse_args()

    if args.cmd == "register":
        register(args.path, args.dry_run)
    elif args.cmd == "validate":
        validate()
    elif args.cmd == "query":
        query(args.category, args.owner, args.depends_on)
    elif args.cmd == "generate-index":
        generate_index()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
