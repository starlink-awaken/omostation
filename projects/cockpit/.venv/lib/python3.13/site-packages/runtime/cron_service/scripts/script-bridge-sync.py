#!/usr/bin/env python3
"""
script-bridge-sync.py — 增量同步 Hermes ↔ Workspace 脚本桥接

功能：
1. 检测 Workspace 项目中新增的脚本 → 自动创建 symlink
2. 检测断裂的 symlink（目标文件已删除/移动）→ 报告
3. 检测 Workspace 中删除的脚本对应的孤立 symlink → 建议移除
4. 定期巡检：每天 06:00 自动运行（已有 cron job）

用法：
  python3 script-bridge-sync.py               # 扫描 + 修复
  python3 script-bridge-sync.py --check-only   # 仅检查，不修改
  python3 script-bridge-sync.py --report       # 输出机器可读的 JSON

架构：
- Workspace 脚本 SSOT：~/Workspace/<project>/scripts/
- Hermes 桥接：~/.hermes/scripts/ (symlink → Workspace)
- 分类规则：复用 migrate-ssot.py 中的 PROJECT_MAP
"""

import json
import os
import sys
from pathlib import Path

HOME = Path.home()
HERMES_SCRIPTS = HOME / ".hermes" / "scripts"
WORKSPACE = HOME / "Workspace"

# ── 复用分类逻辑 ──────────────────────────────────────────────
# ── 脚本分类规则（从 classify.py SSOT 读取）─────────────────
sys.path.insert(0, str(HOME / "Workspace" / "cron-service"))
from runtime.cron_service.classify import (
    SCRIPT_PREFIX_MAP,
    classify,
)
from runtime.cron_service.classify import (
    should_bridge as _should_include,
)


def list_workspace_scripts():
    """Scan all Workspace project scripts/ dirs. Returns {filename: project}"""
    result = {}
    for project, _ in SCRIPT_PREFIX_MAP.items():
        proj_dir = WORKSPACE / project / "scripts"
        if not proj_dir.is_dir():
            continue
        for f in os.listdir(proj_dir):
            fp = proj_dir / f
            if fp.is_file() and _should_include(f):
                result[f] = project
    return result


def list_hermes_symlinks():
    """Scan ~/.hermes/scripts/ symlinks. Returns {filename: target_path}"""
    result = {}
    if not HERMES_SCRIPTS.is_dir():
        return result
    for f in os.listdir(HERMES_SCRIPTS):
        fp = HERMES_SCRIPTS / f
        if fp.is_symlink():
            target = os.readlink(fp)
            result[f] = target
    return result


def sync_bridge():
    """主同步逻辑"""
    workspace_scripts = list_workspace_scripts()
    hermes_symlinks = list_hermes_symlinks()

    actions = {
        "created": [],  # 新增 symlink
        "broken": [],  # 断裂 symlink（目标不存在）
        "orphaned": [],  # 孤立 symlink（workspace 已无此文件）
        "unclassified": [],  # Workspace 有但无法分类
        "skipped": [],  # 已存在且正常
    }

    # 1. 检查 Workspace 中需要桥接到 Hermes 的脚本
    for filename, project in workspace_scripts.items():
        target_path = WORKSPACE / project / "scripts" / filename

        # 检查是否需要 symlink 到 Hermes
        if filename in hermes_symlinks:
            hermes_symlinks[filename]
            if os.path.exists(HERMES_SCRIPTS / filename):
                actual = (HERMES_SCRIPTS / filename).resolve()
                if actual == target_path.resolve():
                    actions["skipped"].append(filename)
                    continue
                else:
                    # 指向不同目标 → 需要更新
                    os.remove(HERMES_SCRIPTS / filename)

        # 该脚本在 Workspace 中，但在 Hermes 无 symlink
        # 判断是否应该桥接（有匹配的分类）
        project_match = classify(filename)
        if project_match:
            # 创建 symlink
            link_path = HERMES_SCRIPTS / filename
            link_path.symlink_to(str(target_path))
            actions["created"].append(f"{project}/{filename}")
        else:
            actions["unclassified"].append(f"{project}/{filename}")

    # 2. 检查断裂/孤立 symlink → 自动清理
    for filename, target in hermes_symlinks.items():
        target_path = Path(target).expanduser()
        if not target_path.exists():
            target_project = classify(filename)
            if target_project and filename not in workspace_scripts:
                # Orphaned symlink — Workspace project no longer has this file
                os.remove(HERMES_SCRIPTS / filename)
                actions["orphaned"].append(filename)
            else:
                # Broken symlink — target exists in workspace but path is wrong
                actions["broken"].append(filename)

    return actions


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Sync Hermes ↔ Workspace script bridge")
    parser.add_argument("--check-only", action="store_true", help="Only check, no modifications")
    parser.add_argument("--report", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    if args.check_only:
        # Read-only mode: collect state but don't modify
        ws = list_workspace_scripts()
        hm = list_hermes_symlinks()

        report = {
            "workspace_scripts": len(ws),
            "hermes_symlinks": len(hm),
            "missing_symlinks": [],
            "broken_symlinks": [],
            "unclassified_scripts": [],
        }

        for f, p in ws.items():
            if f not in hm:
                project_match = classify(f)
                if project_match:
                    report["missing_symlinks"].append(f"{p}/{f}")
                else:
                    report["unclassified_scripts"].append(f"{p}/{f}")

        for f, t in hm.items():
            if not Path(t).expanduser().exists():
                report["broken_symlinks"].append(f)

        if args.report:
            print(json.dumps(report, indent=2))
        else:
            print(f"Workspace 脚本: {report['workspace_scripts']} 个")
            print(f"Hermes symlink: {report['hermes_symlinks']} 个")
            print(f"缺少桥接: {len(report['missing_symlinks'])} 个")
            if report["missing_symlinks"]:
                for s in report["missing_symlinks"]:
                    print(f"  + {s}")
            print(f"断裂: {len(report['broken_symlinks'])} 个")
            if report["broken_symlinks"]:
                for s in report["broken_symlinks"]:
                    print(f"  ! {s}")
            print(f"未分类: {len(report['unclassified_scripts'])} 个")
        return

    # 执行模式
    print("━━━ script-bridge-sync ━━━\n")
    actions = sync_bridge()

    print(f"✅ 已有正常: {len(actions['skipped'])} 个")
    print(f"➕ 新增 symlink: {len(actions['created'])} 个")
    for s in actions["created"]:
        print(f"   ✓ {s}")
    print(f"💔 断裂 symlink: {len(actions['broken'])} 个")
    for s in actions["broken"]:
        print(f"   ! {s}")
    print(f"🗑️ 孤立 symlink: {len(actions['orphaned'])} 个")
    for s in actions["orphaned"]:
        print(f"   ~ {s}")
    print(f"❌ 未分类: {len(actions['unclassified'])} 个")
    for s in actions["unclassified"]:
        print(f"   ? {s}")

    total_issues = len(actions["broken"]) + len(actions["orphaned"])
    if total_issues > 0:
        print(f"\n⚠️  {total_issues} 个问题需人工处理")
    else:
        print("\n✅ 桥接状态健康")


if __name__ == "__main__":
    main()
