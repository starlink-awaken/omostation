#!/usr/bin/env python3
"""
织星 MOF — 统一命令行 (mof)
=============================
L0 工具链的统一入口。支持主动触发所有检查。

用法:
    mof check               # 全量检查 (gate + validate + audit + enforce)
    mof validate            # 仅校验
    mof audit               # 仅审计
    mof gate                # 仅变更门禁
    mof status              # 系统状态摘要
    mof adr create "标题"   # 创建 ADR (架构决策记录)
    mof adr list            # 列出所有 ADR
"""

import sys, os, subprocess, json, yaml
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
SSOT_TOOLS = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools"
OMO_CHANGE = HOME / "Workspace" / ".omo" / "change-log"
L0_M1 = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"


def run_tool(name, args=None):
    tool = SSOT_TOOLS / f"{name}.py"
    if not tool.exists():
        print(f"❌ 工具不存在: {tool}")
        return 1
    cmd = ["python3", str(tool)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd).returncode


def cmd_pipeline():
    """M3→M0 全链路管线"""
    print("═══ 织星 MOF — M3→M0 全链路管线 ═══\n")
    stages = [
        ("L0-M3→M2", "M3 parent 自反一致性", "mof-bootstrap", ["--json"]),
        ("L0-M2→M1", "M2→M1 结构校验 (575节点)", "mof-validate", ["--json"]),
        ("L0-M1↔M0", "M1↔M0 漂移审计", "mof-audit", ["--json"]),
        ("L0-M0→Evt", "M0 异常→治理事件", "mof-events", ["--json"]),
        ("L0-Registry", "层边界合规", "mof-enforce", ["--no-cards", "--json"]),
        ("L0-Self", "自举全量校验", "mof-bootstrap", ["--json"]),
    ]
    
    import subprocess
    failed = 0
    for layer_id, name, tool, args in stages:
        tool_path = SSOT_TOOLS / f"{tool}.py"
        if not tool_path.exists():
            print(f"  ⏭️  [{layer_id}] {name}: 工具不存在")
            continue
        rc = subprocess.run(["python3", str(tool_path)] + args,
                          capture_output=True, timeout=30).returncode
        icon = "✅" if rc == 0 else "❌"
        if rc != 0: failed += 1
        print(f"  {icon} [{layer_id}] {name}")
    
    print(f"\n{'✅ 全链路通过' if failed == 0 else f'❌ {failed} 阶段失败'}")
    print("═══ 管线完成 ═══")


def cmd_check():
    """全量检查"""
    print("═══ 织星 MOF 全量检查 ═══\n")
    checks = [
        ("变更门禁", "mof-gate", ["--no-cards"]),
        ("M1↔M2 校验", "mof-validate", []),
        ("M1↔M0 审计", "mof-audit", []),
        ("层合规", "mof-enforce", ["--no-cards"]),
    ]
    failed = 0
    for name, tool, args in checks:
        print(f"  🔍 {name}...")
        rc = run_tool(tool, args)
        if rc != 0:
            failed += 1
            print(f"  ❌ {name} 失败")
        else:
            print(f"  ✅ {name} 通过")
        print()
    
    print(f"{'✅ 全部通过' if failed == 0 else f'❌ {failed} 项失败'}")


def cmd_status():
    """系统状态摘要"""
    # Quick stats
    m1_count = sum(1 for _ in L0_M1.rglob("*.yaml"))
    m2_count = len(list((SSOT_TOOLS.parent / "mof" / "m2").glob("*.yaml")))
    tools_count = len(list(SSOT_TOOLS.glob("mof-*.py")))
    
    # Latest M0 snapshot
    m0_file = SSOT_TOOLS.parent / "mof" / "m0" / "snapshot.yaml"
    m0 = {}
    if m0_file.exists():
        m0 = yaml.safe_load(open(m0_file)) or {}
    
    print("═══ 织星 MOF 状态 ═══")
    print(f"  M2 类型: {m2_count}")
    print(f"  M1 节点: {m1_count}")
    print(f"  工具链:  {tools_count}")
    print(f"  M0 快照: {m0.get('generated_at', 'N/A')[:19]}")
    
    daemon = m0.get("daemon", {})
    if daemon:
        print(f"  Daemon:  {'🟢' if daemon.get('healthy') else '🟡'} {daemon.get('cycles', 0)} 周期")
    
    protocols = m0.get("protocols", {})
    if protocols:
        aging = [p for p, s in protocols.items() if s.get("status") in ("aging", "expired")]
        if aging:
            print(f"  协议:    ⚠️ {', '.join(aging)} 需关注")
        else:
            print(f"  协议:    ✅ 全部健康")


