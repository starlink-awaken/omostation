#!/usr/bin/env python3
"""
eCOS v5 X2 — CLAUDE.md Freshness Checker
=========================================
Phase X1 / BKL-011 / DEBT-X-003
扫描全量 CLAUDE.md 文件，标记超过 60 天未更新的文件。

用法:
    python3 check-claude-freshness.py [--max-age-days 60] [--json] [--root <path>]

输出:
    - 标准模式: 人类可读的保鲜报告
    - JSON 模式: 结构化输出，供 Agora 事件总线消费

退出码:
    0 = 全部新鲜
    1 = 存在 stale 文件
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# 默认扫描根目录
DEFAULT_ROOT = os.path.expanduser("~/Documents")

# 排除目录
EXCLUDE_DIRS = {
    ".git", ".obsidian", "node_modules", ".venv", "__pycache__",
    ".zotero", "Zotero", ".antigravitycli", ".UTSystemConfig",
    "Claude", "Codex", "Manuscripts", "KOS-Inbox",
}


def find_claude_md_files(root: str) -> list[Path]:
    """查找所有 CLAUDE.md / claude.md 文件"""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fname in filenames:
            if fname in ("CLAUDE.md", "claude.md"):
                filepath = Path(dirpath) / fname
                if filepath.is_symlink():
                    continue  # 跳过符号链接
                files.append(filepath)
    return sorted(files)


def check_freshness(files: list[Path], max_age_days: int) -> dict:
    """检查每个文件的保鲜状态"""
    now = datetime.now()
    cutoff = now - timedelta(days=max_age_days)

    results = {
        "checked_at": now.isoformat(),
        "max_age_days": max_age_days,
        "total": len(files),
        "fresh": 0,
        "stale": 0,
        "files": [],
    }

    for fp in files:
        mtime = datetime.fromtimestamp(fp.stat().st_mtime)
        age_days = (now - mtime).days
        is_stale = mtime < cutoff

        entry = {
            "path": str(fp),
            "domain": _infer_domain(str(fp)),
            "mtime": mtime.strftime("%Y-%m-%d"),
            "age_days": age_days,
            "stale": is_stale,
        }

        if is_stale:
            results["stale"] += 1
        else:
            results["fresh"] += 1

        results["files"].append(entry)

    # 按 age_days 降序排列（最旧的在前）
    results["files"].sort(key=lambda x: x["age_days"], reverse=True)

    return results


def _infer_domain(path: str) -> str:
    """从路径推断功能域"""
    if "驾驶舱" in path:
        return "驾驶舱"
    if "学习进化" in path:
        return "Vault"
    if "工作文档" in path:
        return "工作域"
    if "领域知识库" in path:
        return "领域知识库"
    if "工具箱" in path:
        return "工具箱"
    if "家庭生活" in path:
        return "家庭域"
    if "CLAUDE_COWORK_GLOBAL" in path:
        return "L4 网关"
    return "未知"


def format_report(results: dict) -> str:
    """人类可读报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("  eCOS v5 — CLAUDE.md 保鲜检查报告")
    lines.append("=" * 60)
    lines.append(f"  检查时间: {results['checked_at'][:19]}")
    lines.append(f"  保鲜阈值: {results['max_age_days']} 天")
    lines.append(f"  扫描总数: {results['total']}")
    lines.append(f"  新鲜   : {results['fresh']} ✅")
    lines.append(f"  过期   : {results['stale']} {'⚠️' if results['stale'] > 0 else '✅'}")
    lines.append("")

    if results["stale"] > 0:
        lines.append("  ⚠️  过期文件:")
        lines.append("  " + "-" * 56)
        for f in results["files"]:
            if f["stale"]:
                lines.append(f"  [{f['domain']:8s}] {f['age_days']:4d}d  {f['path']}")
        lines.append("")

    # 按域汇总
    lines.append("  按域汇总:")
    lines.append("  " + "-" * 56)
    domains = {}
    for f in results["files"]:
        d = f["domain"]
        if d not in domains:
            domains[d] = {"total": 0, "stale": 0, "max_age": 0}
        domains[d]["total"] += 1
        if f["stale"]:
            domains[d]["stale"] += 1
        domains[d]["max_age"] = max(domains[d]["max_age"], f["age_days"])

    for domain in sorted(domains.keys()):
        d = domains[domain]
        status = "✅" if d["stale"] == 0 else "⚠️"
        lines.append(f"  {status} {domain:10s}  {d['total']:2d} 文件  "
                     f"过期 {d['stale']:1d}  最旧 {d['max_age']:3d}d")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 CLAUDE.md Freshness Checker")
    parser.add_argument("--max-age-days", type=int, default=60,
                        help="保鲜阈值（天），默认 60")
    parser.add_argument("--json", action="store_true",
                        help="JSON 格式输出")
    parser.add_argument("--root", type=str, default=DEFAULT_ROOT,
                        help="扫描根目录")
    args = parser.parse_args()

    root = os.path.expanduser(args.root)
    if not os.path.isdir(root):
        print(f"❌ 根目录不存在: {root}", file=sys.stderr)
        sys.exit(2)

    files = find_claude_md_files(root)
    results = check_freshness(files, args.max_age_days)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_report(results))

    # 退出码: 0 = 全部新鲜, 1 = 存在过期
    sys.exit(1 if results["stale"] > 0 else 0)


if __name__ == "__main__":
    main()
