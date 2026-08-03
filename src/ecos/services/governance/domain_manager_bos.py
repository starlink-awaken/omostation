"""ecos.services.governance.domain_manager_bos — cmd_bos_validate 拆分 (P110).

P110 关联: TASK-F7114ABA (omo lint god-module 800L 硬规则).
domain_manager.py 1406L 拆分: cmd_bos_validate (93L) 独立到本模块.

模式: 业务函数 import 在 cmd_bos_validate 内部惰性加载 (避免 domain_manager
顶层 re-export 时的循环 import). 单一真源仍是 domain_manager.
原模块的 cmds["bos-validate"] 指向本函数 (调用方不变).
"""

import yaml

# yaml 仅 _load_bos_constraints 用 (局部 import 即可)
# yaml 是 stdlib, 不会触发循环 import


def cmd_bos_validate(args):
    """全量BOS URI健康检查 + X4-C10~C13 约束评估"""
    # 业务函数 import (惰性, 避免 domain_manager 顶层 re-export 时的循环)
    from ecos.services.governance.domain_manager import (
        _evaluate_bos_constraints,  # type: ignore[reportAttributeAccessIssue]
        _load_bos_constraints,  # type: ignore[reportAttributeAccessIssue]
        _load_lifecycle,
        load_registry,
        resolve_path,
    )
    from ecos.services.governance.domain_manager_lifecycle import parse_bos_uri

    registry = load_registry()
    lifecycle = _load_lifecycle()
    constraints = _load_bos_constraints()

    print("\n  ═══ BOS URI 全量健康检查 + X4-C10~C13 约束评估 ═══\n")
    if constraints:
        print(
            f"  加载 {len(constraints)} 条 BOS 约束:",
            ", ".join(c["id"] for c in constraints),
        )
    else:
        print("  ⚠️  未找到 X4-C10~C13 约束定义\n")

    total_uris = 0
    total_ok = 0
    total_violations = 0
    all_violations = []  # (uri, severity, message, detail)

    for d in registry:
        did = d["id"]
        dtype = d.get("domain_type", "document")
        uri_base = f"bos://{did}"

        # URIs to check
        uris_to_check = [(uri_base, None)]
        if dtype == "document":
            for shortcut in ["_state", "_claude", "_memory"]:
                uris_to_check.append((f"bos://{did}/{shortcut}", shortcut))  # type: ignore[reportArgumentType]

        for uri, shortcut in uris_to_check:
            total_uris += 1
            domain_obj, subpath = parse_bos_uri(uri, registry)

            if not domain_obj:
                print(f"  ❌ {uri}")
                print(f"      无法解析: 域 '{did}' 未在注册表中找到")
                all_violations.append((uri, "critical", "E-L0-012", "域未注册"))
                total_violations += 1
                continue

            p = resolve_path(domain_obj)
            full = p / subpath if subpath else p
            path_exists = full.exists()

            # Evaluate X4 constraints
            violations = _evaluate_bos_constraints(uri, registry, lifecycle)

            if path_exists and not violations:
                total_ok += 1
                continue

            # Report issues
            icon = "⚠️" if violations else "❌"
            lc_icon = "📋" if uri in lifecycle.get("uris", {}) else "○"
            print(f"  {icon} {lc_icon} {uri}")

            if not path_exists:
                print(f"      ❌ X4-C12: 路径不存在 → {full}")
                all_violations.append(
                    (uri, "required", "E-L0-013", f"路径不存在: {full}")
                )
                total_violations += 1

            for v in violations:
                sv = v["severity"]
                icon_v = "❌" if sv == "required" else "⚠️"
                print(f"      {icon_v} {v['constraint']}: {v['detail']}")
                all_violations.append((uri, sv, v["constraint"], v["detail"]))
                total_violations += 1

    # Summary
    print("\n  ═══ 摘要 ═══")
    print(f"  URI 总数: {total_uris}")
    print(f"  通过: {total_ok}✅")
    print(f"  违规: {total_violations}❌/⚠️")

    if all_violations:
        print("\n  违规明细:")
        by_severity = {"required": 0, "preferred": 0, "critical": 0}
        for _, sv, cid, _ in all_violations:
            by_severity[sv] = by_severity.get(sv, 0) + 1
        print(f"    required: {by_severity.get('required', 0)} 条")
        print(f"    preferred: {by_severity.get('preferred', 0)} 条")

    # Lifecycle coverage
    lc_uris = len(lifecycle.get("uris", {}))
    print(f"\n  生命周期覆盖: {lc_uris}/{total_uris} URI")

    print()


