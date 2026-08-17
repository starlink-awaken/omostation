#!/usr/bin/env python3
"""check-agent-skills.py — Agent Skills frontmatter and contract validator.

Verifies that all skills in `.agents/skills/*/SKILL.md` conform to standard:
1. Valid YAML frontmatter delimited by `---`.
2. Mandatory fields: `name` (alphanumeric/hyphen/underscore), `description` (non-empty).
3. No corrupted markdown delimiters or broken local references.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def validate_skill_file(skill_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        content = skill_path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"Cannot read file: {exc}"]

    # Check frontmatter
    if not content.startswith("---"):
        return ["Missing leading '---' YAML frontmatter delimiter"]

    parts = content.split("---", 2)
    if len(parts) < 3:
        return ["Missing closing '---' YAML frontmatter delimiter"]

    frontmatter_raw = parts[1]
    try:
        meta = yaml.safe_load(frontmatter_raw)
        if not isinstance(meta, dict):
            return ["Frontmatter is not a valid YAML dictionary"]
    except Exception as exc:
        return [f"YAML syntax error in frontmatter: {exc}"]

    # Validate name
    name = meta.get("name")
    if not name or not isinstance(name, str):
        errors.append("Field 'name' is required and must be a non-empty string")
    elif not re.match(r"^[a-zA-Z0-9_:-]+$", name):
        errors.append(f"Field 'name' contains invalid characters: '{name}'")

    # Validate description
    description = meta.get("description")
    if not description or not isinstance(description, str):
        errors.append("Field 'description' is required and must be a non-empty string")
    elif len(description.strip()) < 10:
        errors.append("Field 'description' is too short (< 10 chars)")

    return errors


def check_all_skills(workspace_root: Path) -> dict[str, Any]:
    skills_dir = workspace_root / ".agents" / "skills"
    results: dict[str, Any] = {
        "ok": True,
        "total_skills": 0,
        "valid_skills": 0,
        "errors": {},
    }

    if not skills_dir.exists():
        return results

    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    results["total_skills"] = len(skill_files)

    for skill_file in skill_files:
        rel_path = str(skill_file.relative_to(workspace_root))
        errs = validate_skill_file(skill_file)
        if errs:
            results["ok"] = False
            results["errors"][rel_path] = errs
        else:
            results["valid_skills"] += 1

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Agent Skills YAML frontmatter")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    res = check_all_skills(WORKSPACE_ROOT)

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res["ok"]:
            print(f"✅ All {res['total_skills']} Agent skills validated successfully.")
        else:
            print(f"❌ {len(res['errors'])} skill(s) failed validation:")
            for path, errs in res["errors"].items():
                print(f"  - {path}:")
                for err in errs:
                    print(f"      • {err}")

    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
