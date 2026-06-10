"""Allow `python3 -m runtime` to work as CLI entry point.

P48-W0: 加 `serve` 子命令支持 (stdio JSON-RPC, 协议同 P33-W4 agora daemon).
P61-W1: re-export _call_action + serve from runtime_serve (供跨仓 import).

用法:
  python -m runtime              # CLI (health/matrix/service/protocol/status/version)
  python -m runtime serve        # stdio JSON-RPC serve 模式 (BOS URI 派发后端)
  from runtime.__main__ import _call_action, serve  # 跨仓 import (P61-W1 修)
"""
import sys

# P61-W1: re-export 跨仓 import (清账 DEBT-RUNTIME-MAIN-CALL-ACTION-2026-06-08)
from runtime.runtime_serve import _call_action, serve  # noqa: F401  # re-export


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "serve":
        return serve()
    from runtime.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main", "_call_action", "serve"]
