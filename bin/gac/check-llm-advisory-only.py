#!/usr/bin/env python3
"""CR-P76-7-1-LLM-ADVISORY-ONLY: 检查 LLM 是否只 generate suggestion, 不 auto-apply.

检查项目中是否存在 auto-apply 模式（如自动 git commit/push 等），
防止 LLM 绕过人工审核直接执行写操作。
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 需要警惕的 auto-apply 模式
AUTO_APPLY_PATTERNS = [
    r'git\s+(commit|push)\s+--no-verify',
    r'git\s+commit\s+-a.*-m\s',
    r'git\s+push\s+--force',
    r'subprocess\.run\(\[.*git.*commit',
    r'os\.system\(.*git.*commit',
]

# 允许的 advisory 模式（建议性，非强制）
ADVISORY_PATTERNS = [
    r'print\(.*git\s+commit',
    r'log.*suggestion',
    r'review.*before.*commit',
]


def main() -> int:
    violations = []
    checked = 0

    for py_file in sorted(REPO_ROOT.rglob("*.py")):
        rel = py_file.relative_to(REPO_ROOT)
        # 跳过无关目录
        skip_dirs = {".venv", "__pycache__", "node_modules", "build", ".git", "_archived"}
        if any(d in rel.parts for d in skip_dirs):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pattern in AUTO_APPLY_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                # 检查是否在注释或 advisory 上下文中
                line = text[:m.start()].count("\n") + 1
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
