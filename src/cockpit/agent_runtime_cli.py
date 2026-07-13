"""Agent Runtime CLI 入口。"""

import argparse
import json
import sys
from pathlib import Path

try:
    from runtime.executor.config import AGENT_RUNTIME_PORT
except ImportError:
    AGENT_RUNTIME_PORT = 0  # fallback: uvicorn picks free port

from runtime.executor.config import DEFAULT_MODEL, log, setup_logging
from runtime.executor.engine import AgentRuntime


def run_agent_runtime(argv: list[str] | None = None) -> int:
    """执行 Agent Runtime CLI；接受显式参数列表，供 cockpit 统一入口复用。"""
    parser = argparse.ArgumentParser(description="Agent Runtime - Run a task")
    parser.add_argument("--prompt", "-p", help="Task prompt (or use --task to load from task_definitions/)")
    parser.add_argument("--task", "-t", help="Task name (load from task_definitions/<name>.json)")
    parser.add_argument("--model", help=f"Override model (default: {DEFAULT_MODEL})")
    parser.add_argument("--tools", nargs="*", help="Enabled tool names")
    parser.add_argument("--server", action="store_true", help="Start HTTP server")
    parser.add_argument("--port", type=int, default=AGENT_RUNTIME_PORT, help="HTTP server port")
    args = parser.parse_args(argv)

    setup_logging()

    if args.server:
        from runtime.executor.server import create_app

        app = create_app()
        import uvicorn

        log.info(f"🚀 Agent Runtime starting on :{args.port}")
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
        return 0

    # CLI 模式
    prompt = args.prompt
    if args.task:
        task_file = Path(__file__).parent / "task_definitions" / f"{args.task}.json"
        if not task_file.exists():
            log.error(f"Task definition not found: {task_file}")
            return 1
        task_def = json.loads(task_file.read_text())
        prompt = task_def.get("prompt", "")
        if not prompt:
            log.error(f"No prompt in task definition: {args.task}")
            return 1

    if not prompt:
        parser.print_help()
        return 1

    runtime = AgentRuntime(model=args.model)
    result = runtime.run_task(prompt, tools_enabled=args.tools)
    if result.get("result"):
        print(result["result"])
    if result.get("error"):
        print(f"[ERROR] {result['error']}", file=sys.stderr)
        return 1
    return 0


def cli_main():
    """CLI 模式：直接执行 task 或启动 HTTP 服务器。"""
    raise SystemExit(run_agent_runtime())


# pyproject 注册的入口
main = cli_main

if __name__ == "__main__":
    cli_main()
