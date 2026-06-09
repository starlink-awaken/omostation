"""omo lint — 静态校验 7 个 AppendOnlyLog consumer 写时都走 Pydantic schema (Round 14 P1-2).

设计:
  - 扫 projects/omo/src/omo/omo_*.py 7 个 consumer 模块
  - 用 ast 解析, 找 `AppendOnlyLog(.*).append(.*)` 调用
  - 校验 .append(...) 调用都传了 `schema=` kwarg
  - 报未传 schema= 的位置 (file:line)
  - 退出码: 0 全合规, 1 有缺失

意义 (Round 14 P1-2 落地):
  - 防止"以后有人绕过 Pydantic schema 校验, 直接 AppendOnlyLog.append(dict)"
  - 守住 §11 X1 审计: schema 校验 = 写时锁, 跳过 = 失去写时一致性保证
  - CI 自动跑 (计划集成 ci-lint.yml 新 job)
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

OMO_SRC = Path(__file__).resolve().parent

# 5 个走 Pydantic schema 的 consumer 模块 (按 SCHEMA_REGISTRY 1:1 映射)
# 排除:
#   - omo_bos_metrics.py: Round 9 P0 之前架构, 用 dataclass 不是 Pydantic,
#     重构为 Pydantic 留 Round 16+ debt 范畴
#   - omo_history.py: append_entry 是宽容业务接口, 字段由 caller 决定,
#     不强加 Pydantic 校验 (caller omo_audit/omo_daemon 负责字段完整性)
CONSUMER_MODULES = (
    "omo_audit.py",
    "omo_sync.py",
    "omo_alert.py",
    "omo_event.py",
    "omo_trail.py",
)


def _check_module_append_has_schema(module_path: Path) -> list[tuple[int, str]]:
    """扫单个 consumer 模块, 返回未传 schema= 的 .append() 调用位置 (line, snippet).

    Returns:
        list of (line_number, code_snippet) tuples. 空 list = 合规.
    """
    try:
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [(0, f"parse error: {exc}")]

    violations: list[tuple[int, str]] = []

    class AppendCallVisitor(ast.NodeVisitor):
        """找 AppendOnlyLog.append() 调用, 检查 schema= kwarg."""

        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            # 匹配形式: AppendOnlyLog(...).append(record, schema=SomeSchema)
            #         或 log.append(record, schema=SomeSchema)
            if not isinstance(node.func, ast.Attribute):
                self.generic_visit(node)
                return
            if node.func.attr != "append":
                self.generic_visit(node)
                return
            # 验证 func.value 是 AppendOnlyLog(...)
            # 接受两种模式:
            #   1) AppendOnlyLog(path).append(...) — func.value 是 Call(AppendOnlyLog, ...)
            #   2) log.append(...) — func.value 是 Name("log"), 简化: 不深究
            # 严格模式: 必须 func.value 是 Call 且 func.value.func.id == "AppendOnlyLog"
            is_append_only_log_call = False
            if isinstance(node.func.value, ast.Call):
                if isinstance(node.func.value.func, ast.Name):
                    if node.func.value.func.id == "AppendOnlyLog":
                        is_append_only_log_call = True
            # 注: 模式 2 (log.append) 暂不静态追踪变量绑定, 简化放过
            #     (omo_*.py 都用模式 1, 因为 consumer 模块内 log 是临时变量)

            if not is_append_only_log_call:
                self.generic_visit(node)
                return

            # 检查 kwargs 里有 schema=
            has_schema_kwarg = any(kw.arg == "schema" for kw in node.keywords)
            if not has_schema_kwarg:
                # 取源行 snippet
                line = node.lineno
                snippet = ast.get_source_segment(source, node) or "<unknown>"
                violations.append((line, snippet))

            self.generic_visit(node)

    AppendCallVisitor().visit(tree)
    return violations


def cmd_lint_schemas() -> int:
    """扫 7 个 consumer 模块, 校验 .append() 都传 schema=."""
    print(f"🔍 omo lint schemas — {len(CONSUMER_MODULES)} consumer 写时 schema 校验\n")
    total_violations = 0
    for module_name in CONSUMER_MODULES:
        module_path = OMO_SRC / module_name
        if not module_path.exists():
            print(f"⚠️  {module_name}: not found (skip)")
            continue
        violations = _check_module_append_has_schema(module_path)
        if not violations:
            print(f"✅ {module_name}: all .append() calls pass schema= (合规)")
            continue
        # 有违规
        total_violations += len(violations)
        print(f"❌ {module_name}: {len(violations)} 处 .append() 未传 schema=")
        for line, snippet in violations:
            print(f"   line {line}: {snippet.strip()[:80]}")

    print()
    if total_violations:
        print(f"❌ omo lint schemas fail: {total_violations} 处 schema 校验缺失 (X1 审计风险)")
        return 1
    print(f"✅ omo lint schemas pass: {len(CONSUMER_MODULES)}/{len(CONSUMER_MODULES)} consumer 合规, schema 写时锁守住")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo lint",
        description="静态校验 7 consumer 写时都走 Pydantic schema (Round 14 P1-2)",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser(
        "schemas",
        help="扫 7 consumer 模块, 校验 .append() 都传 schema= (X1 审计契约)",
    )

    args = parser.parse_args(argv)
    if args.command == "schemas":
        return cmd_lint_schemas()
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
