#!/usr/bin/env python3
"""Incremental Content Model Check — only check git-changed files.

Usage:
    python bin/ssot/incremental-check.py --base origin/main
    python bin/ssot/incremental-check.py --base HEAD~1
"""
import argparse
import subprocess
import sys
from pathlib import Path


def get_changed_files(base: str) -> list:
    """Get list of changed files since base commit."""
    result = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        # Try with merge-base
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            capture_output=True, text=True
        )
    files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    return files


def check_file(filepath: str) -> list:
    """Check a single file for content model violations."""
    violations = []
    p = Path(filepath)
    if not p.exists() or p.is_dir():
        return violations

    try:
        content = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return violations

    # Check markdown files for frontmatter
    if filepath.endswith(".md"):
        if not content.startswith("---"):
            violations.append(f"{filepath}: missing frontmatter")
        else:
            end = content.find("---", 3)
            if end == -1:
                violations.append(f"{filepath}: unclosed frontmatter")
            else:
                fm_text = content[3:end]
                try:
                    import yaml
                    fm = yaml.safe_load(fm_text)
                    if not isinstance(fm, dict):
                        violations.append(f"{filepath}: frontmatter is not a mapping")
                    else:
                        required = ["schema", "status", "lifecycle", "owner"]
                        for field in required:
                            if field not in fm:
                                violations.append(f"{filepath}: missing required FM field '{field}'")
                except yaml.YAMLError as e:
                    violations.append(f"{filepath}: invalid YAML in frontmatter: {e}")

    # Check for hardcoded absolute paths
    if "/Users/xiamingxing/" in content:
        violations.append(f"{filepath}: contains hardcoded absolute path")

    return violations


def main():
    parser = argparse.ArgumentParser(description="Incremental Content Model Check")
    parser.add_argument("--base", default="origin/main",
                        help="Base commit to compare against")
    args = parser.parse_args()

    changed_files = get_changed_files(args.base)
    print(f"Found {len(changed_files)} changed files since {args.base}")

    all_violations = []
    for f in changed_files:
        violations = check_file(f)
        all_violations.extend(violations)

    if all_violations:
        print(f"\n❌ {len(all_violations)} violations found:")
        for v in all_violations:
            print(f"  {v}")
        sys.exit(1)
    else:
        print(f"\n✅ All {len(changed_files)} changed files passed content model check")


if __name__ == "__main__":
    main()
