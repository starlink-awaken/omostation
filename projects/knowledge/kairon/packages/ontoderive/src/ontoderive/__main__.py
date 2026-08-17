"""kairon/ontoderive (engine package) stdio MCP server (POC, P34-W2).

读取 stdin 的 JSON 请求, 写入 stdout 的 JSON 响应.
POC 阶段: 与 minerva.__main__ 同款 JSON 行协议.
完整 MCP 协议在 W4.5+ 实施.

注意: ontoderive 的实际包名是 `engine` (pyproject 包名 ontoderive 但源码在
packages/ontoderive/engine/). 集成测试调 `python -m engine` 时需确保 venv
已安装该包 (实际上 venv scripts 中 `ontoderive` 入口就是 engine.cli).

调用: python -m engine serve --action <action>
"""
# Dynamic class dispatch via inspect (hasattr on unknown-typed objects).
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import argparse
import json
import sys


def _serve(action: str) -> int:
    """POC stdio 协议: stdin JSON 行 → stdout JSON 行."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            err = {
                "status": "error",
                "service": "kairon-ontoderive",
                "action": action,
                "error": f"invalid_json: {exc}",
            }
            sys.stdout.write(json.dumps(err, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue
        resp = {
            "status": "ok",
            "service": "kairon-ontoderive",
            "action": action,
            "request_id": req.get("request_id", ""),
            "result": {
                "message": f"ontoderive {action} invoked",
                "echo_args": req.get("args", []),
                "echo_kwargs": req.get("kwargs", {}),
            },
        }
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kairon-ontoderive")
    parser.add_argument("command", choices=["serve"], help="POC: only 'serve'")
    parser.add_argument("--action", required=True, help="derive/audit/fact-check")
    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args.action)
    return 1


if __name__ == "__main__":
    sys.exit(main())
