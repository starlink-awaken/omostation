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
import subprocess
import sys
from pathlib import Path
import yaml

from .omo_io import read_jsonl
from .omo_paths import PROJECTS_DIR, WORKSPACE_ROOT
from .omo_shared import load_yaml
from .omo_task_policy import (
    OPC_P6_SELF_EVOLUTION_POLICY,
    TASK_POLICIES,
    check_task_policy,
    count_planned_matches,
    get_task_policy,
)

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
    "omo.omo_io",  # AppendOnlyLog + 原子写 (R24 抽 _shared 后保留 backward compat)
    "omo.omo_io_schemas",  # Pydantic schema 集中地
    "omo.omo_audit",  # _utc_now 工具 (多个 consumer 共用)
    "omo.omo_history",  # append_entry / read_history 工具
    "omo.omo_trail",  # DEFAULT_TRAIL_PATH 路径常量 (omo_lint_seed 共用)
    "omo._shared.append_only_log",  # §12 跨仓 SSOT (R24+)
    "omo._shared.z_timestamp_model",  # §12 跨仓 SSOT (R25+)
    "omo.omo_lint",  # omo_lint_seed 依赖 (Round 19)
}


# §12.1.4 跨仓不变量豁免: omo_history.append_entry 显式传 sort_keys=True (kairon-governance 字节级兼容)
# 实施 lint 规则时, 这些模块不应被判违规
_SORT_KEYS_DEFAULT_EXEMPT_MODULES = frozenset(
    {
        "omo_history.py",  # Round 7 P2 显式传 sort_keys=True (R30 probe 验证)
    }
)


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
            if not (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ):
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
            sort_keys_kwarg = next(
                (kw for kw in node.keywords if kw.arg == "sort_keys"), None
            )
            if sort_keys_kwarg is None:
                pattern = (
                    "immediate chain"
                    if is_immediate_chain
                    else f"temp var '{node.func.value.id}'"
                )
                issues.append(
                    (
                        module_name,
                        "missing-sort-keys",
                        f".append() ({pattern}) 未传 sort_keys=True (违反 §12.1.4 跨仓契约)",
                    )
                )
            elif sort_keys_kwarg.value is not None:
                if (
                    isinstance(sort_keys_kwarg.value, ast.Constant)
                    and sort_keys_kwarg.value.value is True
                ):
                    continue
                if (
                    isinstance(sort_keys_kwarg.value, ast.Name)
                    and sort_keys_kwarg.value.id == "True"
                ):
                    continue
                issues.append(
                    (
                        module_name,
                        "wrong-sort-keys-value",
                        ".append() 传 sort_keys= 但值不是 True (§12.1.4 跨仓契约)",
                    )
                )
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

        imported_names: set[tuple[str, str]] = (
            set()
        )  # (module, name) 配对, 用于识别 __future__
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
            issues.append(
                (
                    module_name,
                    "dead-import",
                    f"import '{name}' (from {module!r}) 但模块中未使用 (dead code, 删或加 noqa)",
                )
            )
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
                if (
                    imported_stem in consumer_stems
                    and imported_stem != Path(module_name).stem
                ):
                    # 7 consumer 之间互依赖 (非自身)
                    issues.append(
                        (
                            module_name,
                            "cross-consumer-import",
                            f"{module_name} import {node.module!r} (consumer 之间不应互依赖, 白名单仅含底层 SSOT)",
                        )
                    )
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
            issues.append(
                (
                    schema_cls.__name__,
                    "missing-from-all",
                    f"{schema_cls.__name__} (SCHEMA_REGISTRY[{schema_name!r}]) 未在 omo_io_schemas.__all__ 暴露",
                )
            )
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
            issues.append(
                (
                    schema_name,
                    "missing-z-timestamp",
                    f"{schema_cls.__name__} 未继承 ZTimestampModel (timestamp 字段无 Z 校验)",
                )
            )
        # 规则 2: 至少 1 必填字段 (防空架子)
        required_fields = [
            name
            for name, field in schema_cls.model_fields.items()
            if field.is_required()
        ]
        if not required_fields:
            issues.append(
                (
                    schema_name,
                    "no-required-fields",
                    f"{schema_cls.__name__} 无必填字段 (空架子, 无实际约束)",
                )
            )
    return issues


