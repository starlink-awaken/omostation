#!/usr/bin/env python3
"""Apply explicit pyright suppressions from a JSON diagnostics report."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_RULE = "reportGeneralTypeIssues"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--package", help="Only edit diagnostics whose paths contain this package")
    parser.add_argument("--test-header-threshold", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--suppression-gate",
        action="store_true",
        help="A3 (ADR-0367): exit 1 when file_suppressions >= 3 or suppression_ratio > 0.6",
    )
    return parser.parse_args()


def load_errors(report: Path, package: str | None) -> list[dict[str, Any]]:
    payload = json.loads(report.read_text())
    errors = [item for item in payload.get("generalDiagnostics", []) if item.get("severity") == "error"]
    if package:
        errors = [item for item in errors if f"/{package}/" in item["file"]]
    return errors


def insert_headers(lines: list[str], rules: list[str]) -> tuple[list[str], int]:
    existing = {line.split("=")[0].strip() for line in lines if line.strip().startswith("# pyright:")}
    additions = [f"# pyright: {rule}=false" for rule in rules if f"# pyright: {rule}" not in existing]
    if not additions:
        return lines, 0
    return additions + [""] + lines, len(additions) + 1


def main() -> int:
    args = parse_args()
    by_file: dict[Path, list[dict[str, Any]]] = defaultdict(list)
    for item in load_errors(args.report, args.package):
        by_file[Path(item["file"])].append(item)

    changed = 0
    line_suppressions = 0
    file_suppressions = 0
    for path, items in sorted(by_file.items()):
        if not path.is_file():
            raise FileNotFoundError(path)
        original = path.read_text()
        lines = original.split("\n")
        test_file = "/tests/" in path.as_posix() or "/benchmarks/" in path.as_posix()
        counts = Counter(item.get("rule") or DEFAULT_RULE for item in items)
        header_rules = sorted(
            rule for rule, count in counts.items() if test_file and count >= args.test_header_threshold
        )
        lines, offset = insert_headers(lines, header_rules)
        file_suppressions += offset - 1 if offset else 0

        seen: set[tuple[int, str]] = set()
        for item in sorted(items, key=lambda value: value["range"]["start"]["line"]):
            rule = item.get("rule") or DEFAULT_RULE
            if rule in header_rules:
                continue
            line_number = item["range"]["start"]["line"] + offset
            key = (line_number, rule)
            if key in seen or line_number >= len(lines):
                continue
            seen.add(key)
            line = lines[line_number]
            if "type: ignore" in line or "noqa" in line or line.rstrip().endswith("\\"):
                continue
            lines[line_number] = f"{line.rstrip()}  # type: ignore[{rule}]"
            line_suppressions += 1

        rendered = "\n".join(lines)
        if rendered != original:
            changed += 1
            if not args.dry_run:
                path.write_text(rendered)

    error_count = sum(len(items) for items in by_file.values())
    suppressed_diagnostics = line_suppressions + sum(
        sum(1 for item in items if (item.get("rule") or DEFAULT_RULE) in {
            line.split("=", 1)[0].removeprefix("# pyright: ")
            for line in Path(path).read_text().splitlines()
            if line.startswith("# pyright:")
        })
        for path, items in by_file.items()
        if Path(path).is_file()
    )
    suppression_ratio = suppressed_diagnostics / error_count if error_count else 0.0
    print(
        f"errors={error_count} files={changed} line_suppressions={line_suppressions} "
        f"file_suppressions={file_suppressions} suppression_ratio={suppression_ratio:.3f}"
    )
    if args.suppression_gate and (
        file_suppressions >= 3 or suppression_ratio > 0.6
    ):
        print(
            "❌ suppression gate: "
            f"file_suppressions={file_suppressions} (>=3) 或 "
            f"suppression_ratio={suppression_ratio:.3f} (>0.6), 需要修复而非禁言"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
