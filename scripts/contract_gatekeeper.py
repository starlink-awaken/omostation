#!/usr/bin/env python3
"""OMO Contract Gatekeeper — AST-level linter for forbidden direct mutations.

Detects and blocks direct file-system *mutations* on `.omo/` and `spaces/`
outside of approved broker paths (tests, fixtures, omo core, c2g ingress).

Rules:
- BAN: open(".omo/...", "w"), Path(".omo/...").write_text(), unlink(), mkdir(), etc.
- BAN: same for `spaces/...`
- ALLOW: tests/*, conftest.py, `src/omo/*`, authorized `src/c2g/*` ingress modules
- ALLOW: read-only access, comments, docstrings, error messages

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
import yaml

# Paths that shall never be touched directly by non-omo code
FORBIDDEN_PREFIXES = (".omo/", "spaces/", ".omo\\", "spaces\\")

# Files/paths exempt from the gate (they are the authorized brokers or tests)
EXEMPT_PATH_PATTERNS = (
    r"/(tests|test)/",
    r"conftest\.py$",
    r"/scripts/omo/",
    r"/scripts/projects/",  # scripts 镜像子模块 (scripts/projects/<name>/ 是各仓参考副本, 非工作区源码; 原码在各仓内受管)
    r"/scripts/contract_gatekeeper\.py$",
    r"__init__\.py$",
    r"src/omo/",  # omo core modules are the authorized brokers for .omo/
    # GaC 治理工具 (维护 GaC 注册表/报告/证据, broker 特例; P1 揭示 os.* 后白名单)
    r"/bin/gac-.*\.py$",
    r"/bin/evidence-smoke\.py$",
    # 治理运行时工具 (写 audits/debts/_delivery 产物, broker 特例; P1 揭示预先存在债)
    r"/l4_kernel/monitor/contract_monitor\.py$",
    r"/scripts/opc_p5_radar_cron\.py$",
    # health 分数生成 broker (写 .omo/state/health.yaml; P1 揭示预先存在债)
    r"/bin/m4-health-score\.py$",
    # bin/ 治理工具目录 (AGENTS §4: gac-*/doc-ssot-*/ssot-guardian/agent-workflow/m4-*/cron-hook/evidence-smoke)
    # 都是写 .omo 运行产物的合法 broker — 宽泛豁免避免逐个洋葱 (P1 揭示: bin/ 非 broker 工具应迁出或单独门禁)
    r"/bin/.*\.py$",
)

# AST node types that mutate actual files/dirs when given a path
MUTATION_METHOD_NAMES = {
    "write_text",
    "write_bytes",
    "mkdir",
    "unlink",
    "rename",
    "replace",
    "rmdir",
    "symlink_to",
    "touch",
}
IO_PATHLIB_CTOR = {"Path", "PurePath", "PosixPath", "WindowsPath"}
MUTATION_HELPER_NAMES = {"write_yaml_atomic", "write_text_atomic"}
# P1 物理沙箱: os.* 函数写 .omo/spaces (堵 os.makedirs/replace/rename 绕过 Pathlib 检测)
_OS_MUTATION_NAMES = {"makedirs", "mkdir", "replace", "rename"}


def _is_exempt(path: Path) -> bool:
    """Return True if the file is exempt from gatekeeping."""
    # 用绝对路径 (path.resolve): EXEMPT pattern 带 /bin/ /scripts/ 前导斜杠,
    # 相对路径 str(path) = "bin/..." 不匹配 /bin/ → 白名单失效. resolve() 含 /bin/ 匹配.
    s = str(path.resolve())
    for pat in EXEMPT_PATH_PATTERNS:
        if re.search(pat, s):
            return True
    return False


def _has_forbidden_prefix(value: str) -> bool:
    """Check whether a string literal targets a forbidden path prefix or component."""
    normalized = value.replace("\\", "/")
    return any(
        normalized == prefix.rstrip("/")
        or normalized.startswith(prefix)
        or f"/{prefix}" in normalized
        for prefix in (".omo/", "spaces/")
    )


class _GatekeeperVisitor(ast.NodeVisitor):
    """Walk AST and collect violations."""

    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path
        self.violations: list[tuple[int, str]] = []
        self.forbidden_names: set[str] = set()

    def _add(self, node: ast.AST, detail: str) -> None:
        lineno = getattr(node, "lineno", 0)
        self.violations.append((lineno, detail))

    def _expr_is_forbidden_path(self, node: ast.AST | None) -> bool:
        if node is None:
            return False
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return _has_forbidden_prefix(node.value)
        if isinstance(node, ast.Name):
            return node.id in self.forbidden_names
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in IO_PATHLIB_CTOR and node.args:
                return self._expr_is_forbidden_path(node.args[0])
            if (
                isinstance(func, ast.Attribute)
                and func.attr in IO_PATHLIB_CTOR
                and node.args
            ):
                return self._expr_is_forbidden_path(node.args[0])
        if isinstance(node, ast.BinOp):
            return self._expr_is_forbidden_path(
                node.left
            ) or self._expr_is_forbidden_path(node.right)
        if isinstance(node, ast.JoinedStr):
            return any(
                isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and _has_forbidden_prefix(value.value)
                for value in node.values
            )
        if isinstance(node, ast.Attribute):
            return self._expr_is_forbidden_path(node.value)
        return False

    @staticmethod
    def _open_mode_is_mutating(node: ast.Call) -> bool:
        def _mode_has_write(mode: str) -> bool:
            return any(flag in mode for flag in ("w", "a", "x", "+"))

        if (
            len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            return _mode_has_write(node.args[1].value)
        for kw in node.keywords:
            if (
                kw.arg == "mode"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                return _mode_has_write(kw.value.value)
        return False

    # ── mutating calls ─────────────────────────────────────────
    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func = node.func

        # open(".omo/...", "w")
        if (
            isinstance(func, ast.Name)
            and func.id == "open"
            and self._open_mode_is_mutating(node)
        ):
            if node.args and self._expr_is_forbidden_path(node.args[0]):
                self._add(
                    node.args[0],
                    "forbidden direct mutation via open(..., mutating mode)",
                )

        # write_yaml_atomic(path, ...), write_text_atomic(path, ...)
        if isinstance(func, ast.Name) and func.id in MUTATION_HELPER_NAMES:
            if node.args and self._expr_is_forbidden_path(node.args[0]):
                self._add(
                    node.args[0],
                    f"forbidden direct mutation via {func.id}(...)",
                )

        # Path(".omo/...").write_text(), path_var.unlink(), etc.
        if isinstance(func, ast.Attribute) and func.attr in MUTATION_METHOD_NAMES:
            if self._expr_is_forbidden_path(func.value):
                self._add(node, f"forbidden direct mutation via .{func.attr}()")

        # P1: os.makedirs/os.mkdir/os.replace/os.rename 写 .omo/spaces (堵 os.* 绕过)
        # os.replace(src, dst) / os.rename(src, dst) / os.makedirs(path) — 检查 args 含 forbidden path
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
            and func.attr in _OS_MUTATION_NAMES
        ):
            for arg in node.args:
                if self._expr_is_forbidden_path(arg):
                    self._add(node, f"forbidden direct mutation via os.{func.attr}()")
                    break

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
            if isinstance(target, ast.Name) and self._expr_is_forbidden_path(
                node.value
            ):
                self.forbidden_names.add(target.id)
        self.generic_visit(node)


def _load_baseline_entries(path: Path | None) -> set[tuple[str, int]]:
    if path is None or not path.exists():
        return set()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return set()
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return set()
    out: set[tuple[str, int]] = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        rel_path = item.get("path")
        lines = item.get("lines")
        if not isinstance(rel_path, str) or not isinstance(lines, list):
            continue
        for line in lines:
            if isinstance(line, int):
                out.add((rel_path, line))
    return out


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
    parser.add_argument(
        "--diff", action="store_true", help="Only check Python files in git diff"
    )
    parser.add_argument(
        "--baseline-file",
        help="YAML file listing grandfathered direct-io violations as path+line pairs",
    )
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
                for f in path.rglob("*.py"):
                    if not any(
                        part in f.parts
                        for part in (
                            ".venv",
                            "venv",
                            "node_modules",
                            ".git",
                            "dist",
                            "__pycache__",
                        )
                    ):
                        files.append(f)
    else:
        files = []
        for f in Path(".").rglob("*.py"):
            if not any(
                part in f.parts
                for part in (
                    ".venv",
                    "venv",
                    "node_modules",
                    ".git",
                    "dist",
                    "__pycache__",
                )
            ):
                files.append(f)

    if args.baseline_file:
        baseline_file = Path(args.baseline_file)
    else:
        baseline_file = Path(".omo/_truth/registry/direct-io-baseline.yaml")
    baseline_entries = _load_baseline_entries(baseline_file)

    exit_code = 0
    checked = 0
    suppressed = 0
    for f in files:
        if _is_exempt(f):
            continue
        checked += 1
        try:
            relative_path = str(f.resolve().relative_to(Path.cwd().resolve()))
        except ValueError:
            relative_path = str(f)
        raw_violations = check_file(f)
        violations = [
            (lineno, detail)
            for lineno, detail in raw_violations
            if (relative_path, lineno) not in baseline_entries
        ]
        suppressed += len(raw_violations) - len(violations)
        if violations:
            print(f"\n{f}")
            for lineno, detail in violations:
                print(f"  {lineno}: {detail}")
            exit_code = 1

    if exit_code == 0:
        baseline_note = f", baseline_suppressed={suppressed}" if suppressed else ""
        print(f"Gatekeeper: {checked} files checked{baseline_note} — PASS")
    else:
        print(f"\nGatekeeper: violations detected in {checked} files checked — FAIL")
        print(
            "Remediation: route mutations through omo CLI / omo core / c2g ingress instead of direct file I/O."
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