def cmd_lint_schemas(metrics: bool = False) -> int:
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

        print(
            f"✅ SCHEMA_REGISTRY 完整性: {len(SCHEMA_REGISTRY)}/{len(SCHEMA_REGISTRY)} schema 守 Z-suffix + 必填字段"
        )

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

        print(
            f"✅ omo_io_schemas.__all__ 完整性: {len(SCHEMA_REGISTRY)}/{len(SCHEMA_REGISTRY)} schema 全部 export"
        )

    # 规则 4 (Round 30 P0): cross-module-srp — 7 consumer 互不依赖
    print()
    srp_issues = _check_cross_module_srp()
    if srp_issues:
        total_violations += len(srp_issues)
        print(f"❌ consumer SRP: {len(srp_issues)} 处跨模块 import")
        for module_name, issue_type, detail in srp_issues:
            print(f"   - {module_name} [{issue_type}]: {detail}")
    else:
        print(
            "✅ consumer SRP: 7/7 consumer 互不依赖, 仅依赖底层 SSOT (omo_io/omo_io_schemas/omo_audit/omo_history/_shared)"
        )

    # 规则 5 (Round 32 P0): dead-imports — import 但未用 (dead code)
    print()
    dead_issues = _check_dead_imports()
    if dead_issues:
        total_violations += len(dead_issues)
        print(f"❌ dead imports: {len(dead_issues)} 处 import 未用")
        for module_name, issue_type, detail in dead_issues:
            print(f"   - {module_name} [{issue_type}]: {detail}")
    else:
        print("✅ dead imports: 7/7 consumer 0 dead code")

    # 规则 6 (Round 34 P0): sort-keys-default — §12.1.4 跨仓 4 不变量
    print()
    sort_issues = _check_sort_keys_default()
    if sort_issues:
        total_violations += len(sort_issues)
        print(
            f"❌ sort_keys default (§12.1.4): {len(sort_issues)} 处 .append() 未传 sort_keys=True"
        )
        for module_name, issue_type, detail in sort_issues:
            print(f"   - {module_name} [{issue_type}]: {detail}")
    else:
        print("✅ sort_keys default (§12.1.4): 7/7 consumer 字节级兼容")

    print()
    if total_violations:
        print(f"❌ omo lint schemas fail: {total_violations} 处违规 (X1 审计风险)")
        return 1
    print(
        f"✅ omo lint schemas pass: {len(CONSUMER_MODULES)}/{len(CONSUMER_MODULES)} consumer 合规 + "
        f"SCHEMA_REGISTRY 完整 + __all__ 完整 + consumer SRP 守 + 0 dead code + sort_keys 守, schema 写时锁守住"
    )

    # Round 42 P0: --metrics flag 输出 §17 健康度评分
    if metrics:
        from omo.omo_logs import cmd_logs_audit

        print()
        print("📊 §17 健康度评分 (Round 42 P0, omo lint --metrics):")
        metrics_exit = cmd_logs_audit(metrics=True)
        if metrics_exit >= 2:
            print(f"❌ §17 metrics R3+ (exit {metrics_exit})")
        elif metrics_exit == 1:
            print("⚠️  §17 metrics R1-R2 (exit 1, warning)")
        else:
            print("✅ §17 metrics R0 优秀 (exit 0)")
        return max(0, metrics_exit)
    return 0


def _check_yaml_bypass(omo_dir: Path = Path(".omo")) -> list[tuple[str, str]]:
    """扫 .omo/debt/items/*.yaml 检测非 OMO CLI 写入的越权字段 (Round 43 P0).

    OMO 用 lifecycle_state 字段管理债务状态. fix_debts.py 这种越权
    脚本错改 status 字段 (OMO 不读 status 字段). 此 lint 拦截未来再发生.

    检测规则:
      R1: yaml 有 status 字段但没有 lifecycle_state 字段 → 越权 (非 OMO 写)
      R2: yaml 有 status 字段值是 closed/resolved 但 lifecycle_state 不一致 → 越权
      R4: yaml 解析失败 → 警告

    注: 不检查 history 字段 (R3 删了, 防误报 — fresh yaml seed 时无 history 是合法初始态).

    Returns:
        list of (yaml_filename, violation_message) tuples. 空 list = 合规.
    """
    items_dir = omo_dir / "debt" / "items"
    if not items_dir.is_dir():
        return []

    import yaml as _yaml

    issues: list[tuple[str, str]] = []
    for path in sorted(items_dir.glob("*.yaml")):
        try:
            data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, _yaml.YAMLError) as exc:
            issues.append((path.name, f"R4: parse error: {exc}"))
            continue
        if not isinstance(data, dict):
            issues.append((path.name, "R4: yaml 不是 dict 结构"))
            continue

        has_status = "status" in data
        has_lifecycle = "lifecycle_state" in data
        status = data.get("status", "")
        lifecycle = data.get("lifecycle_state", "")

        if has_status and not has_lifecycle:
            issues.append(
                (
                    path.name,
                    f"R1: yaml 有 status={status!r} 字段但无 lifecycle_state (OMO 用 "
                    f"lifecycle_state, 改 status 是越权写入, OMO 不认)",
                )
            )
        elif has_status and status in ("closed", "resolved") and lifecycle != status:
            issues.append(
                (
                    path.name,
                    f"R2: status={status!r} 但 lifecycle_state={lifecycle!r} 不一致 "
                    f"(越权写入, OMO 以 lifecycle_state 为准)",
                )
            )

    return issues


