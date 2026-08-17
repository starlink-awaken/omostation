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
            # scripts 是独立子模块 (有自身 CI), 主仓不扫; 测试文件不需要 LLM fallback
            if rel.parts[0] == "scripts":
                continue
            if "tests" in rel.parts or rel.name.startswith("test_") or rel.name.startswith("test-"):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            # 精确检测 LLM API 调用 (排除正则/注释/子模块列表误匹配)
            import re as _re
            llm_call_patterns = [
                r"llm\.(complete|generate|chat|predict)",
                r"(?:client|chat|llm)\.(?:chat\.)?(?:completions|messages)\.create",
                r"(?:openai|anthropic|aetherforge|ollama)[\._](?:client|chat|llm|gateway)",
                r"from (?:llm_gateway|openai|anthropic|aetherforge) import",
                r"import (?:openai|anthropic)",
                r"aetherforge[._](?:infer|gateway|generate|complete)",
                r"ollama(?:\.chat|\.generate|_client)",
            ]
            has_llm = any(_re.search(p, text.lower()) for p in llm_call_patterns)
            if not has_llm:
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
