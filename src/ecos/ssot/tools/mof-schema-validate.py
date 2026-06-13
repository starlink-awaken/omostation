"""M1 vs M2 schema 校验工具.

校验 M1 节点 (src/ecos/ssot/mof/m1/**/*.yaml) 是否满足 M2 schema (src/ecos/ssot/mof/m2/*.yaml) 的:
- type 必须在 M2 m2_type 中 (type 不漂移)
- requiredProperties 必须齐全
- status 必须在 M2 stateMachine 合法值中

用法:
    cd projects/ecos
    python3 src/ecos/ssot/tools/mof-schema-validate.py
    python3 src/ecos/ssot/tools/mof-schema-validate.py --strict  # 退出码非 0 if issues
    python3 src/ecos/ssot/tools/mof-schema-validate.py --focus omo_layer,governance  # 只看指定子目录

退出码:
    0: 全部通过
    1: 有 type drift
    2: 有 requiredProperties 缺失
    3: 有 state machine 非法
    4: 多种问题混合
"""
import argparse
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
    args = parser.parse_args()

    focus_dirs = None
    if args.focus:
        focus_dirs = set(args.focus.split(","))

    schemas = load_m2_schemas()
    type_aliases = get_m2_type_aliases(schemas)
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
        print("\n=== omo_layer + governance 详细 ===")
        for sub in ["omo_layer", "governance"]:
            if focus_dirs and sub not in focus_dirs:
                continue
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
                    print(f"  {nid:40} {str(t):20} {str(s):12} {flag}")
                else:
                    print(f"  {nid:40} {str(t):20} -- TYPE NOT IN M2 --")

    # 退出码
    if args.strict:
        if drift or missing_req or invalid_sm:
            code = 1
            if missing_req:
                code |= 2
            if invalid_sm:
                code |= 3
            sys.exit(min(code, 4))


if __name__ == "__main__":
    main()