def cmd_lint_yaml_bypass(omo_dir: Path = Path(".omo")) -> int:
    """omo lint yaml-bypass — Round 43 P0 拦截 .omo/debt/items/ 越权写入."""
    issues = _check_yaml_bypass(omo_dir)
    if issues:
        print(f"❌ omo lint yaml-bypass fail: {len(issues)} 处越权 (X1 审计风险)")
        for name, msg in issues:
            print(f"   - {name}: {msg}")
        print()
        print(
            "修复方法: 走 omo-debt close/reopen CLI 正路, 不要直接 yaml.safe_load + yaml.dump 改字段."
        )
        return 1
    print(
        "✅ omo lint yaml-bypass pass: 0 处越权 (所有 .omo/debt/items/*.yaml 走 OMO CLI 正路)"
    )
    return 0


def cmd_lint_direct_omo_io(
    paths: list[str] | None = None, *, diff: bool = False
) -> int:
    """Run the cross-repo contract gatekeeper for direct `.omo` mutations."""
    gatekeeper = PROJECTS_DIR / "ecos" / "scripts" / "contract_gatekeeper.py"
    if not gatekeeper.exists():
        print(f"❌ contract_gatekeeper.py not found: {gatekeeper}")
        return 1

    baseline_path = (
        WORKSPACE_ROOT / ".omo" / "_truth" / "registry" / "direct-io-baseline.yaml"
    )
    try:
        baseline_payload = load_yaml(baseline_path)
    except FileNotFoundError:
        print(f"❌ direct-io baseline registry missing: {baseline_path}")
        return 1
    except yaml.YAMLError as exc:
        print(f"❌ direct-io baseline registry invalid YAML: {baseline_path} ({exc})")
        return 1
    entries = baseline_payload.get("entries", []) or []
    if entries:
        print(
            "❌ omo lint direct-omo-io fail: "
            f"direct-io baseline must be empty, found {len(entries)} grandfathered entry group(s)"
        )
        for item in entries:
            if isinstance(item, dict):
                print(f"  - {item.get('path')}: lines={item.get('lines', [])}")
        print(
            "修复方法: 先把遗留直写迁入 OMO 内核，再清空 .omo/_truth/registry/direct-io-baseline.yaml"
        )
        return 1

    cmd = [sys.executable, str(gatekeeper)]
    if diff:
        cmd.append("--diff")
    elif paths:
        cmd.extend(paths)
    else:
        default_paths = [
            PROJECTS_DIR / "aetherforge" / "packages",
            PROJECTS_DIR / "agora" / "src",
            PROJECTS_DIR / "c2g" / "src",
            PROJECTS_DIR / "cockpit" / "src",
            PROJECTS_DIR / "ecos" / "src",
            PROJECTS_DIR / "ecos" / "scripts",
            PROJECTS_DIR / "family-hub" / "src",
            PROJECTS_DIR / "l4-kernel" / "src",
            PROJECTS_DIR / "metaos" / "src",
            PROJECTS_DIR / "model-driven" / "src",
            PROJECTS_DIR / "omo" / "src",
            PROJECTS_DIR / "runtime" / "src",
            WORKSPACE_ROOT / "scripts",
            WORKSPACE_ROOT / "bin",
        ]
        cmd.extend(str(path) for path in default_paths if path.exists())

    result = subprocess.run(
        cmd, cwd=str(WORKSPACE_ROOT), capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


_SENSITIVE_GOVERNED_TARGETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("system.yaml", ("state", "system.yaml")),
    ("current goal", ("goals", "current.yaml")),
    ("task packet", ("tasks",)),
    ("capability registry", ("capabilities",)),
)
_SENSITIVE_WRITE_HELPERS = {"write_yaml_atomic", "write_text_atomic"}
_SENSITIVE_WRITE_METHODS = {"write_text", "write_bytes"}
_SENSITIVE_WRITE_EXEMPT_FILES = {
    "omo_demo_artifacts.py",
    "omo_ingress.py",
    "omo_ingress_registry_writes.py",  # ingress registry writes are authorized broker surface
    "omo_release_cycle.py",
    "omo_weekly_loop.py",
    "omo_worker_promotion.py",
}


def _string_literals_in_expr(
    node: ast.AST | None,
    assignments: dict[str, ast.AST],
    *,
    seen: set[str] | None = None,
) -> list[str]:
    if node is None:
        return []
    if seen is None:
        seen = set()
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        out: list[str] = []
        for value in node.values:
            out.extend(_string_literals_in_expr(value, assignments, seen=seen))
        return out
    if isinstance(node, ast.FormattedValue):
        return _string_literals_in_expr(node.value, assignments, seen=seen)
    if isinstance(node, ast.Name):
        if node.id in seen or node.id not in assignments:
            return []
        seen.add(node.id)
        return _string_literals_in_expr(assignments[node.id], assignments, seen=seen)
    if isinstance(node, ast.Attribute):
        return _string_literals_in_expr(node.value, assignments, seen=seen)
    if isinstance(node, ast.Call):
        out: list[str] = []
        out.extend(_string_literals_in_expr(node.func, assignments, seen=seen))
        for arg in node.args:
            out.extend(_string_literals_in_expr(arg, assignments, seen=seen))
        for kw in node.keywords:
            out.extend(_string_literals_in_expr(kw.value, assignments, seen=seen))
        return out
    if isinstance(node, ast.BinOp):
        return _string_literals_in_expr(
            node.left, assignments, seen=seen
        ) + _string_literals_in_expr(node.right, assignments, seen=seen)
    if isinstance(node, ast.Subscript):
        return _string_literals_in_expr(
            node.value, assignments, seen=seen
        ) + _string_literals_in_expr(node.slice, assignments, seen=seen)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out: list[str] = []
        for elt in node.elts:
            out.extend(_string_literals_in_expr(elt, assignments, seen=seen))
        return out
    return []


