"""forge adapters — CLI 适配器协议与实现。"""

from forge.adapters.claude_code import ClaudeCodeAdapter, ICliAdapter  # type: ignore[import-not-found]

__all__ = ["ClaudeCodeAdapter", "ICliAdapter"]
