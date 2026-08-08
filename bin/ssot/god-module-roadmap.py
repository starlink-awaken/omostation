#!/usr/bin/env python3
"""P87 R1: god-module refactor roadmap tool.

读取超大文件, 解析其结构 (top-level 函数/类), 输出拆解 roadmap:
- 函数列表 (按行数排序, 标 top candidates for extraction)
- 类列表
- import 依赖 (找出外部依赖最少的子集, 适合先拆)
- 建议拆解步骤 (优先拆纯函数 + 小依赖, 大类放后面)

使用:
  python3 bin/ssot/god-module-roadmap.py <file_path>
  python3 bin/ssot/god-module-roadmap.py <file_path> --top 10
  python3 bin/ssot/god-module-roadmap.py <file_path> --json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

# TS 简单解析 (正则启发式)
TS_FUNCTION_PATTERNS = [
    re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\("),
    re.compile(r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(.*?\)\s*=>"),
    re.compile(r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function"),
]
TS_CLASS_PATTERN = re.compile(r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)")


def parse_python(path: Path) -> dict:
    """解析 Python 文件, 返回结构 (top-level only)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return {"error": f"Python 解析失败: {e}"}
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # top-level: 只看 tree.body
    functions: list[dict] = []
    classes: list[dict] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n_lines = (node.end_lineno or node.lineno) - node.lineno + 1
            n_args = len(node.args.args)
            has_doc = bool(
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            functions.append({
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": node.end_lineno,
                "lines": n_lines,
                "args": n_args,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "has_docstring": has_doc,
            })
        elif isinstance(node, ast.ClassDef):
            n_lines = (node.end_lineno or node.lineno) - node.lineno + 1
            n_methods = sum(1 for n in node.body
                            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
            classes.append({
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": node.end_lineno,
                "lines": n_lines,
                "methods": n_methods,
                "bases": [ast.unparse(b) for b in node.bases],
            })

    # imports (递归, 因为 import 可在 try 内)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for n in node.names:
                imports.append(f"{mod}.{n.name}" if mod else n.name)

    return {
        "language": "python",
        "total_lines": len(lines),
        "functions": sorted(functions, key=lambda x: -x["lines"]),
        "classes": sorted(classes, key=lambda x: -x["lines"]),
        "imports": sorted(set(imports)),
        "import_count": len(imports),
    }


def parse_typescript(path: Path) -> dict:
    """简化 TS 解析 (正则启发式)."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    functions: list[dict] = []
    classes: list[dict] = []
    imports: list[str] = []

    brace_depth = 0
    in_block_comment = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "/*" in stripped and "*/" not in stripped:
            in_block_comment = True
            continue
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("//"):
            continue

        brace_depth += stripped.count("{") - stripped.count("}")

        if stripped.startswith("import "):
            m = re.search(r"from\s+['\"]([^'\"]+)['\"]", stripped)
            if m:
                imports.append(m.group(1))

        if brace_depth <= 1:
            for pat in TS_FUNCTION_PATTERNS:
                m = pat.match(stripped)
                if m:
                    functions.append({
                        "name": m.group(1),
                        "lineno": i,
                        "lines": 0,
                        "args": stripped.count(",") + 1 if "(" in stripped else 0,
                    })
                    break
            m = TS_CLASS_PATTERN.match(stripped)
            if m:
                classes.append({
                    "name": m.group(1),
                    "lineno": i,
                    "lines": 0,
                    "methods": 0,
                    "bases": [],
                })

    return {
        "language": "typescript",
        "total_lines": len(lines),
        "functions": functions,
        "classes": classes,
        "imports": sorted(set(imports)),
        "import_count": len(imports),
    }


def build_roadmap(structure: dict, top_n: int) -> dict:
    """根据文件结构, 生成拆解 roadmap."""
    if "error" in structure:
        return structure

    funcs = structure["functions"]
    classes = structure["classes"]
    total_lines = structure["total_lines"]
    import_count = structure["import_count"]

    # 找出"小依赖"函数 (args 少, 容易先拆)
    candidates = []
    for f in funcs[:top_n]:
        priority_score = (
            (50 if f.get("lines", 0) > 0 and f["lines"] < 100 else 0)
            + (30 if f.get("has_docstring") else 0)
            + (20 if f.get("args", 0) <= 2 else 0)
        )
        candidates.append({**f, "priority": priority_score})
    candidates.sort(key=lambda x: -x["priority"])

    steps: list[str] = []
    if import_count > 30:
        steps.append(f"Step 1: 拆分 imports ({import_count} 个, 可分组: 标准库/第三方/项目内)")
    if classes:
        biggest = max(classes, key=lambda c: c.get("lines", 0))
        steps.append(f"Step 2: 拆最大类 `{biggest['name']}` ({biggest.get('lines', 0)}L, "
                     f"{biggest.get('methods', 0)} 方法)")
    if funcs:
        standalone = [f for f in funcs if f.get("lines", 0) > 0 and f["lines"] < 100]
        if standalone:
            steps.append(f"Step 3: 提取 {len(standalone)} 个小函数到独立模块 "
                         f"(优先: {', '.join(f['name'] for f in standalone[:3])})")
    steps.append("Step 4: 验证 import + test 通过, 提交并更新 god-module 检测")
    steps.append("Step 5: 循环 Step 1-4 直至 <1500L (error) / <800L (warn)")

    return {
        "structure_summary": {
            "language": structure["language"],
            "total_lines": total_lines,
            "function_count": len(funcs),
            "class_count": len(classes),
            "import_count": import_count,
        },
        "top_functions": funcs[:top_n],
        "top_classes": classes[:top_n],
        "candidates": candidates[:top_n],
        "steps": steps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P87: god-module refactor roadmap")
    parser.add_argument("file", help="god-module 文件路径")
    parser.add_argument("--top", type=int, default=10, help="top N candidates")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ 文件不存在: {path}")
        return 1

    if path.suffix == ".py":
        structure = parse_python(path)
    elif path.suffix in (".ts", ".tsx", ".js", ".jsx"):
        structure = parse_typescript(path)
    else:
        print(f"❌ 不支持的文件类型: {path.suffix}")
        return 1

    if "error" in structure:
        print(f"❌ {structure['error']}")
        return 1

    roadmap = build_roadmap(structure, args.top)

    if args.json:
        print(json.dumps(roadmap, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print(f"🔨 P87 god-module refactor roadmap: {path}")
    print("=" * 60)
    summary = roadmap["structure_summary"]
    print(f"📊 语言: {summary['language']}")
    print(f"📏 总行数: {summary['total_lines']}")
    print(f"🔧 函数: {summary['function_count']}")
    print(f"📦 类: {summary['class_count']}")
    print(f"📥 导入: {summary['import_count']}")
    print()

    if roadmap["top_classes"]:
        print("📦 最大的类 (top):")
        for c in roadmap["top_classes"][:args.top]:
            lines = c.get("lines", 0)
            methods = c.get("methods", 0)
            print(f"   {c['name']:<40s} line={c['lineno']:>5d}  lines={lines:>4d}  methods={methods}")
        print()

    if roadmap["top_functions"]:
        print("🔧 最大的函数 (top):")
        for f in roadmap["top_functions"][:args.top]:
            lines = f.get("lines", 0)
            args_n = f.get("args", 0)
            print(f"   {f['name']:<40s} line={f['lineno']:>5d}  lines={lines:>4d}  args={args_n}")
        print()

    if roadmap["candidates"]:
        print("⭐ 优先拆解 candidates (按 priority):")
        for c in roadmap["candidates"]:
            print(f"   priority={c['priority']:>3d}  {c['name']:<40s} line={c['lineno']:>5d}")
        print()

    print("🛠️  拆解步骤建议:")
    for step in roadmap["steps"]:
        print(f"   {step}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
