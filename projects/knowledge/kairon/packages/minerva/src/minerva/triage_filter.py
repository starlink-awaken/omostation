"""Harvest triage filter — 在知识采集时自动过滤噪音.

集成方式:
- 在 harvest pipeline 中调用 triage_filter()
- 丢弃类: 跳过, 不入库
- 沉淀类: 正常入库 (知识)
- 提醒类: 入库 + 标记需要行动
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Bridge import — unified AetherForge LLM entry (replaces hardcoded HTTP URL)
_AF_SRC = str(Path(__file__).resolve().parents[5] / "aetherforge" / "src")
if _AF_SRC not in sys.path:
    sys.path.insert(0, _AF_SRC)

TRIAGE_PROMPT = """你是信息分诊助手。判断: 丢弃 / 沉淀 / 提醒 三选一。

标准:
- 丢弃: 营销/广告/促销/社交动态/APP推送/续费推销
- 沉淀: 技术文章/知识教程/研究分析/笔记同步/课程更新 (有价值内容)
- 提醒: 会议/截止日期/账单/告警/待办/预约/需行动事项

示例:
【淘宝】5折→丢弃  【GitHub】新PR→沉淀  【日历】开会→提醒
【读书笔记】已同步→沉淀  【京东】续费优惠→丢弃  【银行】账单→提醒

信息: {text}
只输出一个词:"""


@dataclass
class TriageFilterResult:
    """过滤结果."""

    verdict: str  # 丢弃/沉淀/提醒
    should_store: bool  # 是否入库
    needs_action: bool  # 是否需要行动
    latency: float = 0.0
    error: str | None = None


def triage_filter(text: str, timeout: float = 10.0) -> TriageFilterResult:
    """对文本进行分诊过滤.

    Uses AetherForge bridge for unified LLM routing (no hardcoded URLs).

    Args:
        text: 待过滤文本
        timeout: 超时秒数

    Returns:
        TriageFilterResult: 过滤结果
    """
    t0 = time.time()
    try:
        from aetherforge.bridge import llm_generate
        result = llm_generate(
            TRIAGE_PROMPT.format(text=text),
            model="mythos-fast",
            timeout=timeout,
        )
        latency = time.time() - t0
        content = (result.get("content") or "").strip()

        verdict = None
        for v in ("丢弃", "沉淀", "提醒"):
            if v in content:
                verdict = v
                break

        if verdict is None:
            return TriageFilterResult(
                verdict="未知",
                should_store=True,
                needs_action=False,
                latency=latency,
                error=f"无法解析: {content[:20]}",
            )

        return TriageFilterResult(
            verdict=verdict,
            should_store=verdict != "丢弃",
            needs_action=verdict == "提醒",
            latency=latency,
        )
    except Exception as e:
        return TriageFilterResult(
            verdict="错误",
            should_store=True,
            needs_action=False,
            latency=time.time() - t0,
            error=str(e)[:50],
        )


def batch_filter(texts: list[str], timeout: float = 10.0) -> list[TriageFilterResult]:
    """批量过滤."""
    return [triage_filter(t, timeout) for t in texts]
