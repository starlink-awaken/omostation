"""
model_driven.toolchain — 模型驱动工具链

提供 12 个核心工具的统一接口：
- ToolchainBus: 工具注册/路由/执行
- 12 个工具函数 + MOF 操作工具
"""

from .bus import ToolchainBus, ToolDefinition, ToolResult, ToolStatus
from .mof_extract import extract_all
from .mof_model import model_project, model_workspace, classify_by_lifecycle_stage
from .mof_scan import scan_project_dir, scan_system, scan_workspace
from .tools import (
    tool_archive,
    tool_compile,
    tool_connect,
    tool_deploy,
    tool_derive,
    tool_design,
    tool_evolve,
    tool_generate,
    tool_monitor,
    tool_observe,
    tool_report,
    tool_validate,
)

# ── 默认工具注册表 ──────────────────────────────────

DEFAULT_TOOLS = [
    ("model-design", tool_design, ToolDefinition(
        name="model-design",
        description="交互式/模板式创建模型 (M1 节点)",
        category="design",
    )),
    ("model-generate", tool_generate, ToolDefinition(
        name="model-generate",
        description="从模型生成代码/配置 (支持 YAML/JSON 输出)",
        category="generate",
    )),
    ("model-derive", tool_derive, ToolDefinition(
        name="model-derive",
        description="从模型推导关系/风险/洞察 (传递推理+风险推理+缺口发现)",
        category="derive",
    )),
    ("model-validate", tool_validate, ToolDefinition(
        name="model-validate",
        description="校验模型一致性/合规性 (支持严格模式)",
        category="validate",
    )),
    ("model-connect", tool_connect, ToolDefinition(
        name="model-connect",
        description="建立模型间关联",
        category="connect",
    )),
    ("model-compile", tool_compile, ToolDefinition(
        name="model-compile",
        description="编译模型为可执行规则/配置",
        category="compile",
    )),
    ("model-evolve", tool_evolve, ToolDefinition(
        name="model-evolve",
        description="检测漂移/建议演化 (支持批量漂移检测)",
        category="evolve",
    )),
    ("model-monitor", tool_monitor, ToolDefinition(
        name="model-monitor",
        description="监控模型健康度",
        category="monitor",
    )),
    ("model-deploy", tool_deploy, ToolDefinition(
        name="model-deploy",
        description="将模型部署到目标环境",
        category="deploy",
    )),
    ("model-observe", tool_observe, ToolDefinition(
        name="model-observe",
        description="观测模型运行时行为",
        category="observe",
    )),
    ("model-report", tool_report, ToolDefinition(
        name="model-report",
        description="生成模型全景报告",
        category="report",
    )),
    ("model-archive", tool_archive, ToolDefinition(
        name="model-archive",
        description="归档过期模型",
        category="archive",
    )),
    # MOF 操作工具 (移植自 ecos)
    ("mof-scan", scan_system, ToolDefinition(
        name="mof-scan",
        description="System→M1 扫描 — 自动扫描系统资产生成 M1 节点",
        category="scan",
        tags=["mof", "m1", "scan"],
    )),
    ("mof-model", model_workspace, ToolDefinition(
        name="mof-model",
        description="全量资产建模 — 对工作区进行全量 M1 分类建模",
        category="model",
        tags=["mof", "m1", "model"],
    )),
    ("mof-extract", extract_all, ToolDefinition(
        name="mof-extract",
        description="逆向提炼 — 从资产中自动识别提炼 M1 节点 (lessons/decisions/specs)",
        category="extract",
        tags=["mof", "m1", "extract"],
    )),
]


def create_default_bus() -> ToolchainBus:
    """创建预注册了 15 个默认工具的工具链总线"""
    bus = ToolchainBus()
    for name, func, definition in DEFAULT_TOOLS:
        bus.register(name, func, definition)
    return bus


__all__ = [
    "ToolchainBus",
    "ToolDefinition",
    "ToolResult",
    "ToolStatus",
    "create_default_bus",
    "DEFAULT_TOOLS",
    # Tools
    "tool_design",
    "tool_generate",
    "tool_derive",
    "tool_validate",
    "tool_connect",
    "tool_compile",
    "tool_evolve",
    "tool_monitor",
    "tool_deploy",
    "tool_observe",
    "tool_report",
    "tool_archive",
    # MOF
    "scan_system",
    "scan_project_dir",
    "scan_workspace",
    "model_project",
    "model_workspace",
    "classify_by_lifecycle_stage",
    "extract_all",
]
