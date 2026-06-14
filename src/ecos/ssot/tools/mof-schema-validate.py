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
    python3 src/ecos/ssot/tools/mof-schema-validate.py --json  # JSON 输出 (CI 集成)
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
"""
import argparse
import json
import subprocess
import sys
import yaml
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).parent.parent / "mof"
M2_DIR = ROOT / "m2"
M1_DIR = ROOT / "m1"


def load_m2_schemas():
    """加载 M2 schemas, 支持 PascalCase + snake_case + lowercase section 命名.

    返回 schema dict: m2_type -> {requiredProperties, optionalProperties, stateMachine, ...}

    同时支持 alias: m2_type 与 section key (snake_case) 双向都接受。
    """
    schemas = {}
    for f in sorted(M2_DIR.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        mt = data.get("m2_type")
        if not mt:
            continue
        # 尝试多种 section 命名
        section = (
            data.get(mt)
            or data.get(mt[0].lower() + mt[1:])
            or data.get(mt.lower())
        )
        if section is None:
            # 顶层其他 keys (description/requiredProperties 等) 即 section
            top_other = [
                k for k in data
                if k not in ("m2_type", "version", "created", "updated")
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


def check_m1_node(data, schema, m2_type):
    """校验单个 M1 节点 vs M2 schema.

    双向校验: 字段在 properties 或 top-level 都被接受 (历史 M1 节点字段位置不一致).
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

    # 校验 2: state machine
    sm = list((schema.get("stateMachine") or {}).keys())
    if sm and status and status not in sm:
        issues.append(f"  - status={status!r} 不在 stateMachine {sm}")

    return issues


def main():
    parser = argparse.ArgumentParser(description="M1 vs M2 schema validator")
    parser.add_argument("--strict", action="store_true", help="退出码非 0 if issues found")
    parser.add_argument("--focus", help="只校验指定子目录, 逗号分隔 (如 omo_layer,governance)")
    parser.add_argument("--json", dest="json_output", action="store_true", help="JSON 格式输出 (CI 集成)")
    parser.add_argument("--staged", action="store_true", help="只校验 git staged M1 文件 (pre-commit 模式)")
    parser.add_argument("--type-coverage", action="store_true", help="M1 type 覆盖率统计")
    parser.add_argument("--orphaned", action="store_true", help="找孤儿 M2 schema (无 M1 引用)")
    parser.add_argument("--no-color", action="store_true", help="禁用 ANSI 颜色 (CI 集成)")
    args = parser.parse_args()

    focus_dirs = None
    if args.focus:
        focus_dirs = set(args.focus.split(","))

    # --staged 模式: 提取 git staged M1 文件路径
    if args.staged:
        try:
            r = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "--", "src/ecos/ssot/mof/m1/**/*.yaml"],
                capture_output=True, text=True, check=True,
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

            issues = check_m1_node(data, schema, t)
            for issue in issues:
                if "missing required" in issue:
                    missing_req.append((nid, t, issue.strip(), str(f.relative_to(M1_DIR))))
                if "stateMachine" in issue:
                    invalid_sm.append((nid, t, issue.strip(), str(f.relative_to(M1_DIR))))

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
            "type_drift": [
                {"id": nid, "type": t, "path": p}
                for nid, t, p in drift
            ],
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
    if args.strict:
        if drift or missing_req or invalid_sm:
            code = 1
            if missing_req:
                code |= 2
            if invalid_sm:
                code |= 3
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
        print(f"❌ mof-schema-validate 失败: {len(drift)} drift + {len(missing_req)} missing + {len(invalid_sm)} sm_invalid")
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
        print(f"M1 引用 M2 (PASS): {len(used_m2)} / {len(schemas)} = {100*len(used_m2)/len(schemas):.1f}%")
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
        if mt not in type_aliases or not (m1_types & {mt, mt.lower(), mt[0].lower() + mt[1:]}):
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
