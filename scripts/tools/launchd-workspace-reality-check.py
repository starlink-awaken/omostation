#!/usr/bin/env python3
"""launchd-workspace-reality-check — 测量 ~/Library/LaunchAgents 中指向 Workspace 的 plist 全量现实 (BET-Y2Q4-T10-272).

契约：
- 纯观测 (Observe-Only)，退出码恒为 0，绝不修改、卸载或重载任何 LaunchAgent。
- 透视 39 个硬编码指向 Workspace 的 plist，按服务角色分类 (core, resident, maintenance, unmanaged)。
- 检查 EnvironmentVariables.OMOSTATION_STATE_ROOT 写根落点 (profile vs checkout vs undeclared)。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import plistlib
import sys
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
try:
    from repo_root import canonical_root, code_root, install_root
except ImportError:
    def canonical_root():
        return Path("/Users/xiamingxing/Workspace")
    def code_root():
        return Path("/Users/xiamingxing/Workspace")
    def install_root():
        return Path.home() / ".local" / "opt" / "omostation"


def scan_launchd_workspace_targets(launchd_dir: Path | None = None) -> dict:
    target_dir = launchd_dir or (Path.home() / "Library" / "LaunchAgents")
    canon_ws_path = str(canonical_root())
    code_ws_path = str(code_root())
    inst_path = str(install_root())
    profile_base = str(Path.home() / ".local" / "state" / "omostation")

    plists = sorted(glob.glob(str(target_dir / "*.plist")))
    total_count = len(plists)

    workspace_hits: list[dict] = []
    install_hits: list[dict] = []
    other_hits: list[dict] = []

    categories = {
        "core_daemons": [],
        "resident_decision": [],
        "maintenance_gc": [],
        "unmanaged_other": [],
    }

    state_root_distribution = {
        "checkout": 0,
        "profile": 0,
        "install": 0,
        "undeclared": 0,
        "other": 0,
    }

    for plist_path_str in plists:
        p = Path(plist_path_str)
        try:
            with open(p, "rb") as f:
                data = plistlib.load(f)
        except Exception:
            continue

        label = data.get("Label") or p.stem
        raw_text = p.read_text(encoding="utf-8", errors="replace")
        has_ws = (canon_ws_path in raw_text) or (code_ws_path in raw_text)
        has_inst = inst_path in raw_text

        # 检查写根
        env = data.get("EnvironmentVariables") or {}
        raw_state_root = env.get("OMOSTATION_STATE_ROOT")
        if raw_state_root is None:
            sr_state = "undeclared"
        else:
            sr_expanded = str(Path(str(raw_state_root)).expanduser())
            if sr_expanded.startswith(profile_base):
                sr_state = "profile"
            elif sr_expanded == canon_ws_path or sr_expanded == code_ws_path:
                sr_state = "checkout"
            elif sr_expanded == inst_path:
                sr_state = "install"
            else:
                sr_state = "other"

        state_root_distribution[sr_state] += 1

        record = {
            "label": label,
            "plist_file": p.name,
            "has_workspace_reference": has_ws,
            "has_install_reference": has_inst,
            "state_root_state": sr_state,
            "declared_state_root": raw_state_root,
            "working_directory": data.get("WorkingDirectory"),
            "program_arguments": data.get("ProgramArguments"),
        }

        if has_ws:
            workspace_hits.append(record)
            # 分类
            if any(k in label for k in ("agora", "cockpit", "kos", "dashboard")):
                categories["core_daemons"].append(label)
            elif "resident" in label or "claims" in label:
                categories["resident_decision"].append(label)
            elif any(k in label for k in ("gc", "watch", "patrol", "refresh", "prune", "sync")):
                categories["maintenance_gc"].append(label)
            else:
                categories["unmanaged_other"].append(label)
        elif has_inst:
            install_hits.append(record)
        else:
            other_hits.append(record)

    return {
        "schema": "launchd-workspace-reality-check/v1",
        "total_plists": total_count,
        "pointing_to_workspace_count": len(workspace_hits),
        "pointing_to_install_count": len(install_hits),
        "other_count": len(other_hits),
        "workspace_categories": {k: len(v) for k, v in categories.items()},
        "workspace_categories_labels": categories,
        "state_root_distribution": state_root_distribution,
        "workspace_hits_sample": [
            {"label": r["label"], "state_root": r["state_root_state"]}
            for r in workspace_hits[:15]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    report = scan_launchd_workspace_targets()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("==================================================")
        print("B4b Reality-Check 尺子: LaunchAgents Workspace 路径透视")
        print("==================================================")
        print(f"总 Plist 数量: {report['total_plists']}")
        print(f"指向 Workspace: {report['pointing_to_workspace_count']} (目标: 43 → 0)")
        print(f"已指向 Install 根: {report['pointing_to_install_count']}")
        print(f"其他系统级/外部: {report['other_count']}")
        print("--------------------------------------------------")
        print("指向 Workspace 的分类细目:")
        for cat, cnt in report["workspace_categories"].items():
            print(f"  • {cat}: {cnt} 项")
        print("--------------------------------------------------")
        print(f"写根 (OMOSTATION_STATE_ROOT) 分布: {report['state_root_distribution']}")
        print("==================================================")
        print("✅ Observe-only reality check complete (exit=0)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
