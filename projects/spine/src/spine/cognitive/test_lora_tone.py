"""Test entry point for BET-Y2Q2-T3-02 ToneAdapter.

Runs:
1. Four-domain routing (+ specificity ordering, gov default)
2. Persona tone passthrough from MindModelRouter
3. ROUGE-L gate: pass-through vs distorted fallback to neutral
4. Never-raises circuit breaker

Exit 0 = all pass.
"""

from __future__ import annotations

import sys

from spine.cognitive.lora_tone import ADAPTER_NAMES, ToneAdapter, rouge_l, route_domain

_CHECKS: list[tuple[str, bool]] = []


def check(name: str, cond: bool) -> None:
    _CHECKS.append((name, cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")


def main() -> int:
    check("route gov", route_domain("关于医共体请示，请批复。") == "gov")
    check("route tech", route_domain("ADR 技术方案评审。") == "tech")
    check("route collab", route_domain("与合作方洽谈签约。") == "collab")
    check("route essay", route_domain("深夜随笔手记。") == "essay")
    check("route default", route_domain("今天天气不错。") == "gov")
    check("specific collab wins", route_domain("对外协作会议通知。") == "collab")

    ta = ToneAdapter()
    d = ta.directives_for("与合作方洽谈签约备忘录。")
    check("directives domain+adapter", d["domain"] == "collab" and d["adapter"] == ADAPTER_NAMES["collab"])
    check("directives breaker ok", d["circuit_breaker_ok"] is True and d["fallback_neutral"] is False)

    same = ta.directives_for("请示批复。", candidate="批复：同意按方案推进。", reference="批复：同意按方案推进。")
    check("gate pass keeps tone", same["fallback_neutral"] is False and same["rouge_l"] == 1.0)

    bad = ta.directives_for("请示批复。", candidate="天气不错出去走走。", reference="批复：同意按医共体方案推进。")
    check("gate distorted neutral", bad["fallback_neutral"] is True and bad["tone"] == "neutral")

    broken = ToneAdapter(router="not-a-router")
    safe = broken.directives_for("任何任务")
    check("broken router degrades gracefully", safe["tone"] == "neutral" and safe["circuit_breaker_ok"] is True)

    check("rouge identical", rouge_l("批复同意。", "批复同意。") == 1.0)
    check("rouge empty pair", rouge_l("", "") == 1.0)

    failed = [n for n, ok in _CHECKS if not ok]
    print(f"\n{len(_CHECKS) - len(failed)}/{len(_CHECKS)} checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
