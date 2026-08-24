#!/usr/bin/env python3
"""
hardcode-scan.py — Scan for hardcoded values that should be in SSOT.

Usage:
  uv run python3 bin/gac/hardcode-scan.py
  uv run python3 bin/gac/hardcode-scan.py --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCAN_EXTENSIONS = {".py", ".ts", ".js", ".yaml", ".yml", ".json", ".sh", ".md"}

# Patterns that suggest hardcoded values
PATTERNS = [
    (r"https?://[a-zA-Z0-9.-]+\.example\.com", "example.com URL"),
    (r"localhost:\d{4}", "hardcoded localhost port"),
    (r"127\.0\.0\.1:\d{4}", "hardcoded localhost port"),
    (r"port\s*=\s*\d{4}", "hardcoded port number"),
    (r"api_key\s*=\s*['\"][^'\"]+['\"]", "hardcoded API key"),
    (r"password\s*=\s*['\"][^'\"]+['\"]", "hardcoded password"),
    (r"token\s*=\s*['\"][^'\"]+['\"]", "hardcoded token"),
    (r"/Users/[a-zA-Z0-9]+/", "hardcoded user path"),
    (r"/home/[a-zA-Z0-9]+/", "hardcoded home path"),
]


def scan_file(file_path: Path) -> list:
    issues = []
    try:
        text = file_path.read_text(errors="ignore")
    except Exception:
        return issues

    for pattern, desc in PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            line_num = text[:m.start()].count("\n") + 1
            issues.append({
                "file": str(file_path.relative_to(REPO_ROOT)),
                "line": line_num,
                "pattern": desc,
                "match": m.group(0)[:80],
            })

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Hardcoded value scanner")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    all_issues = []
    for d in [REPO_ROOT / "bin", REPO_ROOT / "projects", REPO_ROOT / ".omo"]:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix not in SCAN_EXTENSIONS:
                continue
            if ".git" in str(f):
                continue
            all_issues.extend(scan_file(f))

    if args.json:
        result = {
            "check": "hardcoded_values",
            "issue_count": len(all_issues),
            "issues": all_issues[:50],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if not all_issues else 1)

    print("Hardcoded Value Scan")
    print("=" * 50)
    if all_issues:
        print(f"FAIL: {len(all_issues)} potential hardcoded values found")
        for issue in all_issues[:20]:
            print(f"  - {issue['file']}:{issue['line']}: {issue['pattern']}")
            print(f"       {issue['match']}")
        sys.exit(1)
    else:
        print("PASS: No hardcoded values detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
