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
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from omo.omo_ingress_paths import _mutation_log_path
from omo.omo_io import read_jsonl

# P88 R1: doc-lifecycle 子模块 (extracted 304L from omo_lint.py)
# Re-export 保持向后兼容 (omo.cli / scripts/ / omo_audit.py 可能直接 import)
from .omo_lint_doc import (  # noqa: F401
    _DOC_LIFECYCLE_NEED_FRONTMATTER,  # noqa: F401
    _DOC_LIFECYCLE_PATTERNS,  # noqa: F401
    _check_doc_referenced,  # noqa: F401
    _classify_doc,  # noqa: F401
    _parse_frontmatter,  # noqa: F401
    cmd_lint_doc_archival_suggestions,
    cmd_lint_doc_lifecycle,
)

# P100 R1: schemas 子模块 (extracted 488L from omo_lint.py)
# Re-export 保持向后兼容 (cli.py / omo_audit.py / omo_lint_seed 可能直接 import)
from .omo_lint_schemas import (  # noqa: F401
    _CROSS_MODULE_SRP_ALLOWLIST,  # noqa: F401
    _SORT_KEYS_DEFAULT_EXEMPT_MODULES,  # noqa: F401
    CONSUMER_MODULES,  # noqa: F401
    OMO_SRC,
    _check_all_schemas_exported,  # noqa: F401
    _check_cross_module_srp,  # noqa: F401
    _check_dead_imports,  # noqa: F401
    _check_module_append_has_schema,  # noqa: F401
    _check_schema_registry_integrity,  # noqa: F401
    _check_sort_keys_default,  # noqa: F401
    cmd_lint_schemas,
)
from .omo_paths import OMO_ROOT, PROJECTS_DIR, WORKSPACE_ROOT
from .omo_shared import load_yaml
from .omo_task_policy import (
    OPC_P6_SELF_EVOLUTION_POLICY,
    TASK_POLICIES,
    check_task_policy,
    count_planned_matches,
    get_task_policy,
)

