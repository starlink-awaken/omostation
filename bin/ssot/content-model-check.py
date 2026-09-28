#!/usr/bin/env python3
"""Content Model Check — pre-commit hook for content model validation.

Usage:
    python bin/ssot/content-model-check.py --files file1.md file2.yaml
    python bin/ssot/content-model-check.py --changed-only
"""
import argparse
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: uv run --with pyyaml python bin/ssot/content-model-check.py")
    sys.exit(1)


def get_changed_files() -> list:
    """Get list of changed files from git."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def check_fm_schema(filepath: str) -> list:
    """Check if file has valid frontmatter schema."""
    violations = []
    p = Path(filepath)
    if not p.exists():
        return violations

    content = p.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return violations  # No FM, skip

    end = content.find("---", 3)
    if end == -1:
        violations.append(f"{filepath}: unclosed frontmatter")
        return violations

    fm_text = content[3:end]
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        violations.append(f"{filepath}: invalid YAML in frontmatter: {e}")
        return violations

    if not isinstance(fm, dict):
        return violations

    # Check required fields for md files
    if p.suffix == ".md":
        required = ["schema", "status", "lifecycle", "owner"]
        for field in required:
            if field not in fm:
                violations.append(f"{filepath}: missing required FM field '{field}'")

    return violations


def main():
    parser = argparse.ArgumentParser(description="Content Model Check")
    parser.add_argument("--files", nargs="*", help="Files to check")
    parser.add_argument("--changed-only", action="store_true",
                        help="Check only git-changed files")
    args = parser.parse_args()

    if args.changed_only:
        files = get_changed_files()
    elif args.files:
        files = args.files
    else:
        print("No files specified. Use --changed-only or --files")
        sys.exit(0)

    # Filter to relevant files
    relevant = [f for f in files if f.endswith((".md", ".yaml", ".yml"))]
    if not relevant:
        print("No relevant files to check")
        sys.exit(0)

    print(f"Checking {len(relevant)} files...")

    all_violations = []
    for f in relevant:
        violations = check_fm_schema(f)
        all_violations.extend(violations)

    if all_violations:
        print(f"\n❌ {len(all_violations)} violations found:")
        for v in all_violations:
            print(f"  {v}")
        sys.exit(1)
    else:
        print(f"✅ All {len(relevant)} files passed content model check")


if __name__ == "__main__":
    main()
