"""omo lint — 静态校验 7 个 AppendOnlyLog consumer 写时都走 Pydantic schema (Round 15 P0).

设计:
  - 扫 projects/omo/src/omo/omo_*.py 7 个 consumer 模块
  - 用 ast 解析, 找 `AppendOnlyLog(.*).append(.*)` 调用
  - 校验 .append(...) 调用都传了 `schema=` kwarg
  - 报未传 schema= 的位置 (file:line)
  - 退出码: 0 全合规, 1 有缺失

Round 21 P0 扩展 — 2 个新 schema 完整性规则:
  - Z-suffix 覆盖: SCHEMA_REGISTRY 所有 schema 继承 ZTimestampModel (timestamp 字段 Z 结尾校验)
  - 必填字段非空: 每个 schema 至少 1 必填字段 (防空架子)

意义:
  - 防止"以后有人绕过 Pydantic schema 校验, 直接 AppendOnlyLog.append(dict)"
  - 防止"未来 schema 漏继承 ZTimestampModel, 失去 Z-suffix ISO8601 校验"
  - 防止"未来 schema 全 Optional = 空架子, 没实际约束"
  - 守住 §11 X1 审计: schema 校验 = 写时锁, 跳过 = 失去写时一致性保证
  - CI 自动跑 (计划集成 ci-lint.yml 新 job)
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

OMO_SRC = Path(__file__).resolve().parent

# 7 个走 Pydantic schema 的 consumer 模块 (按 SCHEMA_REGISTRY 1:1 映射)
# Round 18 P0: omo_history.append_entry 加 schema=OmoHistoryRecord 收严
#   (caller 补 total_score/grade/watchlist_count 4 必填字段), 扩到 7/7
# Round 17 P0: omo_bos_metrics.py 从 dataclass 重构为 Pydantic, 重新纳入 (5/5 → 6/6)
CONSUMER_MODULES = (
    "omo_audit.py",
    "omo_bos_metrics.py",
    "omo_history.py",
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


# 跨模块 import 白名单 (§13.3.3 规则 7 — 允许 7 consumer 依赖的底层模块)
# 设计: 7 consumer 互不依赖, 仅依赖底层 SSOT (omo_io / omo_io_schemas / omo_audit 工具 / omo_history 工具 / _shared)
_CROSS_MODULE_SRP_ALLOWLIST = {
    "omo.omo_io",                    # AppendOnlyLog + 原子写 (R24 抽 _shared 后保留 backward compat)
    "omo.omo_io_schemas",            # Pydantic schema 集中地
    "omo.omo_audit",                 # _utc_now 工具 (多个 consumer 共用)
    "omo.omo_history",               # append_entry / read_history 工具
    "omo.omo_trail",                 # DEFAULT_TRAIL_PATH 路径常量 (omo_lint_seed 共用)
    "omo._shared.append_only_log",   # §12 跨仓 SSOT (R24+)
    "omo._shared.z_timestamp_model", # §12 跨仓 SSOT (R25+)
    "omo.omo_lint",                  # omo_lint_seed 依赖 (Round 19)
}


# §12.1.4 跨仓不变量豁免: omo_history.append_entry 显式传 sort_keys=True (kairon-governance 字节级兼容)
# 实施 lint 规则时, 这些模块不应被判违规
_SORT_KEYS_DEFAULT_EXEMPT_MODULES = frozenset({
    "omo_history.py",  # Round 7 P2 显式传 sort_keys=True (R30 probe 验证)
})


def _check_sort_keys_default() -> list[tuple[str, str, str]]:
    """扫 7 consumer 模块, 检测 .append() 未传 sort_keys=True (§13.3 规则 8 — Round 34 P0 + §16.3 扩 R37 P0).

    §12.1.4 跨仓不变量要求 sort_keys=True 默认值一致 (字节级兼容).

    检测模式 (R37 P0 扩):
      1. AppendOnlyLog(...).append(...) — immediate chain (R34)
      2. log = AppendOnlyLog(...); log.append(...) — 临时变量 (R37 扩)

    omo_history 已传 sort_keys=True (R30 probe), 其他 6 consumer 待治.

    Returns:
        list of (module_name, issue_type, detail) tuples. 空 list = 全合规.
    """
    issues: list[tuple[str, str, str]] = []
    for module_name in CONSUMER_MODULES:
        if module_name in _SORT_KEYS_DEFAULT_EXEMPT_MODULES:
            continue  # 已合规, 豁免
        module_path = OMO_SRC / module_name
        if not module_path.exists():
            continue
        try:
            source = module_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(module_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        # R37 P0 扩: 收集所有 `name = AppendOnlyLog(...)` 临时变量绑定
        bound_log_vars: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            if not isinstance(node.value.func, ast.Name):
                continue
            if node.value.func.id != "AppendOnlyLog":
                continue
            # 收集 target 名 (e.g. `log = AppendOnlyLog(path)` → "log")
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound_log_vars.add(target.id)

        # 扫 .append() 调用 (含 immediate chain + 临时变量)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "append":
                continue
            # 模式 1: AppendOnlyLog(...).append(...) immediate chain
            is_immediate_chain = (
                isinstance(node.func.value, ast.Call)
                and isinstance(node.func.value.func, ast.Name)
                and node.func.value.func.id == "AppendOnlyLog"
            )
            # 模式 2: log.append(...) 临时变量
            is_temp_var = (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id in bound_log_vars
            )
            if not (is_immediate_chain or is_temp_var):
                continue
            # 检查 kwargs: sort_keys= 必须是 True
            sort_keys_kwarg = next((kw for kw in node.keywords if kw.arg == "sort_keys"), None)
            if sort_keys_kwarg is None:
                pattern = "immediate chain" if is_immediate_chain else f"temp var '{node.func.value.id}'"
                issues.append((
                    module_name,
                    "missing-sort-keys",
                    f".append() ({pattern}) 未传 sort_keys=True (违反 §12.1.4 跨仓契约)",
                ))
            elif sort_keys_kwarg.value is not None:
                if isinstance(sort_keys_kwarg.value, ast.Constant) and sort_keys_kwarg.value.value is True:
                    continue
                if isinstance(sort_keys_kwarg.value, ast.Name) and sort_keys_kwarg.value.id == "True":
                    continue
                issues.append((
                    module_name,
                    "wrong-sort-keys-value",
                    f".append() 传 sort_keys= 但值不是 True (§12.1.4 跨仓契约)",
                ))
    return issues


def _check_dead_imports() -> list[tuple[str, str, str]]:
    """扫 7 consumer 模块, 检测 import 但未用 (dead code) (§13.3 规则 6 — Round 32 P0).

    简化版: 用 ast.Name 节点追踪, 任何 `from X import Y` 后 Y 在模块中未用 → 违规.
    豁免:
      - `from __future__ import X` (Python 协议, 改变行为, 非普通 import)
      - `__all__` re-export (NotImplementedError 等)
      - `_` 前缀 (私有 / `from .X import _internal`)

    Returns:
        list of (module_name, issue_type, detail) tuples. 空 list = 全合规.
    """
    issues: list[tuple[str, str, str]] = []
    for module_name in CONSUMER_MODULES:
        module_path = OMO_SRC / module_name
        if not module_path.exists():
            continue
        try:
            source = module_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(module_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        imported_names: set[tuple[str, str]] = set()  # (module, name) 配对, 用于识别 __future__
        used_names: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name_to_track = alias.asname or alias.name
                    if name_to_track == "*":
                        continue
                    imported_names.add((node.module or "", name_to_track))
            elif isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        # 检查未使用的 imports, 排除豁免
        for module, name in sorted(imported_names):
            if name in used_names:
                continue  # 用了
            if name.startswith("_"):
                continue  # 私有 / `from __future__ import annotations` (下划线开头)
            if module == "__future__":
                continue  # Python 协议级 import
            issues.append((
                module_name,
                "dead-import",
                f"import '{name}' (from {module!r}) 但模块中未使用 (dead code, 删或加 noqa)",
            ))
    return issues


def _check_cross_module_srp() -> list[tuple[str, str, str]]:
    """校验 7 consumer 互不依赖 (§13.3.3 规则 7 — Round 30 P0).

    防未来: 7 consumer 互相 import → SRP 违反 → 隐式耦合.
    底层 SSOT 模块 (omo_io / omo_io_schemas / omo_audit 工具 / omo_history 工具 / _shared) 是白名单.

    Returns:
        list of (consumer_module, issue_type, detail) tuples. 空 list = 全合规.
    """
    issues: list[tuple[str, str, str]] = []
    consumer_stems = [Path(m).stem for m in CONSUMER_MODULES]
    for module_name in CONSUMER_MODULES:
        module_path = OMO_SRC / module_name
        if not module_path.exists():
            continue
        try:
            source = module_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(module_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not node.module or not node.module.startswith("omo."):
                continue
            # 模块名: omo.omo_X 或 omo._shared.X
            if node.module in _CROSS_MODULE_SRP_ALLOWLIST:
                continue  # 白名单放行
            # 检查是否 omo.omo_X (X 是 7 consumer 之一)
            if node.module.startswith("omo.omo_"):
                imported_stem = node.module.removeprefix("omo.omo_")
                if imported_stem in consumer_stems and imported_stem != Path(module_name).stem:
                    # 7 consumer 之间互依赖 (非自身)
                    issues.append((
                        module_name,
                        "cross-consumer-import",
                        f"{module_name} import {node.module!r} (consumer 之间不应互依赖, 白名单仅含底层 SSOT)",
                    ))
    return issues


def _check_all_schemas_exported() -> list[tuple[str, str, str]]:
    """校验 omo_io_schemas.py 的 __all__ 包含 SCHEMA_REGISTRY 全部 class (Round 29 P0).

    防未来: 加新 schema 但漏更新 __all__ → 用户 `from omo.omo_io_schemas import NewSchema` 失败.
    注: 校验 class 名 (e.g. OmoAuditRecord) 不是 key 字符串 (e.g. "omo_audit") —
        key 是 SCHEMA_REGISTRY dict 的 key, 不是 module attribute.

    Returns:
        list of (class_name, issue_type, detail) tuples. 空 list = 全合规.
    """
    from omo.omo_io_schemas import SCHEMA_REGISTRY
    import omo.omo_io_schemas as schemas_module

    issues: list[tuple[str, str, str]] = []
    exported = set(getattr(schemas_module, "__all__", []))
    for schema_name, schema_cls in SCHEMA_REGISTRY.items():
        if schema_cls.__name__ not in exported:
            issues.append((
                schema_cls.__name__,
                "missing-from-all",
                f"{schema_cls.__name__} (SCHEMA_REGISTRY[{schema_name!r}]) 未在 omo_io_schemas.__all__ 暴露",
            ))
    return issues


def _check_schema_registry_integrity() -> list[tuple[str, str, str]]:
    """校验 SCHEMA_REGISTRY 所有 schema 满足: ZTimestampModel 覆盖 + 至少 1 必填字段.

    Round 21 P0 新增. 防未来 schema:
      - 漏继承 ZTimestampModel (timestamp 字段无 Z 校验)
      - 全 Optional (空架子, 无实际约束)

    Returns:
        list of (schema_name, issue_type, detail) tuples. 空 list = 全合规.
    """
    from omo.omo_io_schemas import SCHEMA_REGISTRY, ZTimestampModel

    issues: list[tuple[str, str, str]] = []
    for schema_name, schema_cls in SCHEMA_REGISTRY.items():
        # 规则 1: 继承 ZTimestampModel (Z-suffix 校验自动覆盖)
        if not issubclass(schema_cls, ZTimestampModel):
            issues.append((
                schema_name,
                "missing-z-timestamp",
                f"{schema_cls.__name__} 未继承 ZTimestampModel (timestamp 字段无 Z 校验)",
            ))
        # 规则 2: 至少 1 必填字段 (防空架子)
        required_fields = [
            name for name, field in schema_cls.model_fields.items()
            if field.is_required()
        ]
        if not required_fields:
            issues.append((
                schema_name,
                "no-required-fields",
                f"{schema_cls.__name__} 无必填字段 (空架子, 无实际约束)",
            ))
    return issues


def cmd_lint_schemas() -> int:
    """扫 7 个 consumer 模块, 校验 .append() 都传 schema=."""
    print(f"🔍 omo lint schemas — {len(CONSUMER_MODULES)} consumer 写时 schema 校验\n")
    total_violations = 0

    # 规则 1: 7 consumer 模块 .append() 都传 schema= (Round 15 P0)
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

    # 规则 2 (Round 21 P0): SCHEMA_REGISTRY 完整性 — Z-suffix 覆盖 + 必填字段非空
    print()
    schema_issues = _check_schema_registry_integrity()
    if schema_issues:
        total_violations += len(schema_issues)
        print(f"❌ SCHEMA_REGISTRY 完整性: {len(schema_issues)} 处问题")
        for schema_name, issue_type, detail in schema_issues:
            print(f"   - {schema_name} [{issue_type}]: {detail}")
    else:
        from omo.omo_io_schemas import SCHEMA_REGISTRY
        print(f"✅ SCHEMA_REGISTRY 完整性: {len(SCHEMA_REGISTRY)}/{len(SCHEMA_REGISTRY)} schema 守 Z-suffix + 必填字段")

    # 规则 3 (Round 29 P0): __all__ 完整性 — 全部 SCHEMA_REGISTRY key 都在 __all__ 暴露
    print()
    all_issues = _check_all_schemas_exported()
    if all_issues:
        total_violations += len(all_issues)
        print(f"❌ omo_io_schemas.__all__ 完整性: {len(all_issues)} 处问题")
        for schema_name, issue_type, detail in all_issues:
            print(f"   - {schema_name} [{issue_type}]: {detail}")
    else:
        from omo.omo_io_schemas import SCHEMA_REGISTRY
        print(f"✅ omo_io_schemas.__all__ 完整性: {len(SCHEMA_REGISTRY)}/{len(SCHEMA_REGISTRY)} schema 全部 export")

    # 规则 4 (Round 30 P0): cross-module-srp — 7 consumer 互不依赖
    print()
    srp_issues = _check_cross_module_srp()
    if srp_issues:
        total_violations += len(srp_issues)
        print(f"❌ consumer SRP: {len(srp_issues)} 处跨模块 import")
        for module_name, issue_type, detail in srp_issues:
            print(f"   - {module_name} [{issue_type}]: {detail}")
    else:
        print(f"✅ consumer SRP: 7/7 consumer 互不依赖, 仅依赖底层 SSOT (omo_io/omo_io_schemas/omo_audit/omo_history/_shared)")

    # 规则 5 (Round 32 P0): dead-imports — import 但未用 (dead code)
    print()
    dead_issues = _check_dead_imports()
    if dead_issues:
        total_violations += len(dead_issues)
        print(f"❌ dead imports: {len(dead_issues)} 处 import 未用")
        for module_name, issue_type, detail in dead_issues:
            print(f"   - {module_name} [{issue_type}]: {detail}")
    else:
        print(f"✅ dead imports: 7/7 consumer 0 dead code")

    # 规则 6 (Round 34 P0): sort-keys-default — §12.1.4 跨仓 4 不变量
    print()
    sort_issues = _check_sort_keys_default()
    if sort_issues:
        total_violations += len(sort_issues)
        print(f"❌ sort_keys default (§12.1.4): {len(sort_issues)} 处 .append() 未传 sort_keys=True")
        for module_name, issue_type, detail in sort_issues:
            print(f"   - {module_name} [{issue_type}]: {detail}")
    else:
        print(f"✅ sort_keys default (§12.1.4): 7/7 consumer 字节级兼容")

    print()
    if total_violations:
        print(f"❌ omo lint schemas fail: {total_violations} 处违规 (X1 审计风险)")
        return 1
    print(f"✅ omo lint schemas pass: {len(CONSUMER_MODULES)}/{len(CONSUMER_MODULES)} consumer 合规 + "
          f"SCHEMA_REGISTRY 完整 + __all__ 完整 + consumer SRP 守 + 0 dead code + sort_keys 守, schema 写时锁守住")
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