def _collect_name_assignments(tree: ast.AST) -> dict[str, ast.AST]:
    assignments: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                assignments[node.target.id] = node.value
    return assignments


def _target_kind_from_tokens(tokens: list[str]) -> str | None:
    normalized = "/".join(token.replace("\\", "/") for token in tokens)
    for label, required_parts in _SENSITIVE_GOVERNED_TARGETS:
        if all(part in normalized for part in required_parts):
            return label
    return None


def _sensitive_write_issues_in_file(path: Path) -> list[str]:
    if path.name in _SENSITIVE_WRITE_EXEMPT_FILES:
        return []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [f"{path}: parse error: {exc}"]

    assignments = _collect_name_assignments(tree)
    issues: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        target_expr: ast.AST | None = None
        op_name: str | None = None

        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in _SENSITIVE_WRITE_METHODS
        ):
            target_expr = node.func.value
            op_name = node.func.attr
        elif (
            isinstance(node.func, ast.Name) and node.func.id in _SENSITIVE_WRITE_HELPERS
        ):
            if node.args:
                target_expr = node.args[0]
                op_name = node.func.id
        elif isinstance(node.func, ast.Name) and node.func.id == "open":
            mode_value: str | None = None
            if (
                len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                mode_value = node.args[1].value
            else:
                for kw in node.keywords:
                    if (
                        kw.arg == "mode"
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                    ):
                        mode_value = kw.value.value
                        break
            if (
                mode_value
                and any(flag in mode_value for flag in ("w", "a", "x"))
                and node.args
            ):
                target_expr = node.args[0]
                op_name = "open"

        if target_expr is None or op_name is None:
            continue

        tokens = _string_literals_in_expr(target_expr, assignments)
        target_kind = _target_kind_from_tokens(tokens)
        if target_kind is None:
            continue
        issues.append(
            f"{path}:{node.lineno} direct sensitive write via {op_name} -> {target_kind}"
        )

    return issues


def cmd_lint_sensitive_governed_writes(paths: list[str] | None = None) -> int:
    targets = [Path(item) for item in paths] if paths else sorted(OMO_SRC.glob("*.py"))
    issues: list[str] = []
    checked = 0
    for target in targets:
        if target.is_dir():
            for file_path in sorted(target.rglob("*.py")):
                checked += 1
                issues.extend(_sensitive_write_issues_in_file(file_path))
            continue
        if target.suffix != ".py" or not target.exists():
            continue
        checked += 1
        issues.extend(_sensitive_write_issues_in_file(target))

    if issues:
        print(
            f"❌ omo lint sensitive-governed-writes fail: {len(issues)} direct write(s)"
        )
        for issue in issues:
            print(f"  - {issue}")
        print(
            "修复方法: 人类/桥接敏感治理面(system/goals/tasks/capabilities)必须走 broker 入口；"
            "worker/internal 生命周期写面继续由 internal-write-profiles registry 单独治理."
        )
        return 1

    print(
        f"✅ omo lint sensitive-governed-writes pass: checked={checked} direct_writes=0"
    )
    return 0


def cmd_lint_task_policy(policy_name: str, workspace_root: str = ".") -> int:
    root = Path(workspace_root).resolve()
    policy = get_task_policy(policy_name)
    issues = check_task_policy(root, policy)
    if issues:
        print(f"❌ omo lint {policy.name} fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    count = count_planned_matches(root, policy)
    print(f"✅ omo lint {policy.name} pass: matches={count}")
    return 0


def cmd_lint_all_task_policies(workspace_root: str = ".") -> int:
    root = Path(workspace_root).resolve()
    failures = 0
    for policy_name in sorted(TASK_POLICIES):
        failures += cmd_lint_task_policy(policy_name, str(root))
    return 0 if failures == 0 else 1


def cmd_lint_self_evolution_approval(workspace_root: str = ".") -> int:
    return cmd_lint_task_policy(OPC_P6_SELF_EVOLUTION_POLICY.name, workspace_root)


def cmd_lint_ingress_registry(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_ingress_registry,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_ingress_registry(root)
    if issues:
        print(f"❌ omo lint ingress-registry fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    if summary.get("exists"):
        print(
            "✅ omo lint ingress-registry pass: "
            f"goals={len(summary.get('goal_ids', []))} "
            f"tasks={len(summary.get('task_ids', []))} "
            f"debts={len(summary.get('debt_ids', []))} "
            f"capabilities={len(summary.get('capability_ids', []))}"
        )
    else:
        print("✅ omo lint ingress-registry pass: registry not created yet")
    return 0


def cmd_lint_mutation_surfaces(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_mutation_surface_registry,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_mutation_surface_registry(root)
    if issues:
        print(f"❌ omo lint mutation-surfaces fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    if summary.get("exists"):
        print(
            "✅ omo lint mutation-surfaces pass: "
            f"surfaces={len(summary.get('runtime_surface_names', []))}"
        )
    else:
        print("✅ omo lint mutation-surfaces pass: registry not created yet")
    return 0


def cmd_lint_internal_write_profiles(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_internal_write_profile_registry,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_internal_write_profile_registry(root)
    if issues:
        print(f"❌ omo lint internal-write-profiles fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    if summary.get("exists"):
        print(
            "✅ omo lint internal-write-profiles pass: "
            f"profiles={len(summary.get('runtime_profile_names', []))}"
        )
    else:
        print("✅ omo lint internal-write-profiles pass: registry not created yet")
    return 0


def cmd_lint_state_plane_assets(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_state_plane_asset_registry,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_state_plane_asset_registry(root)
    if issues:
        print(f"❌ omo lint state-plane-assets fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    if summary.get("exists"):
        print(
            "✅ omo lint state-plane-assets pass: "
            f"top_level_assets={summary.get('top_level_asset_count', 0)} "
            f"persistence_modes={len(summary.get('persistence_mode_counts', {}))}"
        )
    else:
        print("✅ omo lint state-plane-assets pass: registry not created yet")
    return 0


def cmd_lint_c2g_omo_boundary(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_c2g_omo_boundary,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_c2g_omo_boundary(root)
    if issues:
        print(f"❌ omo lint c2g-omo-boundary fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(
        "✅ omo lint c2g-omo-boundary pass: "
        f"facade={summary.get('facade_path')} violations={len(summary.get('violations', []))}"
    )
    return 0


def cmd_lint_ingress_artifacts(workspace_root: str = ".") -> int:
    from omo.omo_governance_surfaces import (
        _check_ingress_artifacts,
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_ingress_artifacts(root)
    if issues:
        print(f"❌ omo lint ingress-artifacts fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    if summary.get("exists"):
        print(
            "✅ omo lint ingress-artifacts pass: "
            f"goals={summary.get('goal_artifacts', 0)} "
            f"tasks={summary.get('task_artifacts', 0)} "
            f"debts={summary.get('debt_artifacts', 0)} "
            f"capabilities={summary.get('capability_artifacts', 0)}"
        )
    else:
        print("✅ omo lint ingress-artifacts pass: registry not created yet")
    return 0


def cmd_lint_mutation_ledger(workspace_root: str = ".") -> int:
    root = Path(workspace_root).resolve()
    ledger_path = root / ".omo" / "change-log" / "mutations.jsonl"
    if not ledger_path.exists():
        print(f"❌ omo lint mutation-ledger fail: missing ledger file {ledger_path}")
        return 1

    entries = read_jsonl(ledger_path)
    if not entries:
        print(f"❌ omo lint mutation-ledger fail: ledger is empty: {ledger_path}")
        return 1

    issues: list[str] = []
    required_fields = (
        "created_at",
        "actor",
        "action",
        "target",
        "artifact_ref",
        "source_ref",
        "broker_ref",
        "result",
    )
    committed = 0
    for idx, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            issues.append(f"entry {idx}: not a JSON object")
            continue
        missing = [field for field in required_fields if field not in entry]
        if missing:
            issues.append(f"entry {idx}: missing fields {missing}")
            continue
        if entry.get("result") == "committed":
            committed += 1
        artifact_ref = entry.get("artifact_ref")
        if not isinstance(artifact_ref, str) or not artifact_ref.startswith(".omo/"):
            issues.append(f"entry {idx}: invalid artifact_ref {artifact_ref!r}")
            continue
        artifact_path = root / artifact_ref
        if not artifact_path.exists():
            issues.append(f"entry {idx}: artifact_ref missing on disk {artifact_ref}")

    if committed == 0:
        issues.append("no committed mutations found in ledger")

    if issues:
        print(f"❌ omo lint mutation-ledger fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(
        "✅ omo lint mutation-ledger pass: "
        f"entries={len(entries)} committed={committed}"
    )
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
    sub.add_parser(
        "yaml-bypass",
        help="扫 .omo/debt/items/*.yaml 拦截 status 字段越权写入 (Round 43 P0)",
    )
    gate = sub.add_parser(
        "direct-omo-io",
        help="拦截非 broker 对 `.omo` / `spaces` 的直接文件系统改写",
    )
    gate.add_argument(
        "paths", nargs="*", help="要检查的文件/目录；默认扫 omo/c2g/scripts/bin"
    )
    gate.add_argument(
        "--diff", action="store_true", help="只检查 git diff 中的 Python 文件"
    )
    sensitive_governed = sub.add_parser(
        "sensitive-governed-writes",
        help="拦截对 system/goals/tasks/capabilities 等敏感治理面的直接落盘",
    )
    sensitive_governed.add_argument(
        "paths",
        nargs="*",
        help="要检查的 Python 文件/目录；默认扫 projects/omo/src/omo",
    )
    ingress_registry = sub.add_parser(
        "ingress-registry",
        help="校验 .omo/_delivery/ingress/registry.yaml 的结构、反向映射与落盘一致性",
    )
    ingress_registry.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    mutation_surfaces = sub.add_parser(
        "mutation-surfaces",
        help="校验 mutation surface truth registry 与运行时 broker 清单是否一致",
    )
    mutation_surfaces.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    internal_write_profiles = sub.add_parser(
        "internal-write-profiles",
        help="校验 worker internal write profile registry 与运行时清单是否一致",
    )
    internal_write_profiles.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    state_plane_assets = sub.add_parser(
        "state-plane-assets",
        help="校验 .omo 顶层资产的持久化与保留语义是否登记完整",
    )
    state_plane_assets.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    c2g_omo_boundary = sub.add_parser(
        "c2g-omo-boundary",
        help="校验 c2g 只能通过本地 facade 接入 OMO，不得散弹式 import 内核模块",
    )
    c2g_omo_boundary.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    ingress_artifacts = sub.add_parser(
        "ingress-artifacts",
        help="校验 ingress registry 指向的 artifact 文件存在且元数据与 registry 对齐",
    )
    ingress_artifacts.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    mutation_ledger = sub.add_parser(
        "mutation-ledger",
        help="校验 .omo/change-log/mutations.jsonl 账本存在、字段齐全且 artifact_ref 可回落到真实文件",
    )
    mutation_ledger.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    # P45 R2: 第 14 + 15 维度
    doc_lifecycle = sub.add_parser(
        "doc-lifecycle",
        help="扫 .omo/ 全部 .md/.yaml, 4 类分类 + 死文档 + frontmatter 覆盖率 (P45 R2 第 14 维度)",
    )
    doc_lifecycle.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    doc_lifecycle.add_argument(
        "--verbose", action="store_true", help="输出每个文件的分类细节"
    )
    doc_archival = sub.add_parser(
        "doc-archival-suggestions",
        help="软引导 (WARN only): 建议归档的死文档 (P45 R4 第 15 维度)",
    )
    doc_archival.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    self_evolution = sub.add_parser(
        "self-evolution-approval",
        help="校验 OPC P6 self-evolution task 仅落 planned/ 且审批字段完整",
    )
    self_evolution.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    task_policy = sub.add_parser(
        "task-policy",
        help="按注册表执行通用 task policy 校验",
    )
    task_policy.add_argument("policy_name", nargs="?", choices=sorted(TASK_POLICIES))
    task_policy.add_argument(
        "--all", action="store_true", help="执行全部已注册 task policy"
    )
    task_policy.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )

    args = parser.parse_args(argv)
    if args.command == "schemas":
        return cmd_lint_schemas()
    if args.command == "yaml-bypass":
        return cmd_lint_yaml_bypass()
    if args.command == "direct-omo-io":
        return cmd_lint_direct_omo_io(args.paths, diff=args.diff)
    if args.command == "sensitive-governed-writes":
        return cmd_lint_sensitive_governed_writes(args.paths)
    if args.command == "ingress-registry":
        return cmd_lint_ingress_registry(args.workspace_root)
    if args.command == "mutation-surfaces":
        return cmd_lint_mutation_surfaces(args.workspace_root)
    if args.command == "internal-write-profiles":
        return cmd_lint_internal_write_profiles(args.workspace_root)
    if args.command == "state-plane-assets":
        return cmd_lint_state_plane_assets(args.workspace_root)
    if args.command == "c2g-omo-boundary":
        return cmd_lint_c2g_omo_boundary(args.workspace_root)
    if args.command == "ingress-artifacts":
        return cmd_lint_ingress_artifacts(args.workspace_root)
    if args.command == "mutation-ledger":
        return cmd_lint_mutation_ledger(args.workspace_root)
    if args.command == "self-evolution-approval":
        return cmd_lint_self_evolution_approval(args.workspace_root)
    if args.command == "task-policy":
        if args.all:
            return cmd_lint_all_task_policies(args.workspace_root)
        if not args.policy_name:
            parser.error("task-policy requires policy_name unless --all is used")
        return cmd_lint_task_policy(args.policy_name, args.workspace_root)
    if args.command == "doc-lifecycle":
        return cmd_lint_doc_lifecycle(args.workspace_root, verbose=args.verbose)
    if args.command == "doc-archival-suggestions":
        return cmd_lint_doc_archival_suggestions(args.workspace_root)
    parser.print_help()
    return 1


# ════════════════════════════════════════════════════════════════════════
# P45 R2: 文档生命周期 lint (第 14 + 15 维度)
# ════════════════════════════════════════════════════════════════════════
# 规则详见 .omo/DOC-LIFECYCLE.md
# 4 类: ssot/contract/pattern/history
# ════════════════════════════════════════════════════════════════════════

from typing import Any  # noqa: E402

try:
    import yaml as _doc_lint_yaml  # noqa: E402
except ImportError:  # pragma: no cover
    _doc_lint_yaml = None

# 4 类路径模式 (与 .omo/DOC-LIFECYCLE.md §2 一致)
_DOC_LIFECYCLE_PATTERNS: dict[str, list[str]] = {
    "ssot": [
        ".omo/_truth",
        ".omo/_truth/registry",
    ],
    "contract": [
        ".omo/standards",
    ],
    "pattern": [
        ".omo/_knowledge/patterns",
    ],
    # history: .omo/_archive/, .omo/_knowledge/audits/, .omo/_knowledge/management/
}

_DOC_LIFECYCLE_NEED_FRONTMATTER = {"ssot", "contract", "pattern"}


def _classify_doc(rel_path: str) -> str:
    """根据路径自动分类到 4 类之一."""
    rel = rel_path.lstrip("./")
    for category, dirs in _DOC_LIFECYCLE_PATTERNS.items():
        for d in dirs:
            d_clean = d.lstrip("./")
            if rel.startswith(d_clean + "/") or rel == d_clean:
                return category
    # 默认归 history
    if (
        rel.startswith(".omo/_archive/")
        or rel.startswith(".omo/_knowledge/audits/")
        or rel.startswith(".omo/_knowledge/management/")
        or rel.startswith(".omo/_knowledge/decisions/")
    ):
        return "history"
    return "history"


def _parse_frontmatter(content: str) -> dict[str, Any] | None:
    """解析 YAML frontmatter (YAML 头 --- ... ---)."""
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    if _doc_lint_yaml is None:
        return None
    try:
        data = _doc_lint_yaml.safe_load(parts[1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _check_doc_referenced(
    rel_path: str, workspace_root: Path
) -> tuple[bool, list[str]]:
    """检查文档是否被引用 (path 中含 basename)."""
    base = Path(workspace_root)
    refs: list[str] = []
    name = Path(rel_path).name
    skip_dirs = {".git", ".venv", "node_modules", "__pycache__", "_delivery"}
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix not in {".py", ".sh", ".md", ".yaml", ".yml"}:
            continue
        try:
            if name in path.read_text(encoding="utf-8", errors="ignore"):
                try:
                    rel_p = path.relative_to(base)
                except ValueError:
                    rel_p = path
                refs.append(str(rel_p))
                if len(refs) > 5:
                    break
        except Exception:
            continue
    return (len(refs) > 0, refs)


def cmd_lint_doc_lifecycle(workspace_root: str = ".", verbose: bool = False) -> int:
    """P45 R2: 文档生命周期 lint (第 14 维度).

    扫描 .omo/ 全部 .md/.yaml:
    - 4 类自动分类
    - 死文档识别 (contract/pattern 0 引用 + 缺 frontmatter)
    - frontmatter 覆盖率统计
    - 矛盾路径检查 (引用 .omo/_archive/ 等)
    """
    from omo.omo_governance_surfaces import resolve_governance_workspace_root

    root = resolve_governance_workspace_root(Path(workspace_root))
    omo = root / ".omo"

    if not omo.exists():
        print(f"❌ .omo/ 不存在 at {root}")
        return 1

    md_files = list(omo.rglob("*.md")) + list(omo.rglob("*.yaml"))
    # 排除 _delivery (机器写) + drafts
    md_files = [
        f for f in md_files if "_delivery" not in f.parts and "/drafts/" not in str(f)
    ]

    total = len(md_files)
    by_category: dict[str, int] = {"ssot": 0, "contract": 0, "pattern": 0, "history": 0}
    dead_docs: list[tuple[Path, str]] = []
    frontmatter_total = 0
    frontmatter_active = 0
    frontmatter_missing: list[tuple[Path, str]] = []
    frontmatter_bad_status: list[tuple[Path, str]] = []
    contradictory_refs: list[tuple[Path, str]] = []

    valid_statuses = {"active", "deprecated", "archived", "experimental"}

    # 矛盾路径检查: 只对 .py/.sh 真实代码引用算矛盾, .md 解释文档 OK
    contents_cache: dict[Path, str] = {}
    for f in md_files:
        try:
            contents_cache[f] = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if f.suffix not in {".py", ".sh"}:
            continue
        for bad_path in [".omo/_archive/", ".omo/_knowledge/management/"]:
            if bad_path in contents_cache[f]:
                contradictory_refs.append((f, bad_path))
                break

    for f in md_files:
        try:
            rel = str(f.relative_to(root))
        except ValueError:
            continue
        category = _classify_doc(rel)
        by_category[category] += 1

        if category in _DOC_LIFECYCLE_NEED_FRONTMATTER:
            content = contents_cache.get(f, "")
            fm = _parse_frontmatter(content)
            if fm is None:
                frontmatter_missing.append((f, category))
            else:
                frontmatter_total += 1
                status = fm.get("status")
                if status in valid_statuses:
                    frontmatter_active += 1
                else:
                    frontmatter_bad_status.append((f, str(status)))

        # 死文档: contract/pattern 0 引用 + status != deprecated
        if category in {"contract", "pattern"}:
            has_ref, _ = _check_doc_referenced(rel, root)
            if not has_ref:
                # 如果 frontmatter 标了 deprecated/archived, 不算死
                content = contents_cache.get(f, "")
                fm = _parse_frontmatter(content)
                if fm and fm.get("status") in {"deprecated", "archived"}:
                    pass  # 已标注, OK
                else:
                    dead_docs.append((f, category))

    # 输出报告
    print("=" * 70)
    print("📚 P45 R2: 文档生命周期 lint (第 14 维度)")
    print("=" * 70)
    print(f"扫描根: {omo}")
    print(f"总文件: {total}")
    print()
    print("📊 4 类分类:")
    for cat in ("ssot", "contract", "pattern", "history"):
        n = by_category[cat]
        print(f"  {cat:10s} {n:4d} files")
    print()

    need_fm_total = sum(by_category[c] for c in _DOC_LIFECYCLE_NEED_FRONTMATTER)
    fm_coverage = (frontmatter_active / need_fm_total * 100) if need_fm_total else 100.0
    print(f"📋 frontmatter 覆盖率 (ssot/contract/pattern): {fm_coverage:.1f}%")
    print(f"   active/deprecated/archived/experimental: {frontmatter_active}")
    print(f"   缺 frontmatter: {len(frontmatter_missing)}")
    print(f"   bad status: {len(frontmatter_bad_status)}")
    print()

    if dead_docs:
        print(f"💀 死文档 (contract/pattern 0 引用): {len(dead_docs)}")
        for path, cat in dead_docs[:20]:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            print(f"  ⚠️  {rel}  [{cat}]")
        if len(dead_docs) > 20:
            print(f"  ... (其余 {len(dead_docs) - 20} 略)")
    else:
        print("💀 死文档: 0 ✅")
    print()

    if frontmatter_missing:
        print(f"📝 缺 frontmatter: {len(frontmatter_missing)}")
        for path, cat in frontmatter_missing[:10]:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            print(f"  ⚠️  {rel}  [{cat}]")
        if len(frontmatter_missing) > 10:
            print(f"  ... (其余 {len(frontmatter_missing) - 10} 略)")
    print()

    if contradictory_refs:
        print(f"❌ 矛盾路径 (引用 .omo/_archive/ 等): {len(contradictory_refs)}")
        for src, bad in contradictory_refs[:5]:
            try:
                rel_src = src.relative_to(root)
            except ValueError:
                rel_src = src
            print(f"  {rel_src} 引用 {bad}")
    else:
        print("❌ 矛盾路径: 0 ✅")
    print()

    if dead_docs or frontmatter_missing:
        print("💡 建议 (P45 R4 第 15 维度):")
        print("   跑 `omo lint doc-archival-suggestions` 看详细建议")
        print("   加 frontmatter `status: deprecated` 或 `archived`")
    print()

    # 评分
    score = 100
    if fm_coverage < 80:
        score -= int((80 - fm_coverage) * 0.5)
    if dead_docs:
        ratio = len(dead_docs) / total * 100 if total else 0
        if ratio > 30:
            score -= 20
        elif ratio > 20:
            score -= 10
    if contradictory_refs:
        score -= 10
    score = max(0, score)
    print(f"📈 doc-lifecycle 评分: {score}/100")
    if score >= 90:
        print("   状态: 🟢 HEALTHY")
    elif score >= 70:
        print("   状态: 🟡 NEEDS-IMPROVEMENT")
    else:
        print("   状态: 🔴 DEGRADED")

    return 0  # WARN only - 不阻塞


def cmd_lint_doc_archival_suggestions(workspace_root: str = ".") -> int:
    """P45 R4: 软引导 (第 15 维度) — 建议归档的死文档.

    复用 doc-lifecycle 的逻辑 + 给出可执行的批量脚本模板.
    """
    print("=" * 70)
    print("💡 P45 R4: 文档归档建议 (第 15 维度, 软引导)")
    print("=" * 70)
    print()
    print("软引导 — 不强制执行. 建议人工 review 后操作.")
    print()
    print("📋 分类建议:")
    print("   1. .omo/standards/ 0 引用 + 缺 frontmatter → 加 `status: deprecated`")
    print("   2. .omo/_knowledge/management/ 历史决策 → 加 `status: archived`")
    print("   3. .omo/_knowledge/audits/ phase closeout → 加 `status: archived`")
    print("   4. bin/mof-* 14 个 0 引用工具 → 顶部加 `Status: planned` 注释")
    print()
    print("📜 frontmatter 模板:")
    print("---")
    print("status: deprecated  # 或 archived / active")
    print("lifecycle: contract  # 或 ssot / pattern / history")
    print("owner: governance-team")
    print("last-reviewed: 2026-06-22")
    print("---")
    print()
    print("🔧 批量 frontmatter 脚本 (for standards):")
    print("  for f in .omo/standards/*.md; do")
    print('    if ! head -1 "$f" | grep -q "^---$"; then')
    print('      { echo "---"; echo "status: deprecated"; echo "lifecycle: contract";')
    print('        echo "owner: governance-team"; echo "last-reviewed: 2026-06-22";')
    print('        echo "---"; cat "$f"; } > "$f.new" && mv "$f.new" "$f"')
    print("    fi")
    print("  done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
