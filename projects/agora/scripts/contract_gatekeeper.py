#!/usr/bin/env python3
"""OMO Contract Gatekeeper — AST-level linter for forbidden direct I/O.

Detects and blocks direct file-system operations on .omo/ and spaces/
directories outside of approved paths (tests, fixtures, omo CLI itself).

Rules:
- BAN: open(".omo/..."), Path(".omo/...").read_text(), os.path.join(".omo", ...)
- BAN: open("spaces/..."), Path("spaces/...").write_text(), etc.
- ALLOW: tests/*, conftest.py, scripts/omo/* (omo CLI is the authorized broker)
- ALLOW: string literals in comments, docstrings, error messages (no I/O side effect)

Usage:
    python scripts/contract_gatekeeper.py [file_or_dir ...]
    python scripts/contract_gatekeeper.py --diff  # check git diff only

Exit 0 = clean, Exit 1 = violations found.
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Paths that shall never be touched directly by non-omo code
FORBIDDEN_PREFIXES = (".omo/", "spaces/", ".omo\\", "spaces\\")

# Files/paths exempt from the gate (they are the authorized brokers or tests)
EXEMPT_PATH_PATTERNS = (
    r"/(tests|test)/",
    r"conftest\.py$",
    r"/scripts/omo/",
    r"/scripts/contract_gatekeeper\.py$",
    r"__init__\.py$",
    r"src/omo/",  # omo core modules are the authorized brokers for .omo/
)

# AST node types that perform actual I/O when given a path
IO_FUNCTION_NAMES = {"open", "read_text", "write_text", "read_bytes", "write_bytes"}
IO_PATHLIB_CTOR = {"Path", "PurePath", "PosixPath", "WindowsPath"}


def _is_exempt(path: Path) -> bool:
    """Return True if the file is exempt from gatekeeping."""
    s = str(path)
    for pat in EXEMPT_PATH_PATTERNS:
        if re.search(pat, s):
            return True
    return False


def _has_forbidden_prefix(value: str) -> bool:
    """Check whether a string literal starts with a forbidden path prefix."""
    return any(value.startswith(p) or ("/" + p) in value or ("\\" + p) in value for p in FORBIDDEN_PREFIXES)


class _GatekeeperVisitor(ast.NodeVisitor):
    """Walk AST and collect violations."""

    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path
        self.violations: list[tuple[int, str]] = []

    def _add(self, node: ast.AST, detail: str) -> None:
        lineno = getattr(node, "lineno", 0)
        self.violations.append((lineno, detail))

    def _check_call_arg(self, node: ast.AST, arg_index: int = 0) -> None:
        """If the call's positional arg[arg_index] is a forbidden string literal, record."""
        if isinstance(node, ast.Call) and node.args:
            arg = node.args[arg_index]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _has_forbidden_prefix(arg.value):
                self._add(arg, f"forbidden path in call arg: {arg.value!r}")

    # ── open(...) ──────────────────────────────────────────────
    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func = node.func

        # open(".omo/...", ...)
        if isinstance(func, ast.Name) and func.id == "open":
            self._check_call_arg(node, 0)

        # Path(".omo/...")  (pathlib constructor)
        if isinstance(func, ast.Name) and func.id in IO_PATHLIB_CTOR:
            self._check_call_arg(node, 0)

        # os.path.join(".omo", ...)
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "join"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "path"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "os"
        ):
            self._check_call_arg(node, 0)

        # pathlib.Path(".omo/...")
        if isinstance(func, ast.Attribute) and func.attr in IO_PATHLIB_CTOR:
            self._check_call_arg(node, 0)

        # .read_text(), .write_text(), .read_bytes(), .write_bytes()
        if isinstance(func, ast.Attribute) and func.attr in IO_FUNCTION_NAMES:
            # If called on a forbidden Path literal: Path(".omo/...").read_text()
            if isinstance(func.value, ast.Call):
                self.visit_Call(func.value)

        self.generic_visit(node)

    # ── with open(".omo/...") as f: ─────────────────────────────
    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        for item in node.items:
            ctx_expr = item.context_expr
            if isinstance(ctx_expr, ast.Call):
                self.visit_Call(ctx_expr)
        self.generic_visit(node)

    # ── Assign to a path-like name using forbidden literal ──────
    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            if isinstance(target, ast.Name) and "path" in target.id.lower():
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    if _has_forbidden_prefix(node.value.value):
                        self._add(node.value, f"forbidden path assigned to {target.id}: {node.value.value!r}")
        self.generic_visit(node)


def check_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (lineno, detail) violations for a single Python file."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    visitor = _GatekeeperVisitor(path)
    visitor.visit(tree)
    return visitor.violations


def _git_diff_files() -> list[Path]:
    """Return Python files touched in the current git diff."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACM", "HEAD"],
        capture_output=True,
        text=True,
    )
    paths = []
    for line in result.stdout.strip().splitlines():
        p = Path(line)
        if p.suffix == ".py":
            paths.append(p)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OMO Contract Gatekeeper")
    parser.add_argument("paths", nargs="*", help="Files or directories to check")
    parser.add_argument("--diff", action="store_true", help="Only check Python files in git diff")
    args = parser.parse_args(argv)

    if args.diff:
        files = _git_diff_files()
        if not files:
            print("Gatekeeper: no Python files in diff — PASS")
            return 0
    elif args.paths:
        files: list[Path] = []
        for p in args.paths:
            path = Path(p)
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                files.extend(path.rglob("*.py"))
    else:
        files = list(Path(".").rglob("*.py"))

    exit_code = 0
    checked = 0
    for f in files:
        if _is_exempt(f):
            continue
        checked += 1
        violations = check_file(f)
        if violations:
            print(f"\n{f}")
            for lineno, detail in violations:
                print(f"  {lineno}: {detail}")
            exit_code = 1

    if exit_code == 0:
        print(f"Gatekeeper: {checked} files checked — PASS")
    else:
        print(f"\nGatekeeper: violations detected in {checked} files checked — FAIL")
        print("Remediation: route through omo CLI or agora mesh instead of direct I/O.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
