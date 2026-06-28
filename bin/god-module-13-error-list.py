#!/usr/bin/env python3
"""P94 R2 + P109-B: god-module error 文件清单 + 拆解建议 + 智能化.

P94 R2 原始功能:
- 14 个 >1500L error 文件清单
- 每个文件的拆解目标 (<800L warn 阈值)
- 拆解策略 (按函数/类)
- 优先级排序 (按行数从大到小)

P109-B 智能化扩展 (--auto-classify / --suggest-modules / --roadmap):
- --auto-classify: 按文件类型 + 拆解难度 + ROI 自动归类
- --suggest-modules: 基于 P104-P108 模式智能建议子模块拆分路径
- --roadmap: 输出 P100+ 风格 4-步拆解 roadmap (按 ROI 排序)

使用:
  python3 bin/god-module-13-error-list.py
  python3 bin/god-module-13-error-list.py --json
  python3 bin/god-module-13-error-list.py --auto-classify
  python3 bin/god-module-13-error-list.py --suggest-modules
  python3 bin/god-module-13-error-list.py --roadmap
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
IDEAL_THRESHOLD = 600
GOLDEN_THRESHOLD = 500


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


def analyze_ts(path: Path) -> dict:
    """P109-C: 调用 bin/ts-file-analyze.py 分析 TS 文件."""
    import subprocess
    try:
        r = subprocess.run(
            ["python3", str(Path(__file__).parent / "ts-file-analyze.py"), str(path), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return {"note": f"ts-file-analyze failed: {r.stderr[:200]}"}
        data = json.loads(r.stdout)
        # Convert to consistent format
        funcs = data.get("top_functions", [])
        classes = data.get("top_classes", [])
        return {
            "top_functions": [{"name": f["name"], "lines": f["lines"], "lineno": f["lineno"]} for f in funcs],
            "top_classes": [{"name": c["name"], "lines": c["lines"], "lineno": c["lineno"]} for c in classes],
            "total_units": len(funcs) + len(classes),
        }
    except Exception as e:
        return {"note": f"TS analysis failed: {e}"}


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
    elif full.suffix in (".ts", ".tsx", ".js", ".jsx") and full.exists():
        # P109-C: use ts-file-analyze for real structure analysis
        plan["analysis"] = analyze_ts(full)
    elif full.exists():
        plan["analysis"] = {"note": f"unsupported: {full.suffix}"}
    else:
        plan["analysis"] = {"note": "file not found (submodule not initialized? run git submodule update)"}
    return plan


# ============================================================
# P109-B 智能化扩展
# ============================================================

def classify_module(path: str, lines: int, analysis: dict | None) -> dict:
    """P109-B 智能归类: 按文件类型/拆解难度/ROI 分级.

    Returns:
        {
            "category": "python-omo" | "python-ecos" | "ts-gbrain" | "ts-other",
            "difficulty": "low" | "medium" | "high",
            "roi": "high" | "medium" | "low",
            "rationale": "<why>",
        }
    """
    # Category: which project / language (path is relative, no leading slash)
    if path.startswith("projects/omo/") or "/projects/omo/" in path:
        category = "python-omo"
    elif path.startswith("projects/ecos/") or "/projects/ecos/" in path:
        category = "python-ecos"
    elif path.startswith("projects/gbrain/") or "/projects/gbrain/" in path:
        category = "ts-gbrain"
    elif path.endswith((".ts", ".tsx")):
        category = "ts-other"
    elif path.endswith((".js", ".jsx")):
        category = "ts-other"
    else:
        category = "other"

    # Difficulty: based on analysis availability
    if analysis is None:
        difficulty = "unknown"
    elif analysis.get("note", "").startswith("TS 文件"):
        difficulty = "high"  # Need ts-morph tool first
    elif analysis.get("note", "").startswith("unsupported"):
        difficulty = "unknown"
    elif analysis.get("error"):
        difficulty = "unknown"
    else:
        # Python with valid AST
        top_funcs = analysis.get("top_functions", [])
        top_classes = analysis.get("top_classes", [])
        max_unit = max(
            [f["lines"] for f in top_funcs] + [0] +
            [c["lines"] for c in top_classes] + [0]
        )
        if max_unit > 300:
            difficulty = "high"  # God-functions inside
        elif max_unit > 150:
            difficulty = "medium"
        else:
            difficulty = "low"

    # ROI: based on category + excess
    excess = lines - WARN_THRESHOLD
    if category == "python-omo" and excess < 1000:
        roi = "high"  # Omo submodule, human approval rhythm OK
    elif category == "python-ecos":
        roi = "medium"  # Cross-submodule governance
    elif category == "ts-gbrain":
        roi = "low"  # Need ts-morph first
    else:
        roi = "low"

    # Rationale
    rationale_parts = [f"category={category}", f"difficulty={difficulty}", f"roi={roi}"]
    if category == "ts-gbrain":
        rationale_parts.append("blocked by ts-morph tool gap (P109-C 候选)")
    elif category == "python-ecos":
        rationale_parts.append("需 ecos submodule 治理节奏")
    elif category == "python-omo":
        rationale_parts.append("omo submodule 内, P104-P108 模式可复用")

    return {
        "category": category,
        "difficulty": difficulty,
        "roi": roi,
        "rationale": ", ".join(rationale_parts),
    }


def suggest_modules(path: str, lines: int, analysis: dict | None) -> list[dict]:
    """P109-B 智能建议: 基于 P104-P108 模式产出子模块拆分路径.

    Returns:
        list of {"phase": "P110", "child_module": "...", "split_lines": N, "rationale": "..."}
    """
    if analysis is None or not analysis.get("top_functions"):
        return []

    top_funcs = analysis["top_functions"][:5]
    excess = lines - WARN_THRESHOLD
    path_basename = Path(path).stem  # e.g. "omo_governance_surfaces"
    # Convert to module name: omo_governance_surfaces -> omo.governance_surfaces
    module_stem = path_basename.replace("_", ".").removeprefix("omo.")

    # Strategy: split top 2-3 functions into child modules
    # Each split: largest first, cumulative reduction
    suggestions = []
    cumulative_reduction = 0
    for i, func in enumerate(top_funcs[:3]):
        func_name = func["name"]
        func_lines = func["lines"]
        if func_lines < 50:
            break  # No more meaningful splits
        # Determine child module name
        child_suffix = func_name.replace("_", ".").replace("check.", "").replace("cmd.", "")
        # Extract semantic: _check_X → X, _mutation_surface_registry_snapshot → mutation_surface.snapshot
        if func_name.startswith("_check_"):
            child_name = func_name[len("_check_"):]
        elif func_name.startswith("cmd_"):
            child_name = func_name[len("cmd_"):]
        else:
            child_name = func_name.lstrip("_")
        child_module = f"omo_{path_basename}_{child_name}"
        phase = f"P{110 + i}"

        cumulative_reduction += func_lines
        rationale = f"P104-P108 模式: 拆 {func_name}({func_lines}L) → {child_module}.py"
        suggestions.append({
            "phase": phase,
            "child_module": child_module,
            "split_function": func_name,
            "split_lines": func_lines,
            "cumulative_reduction": cumulative_reduction,
            "resulting_lines": lines - cumulative_reduction,
            "rationale": rationale,
        })
    return suggestions


def make_roadmap(errors: list[dict]) -> list[dict]:
    """P109-B 4-步 roadmap: 按 ROI 排序.

    Returns:
        list of {"step": 1, "phase": "P110", "target": "...", "rationale": "..."}
    """
    # Sort errors by ROI: high > medium > low
    roi_rank = {"high": 0, "medium": 1, "low": 2}
    classified = []
    for e in errors:
        cls = classify_module(e["path"], e["lines"], e.get("analysis"))
        classified.append({**e, "classification": cls})

    classified.sort(key=lambda x: (roi_rank.get(x["classification"]["roi"], 3), -x["lines"]))

    roadmap = []
    step = 1
    for c in classified[:8]:  # Top 8 god-modules
        cls = c["classification"]
        roadmap.append({
            "step": step,
            "phase": f"P{109 + step}",
            "target": c["path"],
            "current_lines": c["lines"],
            "category": cls["category"],
            "difficulty": cls["difficulty"],
            "roi": cls["roi"],
            "rationale": cls["rationale"],
        })
        step += 1
    return roadmap


def main() -> int:
    parser = argparse.ArgumentParser(description="P94 R2 + P109-B: god-module 13 error list")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--auto-classify", action="store_true",
                        help="P109-B: 按 category/difficulty/ROI 智能归类")
    parser.add_argument("--suggest-modules", action="store_true",
                        help="P109-B: 基于 P104-P108 模式建议子模块拆分路径")
    parser.add_argument("--roadmap", action="store_true",
                        help="P109-B: 输出 4-步 roadmap (按 ROI 排序)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    modules = list_god_modules(root)
    errors = [m for m in modules if m["severity"] == "error"]
    plans = [make_plan(m, root) for m in errors]

    # Inject analysis into modules dict for classify_module
    for i, m in enumerate(errors):
        m["analysis"] = plans[i].get("analysis")

    if args.json:
        print(json.dumps({
            "total_errors": len(errors),
            "total_warns": len(modules) - len(errors),
            "plans": plans,
        }, indent=2, ensure_ascii=False))
        return 0

    # P109-B: roadmap mode
    if args.roadmap:
        roadmap = make_roadmap(errors)
        print("=" * 60)
        print("🗺️  P109-B god-module 4-步 roadmap (按 ROI 排序)")
        print("=" * 60)
        for step in roadmap:
            print(f"  {step['step']}. {step['phase']}: {step['target']}")
            print(f"     {step['current_lines']}L | {step['category']} | {step['difficulty']} | ROI: {step['roi']}")
            print(f"     💡 {step['rationale']}")
            print()
        return 0

    # P109-B: suggest-modules mode
    if args.suggest_modules:
        print("=" * 60)
        print("🧩 P109-B 子模块拆分建议 (基于 P104-P108 模式)")
        print("=" * 60)
        for p in plans:
            suggestions = suggest_modules(p["path"], p["current_lines"], p.get("analysis"))
            if not suggestions:
                continue
            print(f"\n🔴 {p['path']} ({p['current_lines']}L)")
            for s in suggestions:
                print(f"  → {s['phase']}: {s['child_module']}")
                print(f"    split: {s['split_function']}({s['split_lines']}L)")
                print(f"    result: {s['resulting_lines']}L ({s['cumulative_reduction']}L reduced)")
        return 0

    # P109-B: auto-classify mode
    if args.auto_classify:
        print("=" * 60)
        print("🏷️  P109-B god-module 智能归类 (category / difficulty / ROI)")
        print("=" * 60)
        classified = [(p, classify_module(p["path"], p["current_lines"], p.get("analysis"))) for p in plans]
        # Group by ROI
        for roi in ["high", "medium", "low"]:
            items = [(p, c) for p, c in classified if c["roi"] == roi]
            if not items:
                continue
            print(f"\n📊 ROI: {roi.upper()} ({len(items)} files)")
            for p, c in items:
                print(f"  • {p['path']} ({p['current_lines']}L, excess {p['excess']}L)")
                print(f"    category={c['category']} difficulty={c['difficulty']}")
                print(f"    💡 {c['rationale']}")
        return 0

    # Default: P94 R2 original behavior
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
    print()
    print("🆕 P109-B 扩展:")
    print("   --auto-classify:  按 ROI 智能归类")
    print("   --suggest-modules: 基于 P104-P108 模式建议子模块拆分路径")
    print("   --roadmap:        输出 4-步 roadmap (按 ROI 排序)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
