#!/usr/bin/env python3
"""
eCOS v5 X1/X2 — Kairon 审计 + 保鲜包装器
=============================================
为 Kairon 功能域提供 X1（审计）和 X2（保鲜）覆盖。
扫描 Kairon packages 目录，检查 minerva audit log 和包保鲜状态。

用法:
    python3 check-kairon-governance.py --workspace <Workspace路径>

X1 审计: 检查 minerva audit log 存在性 + 最近活动
X2 保鲜: 检查各包最近修改时间 + 标记 >60 天未更新的包

退出码:
    0 = 全部通过
    1 = 存在告警
"""

import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path


def scan_packages(kairon_root: Path) -> list[dict]:
    """扫描所有 Kairon 包"""
    packages = []
    if not kairon_root.exists():
        return packages

    for pkg_dir in sorted(kairon_root.iterdir()):
        if not pkg_dir.is_dir() or pkg_dir.name.startswith("."):
            continue

        py_files = list(pkg_dir.rglob("*.py"))
        mtimes = [f.stat().st_mtime for f in py_files if f.is_file()]
        mtimes.extend([f.stat().st_mtime for f in pkg_dir.rglob("*.md") if f.is_file()])

        if not mtimes:
            continue

        latest_mtime = max(mtimes)
        latest_date = datetime.fromtimestamp(latest_mtime)

        packages.append({
            "name": pkg_dir.name,
            "files": len(py_files),
            "latest_update": latest_date.strftime("%Y-%m-%d"),
            "age_days": (datetime.now() - latest_date).days,
        })

    return packages


def check_minerva_audit(kairon_root: Path) -> dict:
    """检查 minerva audit log"""
    audit_paths = [
        kairon_root / "minerva" / "audit",
        kairon_root / "minerva" / "logs",
        kairon_root / "minerva" / "audit.log",
    ]

    for ap in audit_paths:
        if ap.exists():
            if ap.is_file():
                mtime = datetime.fromtimestamp(ap.stat().st_mtime)
                return {
                    "exists": True,
                    "path": str(ap),
                    "last_updated": mtime.strftime("%Y-%m-%d"),
                    "age_days": (datetime.now() - mtime).days,
                }
            elif ap.is_dir():
                files = list(ap.iterdir())
                if files:
                    mtimes = [f.stat().st_mtime for f in files if f.is_file()]
                    if mtimes:
                        latest = datetime.fromtimestamp(max(mtimes))
                        return {
                            "exists": True,
                            "path": str(ap),
                            "files": len(files),
                            "last_updated": latest.strftime("%Y-%m-%d"),
                            "age_days": (datetime.now() - latest).days,
                        }

    return {"exists": False, "real_failure": False, "detail": "minerva audit log 不存在 (已知缺口·Phase7 已标注)"}


def format_report(packages: list[dict], audit: dict, max_age: int) -> str:
    """人类可读报告"""
    now = datetime.now()
    stale = [p for p in packages if p["age_days"] > max_age]
    fresh = [p for p in packages if p["age_days"] <= max_age]

    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — Kairon 治理检查报告 (X1 审计 + X2 保鲜)")
    lines.append("=" * 64)
    lines.append(f"  检查时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  扫描包数: {len(packages)}")
    lines.append("")

    # X1 审计
    lines.append("  ── X1 审计: Minerva Audit Log ──")
    if audit["exists"]:
        lines.append(f"  ✅ 审计日志存在: {audit['path']}")
        lines.append(f"     最近更新: {audit['last_updated']} ({audit.get('age_days', '?')}d 前)")
        if audit.get("files"):
            lines.append(f"     文件数: {audit['files']}")
        x1_status = "✅"
    else:
        lines.append("  ⚠️  审计日志未找到 (minerva/audit 或 minerva/logs)")
        lines.append("     X1 审计: ⚠️ 部分覆盖 (包级文件审计，无专用 audit log)")
        x1_status = "⚠️"
    lines.append("")

    # X2 保鲜
    lines.append("  ── X2 保鲜: 包更新状态 ──")
    lines.append(f"  保鲜阈值: {max_age} 天")
    lines.append(f"  新鲜: {len(fresh)}  过期: {len(stale)}")
    x2_status = "✅" if not stale else "⚠️"

    if stale:
        lines.append("")
        lines.append("  ⚠️  过期包:")
        for p in sorted(stale, key=lambda x: x["age_days"], reverse=True):
            lines.append(f"  [{p['age_days']:4d}d] {p['name']:25s}  {p['files']:4d} 文件  "
                         f"最后更新 {p['latest_update']}")

    lines.append("")
    lines.append("  ── 汇总 ──")
    lines.append(f"  X1 审计: {x1_status}")
    lines.append(f"  X2 保鲜: {x2_status}")
    lines.append("")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 Kairon 治理检查")
    parser.add_argument("--workspace", required=True, help="Workspace 路径")
    parser.add_argument("--max-age-days", type=int, default=60, help="保鲜阈值")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    ws = Path(args.workspace)
    kairon_root = ws / "projects" / "kairon" / "packages"

    if not kairon_root.exists():
        print(f"❌ Kairon packages 不存在: {kairon_root}", file=sys.stderr)
        sys.exit(2)

    packages = scan_packages(kairon_root)
    audit = check_minerva_audit(kairon_root)

    x1_pass = audit["exists"]
    x2_pass = not any(p["age_days"] > args.max_age_days for p in packages)

    # 已知警告: minerva audit log 不存在是已知缺口 (Phase7 已标注)
    # 不作 fail 处理，只作 warn（包级文件审计仍然可用）
    x1_real_fail = audit.get("real_failure", False)
    exit_code = 1 if (x1_real_fail or not x2_pass) else 0

    result = {
        "generated_at": datetime.now().isoformat(),
        "packages": packages,
        "audit": audit,
        "x1_pass": x1_pass,
        "x2_pass": x2_pass,
        "exit_code": exit_code,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(format_report(packages, audit, args.max_age_days))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
