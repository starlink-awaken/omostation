"""
Agent Runtime — 兼容入口。

旧版单文件 runtime.py 已拆分为：
  config.py   — 配置常量
  tools.py    — Tools 工具类 + 路径沙箱
  engine.py   — AgentRuntime 核心引擎
  server.py   — FastAPI HTTP 服务
  cli.py      — CLI 入口

旧脚本通过 ``python3 runtime.py --server`` 调用，此入口保持兼容。
"""

from runtime.executor.cli import cli_main  # type: ignore[import-not-found]

if __name__ == "__main__":
    cli_main()