# P110-C: _load_bos_constraints + _evaluate_bos_constraints 拆解 (cmd_bos_validate 的依赖)
def _load_bos_constraints() -> list[dict]:
    """从 L0-constraints.yaml 加载 X4-C10~C13 约束"""
    constraints = []
    # 惰性 import (避免循环)
    from .domain_manager import L0_CONSTRAINTS, L0_CONSTRAINTS_L4

    for src in [L0_CONSTRAINTS, L0_CONSTRAINTS_L4]:
        if not src.exists():
            continue
        try:
            with open(src) as f:
                data = yaml.safe_load(f)
            for c in data.get("constraints", []):
                cid = c.get("id", "")
                if cid.startswith("X4-C1"):
                    constraints.append(c)
            if constraints:
                break
        except Exception:  # defensive fallback
            continue
    return constraints


def _evaluate_bos_constraints(
    uri: str,
    registry: list,
    lifecycle: dict = None,  # type: ignore[reportArgumentType]
) -> list[dict]:
    # 惰性 import (避免 domain_manager 顶层 import 的循环)
    from .domain_manager import resolve_path
    from .domain_manager_lifecycle import (
        _load_lifecycle,
        parse_bos_uri,
    )

    """评估 X4-C10~C13 约束，返回 violations 列表"""
    violations = []
    constraints = _load_bos_constraints()
    if not constraints:
        return violations

    # Parse the URI
    domain_obj, subpath = parse_bos_uri(uri, registry)

    # Build evaluation context
    ctx = {
        "uri": uri,
        "format_valid": uri.startswith("bos://")
        and not uri.startswith("bos://l4/")
        and not uri.startswith("bos://l3/"),
        "resolvable": domain_obj is not None,
        "path_exists": False,
        "lifecycle_registered": False,
    }

    if domain_obj:
        base = resolve_path(domain_obj)
        full = base / subpath if subpath else base
        ctx["path_exists"] = full.exists()

    if lifecycle is None:
        lifecycle = _load_lifecycle()
    ctx["lifecycle_registered"] = uri in lifecycle.get("uris", {})

    # Evaluate each constraint
    for c in constraints:
        cid = c["id"]
        c.get("rule", "")
        severity = c.get("type", "required")  # required / preferred
        violation_msg = c.get("violation", f"违反 {cid}")

        # X4-C10: format
        if cid == "X4-C10" and not ctx["format_valid"]:
            violations.append(
                {
                    "constraint": cid,
                    "severity": severity,
                    "message": violation_msg,
                    "detail": f"URI 格式异常: {uri}",
                }
            )

        # X4-C11: resolvable
        if cid == "X4-C11" and not ctx["resolvable"]:
            violations.append(
                {
                    "constraint": cid,
                    "severity": severity,
                    "message": violation_msg,
                    "detail": f"不可解析: {uri}",
                }
            )

        # X4-C12: path exists
        if cid == "X4-C12" and domain_obj and not ctx["path_exists"]:
            violations.append(
                {
                    "constraint": cid,
                    "severity": severity,
                    "message": violation_msg,
                    "detail": f"路径不存在: {uri}",
                }
            )

        # X4-C13: lifecycle
        if cid == "X4-C13" and domain_obj and not ctx["lifecycle_registered"]:
            violations.append(
                {
                    "constraint": cid,
                    "severity": severity,
                    "message": violation_msg,
                    "detail": f"缺生命周期: {uri}",
                }
            )

    return violations
