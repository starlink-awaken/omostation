#!/usr/bin/env python3
"""
织星 MOF — M1 校验器 (mof-validate)
=====================================
读取 M2 元模型定义 + M1 节点声明，校验 M1 节点是否满足 M2 的结构约束。

路径策略 (自动检测):
  1. 优先使用 --m2 / --nodes 参数
  2. 检测 Workspace 环境 → 使用 ecos/ssot/mof/ 路径
  3. 降级到 Documents 路径 (向后兼容)

用法:
    python3 mof-validate.py                     # 自动检测路径
    python3 mof-validate.py --m2 M2.yaml --nodes nodes/  # 显式指定
    python3 mof-validate.py --json              # JSON 输出
    python3 mof-validate.py --type Protocol     # 仅校验指定类型
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from datetime import datetime, timezone


def detect_paths() -> tuple[Path, Path]:
    """自动检测 M2 目录和 M1 节点目录 (新结构: mof/m2/ + mof/m1/)"""
    ws = Path.home() / "Workspace"
    ssot = ws / "projects" / "ecos" / "src" / "ecos" / "ssot"
    ws_m2_dir = ssot / "mof" / "m2"
    ws_m1_dir = ssot / "mof" / "m1"
    
    # New structure
    if ws_m2_dir.exists() and list(ws_m2_dir.glob("*.yaml")):
        return ws_m2_dir, ws_m1_dir
    
    # Old structure (single M2 file + flat nodes/)
    ws_m2_file = ssot / "mof" / "M2-元模型.yaml"
    ws_nodes = ssot / "mof" / "nodes"
    if ws_m2_file.exists():
        return ws_m2_file, ws_nodes
    
    # Fall back
    docs = Path.home() / "Documents"
    return (docs / "驾驶舱" / "元模型" / "M2-元模型.yaml",
            docs / "驾驶舱" / "元模型" / "nodes")


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f)


def load_m2(m2_path: Path) -> dict:
    """加载 M2 — 支持新结构(目录)和旧结构(单文件)"""
    m2 = {}
    if m2_path.is_dir():
        # New structure: mof/m2/*.yaml (one per type)
        for f in sorted(m2_path.glob("*.yaml")):
            if f.name.startswith('.'): continue
            data = load_yaml(f)
            for key in data:
                if key not in ('m2_type', 'version', 'created'):
                    m2[key] = data[key]
    else:
        # Old structure: single M2-元模型.yaml
        data = load_yaml(m2_path)
        m2 = data.get("m2", data)
    return m2


def load_all_m1_nodes(m1_dir: Path) -> list[dict]:
    """加载所有 M1 节点 — 支持新结构(按类型分目录)和旧结构(平铺)"""
    nodes = []
    if not m1_dir.exists():
        return nodes
    for f in sorted(m1_dir.rglob("*.yaml")):
        if f.name.startswith('.'): continue
        try:
            data = load_yaml(f)
            if isinstance(data, dict) and "id" in data:
                nodes.append(data)
        except Exception:
            pass
    return nodes


def validate_node(node: dict, m2: dict) -> list[dict]:
    results = []
    ntype = node.get("type", "")
    nid = node.get("id", "?")

    m2_type = m2.get(ntype)
    if not m2_type:
        results.append({"id": nid, "passed": False, "level": "error",
                        "rule": "type_exists", "message": f"未知类型: {ntype} (M2 中未定义)"})
        return results

    # 1. Required properties
    required = m2_type.get("requiredProperties", {})
    props = node.get("properties", {}) or {}
    for prop_name, prop_def in required.items():
        val = node.get(prop_name) or props.get(prop_name)
        if val is None or val == "":
            results.append({"id": nid, "passed": False, "level": "error",
                           "rule": f"required.{prop_name}",
                           "message": f"缺少必填属性: {prop_name}"})

    # 2. State machine compliance
    sm = m2_type.get("stateMachine", {})
    status = node.get("status", "")
    if sm and status and status not in sm:
        results.append({"id": nid, "passed": False, "level": "error",
                       "rule": "stateMachine",
                       "message": f"无效状态: '{status}' (允许: {list(sm.keys())})"})

    # 3. Overall
    errors = [r for r in results if r["level"] == "error"]
    if not errors:
        results.append({"id": nid, "passed": True, "level": "info",
                       "rule": "overall", "message": f"✅ {ntype} {nid}"})

    return results


def format_report(all_results: list[dict], node_count: int, m2_file: Path) -> str:
    now = datetime.now(timezone.utc)
    lines = []
    lines.append("=" * 64)
    lines.append("  织星 MOF — M1 校验报告")
    lines.append("=" * 64)
    lines.append(f"  时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  M2: {m2_file}")

    passed = sum(1 for r in all_results if r.get("passed"))
    errors = sum(1 for r in all_results if r.get("level") == "error")
    lines.append(f"  节点: {node_count} | 通过: {passed} | 错误: {errors}")
    lines.append("")

    # By type
    type_counts = {}
    for r in all_results:
        t = r["id"].split("-")[0] if "-" in r["id"] else "?"
        type_counts.setdefault(t, {"ok": 0, "err": 0})
        if r.get("passed"):
            type_counts[t]["ok"] += 1
        elif r.get("level") == "error":
            type_counts[t]["err"] += 1

    for t, counts in sorted(type_counts.items()):
        icon = "✅" if counts["err"] == 0 else "⚠️"
        lines.append(f"  {icon} {t:15s}: {counts['ok']}/{counts['ok']+counts['err']}")

    if errors > 0:
        lines.append(f"\n  ── 错误 ──")
        for r in all_results:
            if r.get("level") == "error":
                lines.append(f"  ❌ {r['id']}: {r['message']}")

    lines.append(f"\n{'='*64}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="织星 MOF M1↔M2 校验器")
    parser.add_argument("--m2", type=Path, help="M2 元模型 YAML 路径")
    parser.add_argument("--nodes", type=Path, help="M1 节点目录")
    parser.add_argument("--type", type=str, help="仅校验指定类型")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Determine paths
    if args.m2 and args.nodes:
        m2_file = args.m2
        nodes_dir = args.nodes
    else:
        m2_file, nodes_dir = detect_paths()

    if not m2_file.exists():
        print(f"❌ M2 文件不存在: {m2_file}")
        sys.exit(2)

    try:
        m2 = load_m2(m2_file)
    except Exception as e:
        print(f"⚠️ M2 加载失败 ({m2_file}): {e}", file=sys.stderr)
        if not args.json:
            sys.exit(2)
        print(json.dumps({"error": f"M2 加载失败: {e}"}))
        sys.exit(2)
    nodes = load_all_m1_nodes(nodes_dir)

    if args.type:
        nodes = [n for n in nodes if n.get("type") == args.type]

    all_results = []
    for node in nodes:
        all_results.extend(validate_node(node, m2))

    if args.json:
        print(json.dumps({"node_count": len(nodes), "results": all_results},
                        ensure_ascii=False, indent=2))
    else:
        print(format_report(all_results, len(nodes), m2_file))


if __name__ == "__main__":
    main()
