#!/usr/bin/env python3
"""Merge simple nested context managers without changing body scope."""

import argparse
import ast
import re
from pathlib import Path

WITH_PATTERN = re.compile(r"^(\s*)with (.*):\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip())


def merge(source: str) -> tuple[str, int]:
    lines = source.split("\n")
    output: list[str] = []
    index = 0
    merged = 0
    while index < len(lines):
        outer = WITH_PATTERN.match(lines[index])
        inner = WITH_PATTERN.match(lines[index + 1]) if outer and index + 1 < len(lines) else None
        if not outer or not inner or inner.group(1) != outer.group(1) + "    ":
            output.append(lines[index])
            index += 1
            continue

        body_start = index + 2
        body_end = body_start
        while body_end < len(lines):
            line = lines[body_end]
            if line.strip() and indentation(line) <= len(inner.group(1)):
                break
            body_end += 1
        if body_start == body_end:
            output.append(lines[index])
            index += 1
            continue

        output.append(f"{outer.group(1)}with {outer.group(2)}, {inner.group(2)}:")
        for line in lines[body_start:body_end]:
            output.append(line.removeprefix("    "))
        index = body_end
        merged += 1

    rendered = "\n".join(output)
    ast.parse(rendered)
    return rendered, merged


def main() -> int:
    args = parse_args()
    original = args.path.read_text()
    rendered, merged = merge(original)
    if rendered != original and not args.dry_run:
        args.path.write_text(rendered)
    print(f"{args.path}: merged={merged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
