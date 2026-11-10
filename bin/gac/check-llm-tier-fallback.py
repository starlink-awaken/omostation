#!/usr/bin/env python3
"""CR-P76-7-2-TIER-GRACEFUL-FALLBACK: 检查 LLM provider 3-tier fallback 配置.

LLM provider 必须配置优雅降级: aetherforge 网关(网关内部自带跨后端兜底, 含 Ollama) → heuristic.
检查 bin/ 和 scripts/ 中使用 LLM 的脚本是否实现了至少 2-tier fallback。
脚本自己再直连 Ollama(如 `ollama run`)属于绕过网关, 由 CR-LLM-GATEWAY-ONLY 拦截。
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

# 3-tier LLM provider 层级
TIER_KEYWORDS = {
    "tier1_aetherforge": [
        "aetherforge",
        "aetherforge_url",
        "aetherforge_model",
        "AETHERFORGE",
    ],
    "tier2_ollama": ["ollama", "ollama_model", "OLLAMA_MODEL", "gemma"],
    "tier3_heuristic": [
        "--no-llm",
        "no_llm",
        "heuristic",
        "fallback",
        "heuristic_subject",
        "glm",
        "bigmodel",
        "zhipu",
    ],
}


def count_tiers(text: str) -> dict:
    """统计脚本中实现了哪几层 LLM fallback。"""
    tiers = {
        "tier1_aetherforge": False,
        "tier2_ollama": False,
        "tier3_heuristic": False,
    }
    text_lower = text.lower()
    for tier_name, keywords in TIER_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                tiers[tier_name] = True
                break
    return tiers


def main() -> int:
    violations = []
    check_dirs = ["bin", "scripts"]

    for check_dir in check_dirs:
        d = REPO_ROOT / check_dir
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.suffix not in (".py", ".sh"):
                continue
            rel = f.relative_to(REPO_ROOT)
            if ".venv" in rel.parts or "__pycache__" in rel.parts:
                continue
            # scripts 是独立子模块 (有自身 CI), 其 bin/projects/tests 内容由 scripts 仓治理 — 主仓不扫
            if rel.parts[0] == "scripts":
                continue
            # 排除测试文件 — 测试不需要 LLM fallback
            if "tests" in rel.parts or rel.name.startswith("test_") or rel.name.startswith("test-"):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if not _has_llm(f):
                continue

            tiers = count_tiers(text)
            active_tiers = sum(1 for v in tiers.values() if v)

            if active_tiers < 2:
                tier_summary = ", ".join(
                    f"{k.replace('tier', 'Tier ').replace('_', ' ').title()}: {'✓' if v else '✗'}"
                    for k, v in tiers.items()
                )
                violations.append(f"  {rel} — 仅 {active_tiers} 层 fallback ({tier_summary})")

    if violations:
        print(f"FAIL 发现 {len(violations)} 个脚本 LLM fallback 层级不足 (需 ≥2 层):")
        for v in violations:
            print(v)
        return 1

    print("OK 所有使用 LLM 的脚本均有 ≥2 层 fallback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
