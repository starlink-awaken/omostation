#!/usr/bin/env python3
"""Constraint Coverage Report — show which content is protected by which constraints.

Usage:
    python bin/ssot/coverage_report.py --rules .omo/standards/rules/ --content docs/ .omo/_knowledge/
"""
import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: uv run --with pyyaml python bin/ssot/coverage_report.py")
    sys.exit(1)


def load_rules(rules_dir: str) -> list:
    """Load all rule files from directory."""
    rules = []
    rules_path = Path(rules_dir)
    if not rules_path.exists():
        return rules
    for f in rules_path.glob("*.yaml"):
        with open(f) as fh:
            data = yaml.safe_load(fh)
            if isinstance(data, dict) and "rules" in data:
                rules.extend(data["rules"])
            elif isinstance(data, list):
                rules.extend(data)
    return rules


def scan_content(content_dirs: list) -> dict:
    """Scan content directories and categorize by type."""
    stats = {
        "total_files": 0,
        "by_extension": {},
        "by_directory": {},
    }
    for d in content_dirs:
        p = Path(d)
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if f.is_file():
                stats["total_files"] += 1
                ext = f.suffix or "(none)"
                stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1
                top_dir = f.relative_to(p).parts[0] if len(f.relative_to(p).parts) > 1 else "(root)"
                stats["by_directory"][top_dir] = stats["by_directory"].get(top_dir, 0) + 1
    return stats


def generate_coverage_matrix(rules: list, content_stats: dict) -> dict:
    """Generate coverage matrix: content type x constraint type."""
    matrix = {}
    for rule in rules:
        rule_id = rule.get("rule_id", "unknown")
        predicate = rule.get("predicate", "unknown")
        target = rule.get("target", "")
        severity = rule.get("severity", "unknown")

        # Determine content type from target
        if "docs/" in target:
            content_type = "docs"
        elif ".omo/" in target:
            content_type = ".omo"
        else:
            content_type = "other"

        if content_type not in matrix:
            matrix[content_type] = []
        matrix[content_type].append({
            "rule_id": rule_id,
            "predicate": predicate,
            "severity": severity,
        })
    return matrix


def main():
    parser = argparse.ArgumentParser(description="Constraint Coverage Report")
    parser.add_argument("--rules", default=".omo/standards/rules/",
                        help="Path to rules directory")
    parser.add_argument("--content", nargs="+", default=["docs/", ".omo/_knowledge/"],
                        help="Content directories to scan")
    args = parser.parse_args()

    rules = load_rules(args.rules)
    print(f"Loaded {len(rules)} rules from {args.rules}")

    content_stats = scan_content(args.content)
    print(f"Scanned {content_stats['total_files']} files")

    matrix = generate_coverage_matrix(rules, content_stats)

    print("\n=== Coverage Matrix ===")
    print(f"{'Content Type':<20} {'Rules':<10} {'Predicates'}")
    print("-" * 60)
    for content_type, rule_list in sorted(matrix.items()):
        predicates = ", ".join(sorted(set(r["predicate"] for r in rule_list)))
        print(f"{content_type:<20} {len(rule_list):<10} {predicates}")

    # Find uncovered content types
    all_exts = set(content_stats["by_extension"].keys())
    covered_exts = set()
    for rule in rules:
        target = rule.get("target", "")
        if "docs/" in target:
            covered_exts.add(".md")
        elif ".omo/" in target:
            covered_exts.add(".yaml")

    uncovered = all_exts - covered_exts
    if uncovered:
        print(f"\n⚠️  Uncovered extensions: {', '.join(sorted(uncovered))}")
    else:
        print(f"\n✅ All extensions covered")

    # Find zombie constraints (rules with no matching content)
    print("\n=== Zombie Constraint Check ===")
    zombie_count = 0
    for rule in rules:
        target = rule.get("target", "")
        if target and not any(target in d for d in args.content):
            zombie_count += 1
            print(f"  ⚠️  {rule.get('rule_id', 'unknown')}: target '{target}' not in scanned dirs")
    if zombie_count == 0:
        print("  ✅ No zombie constraints found")


if __name__ == "__main__":
    main()
