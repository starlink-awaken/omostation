"""model-driven 公共路径工具

提供统一的 workspace 和 state 目录获取，替代各处硬编码的 ~/Workspace 路径。
"""

import os
from pathlib import Path


def get_workspace_dir() -> Path:
    """获取 eCOS workspace 根目录。

    优先使用 ECOS_WORKSPACE 环境变量，fallback 到 ~/Workspace。
    """
    return Path(os.environ.get("ECOS_WORKSPACE", str(Path.home() / "Workspace")))


def get_state_dir() -> Path:
    """获取 model-driven 状态目录。

    返回 <workspace>/.omo/state/model-driven/，并确保目录存在。
    """
    state_dir = get_workspace_dir() / ".omo" / "state" / "model-driven"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir
