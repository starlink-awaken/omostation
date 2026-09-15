#!/usr/bin/env python3
# ruff: noqa
"""G5: 流式增量知识管线 — 统一 kronos 摄取 → eidos incremental → kos delta index.

场景覆盖审计 G5 缺口实现 (流式/增量知识, 不全量 rebuild).
现状: kos indexer --daemon/--full-embed (有增量回灌), eidos nks_incremental_indexer (有),
      但分散在各包, 无统一流式编排.
本模块: 统一流式管线编排 (file event → kronos parse → eidos incremental embed → kos delta index),
        不全量 rebuild, 只处理变更.

设计: 轻量编排层, 调用各包已有的 incremental 能力 (不重写), 提供 watch/run 接口.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class StreamEvent:
    """一个文件变更事件 (watch 触发)."""

    path: str
    event_type: str = "modified"  # created / modified / deleted
    timestamp: float = field(default_factory=time.time)


@dataclass
class StreamResult:
    """单次流式处理结果."""

    event: StreamEvent
    parsed: bool = False
    embedded: bool = False
    indexed: bool = False
    error: str | None = None
    duration_ms: float = 0.0


# 各阶段的可注入处理器 (默认 no-op, 实际由 kos/eidos/kronos 提供)
ParseHandler = Callable[[StreamEvent], dict[str, Any] | None]
EmbedHandler = Callable[[dict[str, Any]], bool]
IndexHandler = Callable[[dict[str, Any]], bool]


class StreamPipeline:
    """流式增量管线编排 (file event → parse → embed → index).

    轻量编排: 注入各包的 incremental 处理器, 串行处理事件, 不全量 rebuild.
    """

    def __init__(
        self,
        parse_handler: ParseHandler | None = None,
        embed_handler: EmbedHandler | None = None,
        index_handler: IndexHandler | None = None,
    ) -> None:
        self._parse = parse_handler
        self._embed = embed_handler
        self._index = index_handler
        self._processed: list[StreamResult] = []
        self._stats = {"total": 0, "parsed": 0, "embedded": 0, "indexed": 0, "errors": 0}

    def process(self, event: StreamEvent) -> StreamResult:
        """处理单个流式事件 (parse → embed → index)."""
        start = time.time()
        result = StreamResult(event=event)
        self._stats["total"] += 1

        try:
            # Stage 1: parse (kronos 提取结构化内容)
            if self._parse:
                parsed = self._parse(event)
                if parsed is None:
                    result.error = "parse returned None"
                    self._stats["errors"] += 1
                    self._finalize(result, start)
                    return result
                result.parsed = True
                self._stats["parsed"] += 1
            else:
                parsed = {"path": event.path, "type": event.event_type}

            # Stage 2: embed (eidos incremental 向量化)
            if self._embed:
                result.embedded = bool(self._embed(parsed))
                if result.embedded:
                    self._stats["embedded"] += 1

            # Stage 3: index (kos delta 增量索引)
            if self._index:
                result.indexed = bool(self._index(parsed))
                if result.indexed:
                    self._stats["indexed"] += 1

        except Exception as e:
            result.error = str(e)
            self._stats["errors"] += 1

        self._finalize(result, start)
        return result

    def _finalize(self, result: StreamResult, start: float) -> None:
        result.duration_ms = (time.time() - start) * 1000
        self._processed.append(result)

    def process_batch(self, events: list[StreamEvent]) -> list[StreamResult]:
        """批量处理事件."""
        return [self.process(e) for e in events]

    def watch(
        self,
        paths: list[str],
        poll_interval: float = 2.0,
        max_events: int = 0,
        on_event: Callable[[StreamResult], None] | None = None,
    ) -> None:
        """监听文件变更 (mtime 轮询, 轻量无 watchdog 依赖).

        Args:
            paths: 监听的文件/目录列表.
            poll_interval: 轮询间隔秒.
            max_events: 最多处理事件数 (0 = 无限).
            on_event: 每个事件处理后的回调.
        """
        mtimes: dict[str, float] = {}
        # 初始化基线 mtime
        for p in paths:
            pp = Path(p)
            if pp.exists():
                mtimes[p] = pp.stat().st_mtime

        processed = 0
        while max_events == 0 or processed < max_events:
            for p in paths:
                pp = Path(p)
                if not pp.exists():
                    continue
                curr = pp.stat().st_mtime
                if p not in mtimes:
                    mtimes[p] = curr
                    event = StreamEvent(path=p, event_type="created")
                    result = self.process(event)
                    if on_event:
                        on_event(result)
                    processed += 1
                elif curr > mtimes[p]:
                    mtimes[p] = curr
                    event = StreamEvent(path=p, event_type="modified")
                    result = self.process(event)
                    if on_event:
                        on_event(result)
                    processed += 1
            time.sleep(poll_interval)

    def get_stats(self) -> dict[str, Any]:
        """管线统计."""
        return dict(self._stats)

    def reset(self) -> None:
        """重置管线状态."""
        self._processed.clear()
        self._stats = {"total": 0, "parsed": 0, "embedded": 0, "indexed": 0, "errors": 0}


def build_indexer_pipeline() -> StreamPipeline:
    """构建注入 kos indexer incremental 的流式管线.

    watch 检测文件变更 → 触发 indexer fingerprint incremental index (subprocess).
    parse/embed = None (indexer 内部含全流程 parse+embed+index, 不重复).
    补 indexer 无 daemon 的缺口: indexer 是一次性命令, 本管线提供持续 watch.
    """
    import subprocess
    import sys

    def trigger_incremental(_data: dict[str, Any]) -> bool:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "kos.indexer.engine", "--incremental"],
                capture_output=True,
                text=True,
                timeout=180,
            )
            return r.returncode == 0
        except Exception:
            return False

    return StreamPipeline(index_handler=trigger_incremental)


def main() -> None:
    """CLI: kos stream-pipeline — 流式增量管线 (单次触发 / watch daemon).

    默认: 单次触发 indexer incremental index.
    --watch <paths>: 持续监听文件变更, mtime 变 → 触发 incremental (daemon, Ctrl+C 停).
    """
    import sys

    if "--watch" in sys.argv:
        watch_idx = sys.argv.index("--watch")
        paths = [p for p in sys.argv[watch_idx + 1 :] if not p.startswith("-")]
        if not paths:
            print("用法: python -m kos.stream_pipeline --watch <path1> [path2 ...]")
            return
        pipeline = build_indexer_pipeline()
        print(f"👁 stream watch daemon: 监听 {len(paths)} 路径, 变更 → indexer incremental (Ctrl+C 停)")
        pipeline.watch(
            paths,
            poll_interval=5.0,
            on_event=lambda r: print(f"  [{r.event.event_type}] {r.event.path} → indexed={r.indexed}"),
        )
    else:
        pipeline = build_indexer_pipeline()
        event = StreamEvent(path=".", event_type="modified")
        result = pipeline.process(event)
        print(
            json.dumps(
                {"indexed": result.indexed, "error": result.error, "stats": pipeline.get_stats()},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
