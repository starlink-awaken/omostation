#!/usr/bin/env python3
"""CR-P76-9A-4-HEURISTIC-DEFAULT: 检查脚本是否有 --no-llm 或启发式 fallback.

确保本地工具不强制依赖外部 LLM 服务，有 --no-llm 或 heuristic fallback 选项。
"""

import ast
import re
import sys
from pathlib import Path


def _code_only(path: Path) -> str:
    """只保留代码：抹掉 docstring、所有字符串常量与注释。

    「有没有 LLM 调用」是代码属性; 注释/docstring 里出现 `import openai` /
    `from openai import ...` 只是文字。旧实现注释自称「排除正则/注释/子模块
    列表误匹配」但实际对全文跑正则 —— 实测：注释里写 `import openai` 或
    docstring 里写 `from openai import Client` 的文件会被判成「使用 LLM」，
    在没有 fallback 时误报（2026-11-11 自证）。
    """
    src = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return re.sub(r"#.*", "", src)
    lines = src.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for i in range(node.lineno - 1, node.end_lineno):
                if 0 <= i < len(lines):
                    lines[i] = ""

    return re.sub(r"#.*", "", "".join(lines))


LLM_CALL_PATTERNS = [
    r"llm\.(complete|generate|chat|predict)",
    r"(?:client|chat|llm)\.(?:chat\.)?(?:completions|messages)\.create",
    r"(?:openai|anthropic|aetherforge|ollama)[\._](?:client|chat|llm|gateway)",
    r"from (?:llm_gateway|openai|anthropic|aetherforge) import",
    r"import (?:openai|anthropic)",
    r"aetherforge[._](?:infer|gateway|generate|complete)",
    r"ollama(?:\.chat|\.generate|_client)",
]


def _has_llm(path: Path) -> bool:
    """「有没有 LLM 调用」只由代码决定 —— 注释/docstring/字符串里的 import 不算。

    必须与 `_code_only` 一起用：`has_fallback` 那侧仍须扫全文（argparse 选项
    `--no-llm` 是字符串字面量，抹掉会漏）。
    """
    return any(re.search(p, _code_only(path).lower()) for p in LLM_CALL_PATTERNS)


REPO_ROOT = Path(__file__).resolve().parents[2]

# 需要检查的脚本目录
CHECK_DIRS = ["bin", "scripts"]


def main() -> int:
    violations = []
    for check_dir in CHECK_DIRS:
        d = REPO_ROOT / check_dir
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.suffix not in (".py", ".sh"):
                continue
            rel = f.relative_to(REPO_ROOT)
            if ".venv" in rel.parts:
                continue
            # scripts 是独立子模块 (有自身 CI), 主仓不扫; 测试文件不需要 LLM fallback
            if rel.parts[0] == "scripts":
                continue
            if "tests" in rel.parts or rel.name.startswith("test_") or rel.name.startswith("test-"):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if not _has_llm(f):
                continue
            # 检查是否有 fallback 或 --no-llm
            has_fallback = any(kw in text.lower() for kw in ["--no-llm", "no_llm", "fallback", "heuristic", "glm", "bigmodel", "zhipu"])
            if not has_fallback:
                violations.append(str(rel))

    if violations:
        print(f"FAIL {len(violations)} 个脚本使用 LLM 但无 fallback:")
        for v in violations:
            print(f"  - {v}")
        return 1

    print("OK 所有脚本均有 LLM fallback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
