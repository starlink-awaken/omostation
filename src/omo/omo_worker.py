#!/usr/bin/env python3
from __future__ import annotations

import argparse

# Re-export facade imports for backward compatibility

from .omo_worker_cmd_worker import setup_worker_parser, execute_worker_command
from .omo_worker_cmd_task import setup_task_parser, execute_task_command

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_worker_parser(subparsers)
    setup_task_parser(subparsers)

    args = parser.parse_args(argv)

    if args.command == "worker":
        return execute_worker_command(args)
    if args.command == "task":
        return execute_task_command(args)

    return 1

if __name__ == "__main__":
    raise SystemExit(main())
