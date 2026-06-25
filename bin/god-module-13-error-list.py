#!/usr/bin/env python3
"""P94 R2: god-module 13 error 文件清单 + 拆解建议.

读取 check-god-module.py 输出 (--strict), 输出:
- 14 个 >1500L error 文件清单
- 每个文件的拆解目标 (<800L warn 阈值)
- 拆解策略 (按函数/类)
- 优先级排序 (按行数从大到小)

使用:
  python3 bin/god-module-13-error-list.py
  python3 bin/god-module-13-error-list.py --json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

WARN_THRESHOLD = 800
ERROR_THRESHOLD = 1500


def list_god_modules(root: Path) -> list[dict]:
    """读取 check-god-module.py 输出."""
    r = subprocess.run(
        ["python3", str(root / "bin" / "check-god-module.py"), "--strict"],
        cwd=str(root), capture_output=True, text=True, timeout=30,
    )
    modules: list[dict] = []
    for line in r.stdout.splitlines():
        m = re.match(r"\s*(\d+)L\s+(\S+)", line)
        if m:
            lines_count = int(m.group(1))
            path = m.group(2)
            if lines_count > ERROR_THRESHOLD:
                modules.append({"path": path, "lines": lines_count, "severity": "error"})
            elif lines_count > WARN_THRESHOLD:
                modules.append({"path": path, "lines": lines_count, "severity": "warn"})
    modules.sort(key=lambda x: -x["lines"])
    return modules


def analyze_py(path: Path) -> dict:
    """分析 Python 文件, 给拆解建议."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return {"error": "parse failed"}

    funcs: list[dict] = []
    classes: list[dict] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            n = (node.end_lineno or node.lineno) - node.lineno + 1
            funcs.append({"name": node.name, "lines": n, "lineno": node.lineno})
        elif isinstance(node, ast.ClassDef):
            n = (node.end_lineno or node.lineno) - node.lineno + 1
            classes.append({"name": node.name, "lines": n, "lineno": node.lineno})
    funcs.sort(key=lambda x: -x["lines"])
    classes.sort(key=lambda x: -x["lines"])
    return {
        "top_functions": funcs[:5],
        "top_classes": classes[:5],
    }


def make_plan(mod: dict, root: Path) -> dict:
    """生成拆解 plan."""
    full = root / mod["path"]
    plan = {
        "path": mod["path"],
        "current_lines": mod["lines"],
        "target_lines": WARN_THRESHOLD,
        "excess": mod["lines"] - WARN_THRESHOLD,
        "severity": mod["severity"],
    }
    if full.suffix == ".py" and full.exists():
        plan["analysis"] = analyze_py(full)
    elif full.suffix in (".ts", ".tsx", ".js", ".jsx"):
        plan["analysis"] = {"note": "TS 文件需用 TypeScript AST 工具分析 (ts-morph), 暂用 line count"}
    else:
        plan["analysis"] = {"note": f"unsupported: {full.suffix}"}
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="P94: god-module 13 error list")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    modules = list_god_modules(root)
    errors = [m for m in modules if m["severity"] == "error"]
    plans = [make_plan(m, root) for m in errors]

    if args.json:
        print(json.dumps({
            "total_errors": len(errors),
            "total_warns": len(modules) - len(errors),
            "plans": plans,
        }, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print(f"📦 P94 god-module {len(errors)} error 文件清单")
    print("=" * 60)
    print(f"🔴 Error: {len(errors)} (>1500L)")
    print(f"🟡 Warn:  {len(modules) - len(errors)} (800-1500L)")
    print()
    total_excess = sum(p["excess"] for p in plans)
    print(f"📉 Total excess: {total_excess}L 需拆解")
    print()
    for p in plans:
        print(f"🔴 {p['path']}")
        print(f"   {p['current_lines']}L → {p['target_lines']}L  (excess {p['excess']}L)")
        if "analysis" in p:
            analysis = p["analysis"]
            if analysis.get("error"):
                print(f"   ⚠️  {analysis['error']}")
            elif analysis.get("note"):
                print(f"   📝 {analysis['note']}")
            else:
                if analysis.get("top_functions"):
                    func_strs = [f["name"] + f"({f['lines']}L)" for f in analysis["top_functions"][:3]]
                    print(f"   Top 函数: {', '.join(func_strs)}")
                if analysis.get("top_classes"):
                    cls_strs = [f["name"] + f"({f['lines']}L)" for f in analysis["top_classes"][:3]]
                    print(f"   Top 类: {', '.join(cls_strs)}")
        print()

    print("🛠️  整体拆解策略 (P94+ 推进):")
    print("   1. 按 P89 roadmap: 先 schemas (432L) → surfaces (136L) → mutation_ledger (56L)")
    print("   2. 配合 X2-FRESH-OMO-LINT-SIZE (P90) 持续监督")
    print("   3. 每 P 阶段拆 1 个子模块, 降低单次变更面")
    print("   4. 拆完提交到 omo submodule, 由 omostation 人类审批")
    return 0


if __name__ == "__main__":
    sys.exit(main())
