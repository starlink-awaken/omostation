#!/usr/bin/env python3
# Status: implemented (ADR-0238 P0-2)
"""check-mof-capabilities-drift — MOF 能力注册表 vs 实现 drift 检测.

治 "守门人无人守" (plan §Q1): mof-capabilities.yaml 声明的工具路径/统计与
实际文件/计数对齐. 三类漂移:
  1. tool path 不存在 (声明指向幽灵路径 — bin/mof/* 迁移后最易复发)
  2. model_stats 计数 vs 实际文件数 (m1/m2 节点漂移)
  3. MCPTOOL-MODEL-DRIVEN tool_count vs mcp_server.py _register_tool 实际数 (P0-4 守护)

rule_id: CR-X4-MOF-CAPABILITIES-DRIFT

用法:
    python3 bin/mof/check-mof-capabilities-drift.py        # 全量扫
    python3 bin/mof/check-mof-capabilities-drift.py --json  # JSON 输出
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


# ─── 漂移检测函数 (纯函数, 接受参数便于注入测试) ───


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


def check_model_stats(
    stats: dict, actual_m1: int, actual_m2: int
) -> list[dict]:
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


def detect_drift() -> dict:
    registry = load_registry()
    path_findings = check_tool_paths(registry.get("tools", {}))
    stat_findings = check_model_stats(
        registry.get("model_stats", {}),
        actual_m1=count_yaml(M1_DIR),
        actual_m2=count_yaml(M2_DIR),
    )
    mcp_findings: list[dict] = []
    if MCPTOOL_MODEL_DRIVEN.exists() and MCP_SERVER.exists():
        data = (
            yaml.safe_load(MCPTOOL_MODEL_DRIVEN.read_text(encoding="utf-8")) or {}
        )
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MOF 能力注册表 drift 检测 (ADR-0238 P0-2)"
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    result = detect_drift()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== MOF 能力注册表 drift 检测 ({RULE_ID}) ===\n")
        if not result["findings"]:
            print("✅ 无漂移 — 注册面与实现对齐")
        else:
            for f in result["findings"]:
                print(f"🔴 {f['check']}: {f}")
        print(f"\nTotal: {result['total_drifts']} drifts")
    return 1 if result["total_drifts"] else 0


if __name__ == "__main__":
    sys.exit(main())
