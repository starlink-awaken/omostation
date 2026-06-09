"""
model_driven — 全生命周期模型驱动平台

基于 MOF 本体论正交分解 + SSOT 化，对系统全生命周期所有要素建模。

核心能力:
- MOF 扩展: M3 新增生命周期/价值元素 + M2 新增 ~22 类型
- 生命周期引擎: 7 阶段定义 + 门禁 + 转换 + 追踪
- 模型驱动工具链: 12 个核心工具 (design/generate/derive/validate/...)
- 管理面: Spec + ADR + OKR + OMO 桥接 + 多Agent 协作
- SSOT 全生命周期化: 生命周期/价值/过程 SSOT + 跨阶段一致性
"""

from . import lifecycle, management, mof, ssot, toolchain
from .mcp_server import MCPServer

__version__ = "0.1.0"

__all__ = [
    "mof",
    "lifecycle",
    "toolchain",
    "management",
    "ssot",
    "MCPServer",
    "__version__",
]
