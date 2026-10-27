#!/usr/bin/env python3
"""storage-resilience-check — 4.1T 存储盘分层容灾与外挂盘状态探测工具 (BET-Y2Q4-T10-243).

契约：
- 纯观测 (Observe-Only)，退出码恒为 0，绝不执行格式化或强制卸载等破坏性动作。
- 监控内置根存储与外挂大容量存储盘 (/Volumes/Model, /Volumes/HD)。
- 提供分层容灾状态判定 (NORMAL / DEGRADED_DISCONNECTED / WARNING_LOW_SPACE)。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def probe_mount_point(path_str: str) -> dict:
    p = Path(path_str)
    if not p.exists() or not p.is_dir():
        return {
            "path": path_str,
            "mounted": False,
            "status": "DISCONNECTED",
            "total_gb": 0,
            "used_gb": 0,
            "free_gb": 0,
            "percent_used": 0.0,
        }
    try:
        usage = shutil.disk_usage(p)
        total_gb = round(usage.total / (1024**3), 2)
        used_gb = round(usage.used / (1024**3), 2)
        free_gb = round(usage.free / (1024**3), 2)
        pct = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0.0
        return {
            "path": path_str,
            "mounted": True,
            "status": "ONLINE",
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "percent_used": pct,
        }
    except Exception as exc:
        return {
            "path": path_str,
            "mounted": False,
            "status": f"ERROR: {exc}",
            "total_gb": 0,
            "used_gb": 0,
            "free_gb": 0,
            "percent_used": 0.0,
        }


def check_storage_resilience() -> dict:
    internal_data = probe_mount_point("/System/Volumes/Data")
    if not internal_data["mounted"]:
        internal_data = probe_mount_point("/")

    model_vol = probe_mount_point("/Volumes/Model")
    hd_vol = probe_mount_point("/Volumes/HD")

    # 容灾状态推导
    disconnected = []
    if not model_vol["mounted"]:
        disconnected.append("/Volumes/Model")
    if not hd_vol["mounted"]:
        disconnected.append("/Volumes/HD")

    low_space = []
    if internal_data["mounted"] and internal_data["free_gb"] < 30.0:
        low_space.append(internal_data["path"])
    if model_vol["mounted"] and model_vol["free_gb"] < 50.0:
        low_space.append("/Volumes/Model")

    if disconnected:
        overall_status = "DEGRADED_DISCONNECTED"
        recommended_action = "触发 T3 掉线保护剧本：核心治理留在内置 SSD，大模型推理降级至小模型或云端网关"
    elif low_space:
        overall_status = "WARNING_LOW_SPACE"
        recommended_action = "存储告警：可用空间不足，执行 Model 卷或缓存归档排空 (BET-Y2Q4-T10-242)"
    else:
        overall_status = "NORMAL"
        recommended_action = "存储状态健康，异构算力与热层数据安全"

    return {
        "schema": "storage-resilience-probe/v1",
        "overall_status": overall_status,
        "recommended_action": recommended_action,
        "internal_ssd": internal_data,
        "external_volumes": {
            "model_volume": model_vol,
            "hd_volume": hd_vol,
        },
        "disconnected_volumes": disconnected,
        "low_space_volumes": low_space,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    report = check_storage_resilience()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("==================================================")
        print("4.1T 存储盘分层容灾探测报告 (BET-Y2Q4-T10-243)")
        print("==================================================")
        print(f"总体状态: {report['overall_status']}")
        print(f"行动建议: {report['recommended_action']}")
        print("--------------------------------------------------")
        int_ssd = report["internal_ssd"]
        print(f"内置 SSD ({int_ssd['path']}): 状态={int_ssd['status']}, 可用={int_ssd['free_gb']}GB ({int_ssd['percent_used']}% 已用)")
        for name, vol in report["external_volumes"].items():
            print(f"外置盘 ({vol['path']}): 状态={vol['status']}, 可用={vol['free_gb']}GB ({vol['percent_used']}% 已用)")
        print("==================================================")
        print("✅ Storage resilience probe complete (exit=0)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
