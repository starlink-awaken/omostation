"""Agora CLI — backward-compatibility re-export layer.

All commands have been moved to agora.cli subpackage (parser.py + commands_*.py).
This module re-exports for external consumers importing from agora.cli directly.
"""

from agora.cli import main  # noqa: F401
from agora.cli.parser import build_parser, run_command, start_pipeline_command  # noqa: F401
