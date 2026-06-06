"""omo version - 引用 omostation 工作区统一版本.

工作区根 VERSION 文件权威 (ADR-0007), 此处只镜像.
"""
from pathlib import Path

_workspace_root = Path(__file__).resolve().parent.parent.parent.parent.parent
try:
    __version__ = (_workspace_root / "VERSION").read_text().strip()
except FileNotFoundError:
    __version__ = "0.0.0"
