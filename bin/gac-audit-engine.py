#!/usr/bin/env python3
"""gac-audit-engine: 声明式代码审计与债务拦截引擎.

代替各子仓 discrete pre-commit 钩子中的 Shell grep 正则.
通过 Python AST (抽象语法树) 静态分析 staged Python 文件,
检索潜在的非原子写入 (non-atomic write) 并进行阻断或报警.

Usage:
    python3 bin/gac-audit-engine.py --staged
    python3 bin/gac-audit-engine.py path/to/file.py
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path


class NonAtomicWriteVisitor(ast.NodeVisitor):
    def __init__(self, file_content: str):
        self.file_content = file_content
        self.violations: list[tuple[int, str]] = []
        self.has_atomic_import = False
        self.has_exempt_comment = "audit-exempt: non-atomic-write" in file_content

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "atomic_write" or alias.name.endswith(".atomic_write"):
                self.has_atomic_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and ("atomic_write" in node.module or "atomic" in node.module):
            self.has_atomic_import = True
        for alias in node.names:
            if alias.name == "atomic_write":
                self.has_atomic_import = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # 1. 检查 path.write_text(...)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "write_text":
                self.violations.append((node.lineno, "write_text"))
            # 2. 检查 Path.open(..., 'w')
            elif node.func.attr == "open":
                self._check_open_args(node)
        # 3. 检查 open(...) 全局函数
        elif isinstance(node.func, ast.Name):
            if node.func.id == "open":
                self._check_open_args(node)
        self.generic_visit(node)

    def _check_open_args(self, node: ast.Call) -> None:
        mode = None
        # 位置参数: open(file, mode)
        if len(node.args) >= 2:
            mode_node = node.args[1]
            if isinstance(mode_node, ast.Constant):
                mode = mode_node.value
        # 关键字参数: open(..., mode='w')
        for kw in node.keywords:
            if kw.arg == "mode":
                if isinstance(kw.value, ast.Constant):
                    mode = kw.value.value

        if mode and any(c in str(mode) for c in ("w", "a", "x", "+")):
            self.violations.append((node.lineno, f"open(..., mode='{mode}')"))


def get_staged_python_files() -> list[str]:
    """通过 git diff --cached --name-only 检索 staged python 文件."""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "--", "*.py"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [line.strip() for line in r.stdout.splitlines() if line.strip()]
    except Exception as e:
        print(f"⚠️  获取 staged 文件失败 (可能不在 git 目录): {e}", file=sys.stderr)
        return []


def audit_file(filepath: Path) -> list[str]:
    """静态分析单个 Python 文件."""
    if not filepath.is_file():
        return []

    # 忽略测试文件和 conftest
    if "test" in filepath.name or filepath.name == "conftest.py":
        return []

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return [f"无法读取文件 {filepath}: {e}"]

    # 检查是否包含手动豁免注释
    if "audit-exempt: non-atomic-write" in content:
        return []

    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError as e:
        return [f"语法解析错误 {filepath}:L{e.lineno} - {e.msg}"]

    visitor = NonAtomicWriteVisitor(content)
    visitor.visit(tree)

    # 如果有潜在非原子写，且文件内没有任何 atomic_write 引用，则视为违规
    errors = []
    if visitor.violations and not visitor.has_atomic_import:
        for line, op in visitor.violations:
            errors.append(
                f"❌ {filepath.name}:L{line} - 潜在非原子写入 '{op}'，请使用 atomic_write 包装或添加 '# audit-exempt: non-atomic-write' 豁免。"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="gac-audit-engine: 声明式代码审计引擎")
    parser.add_argument("--staged", action="store_true", help="自动检索并审计 git 暂存区的 Python 文件")
    parser.add_argument("files", nargs="*", help="指定审计的文件列表")
    args = parser.parse_args()

    files_to_audit = []
    if args.staged:
        files_to_audit = [os.path.abspath(f) for f in get_staged_python_files()]
    elif args.files:
        files_to_audit = [os.path.abspath(f) for f in args.files]

    if not files_to_audit:
        print("  ✓ 没有需要审计的 Python 文件。")
        return 0

    print(f"🔍 审计引擎: 正在静态分析 {len(files_to_audit)} 个 Python 文件...")
    total_errors = []
    for f in files_to_audit:
        errors = audit_file(Path(f))
        total_errors.extend(errors)

    if total_errors:
        print("\n═══ 审计违规报告 ═══", file=sys.stderr)
        for err in total_errors:
            print(err, file=sys.stderr)
        print(f"\n❌ 拦截: 发现 {len(total_errors)} 项非原子写违规！提交中止。", file=sys.stderr)
        return 1

    print("  ✓ 静态审计全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
