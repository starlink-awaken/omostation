#!/usr/bin/env python3
"""GaC 治理即代码 — drift 检测器 (ADR-0106, 阶段 2/4, 机制 4).

动态一致性机制 4 (drift 检测): 注册表声明 vs 实际执行/状态.

静态 drift (本脚本, 文件系统 + 配置层面):
  - target 存在检查 (规则声明的 target 文件在不在)
  - executor 合法检查 (executor 字段引用的通道在 EXECUTOR_ENUM)
  - ssot_pointer drift (forbid_copy_in 扫描: SSOT 值是否被复制到禁止位置)
    ← 治 health 分三处不一致病根 (CR-ENG-SSOT-POINTER-01)

动态 drift (阶段 1 hook 绑定后补): hook/MCP/gate 实际注册了哪些规则.

用法:
  python3 bin/gac-drift.py              # drift 检测, exit 0=无 drift, 1=有 drift
  python3 bin/gac-drift.py --gate       # CI gate (drift 则 fail)
  python3 bin/gac-drift.py --report     # 详细

对标: gac-validate.py (规则结构) + evidence-smoke.py (BOS resolve drift).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"

# 已知执行通道 (和 governance-checks.yaml::gac.schema.executor_enum 对齐)
EXECUTOR_ENUM = {
    "hook_pre_edit",
    "hook_post",
    "ci_gate",
    "omo_audit",
    "mcp_tool",
    "mof_validate",
    "mof_audit",
    "evidence_smoke",
    "radar_cron",
    "gc_cron",
    "gac_local_gate",
}


def load_gac_rules(path: Path) -> list[dict]:
    """加载 governance-checks.yaml::gac.rules (多文档 strip frontmatter)."""
    import yaml

    docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    main = docs[-1]
    return main.get("gac", {}).get("rules", [])


def check_target_exists(rule: dict) -> list[str]:
    """target 文件存在检查 (静态 drift: 声明的 target 文件在不在)."""
    drifts: list[str] = []
    target = rule.get("target", "")
    if not target:
        return drifts
    # target 格式: "path::field" / "path" / "描述 (含空格括号)"
    path_part = target.split("::")[0].split(" (")[0]
    # 跳过描述性 target (含空格/括号 = 非文件路径)
    if " " in path_part or not path_part.startswith((".", "/", "projects")):
        return drifts
    # glob 模式 (含 * ? [) 不检查具体存在 (匹配多文件)
    if any(c in path_part for c in "*?["):
        return drifts
    fpath = WORKSPACE / path_part
    if not fpath.exists():
        drifts.append(f"{rule['id']}: target 文件不存在 {path_part}")
    return drifts


def check_executor_valid(rule: dict) -> list[str]:
    """executor 合法检查 (executor 字段引用的通道在 EXECUTOR_ENUM)."""
    drifts: list[str] = []
    for ex in rule.get("executor", []):
        if ex not in EXECUTOR_ENUM:
            drifts.append(
                f"{rule['id']}: executor '{ex}' 不在已知通道 {sorted(EXECUTOR_ENUM)}"
            )
    return drifts


# drift 扫描排除目录 (依赖/历史面/缓存; 这些 hardcode 合法, 非活文档)
EXCLUDE_DIRS = {
    ".venv",
    "node_modules",
    ".git",
    "__pycache__",
    ".mypy_cache",
    "_archive",
    "_knowledge",
    "_delivery",
    "_log",  # 历史面/交付面 (记录当时值合法)
}


def _is_excluded(fpath: Path) -> bool:
    """文件是否在排除目录 (依赖/历史面; hardcode 合法)."""
    try:
        parts = fpath.relative_to(WORKSPACE).parts
    except ValueError:
        return True
    return any(p in EXCLUDE_DIRS for p in parts)


def check_ssot_drift(rule: dict) -> list[str]:
    """ssot_pointer drift: forbid_copy_in 活文档是否复制了 target field 值.

    检测 SSOT 规则违反 (机制 4 核心): 规则声明值不复制, 但活文档硬编码了值.
    排除: 依赖 (.venv/node_modules) + 历史面 (_knowledge/_delivery, 记录当时值合法) + 指针引用.
    """
    drifts: list[str] = []
    if rule.get("check_type") != "ssot_pointer":
        return drifts
    target = rule.get("target", "")
    if "::" not in target:
        return drifts
    field = target.split("::", 1)[1]
    forbid = rule.get("forbid_copy_in", [])
    if not forbid:
        return drifts

    # 搜 field + 数字 (YAML key 冒号 only; 排除 Python = 赋值 / 字典 ["] / 属性 . — 多是代码示例假阳性).
    # (?<![\[\.]) lookbehind 排除字典/属性访问; : 只 YAML key (排除 = Python 赋值).
    pattern = re.compile(rf"(?<![\[\.]){re.escape(field)}\s*:\s*\d")

    for glob_pattern in forbid:
        for fpath in WORKSPACE.glob(glob_pattern):
            if not fpath.is_file() or _is_excluded(fpath):
                continue
            try:
                content = fpath.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in pattern.finditer(content):
                # 排除指针引用 (上下文含 _ref/见/see/指向/SSOT/system.yaml; +80 覆盖同行 SSOT 注释)
                start = max(0, match.start() - 40)
                ctx = content[start : match.end() + 80]
                if any(
                    kw in ctx
                    for kw in [
                        "_ref",
                        "见 ",
                        "see ",
                        "指向",
                        "指针",
                        "SSOT",
                        "system.yaml",
                    ]
                ):
                    continue  # 指针引用, 合法
                drifts.append(
                    f"{rule['id']}: SSOT drift — {fpath.relative_to(WORKSPACE)} 复制了 {field} 值 "
                    f"(违反 SSOT, 应改指针引用 system.yaml)"
                )
    return drifts


def check_indexed_drift(rule: dict) -> list[str]:
    """indexed 规则 drift: source_ref 指向的文件是否存在, 规则 ID 是否在源文件中找到.

    检测 GaC indexed 条目与 source_ref 真值文件之间的漂移.
    不比较字段值 (enforcement 等), 只验证:
    1. source_ref 文件存在
    2. 规则 ID 在源文件中能找到 (rule_id 字符串匹配)
    """
    drifts: list[str] = []
    source_type = rule.get("source_type", "native")
    if source_type != "indexed":
        return drifts

    source_ref = rule.get("source_ref", "")
    if not source_ref:
        drifts.append(f"{rule['id']}: indexed 规则缺少 source_ref")
        return drifts

    # 解析 source_ref: "path::field" 格式
    ref_parts = source_ref.split("::")
    ref_path_str = ref_parts[0]
    ref_path = WORKSPACE / ref_path_str

    if not ref_path.exists():
        drifts.append(f"{rule['id']}: source_ref 文件不存在 {ref_path_str}")
        return drifts

    # 检查规则 ID 是否在源文件中出现
    try:
        content = ref_path.read_text(encoding="utf-8")
    except OSError:
        return drifts

    rule_id = rule.get("id", "")
    if rule_id and rule_id not in content:
        drifts.append(
            f"{rule['id']}: 规则 ID 在 source_ref ({ref_path_str}) 中未找到 — 可能已重命名或删除"
        )

    return drifts


def main() -> int:
    args = sys.argv[1:]
    gate_mode = "--gate" in args
    report_mode = "--report" in args
    json_mode = "--json" in args

    if not REGISTRY.exists():
        print(f"❌ 注册表不存在: {REGISTRY}")
        return 1

    rules = load_gac_rules(REGISTRY)

    all_drifts: list[str] = []
    for rule in rules:
        all_drifts.extend(check_target_exists(rule))
        all_drifts.extend(check_executor_valid(rule))
        all_drifts.extend(check_ssot_drift(rule))
        all_drifts.extend(check_indexed_drift(rule))

    # JSON 模式 (阶段 4 仪表盘/cron 数据源): 输出 JSON, 跳过人读 print
    if json_mode:
        import json

        print(
            json.dumps(
                {
                    "rules": len(rules),
                    "drifts": all_drifts,
                    "drift_count": len(all_drifts),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if (gate_mode and all_drifts) else 0

    rel = REGISTRY.relative_to(WORKSPACE)
    print(f"=== GaC drift 检测 ({rel}) ===")
    print(f"规则数: {len(rules)}")

    if all_drifts:
        print(f"\n⚠️  发现 {len(all_drifts)} 处 drift:")
        for d in all_drifts:
            print(f"  - {d}")
    else:
        print("✅ GaC drift 检测通过 (0 drift)")

    if report_mode:
        print("\n规则 target/executor 明细:")
        for r in rules:
            tgt = r.get("target", "")[:60]
            print(f"  - {r['id']}: target={tgt} executor={r.get('executor')}")

    if gate_mode and all_drifts:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
