"""Allow `python3 -m runtime` to work as CLI entry point.

P48-W0: 加 `serve` 子命令支持 (stdio JSON-RPC, 协议同 P33-W4 agora daemon).
用法:
  python -m runtime              # CLI (health/matrix/service/protocol/status/version)
  python -m runtime serve        # stdio JSON-RPC serve 模式 (BOS URI 派发后端)
"""
import sys


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "serve":
        from runtime.runtime_serve import serve

        return serve()
    from runtime.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
