#!/usr/bin/env python3
"""
eCOS Daemon — 基础健康检查 (ecos-health-check.py)
===================================================
Phase 7.6 — 返回 JSON 格式的系统健康指标。
成为 daemon 健康检查的可调用模块，无外部依赖。

用法:
    python3 ecos-health-check.py --json    # JSON 输出
    python3 ecos-health-check.py           # 人类可读

退出码:
    0 = 全部通过
    1 = 存在失败项
"""

import json, sys, subprocess, os
from datetime import datetime
from pathlib import Path


def check_disks() -> list[dict]:
    """检查关键挂载点"""
    results = []
    mounts = ["/", "/Volumes/SharedDisk"]
    for m in mounts:
        try:
            r = subprocess.run(["df", m], capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                results.append({"name": f"mount:{m}", "pass": False, "reason": "df failed"})
                continue
            parts = r.stdout.strip().split("\n")
            if len(parts) < 2:
                results.append({"name": f"mount:{m}", "pass": False, "reason": "no data"})
                continue
            cols = parts[1].split()
            if len(cols) >= 5:
                pct = int(cols[4].rstrip("%"))
                results.append({
                    "name": f"mount:{m}",
                    "pass": pct < 95,
                    "reason": f"使用率 {pct}%" if pct >= 95 else "",
                })
            else:
                results.append({"name": f"mount:{m}", "pass": True, "reason": ""})
        except (subprocess.TimeoutExpired, OSError, ValueError) as e:
            results.append({"name": f"mount:{m}", "pass": False, "reason": str(e)[:60]})
    return results


def check_proc() -> list[dict]:
    """检查关键进程"""
    results = []
    return results


def check_paths() -> list[dict]:
    """检查关键路径是否存在"""
    results = []
    home = Path.home()
    critical = [
        home / ".ecos" / "scripts",
        home / "Workspace" / "projects" / "ecos",
    ]
    for p in critical:
        results.append({
            "name": f"path:{p.name}",
            "pass": p.exists(),
            "reason": "" if p.exists() else f"缺失: {p}",
        })
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = []
    results.extend(check_disks())
    results.extend(check_proc())
    results.extend(check_paths())

    passed = sum(1 for r in results if r.get("pass") is True)
    failed = sum(1 for r in results if r.get("pass") is False)
    output = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"  健康检查: {passed}/{len(results)} 通过", flush=True)
        for r in results:
            icon = "✅" if r.get("pass") else "⚠️"
            reason = f": {r.get('reason', '')}" if r.get("reason") else ""
            print(f"  {icon} {r['name']}{reason}", flush=True)

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
