#!/usr/bin/env python3
"""Generic Rule Engine — load YAML rules and execute against content.

Usage:
    python bin/ssot/rule_engine.py --rules .omo/standards/rules/l0-constraints.yaml --target docs/
    python bin/ssot/rule_engine.py --rules .omo/standards/rules/content-rules.yaml --target .omo/_knowledge/
"""
import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: uv run --with pyyaml python bin/ssot/rule_engine.py")
    sys.exit(1)


def load_rules(rules_path: str) -> list:
    """Load rules from YAML file."""
    with open(rules_path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, list) else data.get("rules", [])


def check_file_exists(target: str) -> bool:
    """Check if target file/directory exists."""
    return Path(target).exists()


def check_fm_field(content: str, field: str) -> bool:
    """Check if frontmatter has a field."""
    if not content.startswith("---"):
        return False
    end = content.find("---", 3)
    if end == -1:
        return False
    fm = content[3:end]
    return any(line.strip().startswith(f"{field}:") for line in fm.split("\n"))


def execute_rule(rule: dict, target: str) -> dict:
    """Execute a single rule against a target."""
    predicate = rule.get("predicate", "")
    result = {
        "rule_id": rule.get("rule_id", "unknown"),
        "target": target,
        "predicate": predicate,
        "passed": True,
        "message": "",
    }

    if predicate == "file_exists":
        result["passed"] = check_file_exists(target)
        if not result["passed"]:
            result["message"] = f"File not found: {target}"

    elif predicate == "fm_field_exists":
        field = rule.get("field", "")
        if Path(target).is_file():
            content = Path(target).read_text()
            result["passed"] = check_fm_field(content, field)
            if not result["passed"]:
                result["message"] = f"FM field '{field}' not found in {target}"
        else:
            result["passed"] = False
            result["message"] = f"Target is not a file: {target}"

    return result


def main():
    parser = argparse.ArgumentParser(description="Generic Rule Engine")
    parser.add_argument("--rules", required=True, help="Path to rules YAML file")
    parser.add_argument("--target", required=True, help="Target path to check")
    args = parser.parse_args()

    rules = load_rules(args.rules)
    print(f"Loaded {len(rules)} rules from {args.rules}")

    violations = []
    for rule in rules:
        result = execute_rule(rule, args.target)
        if not result["passed"]:
            violations.append(result)
            print(f"  ❌ {result['rule_id']}: {result['message']}")

    if not violations:
        print(f"✅ All {len(rules)} rules passed for {args.target}")
    else:
        print(f"\n❌ {len(violations)}/{len(rules)} rules failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
