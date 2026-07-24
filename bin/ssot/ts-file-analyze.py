#!/usr/bin/env python3
"""
ts-file-analyze.py — P110-D: TS god-module 真实结构分析器 (TypeScript Compiler API)

原 P109-C 工具用 regex 估算 (~80% 精度), P110-D 升级为真实 TypeScript AST 解析 (~100% 精度).

内部调用 bin/ssot/ts-analyze.mjs (Node.js) 使用 TypeScript Compiler API.
失败时 fallback 到 P109-C 的 regex 估算 (graceful degradation).

用法:
  python3 bin/ssot/ts-file-analyze.py <file.ts>          # 详细分析
  python3 bin/ssot/ts-file-analyze.py <file.ts> --top 5   # top 5 函数
  python3 bin/ssot/ts-file-analyze.py --batch <dir>         # 批量分析

退出码:
  0 = success (real AST or fallback)
  1 = error (file not found)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Real TS AST tool (P110-D, requires Node.js + gbrain's typescript)
TS_AST_TOOL = Path(__file__).parent / "ts-analyze.mjs"

# P109-C fallback: regex-based estimation
RE_FUNCTION = re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(", re.MULTILINE)
RE_CLASS = re.compile(r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE)
RE_INTERFACE = re.compile(r"^(?:export\s+)?interface\s+(\w+)", re.MULTILINE)


def find_block_end(lines: list[str], start_idx: int) -> int:
    """找匹配的右大括号 (P109-C 复用)."""
    depth = 0
    in_string = None
    in_line_comment = False
    in_block_comment = False
    for i in range(start_idx, len(lines)):
        line = lines[i]
        j = 0
        while j < len(line):
            ch = line[j]
            if in_line_comment:
                break
            if in_block_comment:
                if ch == "*" and j + 1 < len(line) and line[j+1] == "/":
                    in_block_comment = False
                    j += 2
                    continue
                j += 1
                continue
            if in_string:
                if ch == "\\":
                    j += 2
                    continue
                if ch == in_string:
                    in_string = None
                j += 1
                continue
            if ch == "/" and j + 1 < len(line):
                if line[j+1] == "/":
                    in_line_comment = True
                    break
                elif line[j+1] == "*":
                    in_block_comment = True
                    j += 2
                    continue
            if ch in ('"', "'", "`"):
                in_string = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
            j += 1
        in_line_comment = False
    return len(lines) - 1


def analyze_ts_p109_fallback(path: Path) -> dict:
    """P109-C regex-based fallback (~80% precision)."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return {"error": str(e)}
    lines = text.splitlines()
    functions = []
    classes = []
    interfaces = []
    for m in RE_FUNCTION.finditer(text):
        name = m.group(1)
        line_no = text[:m.start()].count("\n") + 1
        brace_pos = text.find("{", m.end())
        if brace_pos < 0:
            continue
        brace_line = text[:brace_pos].count("\n") + 1
        block_end_line = find_block_end(lines, brace_line - 1) + 1
        functions.append({"name": name, "lines": block_end_line - line_no + 1, "lineno": line_no})
    for m in RE_CLASS.finditer(text):
        name = m.group(1)
        line_no = text[:m.start()].count("\n") + 1
        brace_pos = text.find("{", m.end())
        if brace_pos < 0:
            continue
        brace_line = text[:brace_pos].count("\n") + 1
        block_end_line = find_block_end(lines, brace_line - 1) + 1
        classes.append({"name": name, "lines": block_end_line - line_no + 1, "lineno": line_no})
    for m in RE_INTERFACE.finditer(text):
        name = m.group(1)
        line_no = text[:m.start()].count("\n") + 1
        brace_pos = text.find("{", m.end())
        if brace_pos < 0:
            interfaces.append({"name": name, "lines": 1, "note": "no body"})
            continue
        brace_line = text[:brace_pos].count("\n") + 1
        block_end_line = find_block_end(lines, brace_line - 1) + 1
        interfaces.append({"name": name, "lines": block_end_line - line_no + 1, "lineno": line_no})
    functions.sort(key=lambda x: -x["lines"])
    classes.sort(key=lambda x: -x["lines"])
    interfaces.sort(key=lambda x: -x["lines"])
    return {
        "path": str(path),
        "total_lines": len(lines),
        "functions": functions,
        "classes": classes,
        "interfaces": interfaces,
        "top_functions": functions[:20],
        "top_classes": classes[:20],
        "ast_source": "regex_fallback_p109",
    }


def analyze_ts_real_ast(path: Path) -> dict | None:
    """P110-D: call ts-analyze.mjs (real TypeScript Compiler API)."""
    if not TS_AST_TOOL.exists():
        return None
    try:
        result = subprocess.run(
            ["node", str(TS_AST_TOOL), str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        if isinstance(data, list) and len(data) >= 1:
            return data[0]
        return None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None


def analyze_ts(path: Path) -> dict:
    """Analyze TS file, prefer real AST, fallback to regex."""
    real = analyze_ts_real_ast(path)
    if real is not None and "error" not in real:
        return {
            "path": real["path"],
            "total_lines": real["total_lines"],
            "top_functions": [{"name": f["name"], "lines": f["lines"], "lineno": f.get("lineno", 0)} for f in real.get("top_functions", [])],
            "top_classes": [{"name": c["name"], "lines": c["lines"], "lineno": c.get("lineno", 0)} for c in real.get("top_classes", [])],
            "top_interfaces": [{"name": i["name"], "lines": i["lines"], "lineno": i.get("lineno", 0)} for i in real.get("top_interfaces", [])],
            "ast_source": "typescript_compiler_api",
        }
    result = analyze_ts_p109_fallback(path)
    result["ast_source"] = result.get("ast_source", "regex_fallback_p109")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P110-D: TS god-module real structure analyzer (TypeScript Compiler API + P109-C regex fallback)."
    )
    parser.add_argument("path", help="TS file or directory")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"FAIL: {path} not found")
        return 1

    if args.batch:
        ts_files = sorted(path.rglob("*.ts"))
        results = [analyze_ts(f) for f in ts_files]
        if args.json:
            print(json.dumps(results, indent=2))
            return 0
        for r in results[:20]:
            if "error" in r:
                continue
            top_func = r["top_functions"][0] if r["top_functions"] else None
            hint = f"top fn: {top_func['name']}({top_func['lines']}L)" if top_func else ""
            print(f"  {r['total_lines']}L {r['path']}  {hint}  [{r.get('ast_source', '?')}]")
        return 0

    result = analyze_ts(path)
    if "error" in result:
        print(f"FAIL: {result['error']}")
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"FILE: {result['path']} ({result['total_lines']}L, ast={result.get('ast_source', '?')})")
    if result.get("top_functions"):
        print(f"\nTop {args.top} Functions:")
        for f in result["top_functions"][:args.top]:
            print(f"  {f['name']:40s} L{f['lineno']:4d} ({f['lines']}L)")
    if result.get("top_classes"):
        print(f"\nTop {args.top} Classes:")
        for c in result["top_classes"][:args.top]:
            print(f"  {c['name']:40s} L{c['lineno']:4d} ({c['lines']}L)")
    if result.get("top_interfaces"):
        print(f"\nTop {args.top} Interfaces:")
        for i in result["top_interfaces"][:args.top]:
            print(f"  {i['name']:40s} L{i['lineno']:4d} ({i['lines']}L)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
