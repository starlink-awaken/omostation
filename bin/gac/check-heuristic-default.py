#!/usr/bin/env python3
"""CR-P76-9A-4-HEURISTIC-DEFAULT: 检查脚本是否有 --no-llm 或启发式 fallback.

确保本地工具不强制依赖外部 LLM 服务，有 --no-llm 或 heuristic fallback 选项。
"""

import sys
from pathlib import Path

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
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            # 检查是否使用 LLM（有相关 import 或调用）
            has_llm = any(
                kw in text.lower() for kw in ["llm", "openai", "anthropic", "aetherforge"]
            )
            if not has_llm:
                continue
            # 检查是否有 fallback 或 --no-llm
            has_fallback = any(
                kw in text.lower() for kw in ["--no-llm", "no_llm", "fallback", "heuristic"]
            )
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
