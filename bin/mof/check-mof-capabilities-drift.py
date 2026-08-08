#!/usr/bin/env python3
# Status: implemented (ADR-0238 P0-2; §J1 metaos 面扩展, workorder 2026-07-25)
# 定位 (P0-A 核实 2026-07-28): BLOCKING — exit 1 on any drift (见 main L312). 全 registry 覆盖
#   (MOF 面: tool path / model_stats / mcptool_tool_count + metaos 面: projects-cap 死条目 /
#    INTERFACE cli 可达 / submodule 存在). 非 informational: drift=0 exit 0; 新增死条目或 path
#   漂移立即 fail. 当前 drift=0 (P0-C 清 44 dead 后).
"""check-mof-capabilities-drift — 注册表 vs 实现 drift 检测 (一扇门覆盖 MOF + metaos).

治 "守门人无人守" (plan §Q1): 注册表声明的路径/统计与实际文件/计数对齐.

两面 (§J1 扩展承接 ADR-0238, 严禁新建第二套门禁框架):
  MOF 面 (CR-X4-MOF-CAPABILITIES-DRIFT, ADR-0238 P0-2):
    1. mof-capabilities.yaml tool path 不存在 (bin/mof/* 迁移后最易复发)
    2. model_stats 计数 vs 实际文件数 (m1/m2 节点漂移)
    3. MCPTOOL-MODEL-DRIVEN tool_count vs mcp_server.py _register_tool 实际数
  metaos 面 (CR-X4-METAOS-REGISTRY-DRIFT, §J1):
    4. projects-capabilities.yaml capability entrypoint 存在性 (死条目)
    5. metaos INTERFACE.yaml cli module (metaos.cli:main) 可达性
    6. metaos submodule 目录存在性

用法:
    python3 bin/mof/check-mof-capabilities-drift.py             # 默认全量 (两面)
    python3 bin/mof/check-mof-capabilities-drift.py --scope mof # 仅 MOF (ADR-0238)
    python3 bin/mof/check-mof-capabilities-drift.py --scope metaos
    python3 bin/mof/check-mof-capabilities-drift.py --json      # JSON 输出
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / ".omo/_truth/registry/mof-capabilities.yaml"
M1_DIR = REPO / "projects/ecos/src/ecos/ssot/mof/m1"
M2_DIR = REPO / "projects/ecos/src/ecos/ssot/mof/m2"
MCPTOOL_MODEL_DRIVEN = (
    REPO / "projects/ecos/src/ecos/ssot/mof/m1/mcptool/MCPTOOL-MODEL-DRIVEN.yaml"
)
MCP_SERVER = REPO / "projects/model-driven/src/model_driven/mcp_server.py"

RULE_ID = "CR-X4-MOF-CAPABILITIES-DRIFT"

# ─── metaos registry 漂移面 (§J1 扩展, workorder 2026-07-25) ───
# 同一扇门扩展覆盖 metaos 相关 registry, 不新建第二套门禁框架 (承接 ADR-0238).
PROJECTS_CAPABILITIES = REPO / ".omo/_truth/registry/projects-capabilities.yaml"
METAOS_INTERFACE = REPO / "projects/metaos/INTERFACE.yaml"
METAOS_SUBMODULE_DIR = REPO / "projects/metaos"
METAOS_RULE_ID = "CR-X4-METAOS-REGISTRY-DRIFT"
# phase-scope 路径暂不纳入: phase3 预留阶段路径未建是预期, 报为漂移会误报
# (待 phase verdict 语义成熟后扩展). submodule 分支名: .gitmodules 无 branch 声明,
# 无可比基准, 改查 submodule 目录存在性.


def load_registry(path: Path = REGISTRY) -> dict:
    if not path.exists():
        return {}
    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    return next((d for d in reversed(docs) if d is not None), {})


def count_yaml(root: Path) -> int:
    """递归统计 root 下 *.yaml 数 (m1/m2 节点以实际文件为准, ecos CLAUDE.md)."""
    if not root.exists():
        return 0
    return sum(1 for _ in root.rglob("*.yaml"))


# ─── MOF 漂移检测函数 (纯函数, 接受参数便于注入测试, ADR-0238) ───


def check_tool_paths(tools: dict, repo: Path = REPO) -> list[dict]:
    """每个工具 path 必须存在 (相对 repo). 返回 path 漂移项."""
    findings: list[dict] = []
    for tool_id, tool in (tools or {}).items():
        raw = tool.get("path", "") if isinstance(tool, dict) else ""
        if not raw:
            continue
        if not (repo / raw).exists():
            findings.append(
                {
                    "check": "tool_path_exists",
                    "tool": tool_id,
                    "declared_path": raw,
                    "actual": "MISSING",
                }
            )
    return findings


def check_model_stats(stats: dict, actual_m1: int, actual_m2: int) -> list[dict]:
    """model_stats.{m1_nodes,m2_schemas} vs 实际文件数. 返回 stat 漂移项."""
    findings: list[dict] = []
    checks = [
        ("m1_nodes", actual_m1, M1_DIR),
        ("m2_schemas", actual_m2, M2_DIR),
    ]
    for key, actual, src in checks:
        declared = (stats or {}).get(key)
        if declared is None:
            continue
        if declared != actual:
            findings.append(
                {
                    "check": "model_stat_drift",
                    "stat": key,
                    "declared": declared,
                    "actual": actual,
                    "source": str(src.relative_to(REPO)),
                }
            )
    return findings


def check_mcptool_tool_count(declared: int | None, mcp_code: str) -> list[dict]:
    """MCPTOOL-MODEL-DRIVEN tool_count vs mcp_server _register_tool 数 (P0-4)."""
    findings: list[dict] = []
    if declared is None:
        return findings
    actual = len(re.findall(r"self\._register_tool\(", mcp_code))
    if declared != actual:
        findings.append(
            {
                "check": "mcptool_tool_count_drift",
                "node": "MCPTOOL-MODEL-DRIVEN",
                "declared": declared,
                "actual": actual,
                "source": "mcp_server.py _register_tool",
            }
        )
    return findings


# ─── metaos registry 检查函数 (纯函数, 接受参数便于注入测试, §J1) ───


def check_projects_capabilities_entrypoints(
    capabilities: list, repo: Path = REPO
) -> list[dict]:
    """projects-capabilities.yaml 每个 capability entrypoint 必须存在 (死条目检出).

    治 metaos 拆迁遗留等: entrypoint 指向已删目录 (kairon.metaos →
    projects/kairon/packages/metaos, metaos 2026-06-06 拆到 projects/metaos).
    通用扫所有 capability, 非仅 metaos — 一扇门覆盖整个 registry.
    """
    findings: list[dict] = []
    for cap in capabilities or []:
        if not isinstance(cap, dict):
            continue
        raw = cap.get("entrypoint", "")
        if not raw:
            continue
        if not (repo / raw).exists():
            findings.append(
                {
                    "check": "capability_entrypoint_missing",
                    "capability": cap.get("id", "?"),
                    "declared_entrypoint": raw,
                    "actual": "MISSING",
                }
            )
    return findings


def check_metaos_cli_entrypoint(
    interface_path: Path = METAOS_INTERFACE, repo: Path = REPO
) -> list[dict]:
    """metaos INTERFACE.yaml cli module (metaos.cli:main) 可达性.

    module 形如 'metaos.cli:main' → src/metaos/cli/__init__.py:main.
    INTERFACE.yaml 声明的入口必须真能解析到文件, 否则声明/执行鸿沟.
    """
    findings: list[dict] = []
    if not interface_path.exists():
        return findings
    data = yaml.safe_load(interface_path.read_text(encoding="utf-8")) or {}
    cli_list = data.get("cli") if isinstance(data, dict) else None
    cli_spec = cli_list[0] if isinstance(cli_list, list) and cli_list else {}
    module = cli_spec.get("module", "") if isinstance(cli_spec, dict) else ""
    if ":" not in module:
        return findings
    mod_path = module.split(":", 1)[0]
    pkg_rel = mod_path.replace(".", "/")
    candidates = [
        repo / "projects/metaos/src" / f"{pkg_rel}.py",
        repo / "projects/metaos/src" / pkg_rel / "__init__.py",
    ]
    if not any(c.exists() for c in candidates):
        findings.append(
            {
                "check": "metaos_cli_entrypoint_unreachable",
                "declared_module": module,
                "actual": "MISSING",
            }
        )
    return findings


def check_metaos_submodule_present(
    submodule_dir: Path = METAOS_SUBMODULE_DIR,
) -> list[dict]:
    """metaos submodule 目录存在性 (.gitmodules 无 branch 声明, 改查目录可达)."""
    if not submodule_dir.exists():
        try:
            rel = str(submodule_dir.relative_to(REPO))
        except ValueError:
            rel = str(submodule_dir)
        return [
            {
                "check": "metaos_submodule_missing",
                "declared_path": rel,
                "actual": "MISSING",
            }
        ]
    return []


def detect_drift() -> dict:
    """MOF 面 drift (ADR-0238, 向后兼容 — 现有测试断言此函数 0 drift)."""
    registry = load_registry()
    path_findings = check_tool_paths(registry.get("tools", {}))
    stat_findings = check_model_stats(
        registry.get("model_stats", {}),
        actual_m1=count_yaml(M1_DIR),
        actual_m2=count_yaml(M2_DIR),
    )
    mcp_findings: list[dict] = []
    if MCPTOOL_MODEL_DRIVEN.exists() and MCP_SERVER.exists():
        data = yaml.safe_load(MCPTOOL_MODEL_DRIVEN.read_text(encoding="utf-8")) or {}
        mcp_findings = check_mcptool_tool_count(
            data.get("tool_count"), MCP_SERVER.read_text(encoding="utf-8")
        )
    all_findings = path_findings + stat_findings + mcp_findings
    return {
        "rule_id": RULE_ID,
        "registry": str(REGISTRY.relative_to(REPO)),
        "total_drifts": len(all_findings),
        "findings": all_findings,
    }


def detect_metaos_registry_drift() -> dict:
    """metaos 面 drift (§J1): projects-capabilities 死条目 + INTERFACE 可达性."""
    capabilities: list = []
    if PROJECTS_CAPABILITIES.exists():
        data = load_registry(PROJECTS_CAPABILITIES)
        capabilities = data.get("capabilities", []) or []
    cap_findings = check_projects_capabilities_entrypoints(capabilities)
    entry_findings = check_metaos_cli_entrypoint(METAOS_INTERFACE)
    sub_findings = check_metaos_submodule_present(METAOS_SUBMODULE_DIR)
    all_findings = cap_findings + entry_findings + sub_findings
    registries = [
        str(PROJECTS_CAPABILITIES.relative_to(REPO)),
        str(METAOS_INTERFACE.relative_to(REPO)),
    ]
    return {
        "rule_id": METAOS_RULE_ID,
        "registries": registries,
        "total_drifts": len(all_findings),
        "findings": all_findings,
    }


def detect_all_drift() -> dict:
    """聚合 MOF + metaos 两面 drift — 同一扇门 (§J1 验收: 一扇门覆盖)."""
    mof = detect_drift()
    metaos = detect_metaos_registry_drift()
    all_findings = mof["findings"] + metaos["findings"]
    return {
        "rule_id": "CR-X4-REGISTRY-DRIFT-AGGREGATE",
        "scopes": ["mof", "metaos"],
        "total_drifts": len(all_findings),
        "findings": all_findings,
    }


def _bump_model_stats() -> bool:
    """ADR-0374 G2: auto-bump m1_nodes / m2_schemas declared count to actual.

    Writes the new value back to .omo/_truth/registry/mof-capabilities.yaml
    (only if a delta exists) so the next drift run is clean. Returns
    True if a bump happened, False if the file was already in sync.
    """
    import datetime as _dt
    import yaml as _yaml

    if not REGISTRY.exists():
        return False
    text = REGISTRY.read_text(encoding="utf-8")
    docs = list(_yaml.safe_load_all(text))
    if not docs:
        return False
    data = docs[-1]
    stats = data.get("model_stats") or {}
    actual_m1 = count_yaml(M1_DIR)
    actual_m2 = count_yaml(M2_DIR)
    expected = {
        "m1_nodes": actual_m1,
        "m2_schemas": actual_m2,
    }
    bumps: dict[str, tuple[int, int]] = {}
    for key, new_val in expected.items():
        old_val = stats.get(key)
        if old_val is not None and old_val != new_val:
            bumps[key] = (int(old_val), new_val)
    if not bumps:
        return False
    for key, (old, new) in bumps.items():
        pattern = re.compile(rf"^(\s*){re.escape(key)}:\s*{re.escape(str(old))}\s*$", re.M)
        text, n = pattern.subn(rf"\1{key}: {new}", text, count=1)
        if n == 0:
            print(
                f"::warning::bump-stats: could not find {key}: {old} line in "
                f"{REGISTRY.relative_to(REPO)}",
                file=sys.stderr,
            )
    today = _dt.datetime.now(tz=_dt.timezone.utc).date().isoformat()
    text = re.sub(
        r"^(\s*)stats_as_of:\s*\"[^\"]*\"\s*$",
        rf'\1stats_as_of: "{today}"',
        text,
        count=1,
        flags=re.M,
    )
    REGISTRY.write_text(text, encoding="utf-8")
    for key, (old, new) in bumps.items():
        print(f"::notice::bumped {key}: {old} → {new} in mof-capabilities.yaml")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="注册表 drift 检测 (MOF ADR-0238 + metaos §J1 扩展)"
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument(
        "--scope",
        choices=["mof", "metaos", "all"],
        default="all",
        help="检测面: mof (ADR-0238) / metaos (§J1) / all (默认, 聚合两面)",
    )
    parser.add_argument(
        "--bump-stats",
        action="store_true",
        help=(
            "ADR-0374 G2: auto-update m1_nodes / m2_schemas declared count "
            "in mof-capabilities.yaml to match actual, then re-run drift check"
        ),
    )
    args = parser.parse_args()

    if args.scope == "mof":
        result = detect_drift()
    elif args.scope == "metaos":
        result = detect_metaos_registry_drift()
    else:
        result = detect_all_drift()

    # ADR-0374 G2: --bump-stats auto-fixes model_stats declared→actual when drift
    # is purely a count mismatch (the most common concurrent-work artifact).
    if args.bump_stats:
        try:
            bumped = _bump_model_stats()
        except Exception as exc:  # noqa: BLE001 — keep drift path robust
            print(f"::warning::bump-stats failed: {exc}", file=sys.stderr)
            bumped = False
        if bumped:
            # Re-run after bump so the user sees the post-fix state.
            if args.scope == "mof":
                result = detect_drift()
            elif args.scope == "metaos":
                result = detect_metaos_registry_drift()
            else:
                result = detect_all_drift()

    scope_label = {
        "mof": RULE_ID,
        "metaos": METAOS_RULE_ID,
        "all": "CR-X4-REGISTRY-DRIFT-AGGREGATE",
    }[args.scope]
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== 注册表 drift 检测 ({scope_label}) ===\n")
        if not result["findings"]:
            print("✅ 无漂移 — 注册面与实现对齐")
        else:
            for f in result["findings"]:
                print(f"🔴 {f['check']}: {f}")
        print(f"\nTotal: {result['total_drifts']} drifts")
    return 1 if result["total_drifts"] else 0


if __name__ == "__main__":
    sys.exit(main())