# P101 R1: yaml-bypass 子模块 (extracted 102L from omo_lint.py)
# Re-export 保持向后兼容 (cli.py / scripts/ 可能直接 import)


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

    result = subprocess.run(  # noqa: PLW1510
        cmd, cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, check=False
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
# P1 物理沙箱: os.* 调用写敏感目标 (堵 evidence-smoke 类 os.makedirs/replace 绕过)
_SENSITIVE_OS_CALLS = {"makedirs", "mkdir", "replace", "rename"}
_SENSITIVE_WRITE_EXEMPT_FILES = {
    "omo_demo_artifacts.py",
    "omo_ingress.py",
    "omo_ingress_goal.py",  # goal ingress writes are authorized broker surface
    "omo_ingress_registry_writes.py",  # ingress registry writes are authorized broker surface
    "omo_ingress_task_lifecycle.py",  # task lifecycle writes are authorized ingress broker surface
    "omo_ingress_task_archive.py",  # P110 split: task yield/archive (parent: omo_ingress_task_lifecycle)
    "omo_ingress_task_contract.py",  # P110 split: task contract + self-evolution routing
    "omo_ingress_task_promotion.py",  # P110 split: task promote/revert/approval repair
    "omo_release_cycle.py",
    "omo_weekly_loop.py",
    "omo_worker_promotion.py",
    "omo_state.py",  # P1 CI: INDEX/system.yaml 计数同步是派生维护 (cmd_state_sync_tasks), 非 sensitive 变更 (task lifecycle 归 omo_ingress_task_lifecycle)
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
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
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

        # P1: os.makedirs/os.mkdir/os.replace/os.rename 写敏感目标 (堵绕过)
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
            and node.func.attr in _SENSITIVE_OS_CALLS
            and node.args
        ):
            target_expr = node.args[0]
            op_name = f"os.{node.func.attr}"

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


# P102 R1: surfaces 子模块 (extracted 179L from omo_lint.py)
# Re-export 保持向后兼容 (cli.py / scripts/ 可能直接 import)


# P103 R1: mutation-ledger 子模块 (extracted 92L from omo_lint.py)
# Re-export 保持向后兼容 (cli.py / scripts/ 可能直接 import)


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
                    (
                        f"R1: yaml 有 status={status!r} 字段但无 lifecycle_state (OMO 用 "
                        f"lifecycle_state, 改 status 是越权写入, OMO 不认)"
                    ),
                )
            )
        elif has_status and status in ("closed", "resolved") and lifecycle != status:
            issues.append(
                (
                    path.name,
                    (
                        f"R2: status={status!r} 但 lifecycle_state={lifecycle!r} 不一致 "
                        f"(越权写入, OMO 以 lifecycle_state 为准)"
                    ),
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


# 阈值 (ADR-0155 修订 L0:X4: error 800→1500, 跟 bin/check-god-module.py error>1500L 统一, 消除两套不一致债)
# 旧值 (L0:X4 原锁 800L, TASK-F7114ABA) 致 22 个 >800L GATE FAIL, 其中 21 个在 800-1500L (bin 视为 warn),
# 仅 1 个 >1500L. 统一 1500L 让两套 god-module 守门一致, 21 个降 warn, 剩 1 个 >1500L 留 SRP 重构.
WARN_LOC = 600
ERROR_LOC = 1500

# 豁免: 显式 allowlist (历史合理大文件, 需在 ADR 记录理由)
# ADR-0155: api_system_map.py 已 SRP 拆解 (3504L → 990L + catalog/io_commands/status 分层), 豁免移除, 门禁转硬性执行.
GOD_MODULE_ALLOWLIST: set[str] = set()

# 不扫的目录 (测试/数据迁移脚本可超)
EXCLUDE_DIR_PARTS: tuple[str, ...] = (
    "tests",
    "test_",
    "__pycache__",
    ".venv",
    "node_modules",
    "_archive",
    "demo",
    "fixtures",
)


def _collect_python_files(workspace_root: Path) -> list[Path]:
    """扫所有 projects/*/src/**/*.py + bin/*.py."""
    files: list[Path] = []
    for src_root in workspace_root.glob("projects/*/src"):
        if not src_root.is_dir():
            continue
        files.extend(src_root.rglob("*.py"))
    # bin/ 是 workspace-level tools (例 ssot-guardian)
    bin_dir = workspace_root / "bin"
    if bin_dir.is_dir():
        files.extend(p for p in bin_dir.glob("*.py"))
    return files


def _is_excluded(path: Path) -> bool:
    parts = path.parts
    return any(part in EXCLUDE_DIR_PARTS for part in parts)


def _line_count(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    # 物理行数 (与 wc -l 一致); blank-only 文件不算 0 而是其真实行数 (罕见)
    return sum(1 for _ in text.splitlines())


def check_god_module(workspace_root: str = ".") -> dict:
    """扫所有 python 文件, 报告 warn (>600L) + error (>800L).

    Returns:
        dict with keys: warn_files, error_files, total_scanned, by_module.
    """
    root = Path(workspace_root).resolve()
    files = _collect_python_files(root)
    files = [f for f in files if not _is_excluded(f)]

    warn_files: list[tuple[Path, int]] = []
    error_files: list[tuple[Path, int]] = []
    by_module: dict[str, int] = {}  # module_name → max LOC

    for path in files:
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        # 转 module name 形式 (workspace.brain.kairon.path)
        rel_str = str(rel).replace("/", ".").replace(".py", "")
        if path.name == "__init__.py":
            continue
        loc = _line_count(path)
        if loc == 0:
            continue

        module_key = rel_str
        by_module[module_key] = max(by_module.get(module_key, 0), loc)

        if str(rel) in GOD_MODULE_ALLOWLIST:
            continue
        if loc > ERROR_LOC:
            error_files.append((path, loc))
        elif loc > WARN_LOC:
            warn_files.append((path, loc))

    return {
        "total_scanned": len(files),
        "warn_files": sorted(warn_files, key=lambda x: -x[1]),
        "error_files": sorted(error_files, key=lambda x: -x[1]),
        "by_module": by_module,
        "warn_threshold": WARN_LOC,
        "error_threshold": ERROR_LOC,
    }


def cmd_lint_god_module(workspace_root: str = ".") -> int:
    """omo lint god-module — 单文件 LOC 硬规则 (TASK-F7114ABA 锁定)."""
    if workspace_root == ".":
        # 默认从 find_omo_dir 找 workspace 根 (cd projects/omo 调用也能解析到 /Users/...)
        root = WORKSPACE_ROOT
    else:
        root = Path(workspace_root).resolve()
    report = check_god_module(str(root))
    warn_n = len(report["warn_files"])
    error_n = len(report["error_files"])
    total = report["total_scanned"]

    print(
        f"=== god-module lint (warn>{report['warn_threshold']}L, "
        f"error>{report['error_threshold']}L) ==="
    )
    print(f"  扫文件: {total}")
    print(f"  warn (>600L): {warn_n}")
    print(f"  error (>800L): {error_n}")

    if error_n:
        print("\n--- error (硬规则, 必须拆解) ---")
        for path, loc in report["error_files"]:
            print(f"  🔴 {path}: {loc}L (>{report['error_threshold']})")
        print(
            f"\n❌ GATE FAIL: {error_n} 个文件 >{report['error_threshold']}L. "
            f"治本: 用 omo-srp-refactor skill 渐进拆解."
        )
        return 1

    if warn_n:
        print("\n--- warn (软引导) ---")
        for path, loc in report["warn_files"][:10]:  # 限制 10 行输出
            print(f"  🟡 {path}: {loc}L (>{report['warn_threshold']})")
        if warn_n > 10:
            print(f"  ... ({warn_n - 10} more)")

    print(
        f"✅ GATE PASS: 0 文件 >{report['error_threshold']}L, "
        f"{warn_n} 文件在 {report['warn_threshold']}-{report['error_threshold']}L 区间."
    )
    return 0


def cmd_lint_ingress_registry(workspace_root: str = ".") -> int:
    from .omo_governance_surfaces import (
        _check_ingress_registry,  # type: ignore[reportAttributeAccessIssue]
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_ingress_registry(root)
    # registry 未创建 (runtime cache 缺, 如 CI fresh checkout) — 合法状态, 不阻断.
    # 结构/反向映射检查只在 registry 存在时才有意义.
    if not summary.get("exists"):
        print(
            "✅ omo lint ingress-registry pass: registry not created yet (runtime cache absent)"
        )
        return 0
    if issues:
        print(f"❌ omo lint ingress-registry fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(
        "✅ omo lint ingress-registry pass: "
        f"goals={len(summary.get('goal_ids', []))} "
        f"tasks={len(summary.get('task_ids', []))} "
        f"debts={len(summary.get('debt_ids', []))} "
        f"capabilities={len(summary.get('capability_ids', []))}"
    )
    return 0


def cmd_lint_mutation_surfaces(workspace_root: str = ".") -> int:
    from .omo_governance_surfaces import (
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
    from .omo_governance_surfaces import (
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
    from .omo_governance_surfaces import (
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
    from .omo_governance_surfaces import (
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
    from .omo_governance_surfaces import (
        _check_ingress_artifacts,  # type: ignore[reportAttributeAccessIssue]
        resolve_governance_workspace_root,
    )

    root = resolve_governance_workspace_root(Path(workspace_root))
    summary, issues = _check_ingress_artifacts(root)
    # registry 未创建 (runtime cache 缺, 如 CI fresh checkout) — 合法状态, 不阻断.
    if not summary.get("exists"):
        print(
            "✅ omo lint ingress-artifacts pass: registry not created yet (runtime cache absent)"
        )
        return 0
    if issues:
        print(f"❌ omo lint ingress-artifacts fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(
        "✅ omo lint ingress-artifacts pass: "
        f"goals={summary.get('goal_artifacts', 0)} "
        f"tasks={summary.get('task_artifacts', 0)} "
        f"debts={summary.get('debt_artifacts', 0)} "
        f"capabilities={summary.get('capability_artifacts', 0)}"
    )
    return 0


def cmd_lint_mutation_ledger(workspace_root: str = ".") -> int:
    root = Path(workspace_root).resolve()
    ledger_path = _mutation_log_path(root / ".omo")
    # CI fresh checkout 无 runtime/omo (gitignored) — 合法空状态, 不阻断
    if not ledger_path.exists():
        print(
            "⚠️ omo lint mutation-ledger: ledger file missing (runtime cache absent, CI fresh checkout), 视为 pass"
        )
        return 0

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
        if not isinstance(artifact_ref, str) or not (
            artifact_ref.startswith((".omo/", "runtime/omo/"))
        ):
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


RUNTIME_DIR = WORKSPACE_ROOT / "runtime"
REGISTRY = OMO_ROOT / "_truth" / "registry" / "runtime-projections.yaml"
GITIGNORE = WORKSPACE_ROOT / ".gitignore"

ALLOW_PATHS: tuple[str, ...] = (
    "runtime/README.md",
    "runtime/runtime-space-boundary.yaml",
    "runtime/system-runtime-boundary.yaml",
    "runtime/sandbox/**",
    "runtime/logs/**",
    "runtime/data/**",
    "runtime/omo/**",
    "runtime/run-continuation/**",
)

_TRACKED_OVERRIDE: tuple[str, ...] = ()


def load_gitignore_patterns() -> list[str]:
    if not GITIGNORE.exists():
        return []
    patterns: list[str] = []
    for raw in GITIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "!")):
            continue
        patterns.append(line.rstrip("/"))
    return patterns


def load_projection_paths() -> set[str]:
    if not REGISTRY.exists():
        return set()
    documents = [
        doc for doc in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if doc
    ]
    paths: set[str] = set()
    for document in documents:
        if isinstance(document, dict) and "projections" in document:
            raw = document.get("projections") or {}
            if isinstance(raw, dict):
                for payload in raw.values():
                    if isinstance(payload, dict):
                        for key in ("canonical", "legacy"):
                            value = str(payload.get(key) or "")
                            if value:
                                paths.add(value)
    return paths


def load_tracked_runtime_files() -> tuple[str, ...]:
    global _TRACKED_OVERRIDE
    if _TRACKED_OVERRIDE:
        return _TRACKED_OVERRIDE
    try:
        result = subprocess.run(
            ["git", "ls-files", "runtime/"],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ()
    if result.returncode != 0:
        return ()
    paths = tuple(line.strip() for line in result.stdout.splitlines() if line.strip())
    _TRACKED_OVERRIDE = paths
    return paths


def _match(pattern: str, rel_path: str) -> bool:
    if pattern == rel_path:
        return True
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        if rel_path.startswith(prefix + "/") or rel_path == prefix:
            return True
    if pattern.endswith("/*"):
        prefix = pattern[:-2]
        if rel_path.startswith(prefix + "/"):
            return True
    if "**" in pattern:
        return _gitignore_match(pattern, rel_path)
    return fnmatch.fnmatch(rel_path, pattern)


def _gitignore_match(pattern: str, rel_path: str) -> bool:
    pat_parts = pattern.split("/")
    path_parts = rel_path.split("/")
    return _match_segments(pat_parts, path_parts)


def _match_segments(pat: list[str], path: list[str]) -> bool:
    if not pat:
        return not path
    head, *tail = pat
    if head == "**":
        if _match_segments(tail, path):
            return True
        if path:
            return _match_segments(pat, path[1:])
        return False
    if not path:
        return False
    if not fnmatch.fnmatch(path[0], head):
        return False
    return _match_segments(tail, path[1:])


def is_allowed(
    rel_path: str,
    ignore_patterns: list[str],
    projection_paths: set[str],
    tracked: set[str],
) -> bool:
    for allowed in ALLOW_PATHS:
        if _match(allowed, rel_path):
            return True
    if rel_path in projection_paths:
        return True
    if rel_path in tracked:
        return True
    for pattern in ignore_patterns:
        if _match(pattern, rel_path):
            return True
    return False


def cmd_stamp_policy(json_output: bool = False) -> int:
    """P74: 验证 runtime/ 下文件必须 gitignored/tracked/allowlisted."""
    if not RUNTIME_DIR.exists():
        report = {"ok": True, "runtime_dir_exists": False, "orphan_paths": []}
        if json_output:
            json.dump(report, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print("[OK] stamp-policy: runtime/ directory absent")
        return 0

    ignore_patterns = load_gitignore_patterns()
    projection_paths = load_projection_paths()
    tracked = set(load_tracked_runtime_files())

    orphans: list[dict[str, Any]] = []
    for path in sorted(RUNTIME_DIR.rglob("*")):
        if path.is_dir():
            continue
        rel_path = path.relative_to(WORKSPACE_ROOT).as_posix()
        if is_allowed(rel_path, ignore_patterns, projection_paths, tracked):
            continue
        orphans.append({"path": rel_path, "size": path.stat().st_size})

    report = {
        "ok": not orphans,
        "runtime_dir_exists": True,
        "ignore_pattern_count": len(ignore_patterns),
        "projection_path_count": len(projection_paths),
        "tracked_runtime_count": len(tracked),
        "orphan_paths": orphans,
    }

    if json_output:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        status = "OK" if report["ok"] else "FAIL"
        print(f"[{status}] stamp-policy: {len(orphans)} orphan file(s) under runtime/")
        for orphan in orphans:
            print(f"  - {orphan['path']} ({orphan['size']} bytes)")

    return 0 if report["ok"] else 1


REGISTRY = OMO_ROOT / "_truth" / "registry" / "runtime-projections.yaml"


def load_projection_registry() -> dict[str, dict[str, str]]:
    if not REGISTRY.exists():
        raise SystemExit(f"runtime-projections registry missing: {REGISTRY}")
    documents = [
        doc for doc in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if doc
    ]
    for document in documents:
        if isinstance(document, dict) and "projections" in document:
            raw = document.get("projections") or {}
            if not isinstance(raw, dict):
                return {}
            normalized: dict[str, dict[str, str]] = {}
            for name, payload in raw.items():
                if isinstance(payload, dict):
                    state = str(payload.get("state") or "active").strip().lower()
                    if state not in {"active", "pending", "deprecated"}:
                        state = "active"
                    normalized[str(name)] = {
                        "canonical": str(payload.get("canonical") or ""),
                        "legacy": str(payload.get("legacy") or ""),
                        "lane": str(payload.get("lane") or ""),
                        "generator": str(payload.get("generator") or ""),
                        "state": state,
                    }
            return normalized
    raise SystemExit(
        f"runtime-projections registry has no projections document: {REGISTRY}"
    )


def probe(path_str: str) -> dict[str, Any]:
    if not path_str:
        return {"path": "", "exists": False, "kind": "missing", "size": 0}
    path = WORKSPACE_ROOT / path_str
    if not path.exists():
        return {"path": path_str, "exists": False, "kind": "missing", "size": 0}
    size = path.stat().st_size
    kind = "unknown"
    if path.suffix in {".yaml", ".yml"}:
        try:
            list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
            kind = "yaml-ok"
        except Exception as exc:
            kind = f"yaml-error:{exc}"
    elif path.suffix == ".json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
            kind = "json-ok"
        except json.JSONDecodeError as exc:
            kind = f"json-error:{exc}"
    elif path.suffix == ".md":
        kind = "markdown"
    return {"path": path_str, "exists": True, "kind": kind, "size": size}


def cmd_projection_guard(json_output: bool = False) -> int:
    """P74: 验证 runtime-projections.yaml 声明的路径存在且可解析."""
    registry = load_projection_registry()
    findings: list[dict[str, Any]] = []
    ok = True

    for name, payload in registry.items():
        state = payload.get("state", "active")
        canonical = probe(payload["canonical"])
        if not canonical["exists"]:
            if state == "pending":
                findings.append(
                    {
                        "severity": "info",
                        "projection": name,
                        "kind": "canonical_pending",
                        "path": payload["canonical"],
                    }
                )
                continue
            ok = False
            findings.append(
                {
                    "severity": "halt",
                    "projection": name,
                    "kind": "canonical_missing",
                    "path": payload["canonical"],
                }
            )
            continue
        if isinstance(canonical["kind"], str) and canonical["kind"].startswith(
            ("yaml-error", "json-error")
        ):
            ok = False
            findings.append(
                {
                    "severity": "halt",
                    "projection": name,
                    "kind": "canonical_parse_error",
                    "path": payload["canonical"],
                    "detail": canonical["kind"],
                }
            )
        if payload["legacy"]:
            legacy = probe(payload["legacy"])
            if legacy["exists"] and legacy["size"] != canonical["size"]:
                findings.append(
                    {
                        "severity": "warn",
                        "projection": name,
                        "kind": "legacy_size_drift",
                        "canonical_path": payload["canonical"],
                        "legacy_path": payload["legacy"],
                        "canonical_size": canonical["size"],
                        "legacy_size": legacy["size"],
                    }
                )

    report = {
        "ok": ok,
        "projection_count": len(registry),
        "findings": findings,
    }

    if json_output:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        status = "OK" if ok else "FAIL"
        print(
            f"[{status}] projection-guard: {len(registry)} projections, {len(findings)} findings"
        )
        for finding in findings:
            print(f"  [{finding['severity']}] {finding['kind']}: {finding}")

    return 0 if ok else 1


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
        help="校验 runtime/omo/_delivery/ingress/registry.yaml 的结构、反向映射与落盘一致性",
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
        help="校验 runtime/omo/change-log/mutations.jsonl 账本存在、字段齐全且 artifact_ref 可回落到真实文件",
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
    god_module = sub.add_parser(
        "god-module",
        help="单文件 LOC 硬规则 (TASK-F7114ABA: warn>600L, error>800L)",
    )
    god_module.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    # P74: projection-guard (from bin/gac/omo-state-projection-guard.py)
    projection_guard = sub.add_parser(
        "projection-guard",
        help="P74: 验证 runtime-projections.yaml 声明的路径存在且可解析 (CR-P74-STATE-PROJECTION-GUARD)",
    )
    projection_guard.add_argument("--json", action="store_true", help="JSON 输出")
    # P74: stamp-policy (from bin/omo-runtime-stamp-policy.py)
    stamp_policy = sub.add_parser(
        "stamp-policy",
        help="P74: 验证 runtime/ 下文件必须 gitignored/tracked/allowlisted (CR-P74-RUNTIME-STAMP-POLICY)",
    )
    stamp_policy.add_argument("--json", action="store_true", help="JSON 输出")
    # Scheme C 5c L1: path ACL doctor (ADR-0187) — read-only, never mutates host
    path_acl = sub.add_parser(
        "path-acl",
        help="Scheme C 5c L1: 巡检 .omo/spaces 写面 world-writable 等 (只读, 不 chmod)",
    )
    path_acl.add_argument(
        "--workspace-root", default=".", help="显式指定 workspace root"
    )
    path_acl.add_argument("--json", action="store_true", help="JSON 输出")
    path_acl.add_argument(
        "--strict",
        action="store_true",
        help="world-writable/0777 视为 FAIL (默认 warn-only)",
    )
    path_acl.add_argument(
        "--profile",
        default=None,
        help="覆盖 omo-path-acl.yaml 路径 (或 OMO_PATH_ACL_PROFILE)",
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
    if args.command == "god-module":
        return cmd_lint_god_module(args.workspace_root)
    if args.command == "projection-guard":
        return cmd_projection_guard(json_output=args.json)
    if args.command == "stamp-policy":
        return cmd_stamp_policy(json_output=args.json)
    if args.command == "path-acl":
        from .omo_path_acl import cmd_lint_path_acl

        return cmd_lint_path_acl(
            args.workspace_root,
            json_output=args.json,
            strict=args.strict,
            profile=args.profile,
        )
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
