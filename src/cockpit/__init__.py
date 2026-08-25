# workspace-cli — 研究对象管理系统
# CLI entry in cli.py. Run: python -m cockpit

__version__ = "0.4.0"

# Auto-resolve multi-repository paths across workspace
from . import env_resolver

__all__ = ("__version__", "env_resolver")