def cmd_adr(args):
    """ADR 管理"""
    if not args or args[0] == "list":
        decisions_dir = L0_M1 / "decision"
        if decisions_dir.exists():
            ads = list(decisions_dir.glob("DEC-*.yaml"))
            print(f"═══ 架构决策记录 ({len(ads)} 条) ═══")
            for f in sorted(ads):
                try:
                    d = yaml.safe_load(open(f))
                    status = d.get("status", "?")
                    name = d.get("name", f.stem)[:60]
                    icon = {"accepted": "✅", "proposed": "📋", "rejected": "❌", "superseded": "🔄"}.get(status, "❓")
                    print(f"  {icon} [{status:10s}] {name}")
                except:
                    print(f"  ❓ {f.stem}")
        else:
            print("  (无 ADR)")
        return
    
    if args[0] == "create" and len(args) > 1:
        title = " ".join(args[1:])
        now_str = datetime.now(timezone.utc).isoformat()[:10]
        did = f"DEC-{now_str}-{title[:20]}"
        did = "".join(c if c.isalnum() or c in "-_" else "-" for c in did)[:55]
        
        node = {
            "id": did, "type": "Decision", "name": title,
            "description": title, "status": "proposed",
            "domain": "meta", "created": now_str, "version": "1.0.0", "layer": "L0",
            "properties": {
                "problem": title,
                "decision": "(待填写)",
                "rationale": "(待填写)",
                "options": [],
                "consequences": "",
            },
        }
        
        fp = L0_M1 / "decision" / f"{did}.yaml"
        fp.parent.mkdir(parents=True, exist_ok=True)
        with open(fp, 'w') as f:
            f.write(f"# ADR: {did}\n# Created: {now_str}\n\n")
            yaml.dump(node, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        print(f"✅ ADR 已创建: {did}")
        print(f"   文件: {fp}")
        print(f"   下一步: 编辑 {fp} 填写 problem/options/decision/rationale")
        print(f"   完成后: mof validate 校验")
        return


def print_help():
    print("织星 MOF — L0 统一命令行")
    print()
    print("架构治理:")
    print("  mof check          全量检查 (gate+validate+audit+enforce)")
    print("  mof status         系统状态摘要")
    print("  mof validate       校验 M1↔M2 合规")
    print("  mof audit          审计 M1↔M0 漂移")
    print("  mof gate           变更门禁 (检测未注册资产)")
    print("  mof enforce        层合规强制执行")
    print("  mof bootstrap      L0 自举校验")
    print()
    print("变更管理:")
    print("  mof adr list       列出架构决策")
    print("  mof adr create ... 创建新 ADR")
    print()
    print("查询视图:")
    print("  mof view           生成全量架构视图")
    print("  mof view quick     Agent 快速索引")
    print("  mof entity resolve 跨域实体解析")
    print("  mof entity list    列出所有实体")
    print("  mof entity stats   实体统计")
    print()
    print("运维:")
    print("  mof trail          统一审计追踪")
    print("  mof events         治理事件流")
    print("  mof sla            SLA + M0 快照")
    print("  mof scan           扫描资产 → M1")
    print()


def main():
    if len(sys.argv) < 2:
        print_help()
        return
    
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    # Architecture governance
    if cmd == "pipeline": cmd_pipeline()
    elif cmd == "check": cmd_check()
    elif cmd == "status": cmd_status()
    elif cmd == "validate": run_tool("mof-validate", args)
    elif cmd == "audit": run_tool("mof-audit", args)
    elif cmd == "gate": run_tool("mof-gate", args)
    elif cmd == "enforce": run_tool("mof-enforce", args)
    elif cmd == "bootstrap": run_tool("mof-bootstrap", args)
    
    # Change management
    elif cmd == "adr": cmd_adr(args)
    
    # Query/View
    elif cmd == "view": run_tool("mof-view", args)
    elif cmd == "entity": run_tool("mof-entity", args)
    
    # Operations
    elif cmd == "trail": run_tool("mof-trail", args)
    elif cmd == "events": run_tool("mof-events", args)
    elif cmd == "sla": run_tool("mof-sla", args)
    elif cmd == "scan": run_tool("mof-scan", args)
    
    elif cmd in ("help", "-h", "--help"): print_help()
    else:
        print(f"未知命令: {cmd}\n")
        print_help()


if __name__ == "__main__":
    main()
