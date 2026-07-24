"""Events SSE Source — bos://ecos/events SSE 端点

为 event_listener 提供真实事件源。支持两种模式：
1. SSE 服务器模式：提供 HTTP SSE 端点，listen_forever(agora_sse) 可连接
2. JSONL 写入模式：写入 ~/.ecos/events.jsonl，listen_forever(events.jsonl) 可轮询

用法:
    # SSE 服务器
    python -m ecos.services.events_sse serve  # 启动 :7432 SSE 端点

    # 写入事件
    python -m ecos.services.events_sse emit --bos-uri bos://memory/kos/search --data '{"query": "test"}'
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("ecos.services.events_sse")

# 事件文件路径（与 event_listener.py 的默认路径一致）
_EVENTS_FILE = Path.home() / ".ecos" / "events.jsonl"

# 默认 SSE 端口
_DEFAULT_PORT = 7432


# =========================================================================
# 事件模型
# =========================================================================


def make_event(
    bos_uri: str, data: dict | None = None, source: str = "ecos.services.events_sse"
) -> dict[str, Any]:
    """构建标准事件 dict （兼容 event_listener.match_event）"""
    return {
        "bos_uri": bos_uri,
        "uri": bos_uri,
        "source": source,
        "timestamp": datetime.now().isoformat(),
        "data": data or {},
    }


# =========================================================================
# JSONL 写入/读取
# =========================================================================


def write_event(
    bos_uri: str, data: dict | None = None, source: str = "ecos.services.events_sse"
) -> dict[str, Any]:
    """写入事件到 events.jsonl"""
    event = make_event(bos_uri, data, source)
    _EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_EVENTS_FILE, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    logger.info("Event written: %s", bos_uri)
    return event


# =========================================================================
# SSE 服务器
# =========================================================================


def serve(port: int = _DEFAULT_PORT, interval: float = 5.0) -> None:
    """启动 SSE 事件流服务器

    每 interval 秒生成一个心跳事件。事件通过写入 events.jsonl 注入。
    """
    try:
        from http.server import BaseHTTPRequestHandler, HTTPServer
    except ImportError:
        logger.error("SSE server requires Python stdlib http.server")
        return

    class SSEHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # 发送初始连接事件
            self._send_sse("connected", {"status": "ok", "source": "ecos.events_sse"})

            # 持续从 events.jsonl 中读取新事件推送
            last_pos = _EVENTS_FILE.stat().st_size if _EVENTS_FILE.exists() else 0
            while True:
                time.sleep(interval)

                if not _EVENTS_FILE.exists():
                    self._send_sse("heartbeat", {"ts": datetime.now().isoformat()})
                    continue

                current_size = _EVENTS_FILE.stat().st_size
                if current_size <= last_pos:
                    self._send_sse("heartbeat", {"ts": datetime.now().isoformat()})
                    continue

                with open(_EVENTS_FILE) as f:
                    f.seek(last_pos)
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            self._send_sse("event", event)
                        except json.JSONDecodeError:
                            continue

                last_pos = current_size

        def _send_sse(self, event_type: str, data: dict) -> None:
            """发送 SSE 事件帧"""
            try:
                payload = json.dumps(data, ensure_ascii=False)
                self.wfile.write(f"event: {event_type}\ndata: {payload}\n\n".encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, format: str, *args: Any) -> None:
            logger.debug("SSE: %s", format % args)

    server = HTTPServer(("127.0.0.1", port), SSEHandler)
    logger.info("Events SSE server listening on :%d", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


# =========================================================================
# CLI 入口
# =========================================================================


def main() -> None:
    """CLI 入口"""
    import argparse

    parser = argparse.ArgumentParser(description="ecos Events SSE Source")
    sub = parser.add_subparsers(dest="command", required=True)

    # serve 子命令
    serve_p = sub.add_parser("serve", help="启动 SSE 服务器")
    serve_p.add_argument("--port", type=int, default=_DEFAULT_PORT)
    serve_p.add_argument("--interval", type=float, default=5.0)

    # emit 子命令
    emit_p = sub.add_parser("emit", help="写入一条事件")
    emit_p.add_argument("--bos-uri", required=True, help="BOS URI")
    emit_p.add_argument("--data", default="{}", help="事件数据 JSON")
    emit_p.add_argument("--source", default="ecos.services.events_sse")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "serve":
        serve(args.port, args.interval)
    elif args.command == "emit":
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            data = {"raw": args.data}
        event = write_event(args.bos_uri, data, args.source)
        print(json.dumps(event, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
