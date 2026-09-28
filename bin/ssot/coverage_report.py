#!/usr/bin/env python3
"""Constraint Coverage Report — show which content is protected by which constraints.

Usage:
    python bin/ssot/coverage_report.py --rules .omo/standards/rules/ --content docs/ .omo/_knowledge/
    python bin/ssot/coverage_report.py --all
"""
import argparse
import sys
from pathlib import Path
from collections import defaultdict

try:
    import yaml
except ImportError:
    print("PyYAML required: uv run --with pyyaml python bin/ssot/coverage_report.py")
    sys.exit(1)


# Content type classification
CONTENT_TYPES = {
    "docs": ["docs/", "README.md", "CHANGELOG.md", "CONTRIBUTING.md"],
    "omo_knowledge": [".omo/_knowledge/"],
    "omo_truth": [".omo/_truth/"],
    "omo_state": [".omo/state/"],
    "protocols": ["protocols/"],
    "standards": [".omo/standards/"],
    "config": ["config/"],
    "bin_tools": ["bin/"],
    "projects": ["projects/"],
}

# Constraint type classification
CONSTRAINT_TYPES = {
    "L0": ["L0-constraints", "CR-L0"],
    "X1": ["x1-governance", "X1-Audit"],
    "X2": ["x2-freshness", "X2-Staleness"],
    "X3": ["x3-value", "X3-Value"],
    "X4": ["x4-consistency", "X4-Consistency"],
    "SFOP": ["SFOP", "CR-SFOP"],
    "DFSQ": ["DFSQ", "CR-DFSQ"],
    "MOF": ["MOF", "CR-MOF"],
}


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


def classify_content(filepath: str) -> str:
    """Classify file into content type."""
    for ctype, patterns in CONTENT_TYPES.items():
        for pattern in patterns:
            if pattern in filepath:
                return ctype
    return "other"


def classify_constraint(rule: dict) -> str:
    """Classify rule into constraint type."""
    rule_id = rule.get("rule_id", "")
    rule_str = str(rule)
    for ctype, patterns in CONSTRAINT_TYPES.items():
        for pattern in patterns:
            if pattern in rule_str or pattern in rule_id:
                return ctype
    return "other"


def scan_content(content_dirs: list) -> dict:
    """Scan content directories and categorize by type."""
    stats = {
        "total_files": 0,
        "by_type": defaultdict(int),
        "by_extension": defaultdict(int),
        "uncovered": [],
    }
    for d in content_dirs:
        p = Path(d)
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if f.is_file():
                stats["total_files"] += 1
                ftype = classify_content(str(f))
                stats["by_type"][ftype] += 1
                ext = f.suffix or "(none)"
                stats["by_extension"][ext] += 1
                # Check if file has frontmatter
                if f.suffix == ".md":
                    try:
                        content = f.read_text(encoding="utf-8")
                        if not content.startswith("---"):
                            stats["uncovered"].append(str(f))
                    except:
                        pass
    return stats


def generate_coverage_matrix(rules: list, content_stats: dict) -> dict:
    """Generate coverage matrix: content type x constraint type."""
    matrix = defaultdict(lambda: defaultdict(int))
    for rule in rules:
        ctype = classify_constraint(rule)
        matrix["all"][ctype] += 1
    return matrix


def main():
    parser = argparse.ArgumentParser(description="Constraint Coverage Report")
    parser.add_argument("--rules", default=".omo/standards/rules/",
                        help="Path to rules directory")
    parser.add_argument("--content", nargs="+",
                        default=["docs/", ".omo/_knowledge/", ".omo/_truth/",
                                 "protocols/", ".omo/standards/", "config/"],
                        help="Content directories to scan")
    parser.add_argument("--all", action="store_true",
                        help="Run full coverage analysis")
    args = parser.parse_args()

    rules = load_rules(args.rules)
    print(f"Loaded {len(rules)} rules from {args.rules}")

    content_stats = scan_content(args.content)
    print(f"Scanned {content_stats['total_files']} files")

    matrix = generate_coverage_matrix(rules, content_stats)

    print("\n=== Coverage Matrix ===")
    print(f"{'Content Type':<20} {'Rules':<10} {'Coverage'}")
    print("-" * 60)
    for content_type in sorted(content_stats["by_type"].keys()):
        file_count = content_stats["by_type"][content_type]
        rule_count = len([r for r in rules if classify_content(str(r)) == content_type])
        print(f"{content_type:<20} {file_count:<10} {rule_count}")

    print("\n=== Constraint Type Distribution ===")
    print(f"{'Constraint Type':<20} {'Count'}")
    print("-" * 40)
    for ctype in sorted(matrix["all"].keys()):
        count = matrix["all"][ctype]
        print(f"{ctype:<20} {count}")

    # Find uncovered content
    uncovered = content_stats["uncovered"]
    if uncovered:
        print(f"\n⚠️  {len(uncovered)} markdown files without frontmatter:")
        for f in uncovered[:10]:
            print(f"  - {f}")
        if len(uncovered) > 10:
            print(f"  ... and {len(uncovered) - 10} more")

    if args.all:
        print("\n=== Full Coverage Analysis ===")
        print(f"Total rules: {len(rules)}")
        print(f"Total files: {content_stats['total_files']}")
        print(f"Files with frontmatter: {content_stats['total_files'] - len(uncovered)}")
        print(f"Files without frontmatter: {len(uncovered)}")
        coverage_pct = (content_stats["total_files"] - len(uncovered)) / max(content_stats["total_files"], 1) * 100
        print(f"Frontmatter coverage: {coverage_pct:.1f}%")


if __name__ == "__main__":
    main