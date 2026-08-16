"""Harvest triage filter — 在知识采集时自动过滤噪音.

集成方式:
- 在 harvest pipeline 中调用 triage_filter()
- 丢弃类: 跳过, 不入库
- 沉淀类: 正常入库 (知识)
- 提醒类: 入库 + 标记需要行动
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from urllib.request import urlopen as _urlopen

GATEWAY_URL = "http://100.96.126.35:4000/v1/chat/completions"
GATEWAY_KEY = "sk-omlx-admin"

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

    Args:
        text: 待过滤文本
        timeout: 超时秒数

    Returns:
        TriageFilterResult: 过滤结果
    """
    payload = json.dumps(
        {
            "model": "triage",
            "messages": [{"role": "user", "content": TRIAGE_PROMPT.format(text=text)}],
            "max_tokens": 20,
            "temperature": 0,
            "extra_body": {"reasoning_effort": "none"},
        }
    ).encode()

    req = urllib.request.Request(
        GATEWAY_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GATEWAY_KEY}",
        },
    )

    import time

    t0 = time.time()
    try:
        with _urlopen(req, timeout=timeout) as resp:  # noqa: S310
            d = json.loads(resp.read())
        latency = time.time() - t0
        content = d["choices"][0]["message"]["content"].strip()

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
