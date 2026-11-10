#!/usr/bin/env python3
"""CR-P76-7-1-LLM-ADVISORY-ONLY: 检查 LLM 是否只 generate suggestion, 不 auto-apply.

检查项目中是否存在 auto-apply 模式（如自动 git commit/push 等），
防止 LLM 绕过人工审核直接执行写操作。

已知限制（见 .omo/debt/items/LLM-ADVISORY-ONLY-STRING-AND-SH-COVERAGE.yaml）:
- 字符串字面量里的命令文本一律算命中（保守口径）: `return "git push --force"` 与
  `os.system("git push --force")` 同形, 本检查器不区分 —— 要区分需按 AST 判定
  「字符串是否处于被调用位置」, 见登记条目。
- 只扫 `*.py`: shell 脚本里的 `git commit --no-verify` 不在覆盖范围内; 而
  `bin/gac/swarm-git`（含 --no-verify fail-closed 守卫）正是 .sh, 扩面前需先设计白名单。
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 需要警惕的 auto-apply 模式
AUTO_APPLY_PATTERNS = [
    r"git\s+(commit|push)\s+--no-verify",
    r"git\s+commit\s+-a.*-m\s",
    r"git\s+push\s+--force",
    r"subprocess\.run\(\[.*git.*commit",
    r"os\.system\(.*git.*commit",
]


def _strip_comments_and_docstrings(path: Path) -> str:
    """抹掉注释与 docstring，但**保留**字符串字面量。

    与 `check-llm-tier-fallback` 的 `_code_only`（抹掉所有字符串）刻意不同：
    本规则的判据本身要匹配字符串里的命令文本（`subprocess.run(["git","commit"])`
    / `os.system("git commit ...")`），抹掉字符串会把真违规一并抹没。
    而注释 / docstring 里写 `git commit --no-verify` 只是文字 —— 旧实现对此
    照报不误，实测（2026-11-11）注释与 docstring 各产生一条误报。

    行号保持不变（docstring 跨度替换为等量换行），故报出的行号仍指向原文件。
    """
    src = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return re.sub(r"#.*", "", src)
    lines = src.splitlines(keepends=True)

    def offset(lineno: int, col: int) -> int:
        return sum(len(ln) for ln in lines[: lineno - 1]) + col

    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                doc = body[0]
                spans.append((doc.lineno, doc.col_offset, doc.end_lineno, doc.end_col_offset or 0))
    for sl, sc, el, ec in sorted(spans, key=lambda s: (s[0], s[1]), reverse=True):
        start, end = offset(sl, sc), offset(el, ec)
        src = src[:start] + "\n" * src.count("\n", start, end) + src[end:]

    try:
        return "".join(
            tok.string for tok in tokenize.generate_tokens(io.StringIO(src).readline) if tok.type != tokenize.COMMENT
        )
    except Exception:
        return re.sub(r"#.*", "", src)


def main() -> int:
    violations = []
    checked = 0

    for py_file in sorted(REPO_ROOT.rglob("*.py")):
        rel = py_file.relative_to(REPO_ROOT)
        # 跳过无关目录
        skip_dirs = {
            ".venv",
            "__pycache__",
            "node_modules",
            "build",
            ".git",
            "_archived",
            "tests",
            "test",
        }
        # 也跳过 tests/ 目录
        if "tests" in rel.parts:
            continue
        if any(d in rel.parts for d in skip_dirs):
            continue
        try:
            text = _strip_comments_and_docstrings(py_file)
        except Exception:
            continue

        for pattern in AUTO_APPLY_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                line = text[: m.start()].count("\n") + 1
                violations.append(f"  {rel}:{line} — {m.group()[:60]}")
                checked += 1

    if violations:
        print(f"FAIL 发现 {len(violations)} 处 auto-apply 模式:")
        for v in violations:
            print(v)
        return 1

    print("OK 未发现 auto-apply 模式")
    return 0


if __name__ == "__main__":
    sys.exit(main())
