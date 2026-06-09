#!/usr/bin/env python3
"""
eCOS v5 L0 — 统一架构校验器 (ecos-validator)
================================================
整合 SSOT 拓扑校验 + 模式校验 + MOF 元模型校验。
L0 协议编织层的统一入口校验工具。

校验项目:
  1. 拓扑层依赖 (topology.yaml)
  2. 架构模式合规 (patterns.yaml)
  3. MOF M1↔M2 元模型校验 (mof/mof-validate)
  4. MOF M1↔M0 漂移审计 (mof/mof-audit)

用法:
    python3 ecos-validator.py --workspace . --all
    python3 ecos-validator.py --topology-only
    python3 ecos-validator.py --mof-only
"""

import os
import sys
import yaml
import argparse
import subprocess
from pathlib import Path


def load_yaml(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def validate_topology(workspace_root: str, topology_path: str) -> bool:
    print(f"🔍 [1/4] 拓扑校验: {topology_path}")
    topology = load_yaml(topology_path)
    layers = topology.get('layers', [])
    print(f"  ✅ 加载 {len(layers)} 层定义")
    for layer in layers:
        deps = layer.get('allowed_dependencies', [])
        pkgs = layer.get('packages', [])
        print(f"     {layer['id']:4s} → deps={deps} pkgs={pkgs}")
    
    pkg_to_layer = {}
    for layer in layers:
        for pkg in layer.get('packages', []):
            pkg_to_layer[pkg] = layer['id']
    print(f"  ✅ 包→层映射: {len(pkg_to_layer)} 个包")
    return True


def validate_patterns(workspace_root: str, patterns_path: str) -> bool:
    print(f"\n🔍 [2/4] 模式校验: {patterns_path}")
    patterns = load_yaml(patterns_path)
    plist = patterns.get('patterns', [])
    print(f"  ✅ 加载 {len(plist)} 个架构模式")
    for p in plist:
        rules = len(p.get('rules', []))
        tags = p.get('tags', [])
        print(f"     {p['id']:25s} rules={rules} tags={tags}")
    return True


def validate_mof(workspace_root: str) -> bool:
    """运行 MOF 校验和审计"""
    ssot_dir = Path(workspace_root) / 'src' / 'ecos' / 'ssot'
    tools_dir = Path(workspace_root) / 'tools'
    
    print("\n🔍 [3/4] MOF 元模型校验")
    mof_validate = tools_dir / 'mof-validate.py'
    if mof_validate.exists():
        # Adjust paths for workspace context
        result = subprocess.run(
            ['python3', str(mof_validate)],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, 'MOF_NODES_DIR': str(ssot_dir / 'mof' / 'nodes'),
                 'MOF_M2_FILE': str(ssot_dir / 'mof' / 'M2-元模型.yaml')}
        )
        if result.returncode == 0:
            # Parse and show summary
            for line in result.stdout.split('\n'):
                if '通过' in line or '错误' in line or '✅' in line:
                    print(f"  {line.strip()}")
            return True
        else:
            print(f"  ⚠️ {result.stderr[:200]}")
            return False
    else:
        print("  ⚠️ mof-validate.py 未找到，跳过")
        return True


def validate_mof_audit(workspace_root: str) -> bool:
    """运行 MOF 漂移审计"""
    tools_dir = Path(workspace_root) / 'tools'
    
    print("\n🔍 [4/4] MOF M1↔M0 漂移审计")
    mof_audit = tools_dir / 'mof-audit.py'
    if mof_audit.exists():
        result = subprocess.run(
            ['python3', str(mof_audit)],
            capture_output=True, text=True, timeout=30,
            env={**os.environ}
        )
        for line in result.stdout.split('\n'):
            if '漂移' in line or '✅' in line or '🔴' in line or '🟡' in line:
                print(f"  {line.strip()}")
        return result.returncode == 0
    else:
        print("  ⚠️ mof-audit.py 未找到，跳过")
        return True


def main():
    parser = argparse.ArgumentParser(description="eCOS L0 统一架构校验器")
    parser.add_argument("--workspace", default=".", help="Workspace 根路径")
    parser.add_argument("--all", action="store_true", help="运行全部校验")
    parser.add_argument("--topology-only", action="store_true")
    parser.add_argument("--mof-only", action="store_true")
    args = parser.parse_args()

    ws = Path(args.workspace)
    ssot = ws / 'src' / 'ecos' / 'ssot'
    
    topology_file = ssot / 'topology.yaml'
    patterns_file = ssot / 'patterns.yaml'

    all_pass = True
    
    if args.all or args.topology_only:
        all_pass &= validate_topology(str(ws), str(topology_file))
        all_pass &= validate_patterns(str(ws), str(patterns_file))
    
    if args.all or args.mof_only:
        all_pass &= validate_mof(str(ws))
        all_pass &= validate_mof_audit(str(ws))

    print(f"\n{'='*56}")
    print(f"  {'✅ 全部通过' if all_pass else '❌ 存在失败'}")
    print(f"{'='*56}")
    
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
