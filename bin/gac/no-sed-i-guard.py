#!/usr/bin/env python3
"""no-sed-i-guard — sed -i 禁令检测。

检测并阻止使用 sed -i 做添加/删除条目操作。
推荐用 Python read→check→modify→write 模式替代。

Usage:
    python3 bin/gac/no-sed-i-guard.py <file_or_dir> [--json]
    python3 bin/gac/no-sed-i-guard.py --staged [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 匹配真实命令中的 sed -i / sed --in-place 调用
SED_I_PATTERN = re.compile(r"\bsed\s+(-[a-zA-Z]*i|--in-place)\b|\bsed\s+-i[.\'\"=]")


def scan_content(content: str, path: Path) -> list[dict]:
    """扫描文件内容中的 sed -i 使用，剥离注释与 Python 文档字符串。"""
    if path.name == "no-sed-i-guard.py":
        return []

    is_py = path.suffix == ".py"
    in_multiline_str = False
    quote_char = ""
    violations = []

    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        # 1. 忽略纯单行注释
        if stripped.startswith("#"):
            continue

        # 2. Python 多行字符串/文档字符串处理
        if is_py:
            # 简易多行三引号处理
            if not in_multiline_str:
                for q in ('"""', "'''"):
                    if q in stripped:
                        count = stripped.count(q)
                        if count % 2 == 1:
                            in_multiline_str = True
                            quote_char = q
                            break
                if in_multiline_str:
                    continue
            else:
                if quote_char in stripped:
                    in_multiline_str = False
                continue

        # 3. 剥离行尾单行注释
        code_part = line
        if "#" in code_part:
            # 简化按非引号内的 # 截断，或最外层 \s+# 截断
            parts = re.split(r"\s+#", code_part, maxsplit=1)
            code_part = parts[0]

        # 4. 检测可疑调用
        if SED_I_PATTERN.search(code_part):
            violations.append({
                "file": str(path),
                "line": i,
                "content": stripped,
            })

    return violations


def scan_file(path: Path) -> list[dict]:
    """扫描单个文件。"""
    try:
        content = path.read_text(encoding="utf-8")
        return scan_content(content, path)
    except Exception:
        return []


def scan_staged() -> list[dict]:
    """扫描暂存区中的 .py 和 .sh 文件。"""
    violations = []
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return violations

        for rel in res.stdout.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            p = Path(rel)
            if p.suffix in (".py", ".sh", ".bash"):
                show = subprocess.run(
                    ["git", "show", f":{rel}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if show.returncode == 0:
                    violations.extend(scan_content(show.stdout, p))
    except Exception:
        pass
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="sed -i 禁令检测")
    parser.add_argument("target", nargs="?", default=None, help="文件或目录路径")
    parser.add_argument("--staged", action="store_true", help="扫描暂存区变更文件")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    violations = []

    if args.staged:
        violations = scan_staged()
    elif args.target:
        target = Path(args.target)
        if target.is_file():
            violations = scan_file(target)
        elif target.is_dir():
            for f in target.rglob("*.py"):
                violations.extend(scan_file(f))
            for f in target.rglob("*.sh"):
                violations.extend(scan_file(f))
            for f in target.rglob("*.bash"):
                violations.extend(scan_file(f))
    else:
        parser.print_help(sys.stderr)
        return 1

    result = {
        "ok": len(violations) == 0,
        "violations": len(violations),
        "details": violations,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if violations:
            print(f"❌ Found {len(violations)} sed -i violations:")
            for v in violations:
                print(f"  {v['file']}:{v['line']}: {v['content']}")
        else:
            print("✅ No sed -i violations found")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
