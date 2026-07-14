#!/usr/bin/env python3
"""GaC 治理即代码 — 规则注册表校验器 (ADR-0106, 阶段 2 核心引擎).

动态一致性机制 2 (schema 校验) + 机制 5 (矛盾检测) + 唯一性 + lifecycle:

  - 每条规则必填字段校验 (id/dimension/layer/check_type/executor/lifecycle/version)
  - enum 值校验 (dimension X1-X4 / layer M0-L3-meta / lifecycle draft-active-deprecated-removed)
  - executor 非空 list (至少一个执行通道, 防规则声明了不执行)
  - 唯一 id 校验 (防重复)
  - 规则间矛盾检测 (同 target + 同 dimension 多规则告警)
  - lifecycle 分布统计 (draft 太多 = 未激活告警)

用法:
  python3 bin/gac/gac-validate.py              # 校验, exit 0=pass, 1=有错
  python3 bin/gac/gac-validate.py --gate       # CI gate 模式 (warning 也 fail)
  python3 bin/gac/gac-validate.py --report     # 详细报告

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace (无硬编码).
对标: bin/gac/evidence-smoke.py (BOS 声明/执行 gate). 同 bin/+--gate 模式.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

# CI 可移植: __file__ 定位 workspace (CLAUDE.md 硬编码清规则)
WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"

# GaC schema (机制 2; 和 governance-checks.yaml::gac.schema 对齐)
REQUIRED_FIELDS = [
    "id",
    "dimension",
    "layer",
    "check_type",
    "executor",
    "lifecycle",
    "version",
    "created_at",
]
DIMENSION_ENUM = {"X1", "X2", "X3", "X4"}
LAYER_ENUM = {"M0", "L0", "L1", "L2", "L3", "L4", "I0", "X", "meta"}
LIFECYCLE_ENUM = {"draft", "active", "deprecated", "removed"}


def load_gac_rules(path: Path) -> list[dict]:
    """加载 governance-checks.yaml::gac.rules.

    .omo 数据文件是多文档 (P45 frontmatter + 正文), safe_load_all 取正文 (最后非 None 文档).
    同 c2g strip_frontmatter 模式.
    """
    import yaml

    docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    main = docs[-1]  # 正文 (docs[0] = frontmatter)
    return main.get("gac", {}).get("rules", [])


def validate_rule(rule: dict, idx: int) -> list[str]:
    """校验单条规则 (schema + enum). 返回 errors 列表."""
    errors: list[str] = []
    rid = rule.get("id", f"<rule#{idx}>")

    # 必填字段
    for f in REQUIRED_FIELDS:
        val = rule.get(f)
        if val is None or val == "" or val == []:
            errors.append(f"{rid}: 缺必填字段 '{f}'")

    if errors:
        return errors  # 缺字段后续 enum 校验无意义

    # enum 校验
    if rule["dimension"] not in DIMENSION_ENUM:
        errors.append(
            f"{rid}: dimension '{rule['dimension']}' 不在 {sorted(DIMENSION_ENUM)}"
        )
    if rule["layer"] not in LAYER_ENUM:
        errors.append(f"{rid}: layer '{rule['layer']}' 不在 {sorted(LAYER_ENUM)}")
    if rule["lifecycle"] not in LIFECYCLE_ENUM:
        errors.append(
            f"{rid}: lifecycle '{rule['lifecycle']}' 不在 {sorted(LIFECYCLE_ENUM)}"
        )

    # source_type 校验 (收敛: native=GaC SSOT, indexed=原真策略 SSOT, GaC 执行索引)
    source_type = rule.get("source_type", "native")  # 默认 native (向后兼容已有 13 条)
    if source_type not in {"native", "indexed"}:
        errors.append(f"{rid}: source_type '{source_type}' 不在 [native, indexed]")
    # indexed 必填 source_ref (指向原真策略文件, SSOT 收敛核心)
    if source_type == "indexed" and not rule.get("source_ref"):
        errors.append(f"{rid}: source_type=indexed 必填 source_ref (指向原真策略文件)")

    # executor 必须非空 list (机制 3 前提: 规则至少一个执行通道)
    if not isinstance(rule["executor"], list) or not rule["executor"]:
        errors.append(f"{rid}: executor 必须非空 list (至少一个执行通道, 防声明不执行)")

    return errors


def detect_conflicts(rules: list[dict]) -> list[str]:
    """矛盾检测 (机制 5 深化): 多维冲突 + relates_to 豁免.

    多维: 同 target + 同 dimension + 同 check_type = 可能重复执行.
    豁免: 有 relates_to 的规则 (indexed→native 已识别重叠) 不算冲突.
    返回 warnings (非 error, 需人工确认是否真矛盾).
    """
    warnings: list[str] = []
    groups: dict[tuple, list[dict]] = {}
    for r in rules:
        # 多维 key: target + dimension + check_type
        key = (r.get("target", ""), r.get("dimension", ""), r.get("check_type", ""))
        groups.setdefault(key, []).append(r)

    for (target, dim, ct), group in groups.items():
        if len(group) <= 1 or not target:
            continue
        # relates_to 豁免: 已识别的 indexed→native 重叠不算冲突
        unrelated = [r for r in group if "relates_to" not in r]
        if len(unrelated) > 1:
            ids = [r["id"] for r in unrelated]
            warnings.append(
                f"潜在矛盾: {dim}/{ct} @ {target} 有 {len(unrelated)} 条无 relates_to {ids} (人工确认)"
            )

    return warnings


def check_lifecycle_timeliness(rules: list[dict], draft_days: int = 7) -> list[str]:
    """机制 6: draft 规则超期告警 (draft 超 draft_days 未转 active).

    时间追踪需 created_at (机制 6 完整状态机). draft 超 7 天告警
    (gac.lifecycle.draft_to_active_days). 当前全 active 不触发, 未来加 draft 规则生效.
    """
    import datetime

    warnings: list[str] = []
    today = datetime.date.today()
    for r in rules:
        if r.get("lifecycle") != "draft":
            continue
        created = r.get("created_at")
        if not created:
            continue
        try:
            cd = datetime.date.fromisoformat(created)
        except (ValueError, TypeError):
            continue
        age = (today - cd).days
        if age > draft_days:
            warnings.append(
                f"{r['id']}: draft 超 {age} 天 (>{draft_days} 天 draft_to_active), 待 radar 验证激活"
            )
    return warnings


def validate(path: Path = REGISTRY) -> tuple[int, list[str], list[str]]:
    """主校验. 返回 (exit_code, errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return (1, [f"注册表不存在: {path}"], [])

    rules = load_gac_rules(path)
    if not rules:
        return (1, ["gac.rules 为空或不存在 (GaC 未激活)"], [])

    # 机制 2: schema 校验
    for i, rule in enumerate(rules):
        errors.extend(validate_rule(rule, i))

    # 唯一 id 校验 (防重复注册)
    ids = [r.get("id") for r in rules if "id" in r]
    dupes = [k for k, v in Counter(ids).items() if v > 1]
    for d in dupes:
        errors.append(f"重复 id: {d} (规则 id 必须唯一)")

    # 机制 5: 矛盾检测
    warnings.extend(detect_conflicts(rules))

    # 机制 6: draft 超期检查 (时间追踪, 需 created_at)
    warnings.extend(check_lifecycle_timeliness(rules))

    return (1 if errors else 0, errors, warnings)


def main() -> int:
    args = sys.argv[1:]
    gate_mode = "--gate" in args
    report_mode = "--report" in args
    json_mode = "--json" in args

    exit_code, errors, warnings = validate()

    rules = load_gac_rules(REGISTRY) if REGISTRY.exists() else []
    lc = Counter(r.get("lifecycle", "?") for r in rules)
    dims = Counter(r.get("dimension", "?") for r in rules)
    layers = Counter(r.get("layer", "?") for r in rules)

    # JSON 模式 (阶段 4 仪表盘/cron 数据源): 输出 JSON, 跳过人读 print
    if json_mode:
        import json

        print(
            json.dumps(
                {
                    "rules": len(rules),
                    "lifecycle": dict(lc),
                    "dimension": dict(dims),
                    "layer": dict(layers),
                    "errors": errors,
                    "warnings": warnings,
                    "ok": not errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if (gate_mode and (errors or warnings)) else exit_code

    rel_path = REGISTRY.relative_to(WORKSPACE) if REGISTRY.exists() else REGISTRY
    print(f"=== GaC 校验 ({rel_path}) ===")
    print(f"规则数: {len(rules)}")

    # lifecycle 分布 (机制 6 健康告警: draft 待 radar 激活, deprecated 待 gc 清理)
    print(f"lifecycle 分布: {dict(lc)}")
    if lc.get("draft", 0) > 0:
        print(f"⚠️  {lc['draft']} 条 draft 规则待 radar 验证激活 (机制 6: draft→active)")
    if lc.get("deprecated", 0) > 0:
        print(
            f"⚠️  {lc['deprecated']} 条 deprecated 规则待 gc 清理 (机制 6: deprecated→removed)"
        )

    print(f"dimension 覆盖: {dict(dims)}")
    print(f"layer 覆盖: {dict(layers)}")

    if errors:
        print(f"\n❌ {len(errors)} 错误:")
        for e in errors:
            print(f"  - {e}")

    if warnings:
        print(f"\n⚠️  {len(warnings)} 警告 (矛盾检测, 需人工确认):")
        for w in warnings:
            print(f"  - {w}")

    if report_mode and rules:
        print("\n规则详情:")
        for r in rules:
            print(
                f"  - {r['id']} [{r['dimension']}/{r['layer']}] "
                f"{r['check_type']} → {r['executor']} ({r['lifecycle']}, v{r['version']})"
            )

    if not errors and not warnings:
        print("✅ GaC 校验通过 (0 error, 0 warning)")

    # gate 模式: warning 也 fail (严格, CI 用)
    if gate_mode and (errors or warnings):
        return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
