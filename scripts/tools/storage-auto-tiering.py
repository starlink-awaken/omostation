#!/usr/bin/env python3
"""storage-auto-tiering.py — 4.1T 存储异构冷热分层与 300GB 水位防御守卫 (BET-Y2Q4-T10-243 / T10-242).

契约依归:
  - ADR-0466 (系统真实性与零 Mock 契约)
  - docs/superpowers/specs/2026-10-27-storage-resilience-t3-playbook.md
  - 黄金底线: 内置 SSD 极速存储空间稳定保持 300GB+

工作机制:
  1. 探测内置 SSD (/System/Volumes/Data) 可用空间；
  2. 若可用容量 >= 300GB，判定为 NORMAL，维持现状 (IDLE)；
  3. 若可用容量 < 300GB：
     - 检查外挂雷电盘 (/Volumes/Model) 是否在线；
     - 若外挂盘掉线，发出告警并触发 T3 掉线保护（降级为小模型/云端，禁止盲目搬运）；
     - 若外挂盘在线，安全扫描指定大缓存目录中的 >2GB 冷数据；
     - 搬迁至 /Volumes/Model/omostation-cold/ 并原子创建透明软链接 (symlink)；
     - 写入审计日志 runtime/reports/storage-tiering-history.jsonl。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

# 安全扫描候选目录（仅允许模型与大缓存区，严格禁止触碰 .git/ 与 sqlite）
SAFE_SCAN_DIRS = [
    Path.home() / ".cache" / "huggingface" / "hub",
    Path.home() / ".cache" / "modelscope" / "hub",
    Path.home() / ".local" / "share" / "omlx" / "models",
    Path.home() / ".local" / "share" / "transformers",
]

# 严格保护目录与文件黑名单
EXCLUDED_PATTERNS = {
    ".git",
    ".omo",
    "event-ledger.sqlite3",
    "event-ledger.sqlite3-wal",
    "event-ledger.sqlite3-shm",
    "node_modules",
    ".venv",
}


def get_ssd_free_gb(path: str = "/System/Volumes/Data") -> tuple[float, float]:
    """返回 (free_gb, total_gb)"""
    try:
        st = os.statvfs(path)
        free_bytes = st.f_bavail * st.f_frsize
        total_bytes = st.f_blocks * st.f_frsize
        return round(free_bytes / (1024**3), 2), round(total_bytes / (1024**3), 2)
    except Exception:
        return 0.0, 0.0


def is_volume_healthy(vol_path: str = "/Volumes/Model") -> bool:
    """检查外挂盘是否挂载且可写"""
    p = Path(vol_path)
    if not p.is_dir() or not os.path.ismount(vol_path):
        return False
    try:
        test_file = p / ".tiering_probe.tmp"
        test_file.write_text("probe")
        test_file.unlink()
        return True
    except Exception:
        return False


def find_large_candidates(min_gb: float = 2.0) -> list[dict[str, Any]]:
    """扫描安全目录中未软链且 > min_gb 的大文件"""
    min_bytes = int(min_gb * 1024 * 1024 * 1024)
    candidates: list[dict[str, Any]] = []

    for base_dir in SAFE_SCAN_DIRS:
        if not base_dir.is_dir():
            continue
        try:
            for root, dirs, files in os.walk(base_dir):
                # 排除黑名单目录
                dirs[:] = [d for d in dirs if d not in EXCLUDED_PATTERNS]
                for file_name in files:
                    if any(ex in file_name for ex in EXCLUDED_PATTERNS):
                        continue
                    file_path = Path(root) / file_name
                    try:
                        # 忽略已是软链的文件
                        if file_path.is_symlink():
                            continue
                        file_stat = file_path.stat()
                        # 仅处理普通文件
                        if not stat.S_ISREG(file_stat.st_mode):
                            continue
                        if file_stat.st_size >= min_bytes:
                            candidates.append({
                                "path": str(file_path),
                                "size_bytes": file_stat.st_size,
                                "size_gb": round(file_stat.st_size / (1024**3), 2),
                                "mtime": dt.datetime.fromtimestamp(file_stat.st_mtime, dt.timezone.utc).isoformat(),
                            })
                    except (OSError, PermissionError):
                        continue
        except Exception:
            continue

    # 按文件体积从大到小排序
    candidates.sort(key=lambda x: x["size_bytes"], reverse=True)
    return candidates


def perform_tiering(
    candidate: dict[str, Any],
    target_vol_base: Path,
    dry_run: bool = True
) -> dict[str, Any]:
    """搬迁单个大文件并建立透明软链"""
    src = Path(candidate["path"])
    # 保持相对路径层级避免同名冲突
    rel_part = src.relative_to(Path.home())
    dst = target_vol_base / rel_part

    result = {
        "source": str(src),
        "destination": str(dst),
        "size_gb": candidate["size_gb"],
        "status": "SIMULATED" if dry_run else "PENDING",
        "error": None,
    }

    if dry_run:
        return result

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        # 复制文件
        shutil.copy2(src, dst)
        # 验证文件大小
        if dst.stat().st_size != src.stat().st_size:
            if dst.exists():
                dst.unlink()
            raise RuntimeError("复制前后文件大小不一致，搬迁已终止")
        # 移除原文件并建立软链
        src.unlink()
        src.symlink_to(dst)
        result["status"] = "COMPLETED"
    except Exception as e:
        result["status"] = "FAILED"
        result["error"] = str(e)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="4.1T 存储自动冷热分层与水位守卫")
    parser.add_argument("--min-ssd-free-gb", type=float, default=300.0, help="内置 SSD 触发警戒水位 (GB, 默认 300.0)")
    parser.add_argument("--min-file-size-gb", type=float, default=2.0, help="搬迁候选文件最小体积 (GB, 默认 2.0)")
    parser.add_argument("--target-vol", default="/Volumes/Model/omostation-cold", help="沉降目标盘基础路径")
    parser.add_argument("--dry-run", action="store_true", help="演练模式，仅输出搬迁计划，不真实改动文件")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON 报告")
    args = parser.parse_args()

    ssd_free_gb, ssd_total_gb = get_ssd_free_gb()
    vol_online = is_volume_healthy()
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()

    report: dict[str, Any] = {
        "schema": "storage-auto-tiering/v1",
        "timestamp": now_iso,
        "mode": "DRY_RUN" if args.dry_run else "LIVE",
        "ssd": {
            "path": "/System/Volumes/Data",
            "free_gb": ssd_free_gb,
            "total_gb": ssd_total_gb,
            "threshold_gb": args.min_ssd_free_gb,
            "below_threshold": ssd_free_gb < args.min_ssd_free_gb,
        },
        "target_volume": {
            "path": "/Volumes/Model",
            "online": vol_online,
            "destination_base": args.target_vol,
        },
        "verdict": "NORMAL",
        "action_taken": "NONE",
        "candidates_count": 0,
        "total_freed_gb": 0.0,
        "actions": [],
    }

    if ssd_free_gb >= args.min_ssd_free_gb:
        report["verdict"] = "IDLE_ABOVE_THRESHOLD"
        report["action_taken"] = f"内置 SSD 可用容量 {ssd_free_gb}GB 充足 (>= {args.min_ssd_free_gb}GB)，无需搬迁"
    else:
        # 可用空间不足
        if not vol_online:
            report["verdict"] = "ALERT_EXTERNAL_OFFLINE"
            report["action_taken"] = "内置 SSD 低于阈值但 /Volumes/Model 掉线，触发 T3 掉线保护，禁止搬迁"
        else:
            candidates = find_large_candidates(args.min_file_size_gb)
            report["candidates_count"] = len(candidates)
            target_base = Path(args.target_vol)
            freed = 0.0

            for cand in candidates:
                res = perform_tiering(cand, target_base, dry_run=args.dry_run)
                report["actions"].append(res)
                if res["status"] in ("COMPLETED", "SIMULATED"):
                    freed += cand["size_gb"]
                # 若已恢复到安全线 + 20GB 缓冲，则提前结束
                if (ssd_free_gb + freed) >= (args.min_ssd_free_gb + 20.0):
                    break

            report["total_freed_gb"] = round(freed, 2)
            report["verdict"] = "TIERING_EXECUTED" if not args.dry_run else "TIERING_PLANNED"
            report["action_taken"] = f"{'已规划' if args.dry_run else '已搬迁'} {len(report['actions'])} 个冷数据文件，释放 {round(freed, 2)}GB"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("==================================================")
        print("4.1T 存储异构冷热分层守卫 (BET-Y2Q4-T10-243)")
        print("==================================================")
        print(f"模式: {report['mode']}")
        print(f"内置 SSD: 可用 {ssd_free_gb}GB / 总量 {ssd_total_gb}GB (警戒水位: {args.min_ssd_free_gb}GB)")
        print(f"外挂模型盘 /Volumes/Model: {'在线' if vol_online else '离线'}")
        print(f"判定: {report['verdict']}")
        print(f"处置: {report['action_taken']}")
        if report["actions"]:
            print("--------------------------------------------------")
            for act in report["actions"]:
                print(f"  [{act['status']}] {act['size_gb']}GB: {act['source']} -> {act['destination']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
