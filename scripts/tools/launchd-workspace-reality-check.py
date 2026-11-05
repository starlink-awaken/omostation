#!/usr/bin/env python3
"""launchd-workspace-reality-check — 测量 ~/Library/LaunchAgents 中指向 Workspace 的 plist 全量现实 (BET-Y2Q4-T10-272).

契约：
- 纯观测 (Observe-Only)，退出码恒为 0，绝不修改、卸载或重载任何 LaunchAgent。
- 透视所有硬编码指向 Workspace 的 plist，按服务角色分类 (core, resident, maintenance, unmanaged)。
- 指认判据取自服务自己的目标值 (plist 解析后的全部字符串叶子)，唯独排除 EnvironmentVariables.PATH：
  解释器搜索路径里出现某个根，不等于该服务从那个根运行。
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

_LIB_DIR = Path(__file__).resolve().parents[2] / "bin" / "lib"
if not _LIB_DIR.is_dir():
    raise SystemExit(f"repo_root 缝不可达: {_LIB_DIR} —— 尺不得静默兜底")
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
from repo_root import canonical_root, code_root, install_root  # noqa: E402


def service_target_values(data: dict) -> list[str]:
    """服务自己的全部目标字符串值；仅剔除 EnvironmentVariables.PATH 这一个键。"""
    values: list[str] = []

    def walk(node: object, key_path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                walk(child, key_path + (str(key),))
        elif isinstance(node, list):
            for child in node:
                walk(child, key_path + ("*",))
        elif isinstance(node, str):
            if key_path == ("EnvironmentVariables", "PATH"):
                return
            values.append(node)

    walk(data, ())
    return values


def scan_launchd_workspace_targets(launchd_dir: Path | None = None) -> dict:
    target_dir = launchd_dir or (Path.home() / "Library" / "LaunchAgents")
    canon_ws_path = str(canonical_root())
    code_ws_path = str(code_root())
    _inst = install_root()
    if _inst is None:
        raise SystemExit("运行时安装位未落位 (install_root() -> None) —— 尺拒绝静默退回检出根")
    inst_path = str(_inst)
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
        targets = service_target_values(data)
        has_ws = any(
            root in value for value in targets for root in (canon_ws_path, code_ws_path)
        )
        has_inst = any(inst_path in value for value in targets)

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
