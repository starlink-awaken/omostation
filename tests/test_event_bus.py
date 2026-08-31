"""BET-Y1Q4-T2-01 event bus: 优先级/背压/吞吐/关闭语义。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "projects/omo/src"))
from omo.event_bus import Event, PriorityEventBus, run_producer, stream_benchmark  # noqa: E402


def test_priority_high_beats_normal():
    async def go():
        bus = PriorityEventBus()
        bus.publish(Event("s", "mail", {}, priority="normal"))
        bus.publish(Event("s", "policy", {}, priority="high"))
        bus.close()
        out = [e.priority async for e in bus.subscribe()]
        assert out == ["high", "normal"]

    asyncio.run(go())


def test_backpressure_drops_oldest_normal_and_counts():
    bus = PriorityEventBus(maxsize=3)
    for i in range(5):
        bus.publish(Event("s", "rss", {"i": i}))
    assert len(bus._normal) == 3
    assert bus.stats.dropped_overflow == 2
    assert bus._normal[0].payload["i"] == 2  # 最旧被丢


def test_high_never_dropped():
    bus = PriorityEventBus(maxsize=2)
    for i in range(4):
        bus.publish(Event("s", "policy", {"i": i}, priority="high"))
    assert len(bus._high) == 4 and bus.stats.dropped_overflow == 0


def test_invalid_priority_rejected():
    bus = PriorityEventBus()
    assert bus.publish(Event("s", "x", {}, priority="urgent")) is False


def test_benchmark_meets_contract():
    r = asyncio.run(stream_benchmark(sources=4, per_source=1500))
    assert r["throughput_ok"] and r["high_priority_ok"]
    assert r["events"] == 6000
