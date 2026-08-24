#!/usr/bin/env python3
"""
skill-registry-verify.py — Verify .agents/skills/ registry health.

Usage:
  uv run python3 bin/gac/skill-registry-verify.py
  uv run python3 bin/gac/skill-registry-verify.py --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = REPO_ROOT / ".agents" / "skills"


def check_skill_registry() -> dict:
    if not SKILLS_DIR.exists():
        return {"check": "skill_registry_validity", "pass": True, "output": "No skills directory"}

    orphaned = []
    total = 0
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            orphaned.append(f"{skill_dir.name}: no SKILL.md")
            continue
        total += 1
        text = skill_md.read_text(errors="ignore")
        # Skip builtin skills
        if "location: builtin" in text or "builtin" in text.lower():
            continue
        # Check for broken references to bin/ commands
        for m in re.finditer(r"`(bin/[^`]+)`", text):
            cmd_path = m.group(1).split()[0]
            # Skip placeholders like bin/ssot/<tool-name>.py
            if "<" in cmd_path or ">" in cmd_path:
                continue
            # Skip wildcard patterns like bin/gac-*.py
            if "*" in cmd_path:
                continue
            # Skip module/constant references like bin/gac-drift.py::EXECUTOR_ENUM
            if "::" in cmd_path:
                continue
            # Skip documentation examples with explanatory comments
            if "#" in m.group(1) and ("example" in m.group(1).lower() or "e.g." in m.group(1).lower() or "替代" in m.group(1)):
                continue
            # Skip project-local tools (e.g. projects/agora/bin/evidence-smoke.py)
            if cmd_path.startswith("projects/") or "/projects/" in cmd_path:
                continue
            if not (REPO_ROOT / cmd_path).exists():
                orphaned.append(f"{skill_dir.name}: references missing {cmd_path}")

    return {
        "check": "skill_registry_validity",
        "pass": len(orphaned) == 0,
        "output": f"Checked {total} skills, {len(orphaned)} issues" + (f": {orphaned[0]}" if orphaned else ""),
        "details": orphaned,
    }


def check_skill_frontmatter() -> dict:
    if not SKILLS_DIR.exists():
        return {"check": "skill_frontmatter_validity", "pass": True, "output": "No skills directory"}

    issues = []
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(errors="ignore")
        if not text.startswith("---"):
            issues.append(f"{skill_dir.name}: missing frontmatter")
            continue
        frontmatter = text.split("---", 2)[1]
        for field in ["name:", "description:"]:
            if field not in frontmatter:
                issues.append(f"{skill_dir.name}: missing {field}")

    return {
        "check": "skill_frontmatter_validity",
        "pass": len(issues) == 0,
        "output": f"{len(issues)} issues found" if issues else "All skills have valid frontmatter",
        "details": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill registry verification")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    checks = [check_skill_registry(), check_skill_frontmatter()]
    failures = [c for c in checks if not c["pass"]]

    if args.json:
        print(json.dumps({"checks": checks, "failures": len(failures), "pass": len(failures) == 0}, indent=2))
        sys.exit(0 if len(failures) == 0 else 1)

    print("Skill Registry Verification")
    print("=" * 50)
    for c in checks:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"[{status}] {c['check']}")
        if c.get("details"):
            for d in c["details"][:10]:
                print(f"       - {d}")
        elif c["output"]:
            print(f"       {c['output']}")
    print("=" * 50)
    if failures:
        print(f"FAILED: {len(failures)} check(s) failed")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
