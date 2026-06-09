"""model-driven 公共路径工具

提供统一的 workspace 和 state 目录获取，替代各处硬编码的 ~/Workspace 路径。
"""

import os
import warnings
from pathlib import Path


def get_workspace_dir() -> Path:
    """获取 eCOS workspace 根目录。

    优先使用 ECOS_WORKSPACE 环境变量，fallback 到 ~/Workspace。
    当环境变量未设置时发出 UserWarning，提醒显式配置。
    """
    env_path = os.environ.get("ECOS_WORKSPACE")
    if env_path:
        ws = Path(env_path)
        if not ws.exists():
            warnings.warn(f"ECOS_WORKSPACE 指向的路径不存在: {ws}", stacklevel=2)
        return ws

    fallback = Path.home() / "Workspace"
    warnings.warn(
        f"ECOS_WORKSPACE 环境变量未设置，使用默认路径: {fallback}。"
        f"建议设置 export ECOS_WORKSPACE=/path/to/workspace",
        stacklevel=2,
    )
    return fallback


def get_state_dir() -> Path:
    """获取 model-driven 状态目录。

    返回 <workspace>/.omo/state/model-driven/，并确保目录存在。
    """
    state_dir = get_workspace_dir() / ".omo" / "state" / "model-driven"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir
