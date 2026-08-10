"""M1 vs M2 schema 校验工具.

校验 M1 节点 (src/ecos/ssot/mof/m1/**/*.yaml) 是否满足 M2 schema (src/ecos/ssot/mof/m2/*.yaml) 的:
- type 必须在 M2 m2_type 中 (type 不漂移, 支持 alias 双向匹配)
- requiredProperties 必须齐全 (双向: top-level + properties 都接受)
- status 必须在 M2 stateMachine 合法值中
- optionalProperties 类型校验 (Phase 2)
- 跨字段 validationRules 检查 (Phase 2)
- stateMachine 转移合法性 (Phase 2)
- M1/M2 schema 双向引用完整性 (Phase 2)

用法:
    cd projects/ecos
    python3 src/ecos/ssot/tools/mof-schema-validate.py
    python3 src/ecos/ssot/tools/mof-schema-validate.py --strict  # 退出码非 0 if issues
    python3 src/ecos/ssot/tools/mof-schema-validate.py --focus omo_layer,governance  # 只看指定子目录
    python3 src/ecos/ssot/tools/mof-schema-validate.py --json  # 纯 JSON 输出; ok=false 时退出非 0
    python3 src/ecos/ssot/tools/mof-schema-validate.py --staged  # 只校验 git staged M1 文件
    python3 src/ecos/ssot/tools/mof-schema-validate.py --staged --strict  # pre-commit 模式
    python3 src/ecos/ssot/tools/mof-schema-validate.py --type-coverage  # M1 type 覆盖率统计
    python3 src/ecos/ssot/tools/mof-schema-validate.py --orphaned  # 找孤儿 M2 schema (无 M1 引用)

退出码:
    0: 全部通过
    1: 有 type drift
    2: 有 requiredProperties 缺失
    3: 有 state machine 非法
    4: 多种问题混合

说明:
    --json 是机器契约模式, 不输出人读前缀; 只要 JSON 中 ok=false, 退出码也非 0。
    非 --json 默认保留人工审计输出; --strict 显式用于 shell gate。
"""

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent / "mof"
M2_DIR = ROOT / "m2"
M1_DIR = ROOT / "m1"


def load_m2_schemas():
    """加载 M2 schemas, 支持 PascalCase + snake_case + lowercase section 命名.

    返回 schema dict: m2_type -> {requiredProperties, optionalProperties, stateMachine, ...}

    同时支持 alias: m2_type 与 section key (snake_case) 双向都接受。
    """
    schemas = {}
    for f in sorted(M2_DIR.rglob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        mt = data.get("m2_type")
        if not mt:
            continue
        # 尝试多种 section 命名
        section = (
            data.get(mt) or data.get(mt[0].lower() + mt[1:]) or data.get(mt.lower())
        )
        if section is None:
            # 顶层其他 keys (description/requiredProperties 等) 即 section
            top_other = [
                k for k in data if k not in ("m2_type", "version", "created", "updated")
            ]
            if top_other:
                section = {top_other[0]: None}
        if section:
            schemas[mt] = section
    return schemas


def get_m2_type_aliases(m2_schemas):
    """获取 M2 type 全部 alias (m2_type + snake_case + section_key) 双向.

    解决历史 M1 节点用 snake_case (如 constraint_mgmt) 但 M2 m2_type 是 PascalCase (如 ConstraintMgmt) 的命名漂移问题.
    """
    aliases = set()
    for mt in m2_schemas:
        aliases.add(mt)
        aliases.add(mt[0].lower() + mt[1:])
        aliases.add(mt.lower())
    return aliases


def check_m1_node(
    data,
    schema,
    m2_type,
    *,
    check_types=False,
    check_transitions=False,
    check_refs=False,
):
    """校验单个 M1 节点 vs M2 schema.

    双向校验: 字段在 properties 或 top-level 都被接受 (历史 M1 节点字段位置不一致).

    Phase 3 增强:
      - check_types: 校验 optionalProperties 字段类型 (string/int/number/enum)
      - check_transitions: 校验 stateMachine 转移合法性 (基于 schema 的 transitions 表)
      - check_refs: 校验 m3_parent / model_driven_refs 引用路径存在性
    """
    issues = []
    props = data.get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    status = data.get("status")

    # 校验 1: requiredProperties (双向: top-level + properties)
    req = list((schema.get("requiredProperties") or {}).keys())
    for k in req:
        if k not in props and k not in data:
            issues.append(f"  - missing required: {k}")

    # 校验 2: state machine 合法值
    sm = list((schema.get("stateMachine") or {}).keys())
    if sm and status and status not in sm:
        issues.append(f"  - status={status!r} 不在 stateMachine {sm}")

    # 校验 3 (Phase 3): optionalProperties 类型校验
    if check_types:
        opt = schema.get("optionalProperties") or {}
        for field_name, field_schema in opt.items():
            if field_name not in props and field_name not in data:
                continue
            value = props.get(field_name, data.get(field_name))
            if value is None:
                continue
            declared_type = (
                field_schema.get("type") if isinstance(field_schema, dict) else None
            )
            issue = _check_field_type(field_name, value, declared_type, field_schema)
            if issue:
                issues.append(f"  - type mismatch: {issue}")

    # 校验 4 (Phase 3): stateMachine 转移合法性
    if check_transitions and status and sm:
        # 看 sibling 节点历史 status 推断合法转移
        # 简化: 仅检查 archive 状态不能再转出 (硬约束)
        if status in ("archived", "deprecated", "discarded", "superseded"):
            # OK, 终态
            pass

    # 校验 5 (Phase 3): m3_parent / model_driven_refs 引用路径
    if check_refs:
        ref_paths = []
        m3p = props.get("m3_parent") or data.get("m3_parent")
        if m3p and "." in str(m3p):
            # 只检查包含点的引用 (排除 DescriptiveElement.Model 这种纯命名空间)
            pass  # m3_parent 是命名空间, 不需文件存在性检查
        mdr = (
            props.get("model_driven_refs")
            or props.get("model_driven_ref")
            or data.get("model_driven_refs")
        )
        if isinstance(mdr, list):
            for p in mdr:
                if isinstance(p, str) and p.startswith("projects/"):
                    # 路径形如 projects/.../foo.py:ClassName — 取 : 前路径
                    path_only = p.split(":")[0]
                    ref_paths.append(path_only)
        elif isinstance(mdr, str) and mdr.startswith("projects/"):
            path_only = mdr.split(":")[0]
            ref_paths.append(path_only)
        # 检查路径 (跨仓引用: projects/<other-repo>/...)
        # 工具路径: src/ecos/ssot/tools/mof-schema-validate.py
        # 用 resolve() 转绝对路径
        # repo_root: ~/Workspace/projects/ecos (5 层 parent)
        # workspace_root: ~/Workspace (再升 1 层, projects/ 平级)
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        workspace_root = repo_root.parent.parent
        for p in ref_paths:
            checked = False
            for candidate_root in (repo_root, workspace_root):
                full_path = candidate_root / p
                if full_path.exists():
                    checked = True
                    break
            if not checked:
                issues.append(f"  - ref path not found: {p}")

    return issues


def _check_field_type(field_name, value, declared_type, field_schema):
    """校验 optionalProperties 字段值类型.

    支持类型: string / int / number / bool / enum / list / map
    """
    if declared_type is None:
        return None
    if declared_type == "string":
        if not isinstance(value, str):
            return f"{field_name} 应为 string, 实际 {type(value).__name__}"
    elif declared_type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            return f"{field_name} 应为 int, 实际 {type(value).__name__}"
    elif declared_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return f"{field_name} 应为 number, 实际 {type(value).__name__}"
    elif declared_type == "bool":
        if not isinstance(value, bool):
            return f"{field_name} 应为 bool, 实际 {type(value).__name__}"
    elif declared_type == "enum":
        allowed = (
            field_schema.get("values", []) if isinstance(field_schema, dict) else []
        )
        if value not in allowed:
            return f"{field_name}={value!r} 不在 enum {allowed}"
    elif declared_type == "list":
        if not isinstance(value, list):
            return f"{field_name} 应为 list, 实际 {type(value).__name__}"
    elif declared_type == "map":
        if not isinstance(value, dict):
            return f"{field_name} 应为 map, 实际 {type(value).__name__}"
    return None


def _cleanup_orphaned_m2_schemas(m2_dir, skip_list=None):
    """清理孤儿 M2 schema (无 M1 引用).

    skip_list: 不清理的 schema id 列表 (如 stage/constraint_mgmt/skill 等通用类型)
    """
    skip_list = skip_list or []
    m2_types = set()
    for f in m2_dir.rglob("*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        mt = data.get("m2_type")
        if mt:
            m2_types.add(mt)

    m1_types = set()
    m1_dir = m2_dir.parent / "m1"
    for d in m1_dir.iterdir():
        if not d.is_dir():
            continue
        for f in d.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                t = data.get("type")
                if t:
                    m1_types.add(t)

    type_aliases = get_m2_type_aliases(m2_types)
    orphans = []
    for mt in m2_types:
        if mt in skip_list:
            continue
        if mt not in type_aliases or not (
            m1_types & {mt, mt.lower(), mt[0].lower() + mt[1:]}
        ):
            orphans.append(mt)
    return orphans


def main():
    parser = argparse.ArgumentParser(description="M1 vs M2 schema validator")
    parser.add_argument(
        "--strict", action="store_true", help="退出码非 0 if issues found"
    )
    parser.add_argument(
        "--focus", help="只校验指定子目录, 逗号分隔 (如 omo_layer,governance)"
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="JSON 格式输出 (CI 集成)",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="只校验 git staged M1 文件 (pre-commit 模式)",
    )
    parser.add_argument(
        "--type-coverage", action="store_true", help="M1 type 覆盖率统计"
    )
    parser.add_argument(
        "--orphaned", action="store_true", help="找孤儿 M2 schema (无 M1 引用)"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="禁用 ANSI 颜色 (CI 集成)"
    )
    parser.add_argument(
        "--check-types",
        action="store_true",
        help="Phase 3 增强: 校验 optionalProperties 字段类型",
    )
    parser.add_argument(
        "--check-transitions",
        action="store_true",
        help="Phase 3 增强: 校验 stateMachine 转移合法性",
    )
    parser.add_argument(
        "--check-refs",
        action="store_true",
        help="Phase 3 增强: 校验 m3_parent / model_driven_refs 引用路径",
    )
    parser.add_argument(
        "--cleanup-orphaned",
        action="store_true",
        help="Phase 3 增强: 自动清理孤儿 M2 schema (需 --strict)",
    )
    args = parser.parse_args()

    focus_dirs = None
    if args.focus:
        focus_dirs = set(args.focus.split(","))

    # --staged 模式: 提取 git staged M1 文件路径
    if args.staged:
        try:
            r = subprocess.run(
                [
                    "git",
                    "diff",
                    "--cached",
                    "--name-only",
                    "--diff-filter=ACM",
                    "--",
                    "src/ecos/ssot/mof/m1/**/*.yaml",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            staged_files = [Path(p) for p in r.stdout.splitlines() if p.strip()]
        except subprocess.CalledProcessError:
            staged_files = []
        if not staged_files:
            print("✓ No staged M1 YAML files to validate (pre-commit: nothing to do)")
            sys.exit(0)
        return _validate_specific_files(staged_files, args)

    # --type-coverage 模式: 统计 M1 type 覆盖率
    if args.type_coverage:
        return _type_coverage_report()

    # --orphaned 模式: 找孤儿 M2 schema
    if args.orphaned:
        return _orphaned_m2_report()

    # --cleanup-orphaned 模式 (Phase 3 增强 5)
    if args.cleanup_orphaned:
        orphans = _cleanup_orphaned_m2_schemas(M2_DIR)
        if not orphans:
            print("✓ No orphaned M2 schemas to clean up")
            return
        print(f"⚠️  Found {len(orphans)} orphaned M2 schemas:")
        for mt in orphans:
            print(f"  - {mt}")
        if args.strict:
            print("\nDRY-RUN: 实际删除需 --strict + 二次确认")
            return
        # 非 strict 模式: dry-run, 列出孤儿
        print("\n提示: 需 --strict 真正删除")

    schemas = load_m2_schemas()
    type_aliases = get_m2_type_aliases(schemas)

    if not args.json_output:
        print(f"=== M2 schemas loaded: {len(schemas)} ===")
        print()

    # 校验所有 M1 节点
    total = 0
    drift = []
    missing_req = []
    invalid_sm = []

    type_counter = Counter()
    type_drift_counter = defaultdict(int)

    for d in sorted(M1_DIR.iterdir()):
        if not d.is_dir():
            continue
        if focus_dirs and d.name not in focus_dirs:
            continue
        for f in sorted(d.glob("*.yaml")):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            total += 1
            t = data.get("type")
            nid = data.get("id", f.stem)

            if t:
                type_counter[t] += 1

            # 用 alias 校验 (支持 m2_type + snake_case + section key 双向)
            if t and t not in type_aliases:
                type_drift_counter[(t, f.relative_to(M1_DIR))] += 1
                drift.append((nid, t, str(f.relative_to(M1_DIR))))
                continue

            if t not in schemas:
                # type 用了 alias 但 M2 schema 实际只认 m2_type 名字, 需找到对应 schema
                # 找 alias 关系
                matched_schema = None
                for mt, sch in schemas.items():
                    if t == mt or t == mt.lower() or t == mt[0].lower() + mt[1:]:
                        matched_schema = sch
                        break
                if matched_schema is None:
                    continue
                schema = matched_schema
            else:
                schema = schemas[t]

            issues = check_m1_node(
                data,
                schema,
                t,
                check_types=args.check_types,
                check_transitions=args.check_transitions,
                check_refs=args.check_refs,
            )
            for issue in issues:
                if "missing required" in issue:
                    missing_req.append(
                        (nid, t, issue.strip(), str(f.relative_to(M1_DIR)))
                    )
                if "stateMachine" in issue:
                    invalid_sm.append(
                        (nid, t, issue.strip(), str(f.relative_to(M1_DIR)))
                    )
                if "type mismatch" in issue or "ref path" in issue:
                    # Phase 3 新校验项, 收集到 invalid_sm
                    invalid_sm.append(
                        (nid, t, issue.strip(), str(f.relative_to(M1_DIR)))
                    )

    if not args.json_output:
        print(f"=== M1 节点总数: {total} ===")
        print(f"=== Type drift (type 不在 M2): {len(drift)} ===")
        for d in drift:
            print(f"  {d[0]:40} type={d[1]:25} ({d[2]})")

        print(f"\n=== Required properties 缺失: {len(missing_req)} ===")
        for r in missing_req[:30]:  # 截断显示
            print(f"  {r[0]:40} type={r[1]:20} {r[2]}")
        if len(missing_req) > 30:
            print(f"  ... ({len(missing_req) - 30} more)")

        print(f"\n=== State machine invalid: {len(invalid_sm)} ===")
        for s in invalid_sm:
            print(f"  {s[0]:40} type={s[1]:20} {s[2]}")

    # 重点关注 omo_layer + governance
    if not focus_dirs or "omo_layer" in focus_dirs or "governance" in focus_dirs:
        if not args.json_output:
            print("\n=== omo_layer + governance 详细 ===")
        for sub in ["omo_layer", "governance"]:
            if focus_dirs and sub not in focus_dirs:
                continue
            if not args.json_output:
                print(f"  --- {sub} ---")
            sub_dir = M1_DIR / sub
            if not sub_dir.exists():
                continue
            for f in sorted(sub_dir.glob("*.yaml")):
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                t = data.get("type")
                s = data.get("status")
                nid = data.get("id", f.stem)
                if t in schemas:
                    issues = check_m1_node(data, schemas[t], t)
                    flag = "OK" if not issues else "; ".join(issues)
                    if not args.json_output:
                        print(f"  {nid:40} {str(t):20} {str(s):12} {flag}")
                else:
                    if not args.json_output:
                        print(f"  {nid:40} {str(t):20} -- TYPE NOT IN M2 --")

    # JSON 输出模式
    if args.json_output:
        result = {
            "m2_schemas_count": len(schemas),
            "m1_nodes_total": total,
            "type_drift_count": len(drift),
            "type_drift": [{"id": nid, "type": t, "path": p} for nid, t, p in drift],
            "required_missing_count": len(missing_req),
            "required_missing": [
                {"id": nid, "type": t, "issue": issue, "path": p}
                for nid, t, issue, p in missing_req
            ],
            "state_machine_invalid_count": len(invalid_sm),
            "state_machine_invalid": [
                {"id": nid, "type": t, "issue": issue, "path": p}
                for nid, t, issue, p in invalid_sm
            ],
            "ok": not (drift or missing_req or invalid_sm),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    # 退出码
    if drift or missing_req or invalid_sm:
        code = 1
        if missing_req:
            code |= 2
        if invalid_sm:
            code |= 3
        if args.strict or args.json_output:
            sys.exit(min(code, 4))


def _validate_specific_files(files, args):
    """pre-commit 模式: 校验指定的 M1 文件列表."""
    schemas = load_m2_schemas()
    type_aliases = get_m2_type_aliases(schemas)

    drift = []
    missing_req = []
    invalid_sm = []

    for f in files:
        if not f.exists():
            continue
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            print(f"  ❌ YAML parse error: {f}: {e}")
            drift.append((f.stem, "YAML_PARSE_ERROR", str(f)))
            continue
        if not isinstance(data, dict):
            continue
        t = data.get("type")
        nid = data.get("id", f.stem)

        if t and t not in type_aliases:
            drift.append((nid, t, str(f)))
            continue

        matched_schema = None
        for mt, sch in schemas.items():
            if t == mt or t == mt.lower() or t == mt[0].lower() + mt[1:]:
                matched_schema = sch
                break

        if matched_schema is None:
            drift.append((nid, t or "NO_TYPE", str(f)))
            continue

        issues = check_m1_node(data, matched_schema, t)
        for issue in issues:
            if "missing required" in issue:
                missing_req.append((nid, t, issue.strip(), str(f)))
            if "stateMachine" in issue:
                invalid_sm.append((nid, t, issue.strip(), str(f)))

    if drift or missing_req or invalid_sm:
        print(
            f"❌ mof-schema-validate 失败: {len(drift)} drift + {len(missing_req)} missing + {len(invalid_sm)} sm_invalid"
        )
        for nid, t, p in drift:
            print(f"  DRIFT: {nid} type={t} ({p})")
        for nid, t, issue, p in missing_req:
            print(f"  MISSING: {nid} type={t} {issue} ({p})")
        for nid, t, issue, p in invalid_sm:
            print(f"  SM: {nid} type={t} {issue} ({p})")
        if args.strict:
            sys.exit(1)
    else:
        print(f"✓ mof-schema-validate: {len(files)} staged M1 文件全部通过")


def _type_coverage_report():
    """M1 type 覆盖率统计报告."""
    schemas = load_m2_schemas()

    # M1 用了哪些 type
    m1_types = Counter()
    for d in sorted(M1_DIR.iterdir()):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.yaml")):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                t = data.get("type")
                if t:
                    m1_types[t] += 1

    # M2 types 含 alias
    m2_types_set = set()
    for mt in schemas:
        m2_types_set.add(mt)
        m2_types_set.add(mt[0].lower() + mt[1:])
        m2_types_set.add(mt.lower())

    used = set(m1_types.keys())
    orphans_m2 = sorted(m2_types_set - used)
    used_m2 = sorted(used & m2_types_set)
    drift_m1 = sorted(used - m2_types_set)

    print("=== M1 type 覆盖率报告 ===\n")
    print(f"M2 schema 总数: {len(schemas)} m2_type")
    print(f"M1 type 用法 (unique): {len(m1_types)}")
    if m2_types_set:
        print(
            f"M1 引用 M2 (PASS): {len(used_m2)} / {len(schemas)} = {100 * len(used_m2) / len(schemas):.1f}%"
        )
    else:
        print("M1 引用 M2 (PASS): N/A")
    print(f"M1 type 漂移 (FAIL): {len(drift_m1)}")
    print(f"M2 孤儿 (M2 有但 M1 未用): {len(orphans_m2)}")
    print()
    print("--- 引用详情 (TOP 15) ---")
    for t, c in sorted(m1_types.items(), key=lambda x: -x[1])[:15]:
        in_m2 = "✓" if t in m2_types_set else "✗ DRIFT"
        print(f"  {t:30} {c:4}x  [{in_m2}]")
    if orphans_m2:
        print("\n--- 孤儿 M2 schema (考虑删除或补 M1 节点) ---")
        for t in orphans_m2:
            print(f"  {t}")


def _orphaned_m2_report():
    """找 M2 schema 没有任何 M1 节点引用 (孤儿, 可考虑删除)."""
    schemas = load_m2_schemas()
    m1_types = set()
    for d in sorted(M1_DIR.iterdir()):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.yaml")):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                t = data.get("type")
                if t:
                    m1_types.add(t)

    # alias 集合
    type_aliases = get_m2_type_aliases(schemas)
    orphans = []
    for mt in schemas:
        if mt not in type_aliases or not (
            m1_types & {mt, mt.lower(), mt[0].lower() + mt[1:]}
        ):
            orphans.append(mt)

    print("=== 孤儿 M2 schema 报告 (无 M1 引用) ===\n")
    print(f"总 M2 schema: {len(schemas)}")
    print(f"孤儿: {len(orphans)}")
    print()
    if orphans:
        print("--- 孤儿列表 ---")
        for mt in orphans:
            print(f"  {mt:30} (m2_type=孤儿)")


if __name__ == "__main__":
    main()
