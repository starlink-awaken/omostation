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

from .omo_paths import PROJECTS_DIR, WORKSPACE_ROOT
from .omo_shared import load_yaml
from .omo_task_policy import (
    OPC_P6_SELF_EVOLUTION_POLICY,
    TASK_POLICIES,
    check_task_policy,
    count_planned_matches,
    get_task_policy,
)

# P88 R1: doc-lifecycle 子模块 (extracted 304L from omo_lint.py)
# Re-export 保持向后兼容 (omo.cli / scripts/ / omo_audit.py 可能直接 import)
from .omo_lint_doc import (  # noqa: E402, F401
    _DOC_LIFECYCLE_NEED_FRONTMATTER,
    _DOC_LIFECYCLE_PATTERNS,
    _check_doc_referenced,
    _classify_doc,
    _parse_frontmatter,
    cmd_lint_doc_archival_suggestions,
    cmd_lint_doc_lifecycle,
)

# P100 R1: schemas 子模块 (extracted 488L from omo_lint.py)
# Re-export 保持向后兼容 (cli.py / omo_audit.py / omo_lint_seed 可能直接 import)
from .omo_lint_schemas import (  # noqa: E402, F401
    CONSUMER_MODULES,
    OMO_SRC,
    _CROSS_MODULE_SRP_ALLOWLIST,
    _SORT_KEYS_DEFAULT_EXEMPT_MODULES,
    _check_all_schemas_exported,
    _check_cross_module_srp,
    _check_dead_imports,
    _check_module_append_has_schema,
    _check_schema_registry_integrity,
    _check_sort_keys_default,
    cmd_lint_schemas,
)


# P101 R1: yaml-bypass 子模块 (extracted 102L from omo_lint.py)
# Re-export 保持向后兼容 (cli.py / scripts/ 可能直接 import)
from .omo_lint_yaml_bypass import (  # noqa: E402, F401
    _check_yaml_bypass,
    cmd_lint_yaml_bypass,
)
from .omo_lint_god_module import (  # noqa: E402, F401
    cmd_lint_god_module,
    ERROR_LOC as _GOD_MODULE_ERROR_LOC,
    WARN_LOC as _GOD_MODULE_WARN_LOC,
)


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
from .omo_lint_surfaces import (  # noqa: E402, F401
    cmd_lint_c2g_omo_boundary,
    cmd_lint_ingress_artifacts,
    cmd_lint_ingress_registry,
    cmd_lint_internal_write_profiles,
    cmd_lint_mutation_surfaces,
    cmd_lint_state_plane_assets,
)


# P103 R1: mutation-ledger 子模块 (extracted 92L from omo_lint.py)
# Re-export 保持向后兼容 (cli.py / scripts/ 可能直接 import)
from .omo_lint_mutation_ledger import (  # noqa: E402, F401
    cmd_lint_mutation_ledger,
)


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
    # P74: projection-guard (from bin/omo-state-projection-guard.py)
    projection_guard = sub.add_parser(
        "projection-guard",
        help="P74: 验证 runtime-projections.yaml 声明的路径存在且可解析 (CR-P74-STATE-PROJECTION-GUARD)",
    )
    projection_guard.add_argument(
        "--json", action="store_true", help="JSON 输出"
    )
    # P74: stamp-policy (from bin/omo-runtime-stamp-policy.py)
    stamp_policy = sub.add_parser(
        "stamp-policy",
        help="P74: 验证 runtime/ 下文件必须 gitignored/tracked/allowlisted (CR-P74-RUNTIME-STAMP-POLICY)",
    )
    stamp_policy.add_argument(
        "--json", action="store_true", help="JSON 输出"
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
        from omo.omo_lint_projection import cmd_projection_guard
        return cmd_projection_guard(json_output=args.json)
    if args.command == "stamp-policy":
        from omo.omo_lint_stamp import cmd_stamp_policy
        return cmd_stamp_policy(json_output=args.json)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
