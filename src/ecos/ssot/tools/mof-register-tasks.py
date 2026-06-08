#!/usr/bin/env python3
"""
织星 MOF — 任务与脚本注册器 (mof-register-tasks)
==================================================
全量扫描定时任务·后台脚本·临时工具，生成 M1 Mechanism 节点，
建立完整的任务生命周期管理。

扫描源:
  1. Claude/Scheduled/ (31 SKILL.md) → Mechanism (定时任务)
  2. @驾驶舱/scripts/*.py (22)       → Mechanism (治理脚本)
  3. Workspace 各项目 scripts/       → Mechanism (项目脚本)
  4. LaunchAgents plist              → Component (守护进程)
  5. L0 tools/                       → Mechanism (MOF 工具)

生命周期建模:
  创建 → 注册到 L0 → 调度执行 → 健康监控 → 审计 → 退役

用法:
    python3 mof-register-tasks.py           # 扫描+生成 M1 节点
    python3 mof-register-tasks.py --summary # 仅统计
"""

import sys, os, json, yaml, re
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
DOCS = HOME / 'Documents'
WS = HOME / 'Workspace'
L0_NODES = WS / 'projects' / 'ecos' / 'src' / 'ecos' / 'ssot' / 'mof' / 'nodes'
L0_TOOLS = WS / 'projects' / 'ecos' / 'tools'

def now(): return datetime.now(timezone.utc).isoformat()[:10]


def scan_scheduled_tasks() -> list[dict]:
    """Claude/Scheduled/ → Mechanism 节点"""
    nodes = []
    sched = DOCS / 'Claude' / 'Scheduled'
    if not sched.exists():
        return nodes
    
    for d in sorted(sched.iterdir()):
        if not d.is_dir() or d.name.startswith('.'):
            continue
        skill = d / 'SKILL.md'
        if not skill.exists():
            continue
        
        stat = skill.stat()
        with open(skill) as f:
            head = f.read(300)
        
        # Determine category
        name = d.name
        if 'daily' in name: freq = 'daily'
        elif 'weekly' in name or any(k in name for k in ['monday','friday','wednesday']): freq = 'weekly'
        elif 'monthly' in name or 'quarterly' in name: freq = 'monthly'
        elif 'sync' in name: freq = 'event'
        elif 'fetch' in name or 'caiji' in name: freq = 'event'
        elif 'check' in name or 'health' in name: freq = 'daily'
        else: freq = 'weekly'
        
        nodes.append({
            "id": f"MECH-SCHEDULED-{name}",
            "type": "Mechanism", "subtype": "ScheduledTask",
            "name": name.replace('-', ' ').title(),
            "description": f"定时任务: {name}",
            "status": "active", "domain": "meta",
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat()[:10],
            "version": "1.0.0", "layer": "L4",
            "properties": {
                "trigger": f"scheduled ({freq})",
                "action": f"执行 SKILL.md 中定义的指令",
                "interval": {"daily": 86400, "weekly": 604800, "monthly": 2592000, "event": 0}.get(freq, 0),
                "feedback": "task-runlog.md (手动)",
                "sla_target": {"max_stale_hours": {"daily": 48, "weekly": 240, "monthly": 1440}.get(freq, 0)},
            },
        })
    return nodes


def scan_governance_scripts() -> list[dict]:
    """@驾驶舱/scripts → Mechanism 节点"""
    nodes = []
    scripts = DOCS / '@驾驶舱' / 'scripts'
    if not scripts.exists():
        return nodes
    
    layer_map = {
        'ecos-daemon': 'L1', 'ecos-healer': 'L1', 'ecos-sla-tracker': 'L1',
        'ecos-constraint-compiler': 'L0', 'ecos-constraint-validator': 'L0',
        'ecos-brief': 'L4', 'ecos-health-check': 'L4', 'ecos-whoami': 'L4',
        'ecos-onboard': 'L4', 'ecos-bootstrap': 'L4', 'ecos-weekly-digest': 'L4',
        'ecos-entry': 'L4',
        'check-claude-freshness': 'X2', 'check-vault-audit': 'X1',
        'vault-value-attribution': 'X3', 'domain-value-attribution': 'X3',
        'x3-coverage-report': 'X3', 'check-cards-state-consistency': 'X4',
        'fix-debts': 'L1', 'runtime-mcp-server': 'L3',
        'task-status': 'X4',
    }
    
    for f in sorted(scripts.glob("*.py")):
        name = f.stem
        layer = layer_map.get(name, 'L4')
        is_daemon = any(k in name for k in ['daemon', 'healer', 'sla'])
        
        nodes.append({
            "id": f"MECH-SCRIPT-{name}",
            "type": "Mechanism", "subtype": "GovernanceScript",
            "name": name,
            "description": f"治理脚本: {name}",
            "status": "active", "domain": "meta",
            "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat()[:10],
            "version": "1.0.0", "layer": layer,
            "properties": {
                "trigger": "scheduled (daemon)" if is_daemon else "manual/daemon",
                "action": f"python3 {f.name}",
                "interval": 21600 if is_daemon else 0,
                "feedback": "stdout/stderr + daemon-state.db",
            },
        })
    return nodes


def scan_launchd() -> list[dict]:
    """LaunchAgents → Component 节点"""
    nodes = []
    launch = HOME / 'Library' / 'LaunchAgents'
    for plist in sorted(launch.glob('com.ecos*')):
        nodes.append({
            "id": f"COMP-LAUNCHD-{plist.stem}",
            "type": "Component", "subtype": "Daemon",
            "name": plist.stem,
            "description": f"launchd 守护进程: {plist.stem}",
            "status": "active", "domain": "infra",
            "created": datetime.fromtimestamp(plist.stat().st_ctime).isoformat()[:10],
            "version": "1.0.0", "layer": "L1",
            "properties": {
                "layer": "L1",
                "runtime": "active",
                "protocol": "launchd",
            },
        })
    return nodes


def save_nodes(nodes: list[dict], prefix: str):
    L0_NODES.mkdir(parents=True, exist_ok=True)
    for n in nodes:
        fp = L0_NODES / f"{n['id']}.yaml"
        with open(fp, 'w') as f:
            f.write(f"# M1 Node: {n['id']}\n# Type: {n['type']}\n# Registered by mof-register-tasks\n\n")
            yaml.dump(n, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def main():
    all_nodes = []
    all_nodes.extend(scan_scheduled_tasks())
    all_nodes.extend(scan_governance_scripts())
    all_nodes.extend(scan_launchd())

    # Summary
    by_layer = {}
    by_type = {}
    for n in all_nodes:
        by_layer[n.get('layer','?')] = by_layer.get(n.get('layer','?'), 0) + 1
        by_type[n.get('subtype','?')] = by_type.get(n.get('subtype','?'), 0) + 1

    print("=" * 56)
    print("  任务/脚本 注册报告")
    print("=" * 56)
    print(f"  总计: {len(all_nodes)} Mechanism/Component 节点")
    for t, c in sorted(by_type.items()):
        print(f"  {t:25s}: {c:3d}")
    print(f"\n  ── 按层 ──")
    for l in ['L0','L1','L2','L3','L4','X1','X2','X3','X4','I0']:
        if l in by_layer:
            print(f"  {l:6s}: {by_layer[l]:3d}")
    
    save_nodes(all_nodes, "task")
    print(f"\n  ✅ 节点已注册到 L0 nodes/")


if __name__ == "__main__":
    main()
