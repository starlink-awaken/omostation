"""ToolForge — 思维工具匹配模块

从 MindForge 项目并入 OntoDerive，作为推导的前置步骤：
先匹配适合的思维框架（波特五力/SWOT/系统论/博弈论等），
再在选定的框架内执行 OntoDerive 的"事实→推论→方案"推导。

用法:
    from ontoderive.toolforge import ToolForge
    tf = ToolForge()
    selection = tf.select("分析新能源汽车市场", "竞争,政策")
    guide = tf.to_inference_guide("分析新能源汽车市场", "竞争,政策")
"""

from .matcher import CATALOG_PATH, ToolForge

__all__ = ["ToolForge", "CATALOG_PATH"]
