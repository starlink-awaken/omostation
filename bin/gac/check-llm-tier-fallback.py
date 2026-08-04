#!/usr/bin/env python3
"""CR-P76-7-2-TIER-GRACEFUL-FALLBACK: 检查 LLM provider 3-tier fallback 配置.

LLM provider 必须配置 3-tier 优雅降级: aetherforge → ollama → heuristic.
检查 bin/ 和 scripts/ 中使用 LLM 的脚本是否实现了至少 2-tier fallback。
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 3-tier LLM provider 层级
TIER_KEYWORDS = {
    "tier1_aetherforge": ["aetherforge", "aetherforge_url", "aetherforge_model", "AETHERFORGE"],
    "tier2_ollama": ["ollama", "ollama_model", "OLLAMA_MODEL", "gemma"],
    "tier3_heuristic": ["--no-llm", "no_llm", "heuristic", "fallback", "heuristic_subject"],
}


def count_tiers(text: str) -> dict:
    """统计脚本中实现了哪几层 LLM fallback。"""
    tiers = {"tier1_aetherforge": False, "tier2_ollama": False, "tier3_heuristic": False}
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
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # 跳过不使用 LLM 的脚本
            has_llm = any(
                kw in text.lower() for kw in ["llm", "openai", "anthropic", "aetherforge", "ollama"]
            )
            if not has_llm:
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
